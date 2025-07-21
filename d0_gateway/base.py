"""
Base API client with common functionality for all external API providers
"""

import time
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

import httpx

from core.config import get_settings
from core.exceptions import ExternalAPIError, RateLimitError
from core.logging import get_logger

from .cache import ResponseCache
from .circuit_breaker import CircuitBreaker
from .guardrail_middleware import GuardrailBlocked
from .metrics import GatewayMetrics
from .middleware.cost_enforcement import OperationPriority, cost_enforcement
from .rate_limiter import RateLimiter


class BaseAPIClient(ABC):
    """Abstract base class for all external API clients"""

    def __init__(
        self,
        provider: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.provider = provider
        self.settings = get_settings()
        self.logger = get_logger(f"gateway.{provider}", domain="d0")

        # Use stub URLs and keys if configured
        if self.settings.use_stubs:
            self.api_key = f"stub-{provider}-key"
            # Only set base_url if it wasn't already set by child class
            if not hasattr(self, "base_url"):
                self.base_url = self.settings.stub_base_url
        else:
            self.api_key = api_key or self.settings.get_api_key(provider)
            self.base_url = base_url or self._get_base_url()

        # Initialize gateway components
        self.rate_limiter = RateLimiter(provider)
        self.circuit_breaker = CircuitBreaker(provider)
        self.cache = ResponseCache(provider)
        self.metrics = GatewayMetrics()

        # HTTP client with proper timeouts
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0), headers=self._get_headers())

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    @abstractmethod
    def _get_base_url(self) -> str:
        """Get the base URL for this provider"""

    @abstractmethod
    def _get_headers(self) -> dict[str, str]:
        """Get authentication headers for this provider"""

    @abstractmethod
    def get_rate_limit(self) -> dict[str, int]:
        """Get rate limit configuration for this provider"""

    @abstractmethod
    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        """Calculate cost for a specific operation"""

    async def make_request(
        self, method: str, endpoint: str, priority: OperationPriority | None = None, **kwargs
    ) -> dict[str, Any]:
        """
        Make an authenticated API request with all gateway features

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            priority: Operation priority (defaults to NORMAL)
            **kwargs: Additional arguments passed to httpx

        Returns:
            Dict containing the API response

        Raises:
            RateLimitError: When rate limit is exceeded
            ExternalAPIError: When the API returns an error
        """
        operation = f"{method}:{endpoint}"
        cache_key = self.cache.generate_key(endpoint, kwargs.get("params", {}))

        # Check cache first
        cached_response = await self.cache.get(cache_key)
        if cached_response:
            self.metrics.record_cache_hit(self.provider, endpoint)
            self.logger.debug(f"Cache hit for {operation}")
            return cached_response

        self.metrics.record_cache_miss(self.provider, endpoint)

        # Extract operation name
        operation_name = endpoint.split("/")[0] if "/" in endpoint else endpoint
        lead_id = kwargs.get("lead_id")
        campaign_id = kwargs.get("campaign_id")

        # Use the new cost enforcement middleware (skip in stub mode to avoid database calls)
        if not self.settings.use_stubs:
            # Remove lead_id and campaign_id from kwargs to avoid duplicate args
            enforcement_kwargs = {k: v for k, v in kwargs.items() if k not in ("lead_id", "campaign_id")}
            enforcement_result = await cost_enforcement.check_and_enforce(
                provider=self.provider,
                operation=operation_name,
                campaign_id=campaign_id,
                priority=priority or OperationPriority.NORMAL,
                **enforcement_kwargs,
            )

            if enforcement_result is not True:
                # Handle enforcement failure
                if enforcement_result.get("reason") == "rate_limit_exceeded":
                    raise RateLimitError(
                        provider=self.provider,
                        retry_after=enforcement_result.get("retry_after", 60),
                        daily_limit=0,
                        daily_used=0,
                    )
                if enforcement_result.get("reason") == "guardrail_violation":
                    violation = enforcement_result.get("violation", {})
                    raise GuardrailBlocked(
                        f"Operation blocked by guardrail '{violation.get('limit_name', 'unknown')}': "
                        f"${violation.get('current_spend', 0):.2f} / ${violation.get('limit_amount', 0):.2f} "
                        f"({violation.get('percentage_used', 0):.1%})"
                    )

        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            self.logger.warning(f"Circuit breaker open for {self.provider}")
            raise ExternalAPIError(
                provider=self.provider,
                message="Service temporarily unavailable",
                status_code=503,
            )

        start_time = time.time()
        response = None
        error = None

        try:
            # Make the actual HTTP request
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            response = await self.client.request(method, url, **kwargs)

            # Handle HTTP errors
            if response.status_code >= 400:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", error_msg)
                except Exception:
                    error_msg = response.text or error_msg

                raise ExternalAPIError(
                    provider=self.provider,
                    message=error_msg,
                    status_code=response.status_code,
                    response_body=response.text,
                )

            # Parse successful response
            response_data = response.json()

            # Record successful request
            self.circuit_breaker.record_success()

            # Cache the response
            await self.cache.set(cache_key, response_data)

            # Calculate and record cost
            cost = self.calculate_cost(operation_name, **kwargs)

            # Record cost in ledger (P1-050 requirement)
            if not self.settings.use_stubs and self.settings.enable_cost_tracking:
                try:
                    from .cost_ledger import cost_ledger

                    cost_ledger.record_cost(
                        provider=self.provider,
                        operation=operation_name,
                        cost_usd=cost,
                        lead_id=lead_id,
                        campaign_id=campaign_id,
                        request_id=str(response.headers.get("x-request-id", "")),
                        metadata={
                            "endpoint": endpoint,
                            "method": method,
                            "status_code": response.status_code,
                            "response_time_ms": int((time.time() - start_time) * 1000),
                        },
                    )
                except Exception as e:
                    # Don't fail the request if cost tracking fails
                    self.logger.warning(f"Failed to record cost to ledger: {e}")

            return response_data

        except Exception as e:
            error = e
            self.circuit_breaker.record_failure()

            if isinstance(e, ExternalAPIError):
                raise
            raise ExternalAPIError(provider=self.provider, message=str(e), status_code=500) from e

        finally:
            # Record metrics
            duration = time.time() - start_time
            status_code = response.status_code if response else 0

            self.metrics.record_api_call(
                provider=self.provider,
                endpoint=endpoint,
                status_code=status_code,
                duration=duration,
            )

            if not error:
                cost = self.calculate_cost(operation_name, **kwargs)
                self.metrics.record_cost(self.provider, endpoint, float(cost))
            else:
                # Record cost for failed requests too (P1-050 requirement)
                if not self.settings.use_stubs and self.settings.enable_cost_tracking:
                    try:
                        cost = self.calculate_cost(operation_name, **kwargs)
                        from .cost_ledger import cost_ledger

                        cost_ledger.record_cost(
                            provider=self.provider,
                            operation=operation_name,
                            cost_usd=cost,
                            lead_id=lead_id,
                            campaign_id=campaign_id,
                            request_id=str(response.headers.get("x-request-id", "")) if response else "",
                            metadata={
                                "endpoint": endpoint,
                                "method": method,
                                "status_code": status_code,
                                "response_time_ms": int(duration * 1000),
                                "error": str(error),
                            },
                        )
                    except Exception as e:
                        # Don't fail the request if cost tracking fails
                        self.logger.warning(f"Failed to record cost to ledger: {e}")

    async def _check_rate_limit(self, operation: str) -> None:
        """Check if request is within rate limits"""
        allowed = await self.rate_limiter.is_allowed(operation)
        if not allowed:
            rate_info = self.get_rate_limit()
            self.logger.warning(f"Rate limit exceeded for {self.provider}")

            raise RateLimitError(
                provider=self.provider,
                retry_after=3600,  # 1 hour default
                daily_limit=rate_info.get("daily_limit", 0),
                daily_used=rate_info.get("daily_used", 0),
            )

    async def health_check(self) -> dict[str, Any]:
        """Perform a health check on the API"""
        try:
            # Simple test request to verify connectivity
            await self.make_request("GET", "health")
            return {
                "provider": self.provider,
                "status": "healthy",
                "circuit_breaker": self.circuit_breaker.state.name,
                "rate_limit": self.get_rate_limit(),
            }
        except Exception as e:
            return {
                "provider": self.provider,
                "status": "unhealthy",
                "error": str(e),
                "circuit_breaker": self.circuit_breaker.state.name,
            }

    def emit_cost(
        self,
        lead_id: int | None = None,
        campaign_id: int | None = None,
        cost_usd: float = 0.0,
        operation: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Emit cost tracking event for API usage

        Args:
            lead_id: Associated lead ID
            campaign_id: Associated campaign ID
            cost_usd: Cost in USD
            operation: Specific operation performed
            metadata: Additional context
        """
        # Import here to avoid circular dependency
        from database.models import APICost
        from database.session import get_db_sync

        try:
            # Create cost record in database
            with get_db_sync() as db:
                cost_record = APICost(
                    provider=self.provider,
                    operation=operation or "unknown",
                    lead_id=lead_id,
                    campaign_id=campaign_id,
                    cost_usd=cost_usd,
                    meta_data=metadata or {},
                )
                db.add(cost_record)
                db.commit()

            # Also record in metrics
            self.metrics.record_cost(self.provider, operation or "unknown", cost_usd)

            self.logger.info(
                f"Cost recorded: ${cost_usd:.4f} for {self.provider}/{operation} "
                f"(lead_id={lead_id}, campaign_id={campaign_id})"
            )

        except Exception as e:
            # Don't fail the request if cost tracking fails
            self.logger.error(f"Failed to record cost: {e}")

    def set_operation_priority(self, operation: str, priority: OperationPriority) -> None:
        """
        Set the priority for a specific operation

        Args:
            operation: Operation name
            priority: Priority level
        """
        cost_enforcement.set_operation_priority(self.provider, operation, priority)
        self.logger.info(f"Set priority {priority.value} for {self.provider}:{operation}")

    async def make_critical_request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """
        Make a critical API request that should never be blocked

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional arguments

        Returns:
            API response
        """
        return await self.make_request(method, endpoint, priority=OperationPriority.CRITICAL, **kwargs)

    async def make_low_priority_request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """
        Make a low priority API request that can be aggressively limited

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional arguments

        Returns:
            API response
        """
        return await self.make_request(method, endpoint, priority=OperationPriority.LOW, **kwargs)
