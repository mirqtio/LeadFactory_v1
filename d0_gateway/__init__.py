"""
D0 Gateway - Unified facade for all external APIs

Provides caching, rate limiting, circuit breakers, and cost tracking.
No other domain makes direct external calls - everything goes through this gateway.
"""

from .base import BaseAPIClient
from .cache import ResponseCache
from .circuit_breaker import CircuitBreaker
from .exceptions import (
    APIProviderError,
    AuthenticationError,
    CircuitBreakerOpenError,
    ConfigurationError,
    GatewayError,
    InvalidResponseError,
    QuotaExceededError,
    RateLimitExceededError,
    ServiceUnavailableError,
    TimeoutError,
)
from .metrics import GatewayMetrics
from .rate_limiter import RateLimiter
from .types import (
    APICredentials,
    APIProvider,
    APIQuota,
    APIRequest,
    APIResponse,
    BulkRequest,
    BulkResponse,
    CacheConfig,
    CacheStrategy,
    CircuitBreakerConfig,
    CircuitBreakerState,
    PriorityRequest,
    ProviderStatus,
    RateLimitConfig,
    RateLimitType,
    RequestPriority,
    TokenBucket,
    UsageMetrics,
)

__all__ = [
    "BaseAPIClient",
    "RateLimiter",
    "CircuitBreaker",
    "ResponseCache",
    "GatewayMetrics",
    # Exceptions
    "GatewayError",
    "APIProviderError",
    "RateLimitExceededError",
    "CircuitBreakerOpenError",
    "AuthenticationError",
    "QuotaExceededError",
    "ServiceUnavailableError",
    "InvalidResponseError",
    "TimeoutError",
    "ConfigurationError",
    # Types
    "APIProvider",
    "CircuitBreakerState",
    "RateLimitType",
    "CacheStrategy",
    "APICredentials",
    "RateLimitConfig",
    "CircuitBreakerConfig",
    "CacheConfig",
    "APIRequest",
    "APIResponse",
    "UsageMetrics",
    "ProviderStatus",
    "BulkRequest",
    "BulkResponse",
    "TokenBucket",
    "APIQuota",
    "RequestPriority",
    "PriorityRequest",
]
