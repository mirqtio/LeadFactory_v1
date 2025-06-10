"""
Prometheus metrics for D0 Gateway monitoring
"""
from typing import Any, Dict

from prometheus_client import (REGISTRY, CollectorRegistry, Counter, Gauge,
                               Histogram, Info)

from core.logging import get_logger


class GatewayMetrics:
    """Prometheus metrics collector for D0 Gateway"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.logger = get_logger("gateway.metrics", domain="d0")

        # API call metrics
        self.api_calls_total = Counter(
            "gateway_api_calls_total",
            "Total number of API calls made through gateway",
            ["provider", "endpoint", "status_code"],
        )

        self.api_latency_seconds = Histogram(
            "gateway_api_latency_seconds",
            "API call latency in seconds",
            ["provider", "endpoint"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
        )

        self.api_cost_usd_total = Counter(
            "gateway_api_cost_usd_total",
            "Total API costs in USD",
            ["provider", "endpoint"],
        )

        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(
            "gateway_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half-open)",
            ["provider"],
        )

        # Cache metrics
        self.cache_hits_total = Counter(
            "gateway_response_cache_hits_total",
            "Total number of cache hits",
            ["provider", "endpoint"],
        )

        self.cache_misses_total = Counter(
            "gateway_response_cache_misses_total",
            "Total number of cache misses",
            ["provider", "endpoint"],
        )

        # Rate limiting metrics
        self.rate_limit_exceeded_total = Counter(
            "gateway_rate_limit_exceeded_total",
            "Total number of rate limit violations",
            ["provider", "limit_type"],
        )

        self.rate_limit_usage = Gauge(
            "gateway_rate_limit_usage",
            "Current rate limit usage",
            ["provider", "limit_type"],
        )

        # Gateway info
        self.gateway_info = Info(
            "gateway_info", "Gateway version and configuration info"
        )

        # Set initial gateway info
        self.gateway_info.info({"version": "1.0.0", "domain": "d0_gateway"})

        # Mark as initialized
        self.__class__._initialized = True

    def record_api_call(
        self, provider: str, endpoint: str, status_code: int, duration: float
    ) -> None:
        """Record an API call with metrics"""
        try:
            # Convert status code to string for labels
            status_str = str(status_code)

            # Record call count
            self.api_calls_total.labels(
                provider=provider, endpoint=endpoint, status_code=status_str
            ).inc()

            # Record latency
            self.api_latency_seconds.labels(
                provider=provider, endpoint=endpoint
            ).observe(duration)

            self.logger.debug(
                f"Recorded API call: {provider}/{endpoint} "
                f"status={status_code} duration={duration:.3f}s"
            )

        except Exception as e:
            self.logger.error(f"Failed to record API call metrics: {e}")

    def record_cost(self, provider: str, endpoint: str, cost_usd: float) -> None:
        """Record API cost"""
        try:
            self.api_cost_usd_total.labels(provider=provider, endpoint=endpoint).inc(
                cost_usd
            )

            self.logger.debug(f"Recorded cost: {provider}/{endpoint} ${cost_usd:.6f}")

        except Exception as e:
            self.logger.error(f"Failed to record cost metrics: {e}")

    def record_circuit_breaker_state(self, provider: str, state: str) -> None:
        """Record circuit breaker state"""
        try:
            # Map state names to numbers
            state_mapping = {"closed": 0, "open": 1, "half_open": 2}

            state_value = state_mapping.get(state, 0)
            self.circuit_breaker_state.labels(provider=provider).set(state_value)

            self.logger.debug(f"Circuit breaker state: {provider}={state}")

        except Exception as e:
            self.logger.error(f"Failed to record circuit breaker state: {e}")

    def record_cache_hit(self, provider: str, endpoint: str) -> None:
        """Record cache hit"""
        try:
            self.cache_hits_total.labels(provider=provider, endpoint=endpoint).inc()

        except Exception as e:
            self.logger.error(f"Failed to record cache hit: {e}")

    def record_cache_miss(self, provider: str, endpoint: str) -> None:
        """Record cache miss"""
        try:
            self.cache_misses_total.labels(provider=provider, endpoint=endpoint).inc()

        except Exception as e:
            self.logger.error(f"Failed to record cache miss: {e}")

    def record_rate_limit_exceeded(self, provider: str, limit_type: str) -> None:
        """Record rate limit exceeded"""
        try:
            self.rate_limit_exceeded_total.labels(
                provider=provider, limit_type=limit_type
            ).inc()

            self.logger.warning(f"Rate limit exceeded: {provider} {limit_type}")

        except Exception as e:
            self.logger.error(f"Failed to record rate limit violation: {e}")

    def update_rate_limit_usage(
        self, provider: str, limit_type: str, current_usage: int
    ) -> None:
        """Update current rate limit usage"""
        try:
            self.rate_limit_usage.labels(provider=provider, limit_type=limit_type).set(
                current_usage
            )

        except Exception as e:
            self.logger.error(f"Failed to update rate limit usage: {e}")

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of current metrics"""
        try:
            # This would typically be implemented by querying the metrics
            # For now, return a basic summary
            return {
                "metrics_enabled": True,
                "collectors": [
                    "api_calls_total",
                    "api_latency_seconds",
                    "api_cost_usd_total",
                    "circuit_breaker_state",
                    "cache_hits_total",
                    "cache_misses_total",
                    "rate_limit_exceeded_total",
                    "rate_limit_usage",
                ],
            }

        except Exception as e:
            self.logger.error(f"Failed to get metrics summary: {e}")
            return {"metrics_enabled": False, "error": str(e)}
