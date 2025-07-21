"""
Assessment API Schemas - Task 035

Pydantic schemas for assessment API request/response validation.
Provides structured data models for triggering assessments, checking status,
and retrieving results with proper error handling.

Acceptance Criteria:
- Trigger assessment endpoint
- Status checking works
- Results retrieval API
- Proper error responses
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Union

from pydantic import BaseModel, Field, HttpUrl, validator

from .types import AssessmentStatus, AssessmentType


class TriggerAssessmentRequest(BaseModel):
    """Request model for triggering an assessment"""

    business_id: str = Field(..., description="Business identifier")
    url: HttpUrl = Field(..., description="Website URL to assess")
    assessment_types: list[AssessmentType] | None = Field(
        default=None, description="Types of assessments to run (defaults to all)"
    )
    industry: str | None = Field(default="default", description="Industry for specialized insights")
    priority: str | None = Field(
        default="medium",
        description="Assessment priority (low, medium, high, critical)",
    )
    session_config: dict[str, Any] | None = Field(
        default=None, description="Additional configuration for the assessment session"
    )
    business_data: dict[str, Any] | None = Field(
        default=None, description="Business information for enhanced assessments (e.g., GBP)"
    )
    callback_url: HttpUrl | None = Field(default=None, description="URL to POST results when assessment completes")

    @validator("priority")
    def validate_priority(cls, v):
        valid_priorities = ["low", "medium", "high", "critical"]
        if v.lower() not in valid_priorities:
            raise ValueError(f"Priority must be one of: {valid_priorities}")
        return v.lower()

    @validator("industry")
    def validate_industry(cls, v):
        valid_industries = [
            "default",
            "ecommerce",
            "healthcare",
            "finance",
            "education",
            "nonprofit",
            "technology",
            "professional_services",
            "retail",
            "manufacturing",
        ]
        if v.lower() not in valid_industries:
            raise ValueError(f"Industry must be one of: {valid_industries}")
        return v.lower()

    class Config:
        json_schema_extra = {
            "example": {
                "business_id": "biz_123456789",
                "url": "https://example-store.com",
                "assessment_types": ["pagespeed", "tech_stack", "ai_insights"],
                "industry": "ecommerce",
                "priority": "high",
                "session_config": {
                    "detailed_analysis": True,
                    "include_screenshots": False,
                },
                "callback_url": "https://api.example.com/webhooks/assessment-complete",
            }
        }


class TriggerAssessmentResponse(BaseModel):
    """Response model for assessment trigger"""

    session_id: str = Field(..., description="Unique session identifier for tracking")
    business_id: str = Field(..., description="Business identifier")
    status: AssessmentStatus = Field(..., description="Initial assessment status")
    total_assessments: int = Field(..., description="Number of assessments to run")
    estimated_completion_time: datetime | None = Field(default=None, description="Estimated completion time")
    tracking_url: str = Field(..., description="URL to check assessment status")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_abcdef123456",
                "business_id": "biz_123456789",
                "status": "running",
                "total_assessments": 3,
                "estimated_completion_time": "2025-06-09T03:00:00Z",
                "tracking_url": "/api/v1/assessments/sess_abcdef123456/status",
            }
        }


class AssessmentStatusResponse(BaseModel):
    """Response model for assessment status checking"""

    session_id: str = Field(..., description="Session identifier")
    business_id: str = Field(..., description="Business identifier")
    status: AssessmentStatus = Field(..., description="Current assessment status")
    progress: str = Field(..., description="Progress description (e.g., '2/3 complete')")
    total_assessments: int = Field(..., description="Total number of assessments")
    completed_assessments: int = Field(..., description="Number of completed assessments")
    failed_assessments: int = Field(..., description="Number of failed assessments")
    started_at: datetime = Field(..., description="Assessment start time")
    estimated_completion: datetime | None = Field(default=None, description="Estimated completion time")
    completed_at: datetime | None = Field(default=None, description="Actual completion time")
    current_step: str | None = Field(default=None, description="Description of current processing step")
    errors: list[str] | None = Field(default=None, description="List of error messages if any assessments failed")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_abcdef123456",
                "business_id": "biz_123456789",
                "status": "running",
                "progress": "2/3 complete",
                "total_assessments": 3,
                "completed_assessments": 2,
                "failed_assessments": 0,
                "started_at": "2025-06-09T02:45:00Z",
                "estimated_completion": "2025-06-09T03:00:00Z",
                "completed_at": None,
                "current_step": "Running AI insights analysis",
                "errors": None,
            }
        }


class TechStackResult(BaseModel):
    """Technology stack detection result"""

    technology_name: str = Field(..., description="Name of detected technology")
    category: str = Field(..., description="Technology category")
    confidence: float = Field(..., description="Detection confidence (0-1)")
    version: str | None = Field(default=None, description="Detected version")


class PageSpeedMetrics(BaseModel):
    """PageSpeed performance metrics"""

    performance_score: int = Field(..., description="Performance score (0-100)")
    accessibility_score: int | None = Field(default=None, description="Accessibility score")
    seo_score: int | None = Field(default=None, description="SEO score")
    best_practices_score: int | None = Field(default=None, description="Best practices score")
    largest_contentful_paint: int | None = Field(default=None, description="LCP in milliseconds")
    first_input_delay: int | None = Field(default=None, description="FID in milliseconds")
    cumulative_layout_shift: float | None = Field(default=None, description="CLS score")
    speed_index: int | None = Field(default=None, description="Speed Index in milliseconds")
    time_to_interactive: int | None = Field(default=None, description="TTI in milliseconds")


class AIInsightsResult(BaseModel):
    """AI-generated insights result"""

    recommendations: list[dict[str, Any]] = Field(..., description="List of recommendations")
    industry_insights: dict[str, Any] = Field(..., description="Industry-specific insights")
    summary: dict[str, Any] = Field(..., description="Overall assessment summary")
    ai_model_version: str = Field(..., description="AI model version used")
    processing_cost_usd: Decimal = Field(..., description="Cost of AI processing")

    class Config:
        protected_namespaces = ()


class AssessmentResults(BaseModel):
    """Complete assessment results"""

    session_id: str = Field(..., description="Session identifier")
    business_id: str = Field(..., description="Business identifier")
    url: str = Field(..., description="Assessed website URL")
    domain: str = Field(..., description="Domain name")
    industry: str = Field(..., description="Industry category")
    status: AssessmentStatus = Field(..., description="Final assessment status")
    total_assessments: int = Field(..., description="Total assessments requested")
    completed_assessments: int = Field(..., description="Successfully completed assessments")
    failed_assessments: int = Field(..., description="Failed assessments")

    # Assessment results by type
    pagespeed_results: PageSpeedMetrics | None = Field(default=None, description="PageSpeed assessment results")
    tech_stack_results: list[TechStackResult] | None = Field(
        default=None, description="Technology stack detection results"
    )
    ai_insights_results: AIInsightsResult | None = Field(
        default=None, description="AI-generated insights and recommendations"
    )

    # Timing and cost information
    started_at: datetime = Field(..., description="Assessment start time")
    completed_at: datetime = Field(..., description="Assessment completion time")
    execution_time_ms: int = Field(..., description="Total execution time in milliseconds")
    total_cost_usd: Decimal = Field(..., description="Total cost of assessment")

    # Error information
    errors: dict[str, str] | None = Field(default=None, description="Errors by assessment type")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_abcdef123456",
                "business_id": "biz_123456789",
                "url": "https://example-store.com",
                "domain": "example-store.com",
                "industry": "ecommerce",
                "status": "completed",
                "total_assessments": 3,
                "completed_assessments": 3,
                "failed_assessments": 0,
                "pagespeed_results": {
                    "performance_score": 85,
                    "accessibility_score": 78,
                    "seo_score": 92,
                    "largest_contentful_paint": 2500,
                    "first_input_delay": 120,
                    "cumulative_layout_shift": 0.08,
                },
                "tech_stack_results": [
                    {
                        "technology_name": "WordPress",
                        "category": "cms",
                        "confidence": 0.95,
                        "version": "6.0",
                    }
                ],
                "ai_insights_results": {
                    "recommendations": [
                        {
                            "title": "Optimize Image Loading",
                            "priority": "High",
                            "impact": "Reduce LCP by 30%",
                        }
                    ],
                    "industry_insights": {
                        "industry": "ecommerce",
                        "competitive_advantage": "Fast loading improves conversion",
                    },
                    "summary": {"overall_health": "Good performance with improvement opportunities"},
                    "model_version": "gpt-4-0125-preview",
                    "processing_cost_usd": "0.35",
                },
                "started_at": "2025-06-09T02:45:00Z",
                "completed_at": "2025-06-09T02:47:30Z",
                "execution_time_ms": 150000,
                "total_cost_usd": "0.50",
                "errors": None,
            }
        }


class BatchAssessmentRequest(BaseModel):
    """Request model for batch assessment processing"""

    assessments: list[TriggerAssessmentRequest] = Field(
        ..., description="List of assessments to process", min_items=1, max_items=50
    )
    max_concurrent: int | None = Field(default=3, description="Maximum concurrent assessments", ge=1, le=10)
    batch_id: str | None = Field(default=None, description="Optional batch identifier for tracking")

    class Config:
        json_schema_extra = {
            "example": {
                "assessments": [
                    {
                        "business_id": "biz_123",
                        "url": "https://site1.com",
                        "industry": "ecommerce",
                    },
                    {
                        "business_id": "biz_456",
                        "url": "https://site2.com",
                        "industry": "healthcare",
                    },
                ],
                "max_concurrent": 3,
                "batch_id": "batch_202506091234",
            }
        }


class BatchAssessmentResponse(BaseModel):
    """Response model for batch assessment trigger"""

    batch_id: str = Field(..., description="Batch identifier")
    total_assessments: int = Field(..., description="Total assessments in batch")
    session_ids: list[str] = Field(..., description="List of session IDs")
    estimated_completion_time: datetime | None = Field(default=None, description="Estimated time for batch completion")
    tracking_url: str = Field(..., description="URL to check batch status")

    class Config:
        json_schema_extra = {
            "example": {
                "batch_id": "batch_202506091234",
                "total_assessments": 2,
                "session_ids": ["sess_abc123", "sess_def456"],
                "estimated_completion_time": "2025-06-09T03:10:00Z",
                "tracking_url": "/api/v1/assessments/batch/batch_202506091234/status",
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response model"""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(default=None, description="Additional error details")
    request_id: str | None = Field(default=None, description="Request identifier for tracking")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        json_schema_extra = {
            "example": {
                "error": "validation_error",
                "message": "Invalid URL format provided",
                "details": {"field": "url", "value": "not-a-valid-url"},
                "request_id": "req_abcdef123456",
                "timestamp": "2025-06-09T02:45:00Z",
            }
        }


class HealthCheckResponse(BaseModel):
    """Health check response model"""

    status: str = Field(..., description="Service health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    version: str = Field(..., description="API version")
    uptime_seconds: int = Field(..., description="Service uptime in seconds")
    dependencies: dict[str, str] = Field(..., description="Status of dependent services")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-06-09T02:45:00Z",
                "version": "1.0.0",
                "uptime_seconds": 86400,
                "dependencies": {
                    "database": "healthy",
                    "pagespeed_api": "healthy",
                    "llm_service": "healthy",
                },
            }
        }


# Response unions for API documentation
AssessmentResponse = Union[
    TriggerAssessmentResponse,
    AssessmentStatusResponse,
    AssessmentResults,
    BatchAssessmentResponse,
    ErrorResponse,
]


# Common field validators
def validate_business_id(business_id: str) -> str:
    """Validate business ID format"""
    if not business_id or len(business_id) < 3:
        raise ValueError("Business ID must be at least 3 characters")
    return business_id


def validate_session_id(session_id: str) -> str:
    """Validate session ID format"""
    if not session_id or len(session_id) < 10:
        raise ValueError("Session ID must be at least 10 characters")
    return session_id
