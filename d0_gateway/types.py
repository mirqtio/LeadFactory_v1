"""
Type definitions for gateway domain
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class APIProvider(str, Enum):
    """Supported API providers"""

    PAGESPEED = "pagespeed"
    OPENAI = "openai"
    SENDGRID = "sendgrid"
    STRIPE = "stripe"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RateLimitType(str, Enum):
    """Types of rate limits"""

    DAILY = "daily"
    BURST = "burst"
    MONTHLY = "monthly"


class CacheStrategy(str, Enum):
    """Cache strategies"""

    CACHE_FIRST = "cache_first"  # Check cache first, then API
    API_FIRST = "api_first"  # Check API first, then cache as fallback
    CACHE_ONLY = "cache_only"  # Only use cache, never hit API
    NO_CACHE = "no_cache"  # Never use cache


@dataclass
class APICredentials:
    """API credentials for a provider"""

    api_key: str
    secret_key: str | None = None
    additional_params: dict[str, str] | None = None


@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""

    daily_limit: int
    burst_limit: int
    burst_window_seconds: int = 60
    monthly_limit: int | None = None


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""

    failure_threshold: int = 5
    recovery_timeout_seconds: int = 60
    success_threshold: int = 3  # For half-open state


@dataclass
class CacheConfig:
    """Cache configuration"""

    ttl_seconds: int = 300
    max_size: int = 1000
    strategy: CacheStrategy = CacheStrategy.CACHE_FIRST


@dataclass
class APIRequest:
    """API request details"""

    method: str
    endpoint: str
    params: dict[str, Any] | None = None
    headers: dict[str, str] | None = None
    data: dict[str, Any] | None = None
    timeout: int = 30


@dataclass
class APIResponse:
    """API response wrapper"""

    status_code: int
    data: dict[str, Any]
    headers: dict[str, str]
    response_time: float
    cached: bool = False
    provider: str | None = None
    cost: Decimal | None = None


@dataclass
class UsageMetrics:
    """API usage metrics"""

    requests_today: int
    requests_this_month: int
    cost_today: Decimal
    cost_this_month: Decimal
    quota_remaining: int | None = None
    quota_reset_time: datetime | None = None


@dataclass
class ProviderStatus:
    """Current status of an API provider"""

    provider: APIProvider
    circuit_breaker_state: CircuitBreakerState
    rate_limit_remaining: dict[RateLimitType, int]
    last_request_time: datetime | None
    consecutive_failures: int
    usage_metrics: UsageMetrics


@dataclass
class BulkRequest:
    """Bulk API request for batch operations"""

    requests: list[APIRequest]
    batch_size: int = 10
    delay_between_batches: float = 1.0
    fail_fast: bool = False  # Stop on first failure


@dataclass
class BulkResponse:
    """Bulk API response"""

    responses: list[APIResponse]
    successful_count: int
    failed_count: int
    total_cost: Decimal
    total_time: float


# Type aliases for common patterns
ProviderConfig = dict[str, Any]
RequestHeaders = dict[str, str]
QueryParams = dict[str, str | int | float | bool]
ResponseData = dict[str, Any]
ErrorContext = dict[str, Any]

# Rate limiting token bucket types
TokenCount = int
TimeSeconds = float
BucketKey = str


@dataclass
class TokenBucket:
    """Token bucket for rate limiting"""

    capacity: int
    tokens: int
    last_refill: datetime
    refill_rate: float  # tokens per second


@dataclass
class APIQuota:
    """API quota information"""

    limit: int
    used: int
    remaining: int
    reset_time: datetime
    period: str  # "daily", "monthly", etc.


class RequestPriority(str, Enum):
    """Request priority levels"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class PriorityRequest:
    """Request with priority"""

    request: APIRequest
    priority: RequestPriority
    submitted_at: datetime
    max_wait_seconds: int | None = None
