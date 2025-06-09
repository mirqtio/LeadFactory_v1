"""
D0 Gateway - Unified facade for all external APIs

Provides caching, rate limiting, circuit breakers, and cost tracking.
No other domain makes direct external calls - everything goes through this gateway.
"""

from .base import BaseAPIClient
from .rate_limiter import RateLimiter
from .circuit_breaker import CircuitBreaker
from .cache import ResponseCache
from .metrics import GatewayMetrics
from .exceptions import (
    GatewayError,
    APIProviderError,
    RateLimitExceededError,
    CircuitBreakerOpenError,
    AuthenticationError,
    QuotaExceededError,
    ServiceUnavailableError,
    InvalidResponseError,
    TimeoutError,
    ConfigurationError
)
from .types import (
    APIProvider,
    CircuitBreakerState,
    RateLimitType,
    CacheStrategy,
    APICredentials,
    RateLimitConfig,
    CircuitBreakerConfig,
    CacheConfig,
    APIRequest,
    APIResponse,
    UsageMetrics,
    ProviderStatus,
    BulkRequest,
    BulkResponse,
    TokenBucket,
    APIQuota,
    RequestPriority,
    PriorityRequest
)

__all__ = [
    'BaseAPIClient',
    'RateLimiter',
    'CircuitBreaker',
    'ResponseCache',
    'GatewayMetrics',
    # Exceptions
    'GatewayError',
    'APIProviderError',
    'RateLimitExceededError',
    'CircuitBreakerOpenError',
    'AuthenticationError',
    'QuotaExceededError',
    'ServiceUnavailableError',
    'InvalidResponseError',
    'TimeoutError',
    'ConfigurationError',
    # Types
    'APIProvider',
    'CircuitBreakerState',
    'RateLimitType',
    'CacheStrategy',
    'APICredentials',
    'RateLimitConfig',
    'CircuitBreakerConfig',
    'CacheConfig',
    'APIRequest',
    'APIResponse',
    'UsageMetrics',
    'ProviderStatus',
    'BulkRequest',
    'BulkResponse',
    'TokenBucket',
    'APIQuota',
    'RequestPriority',
    'PriorityRequest'
]
