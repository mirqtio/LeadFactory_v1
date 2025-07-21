"""
Type definitions for targeting domain
"""

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any


class VerticalMarket(str, Enum):
    """Industry verticals for targeting"""

    RESTAURANTS = "restaurants"
    RETAIL = "retail"
    PROFESSIONAL_SERVICES = "professional_services"
    HEALTHCARE = "healthcare"
    AUTOMOTIVE = "automotive"
    REAL_ESTATE = "real_estate"
    FITNESS = "fitness"
    BEAUTY_WELLNESS = "beauty_wellness"
    HOME_SERVICES = "home_services"
    EDUCATION = "education"
    HOSPITALITY = "hospitality"
    FINANCIAL_SERVICES = "financial_services"
    TECHNOLOGY = "technology"
    MANUFACTURING = "manufacturing"
    CONSTRUCTION = "construction"
    LEGAL = "legal"
    NONPROFIT = "nonprofit"
    ENTERTAINMENT = "entertainment"
    AGRICULTURE = "agriculture"
    TRANSPORTATION = "transportation"


class GeographyLevel(str, Enum):
    """Geographic hierarchy levels"""

    COUNTRY = "country"
    STATE = "state"
    COUNTY = "county"
    CITY = "city"
    ZIP_CODE = "zip_code"
    NEIGHBORHOOD = "neighborhood"
    RADIUS = "radius"  # Mile radius from coordinates


class CampaignStatus(str, Enum):
    """Campaign execution status"""

    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class BatchProcessingStatus(str, Enum):
    """Status of batch processing"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class TargetQualificationStatus(str, Enum):
    """Target qualification status"""

    UNQUALIFIED = "unqualified"
    PENDING_REVIEW = "pending_review"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    CONVERTED = "converted"
    EXCLUDED = "excluded"


@dataclass
class TargetingCriteria:
    """Criteria for target selection"""

    verticals: list[VerticalMarket]
    geography: dict[str, Any]  # Geographic constraints
    business_size: dict[str, int] | None = None  # employee/revenue ranges
    website_required: bool = True
    phone_required: bool = True
    email_required: bool = False
    min_rating: float | None = None
    max_age_days: int | None = None  # How recent the business data should be
    exclude_chains: bool = False
    exclude_franchises: bool = False


@dataclass
class GeographicConstraint:
    """Geographic targeting constraint"""

    level: GeographyLevel
    values: list[str]  # State codes, city names, zip codes, etc.
    radius_miles: float | None = None  # For radius-based targeting
    center_lat: float | None = None
    center_lng: float | None = None


@dataclass
class BatchSchedule:
    """Batch processing schedule configuration"""

    batch_size: int = 100
    max_concurrent_batches: int = 5
    delay_between_batches_seconds: int = 60
    retry_failed_attempts: int = 3
    retry_delay_seconds: int = 300
    max_daily_targets: int | None = None
    allowed_hours_start: time = time(9, 0)  # 9 AM
    allowed_hours_end: time = time(17, 0)  # 5 PM
    allowed_days: list[int] = None  # Monday=0, Sunday=6, None = all days


@dataclass
class TargetMetrics:
    """Metrics for a target or campaign"""

    total_targets: int = 0
    qualified_targets: int = 0
    contacted_targets: int = 0
    responded_targets: int = 0
    converted_targets: int = 0
    excluded_targets: int = 0
    qualification_rate: float = 0.0
    contact_rate: float = 0.0
    response_rate: float = 0.0
    conversion_rate: float = 0.0
    avg_contact_attempts: float = 0.0
    total_cost: Decimal = Decimal("0.00")
    cost_per_contact: Decimal = Decimal("0.00")
    cost_per_conversion: Decimal = Decimal("0.00")


@dataclass
class CampaignSettings:
    """Campaign execution settings"""

    auto_qualify: bool = True
    auto_contact: bool = False
    contact_method: str = "email"  # email, phone, both
    max_contact_attempts: int = 3
    contact_interval_hours: int = 24
    personalization_level: str = "basic"  # basic, advanced, custom
    a_b_test_enabled: bool = False
    conversion_tracking: bool = True


@dataclass
class TargetSource:
    """Source information for a target"""

    provider: str  # google, manual, etc.
    external_id: str | None = None
    discovered_at: datetime | None = None
    last_updated: datetime | None = None
    data_quality_score: float | None = None
    verification_status: str = "unverified"


# Type aliases for convenience
TargetId = str
CampaignId = str
BatchId = str
GeographyConfig = dict[str, Any]
ContactInfo = dict[str, str]
BusinessInfo = dict[str, Any]


@dataclass
class QualificationRules:
    """Rules for automatic target qualification"""

    min_website_score: float | None = None
    required_contact_methods: list[str] = None
    exclude_keywords: list[str] = None
    require_keywords: list[str] = None
    min_business_age_months: int | None = None
    max_distance_miles: float | None = None
    business_hours_required: bool = False
    social_media_required: bool = False


@dataclass
class TargetingMetrics:
    """Detailed metrics for targeting analysis"""

    search_queries_executed: int = 0
    raw_results_found: int = 0
    duplicates_removed: int = 0
    filtered_by_criteria: int = 0
    qualified_targets: int = 0
    processing_time_seconds: float = 0.0
    api_calls_made: int = 0
    api_cost_total: Decimal = Decimal("0.00")
    data_quality_score: float = 0.0
    coverage_percentage: float = 0.0
