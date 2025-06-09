"""
D3 Assessment Types - Task 030

Enums and type definitions for website assessment functionality.
"""
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime


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
    cost_limit: Optional[float] = None
    priority: int = 5  # 1-10 scale
    custom_settings: Optional[Dict[str, Any]] = None


@dataclass
class PageSpeedScore:
    """PageSpeed Insights score data"""
    metric: PageSpeedMetric
    score: float
    value: Optional[float] = None
    unit: Optional[str] = None
    display_value: Optional[str] = None
    description: Optional[str] = None


@dataclass
class TechStackItem:
    """Individual technology detected"""
    name: str
    category: TechCategory
    version: Optional[str] = None
    confidence: float = 1.0
    website: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    pricing: Optional[str] = None


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
    actionable_steps: Optional[List[str]] = None
    estimated_improvement: Optional[str] = None


@dataclass
class AssessmentCostItem:
    """Individual cost item for an assessment"""
    cost_type: CostType
    amount: float
    currency: str = "USD"
    provider: Optional[str] = None
    description: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class AssessmentMetadata:
    """Metadata about an assessment"""
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    referrer: Optional[str] = None
    assessment_config: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None
    cache_hit: bool = False
    retry_count: int = 0
    error_details: Optional[Dict[str, Any]] = None


# Type aliases for common data structures
PageSpeedData = Dict[str, Any]
TechStackData = Dict[str, Any] 
AIInsightData = Dict[str, Any]
AssessmentData = Dict[str, Any]