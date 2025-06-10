"""
Base API client with common functionality for all external API providers
"""
import asyncio
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx
from prometheus_client import Counter, Gauge, Histogram

from core.config import get_settings
from core.exceptions import ExternalAPIError, RateLimitError
from core.logging import get_logger

from .cache import ResponseCache
from .circuit_breaker import CircuitBreaker
from .metrics import GatewayMetrics
from .rate_limiter import RateLimiter


class BaseAPIClient(ABC):
    """Abstract base class for all external API clients"""

    def __init__(
        self,
        provider: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider = provider
        self.settings = get_settings()
        self.logger = get_logger(f"gateway.{provider}", domain="d0")

        # Use stub URLs and keys if configured
        if self.settings.use_stubs:
            self.api_key = f"stub-{provider}-key"
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
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0), headers=self._get_headers()
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    @abstractmethod
    def _get_base_url(self) -> str:
        """Get the base URL for this provider"""
        pass

    @abstractmethod
    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers for this provider"""
        pass

    @abstractmethod
    def get_rate_limit(self) -> Dict[str, int]:
        """Get rate limit configuration for this provider"""
        pass

    @abstractmethod
    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        """Calculate cost for a specific operation"""
        pass

    async def make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Make an authenticated API request with all gateway features

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
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

        # Check rate limits
        await self._check_rate_limit(operation)

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
                except:
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
            cost = self.calculate_cost(operation, **kwargs)

            return response_data

        except Exception as e:
            error = e
            self.circuit_breaker.record_failure()

            if isinstance(e, ExternalAPIError):
                raise
            else:
                raise ExternalAPIError(
                    provider=self.provider, message=str(e), status_code=500
                ) from e

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
                cost = self.calculate_cost(operation, **kwargs)
                self.metrics.record_cost(self.provider, endpoint, float(cost))

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

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the API"""
        try:
            # Simple test request to verify connectivity
            response = await self.make_request("GET", "health")
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
