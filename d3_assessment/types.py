"""
D3 Assessment Types - Task 030

Enums and type definitions for website assessment functionality.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class AssessmentStatus(Enum):
    """Status of an assessment"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class AssessmentType(Enum):
    """Type of assessment being performed"""

    PAGESPEED = "pagespeed"
    TECH_STACK = "tech_stack"
    AI_INSIGHTS = "ai_insights"
    BUSINESS_INFO = "business_info"  # For GBP assessor
    LIGHTHOUSE = "lighthouse"  # For Lighthouse assessor
    VISUAL = "visual"  # For visual analyzer
    FULL_AUDIT = "full_audit"
    QUICK_SCAN = "quick_scan"
    CUSTOM = "custom"


class PageSpeedMetric(Enum):
    """PageSpeed Insights metrics"""

    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    BEST_PRACTICES = "best_practices"
    SEO = "seo"
    PWA = "pwa"
    FCP = "first_contentful_paint"
    LCP = "largest_contentful_paint"
    FID = "first_input_delay"
    CLS = "cumulative_layout_shift"
    SI = "speed_index"
    TTI = "time_to_interactive"
    TBT = "total_blocking_time"


class TechCategory(Enum):
    """Technology stack categories"""

    CMS = "cms"
    ECOMMERCE = "ecommerce"
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATABASE = "database"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    HOSTING = "hosting"
    CDN = "cdn"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ADVERTISING = "advertising"
    SOCIAL = "social"
    PAYMENT = "payment"
    EMAIL = "email"
    CHAT = "chat"
    MONITORING = "monitoring"
    DEVELOPMENT = "development"
    OTHER = "other"


class InsightCategory(Enum):
    """AI insight categories"""

    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    SEO_RECOMMENDATIONS = "seo_recommendations"
    USER_EXPERIENCE = "user_experience"
    ACCESSIBILITY_ISSUES = "accessibility_issues"
    SECURITY_CONCERNS = "security_concerns"
    MOBILE_OPTIMIZATION = "mobile_optimization"
    CONVERSION_OPTIMIZATION = "conversion_optimization"
    TECHNICAL_DEBT = "technical_debt"
    COMPETITIVE_ANALYSIS = "competitive_analysis"
    BUSINESS_INSIGHTS = "business_insights"
    COST_OPTIMIZATION = "cost_optimization"
    CONTENT_QUALITY = "content_quality"


class InsightType(Enum):
    """Types of LLM insights to generate"""

    RECOMMENDATIONS = "recommendations"
    TECHNICAL_ANALYSIS = "technical_analysis"
    INDUSTRY_BENCHMARK = "industry_benchmark"
    QUICK_WINS = "quick_wins"
    COMPETITIVE_ANALYSIS = "competitive_analysis"
    SECURITY_AUDIT = "security_audit"


class CostType(Enum):
    """Types of costs associated with assessments"""

    API_CALL = "api_call"
    PROCESSING_TIME = "processing_time"
    STORAGE = "storage"
    BANDWIDTH = "bandwidth"
    AI_TOKENS = "ai_tokens"
    EXTERNAL_SERVICE = "external_service"
    COMPUTE = "compute"
    CACHE_MISS = "cache_miss"


class IssueType(Enum):
    """Types of issues that can be identified in assessments"""

    PERFORMANCE = "performance"
    SEO = "seo"
    USABILITY = "usability"
    ACCESSIBILITY = "accessibility"
    SECURITY = "security"
    CONTENT = "content"
    TECHNICAL = "technical"
    MOBILE = "mobile"
    COMPLIANCE = "compliance"
    CONVERSION = "conversion"


class IssueSeverity(Enum):
    """Severity levels for assessment issues"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class AssessmentConfig:
    """Configuration for assessment operations"""

    assessment_type: AssessmentType
    include_pagespeed: bool = True
    include_tech_stack: bool = True
    include_ai_insights: bool = True
    mobile_assessment: bool = True
    desktop_assessment: bool = True
    max_processing_time: int = 300  # seconds
    enable_caching: bool = True
    cache_ttl: int = 3600  # seconds
    cost_limit: float | None = None
    priority: int = 5  # 1-10 scale
    custom_settings: dict[str, Any] | None = None


@dataclass
class PageSpeedScore:
    """PageSpeed Insights score data"""

    metric: PageSpeedMetric
    score: float
    value: float | None = None
    unit: str | None = None
    display_value: str | None = None
    description: str | None = None


@dataclass
class TechStackItem:
    """Individual technology detected"""

    name: str
    category: TechCategory
    version: str | None = None
    confidence: float = 1.0
    website: str | None = None
    icon: str | None = None
    description: str | None = None
    pricing: str | None = None


@dataclass
class AIInsightItem:
    """Individual AI-generated insight"""

    category: InsightCategory
    title: str
    description: str
    impact: str  # high, medium, low
    effort: str  # high, medium, low
    confidence: float = 1.0
    priority: int = 5
    actionable_steps: list[str] | None = None
    estimated_improvement: str | None = None


@dataclass
class AssessmentCostItem:
    """Individual cost item for an assessment"""

    cost_type: CostType
    amount: float
    currency: str = "USD"
    provider: str | None = None
    description: str | None = None
    timestamp: datetime | None = None


@dataclass
class AssessmentMetadata:
    """Metadata about an assessment"""

    user_agent: str | None = None
    ip_address: str | None = None
    referrer: str | None = None
    assessment_config: dict[str, Any] | None = None
    processing_time: float | None = None
    cache_hit: bool = False
    retry_count: int = 0
    error_details: dict[str, Any] | None = None


# Type aliases for common data structures
PageSpeedData = dict[str, Any]
TechStackData = dict[str, Any]
AIInsightData = dict[str, Any]
AssessmentData = dict[str, Any]
