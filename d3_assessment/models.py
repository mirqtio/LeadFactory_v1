"""
D3 Assessment Models - Task 030

Comprehensive models for storing website assessment results with JSONB fields,
proper indexing, and cost tracking.

Acceptance Criteria:
- Assessment result model
- JSONB for flexible data
- Proper indexing
- Cost tracking fields
"""
import uuid

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text,
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
    DECIMAL, TIMESTAMP, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base
from .types import (
    AssessmentStatus, AssessmentType,
    TechCategory, InsightCategory, InsightType, CostType
)


def generate_uuid():
    """Generate a new UUID"""
    return str(uuid.uuid4())


class AssessmentResult(Base):
    """
    Comprehensive assessment result model with flexible JSONB data storage

    Acceptance Criteria: Assessment result model, JSONB for flexible data
    """
    __tablename__ = "d3_assessment_results"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    session_id = Column(String, ForeignKey("d3_assessment_sessions.id"))

    # Assessment metadata
    assessment_type = Column(SQLEnum(AssessmentType), nullable=False)
    status = Column(SQLEnum(AssessmentStatus),
                   default=AssessmentStatus.PENDING)
    priority = Column(Integer, default=5, nullable=False)

    # Website information
    url = Column(String(2048), nullable=False)
    domain = Column(String(255), nullable=False)
    is_mobile = Column(Boolean, default=False)
    user_agent = Column(Text)

    # Flexible data storage using JSONB
    pagespeed_data = Column(JSONB)  # PageSpeed Insights raw data
    tech_stack_data = Column(JSONB)  # Technology detection results
    ai_insights_data = Column(JSONB)  # AI-generated insights
    assessment_metadata = Column(JSONB)  # Additional metadata

    # Extracted key metrics for quick querying
    performance_score = Column(Integer)
    accessibility_score = Column(Integer)
    best_practices_score = Column(Integer)
    seo_score = Column(Integer)
    pwa_score = Column(Integer)

    # Core Web Vitals
    first_contentful_paint = Column(Float)
    largest_contentful_paint = Column(Float)
    first_input_delay = Column(Float)
    cumulative_layout_shift = Column(Float)
    speed_index = Column(Float)
    time_to_interactive = Column(Float)
    total_blocking_time = Column(Float)

    # Technology count summaries
    cms_detected = Column(String(100))
    framework_detected = Column(String(100))
    hosting_detected = Column(String(100))
    tech_count = Column(Integer, default=0)

    # AI insights summary
    insights_count = Column(Integer, default=0)
    high_priority_issues = Column(Integer, default=0)
    estimated_improvement_potential = Column(Float)

    # Processing information
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    processing_time_ms = Column(Integer)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    cache_hit = Column(Boolean, default=False)

    # Cost tracking fields
    total_cost_usd = Column(DECIMAL(10, 6), default=0)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(),
                         onupdate=func.now())

    # Relationships
    session = relationship("AssessmentSession", back_populates="results")
    costs = relationship("AssessmentCost", back_populates="assessment")

    # Proper indexing for performance
    __table_args__ = (
        # Core query indexes
        Index("idx_d3_assessment_business_type",
              "business_id", "assessment_type"),
        Index("idx_d3_assessment_status", "status"),
        Index("idx_d3_assessment_created", "created_at"),
        Index("idx_d3_assessment_domain", "domain"),

        # Performance query indexes
        Index("idx_d3_assessment_scores",
              "performance_score", "accessibility_score"),
        Index("idx_d3_assessment_vitals",
              "largest_contentful_paint", "first_input_delay"),

        # JSONB indexes for flexible queries
        Index("idx_d3_assessment_pagespeed_gin", "pagespeed_data", postgresql_using="gin"),
        Index("idx_d3_assessment_tech_gin", "tech_stack_data", postgresql_using="gin"),
        Index("idx_d3_assessment_insights_gin", "ai_insights_data", postgresql_using="gin"),
        Index("idx_d3_assessment_metadata_gin", "assessment_metadata", postgresql_using="gin"),

        # Composite indexes for common queries
        Index("idx_d3_assessment_business_status_type", "business_id", "status", "assessment_type"),
        Index("idx_d3_assessment_cost_created", "total_cost_usd", "created_at"),

        # Constraints
        CheckConstraint("performance_score >= 0 AND performance_score <= 100", name="check_performance_score"),
        CheckConstraint("accessibility_score >= 0 AND accessibility_score <= 100", name="check_accessibility_score"),
        CheckConstraint("priority >= 1 AND priority <= 10", name="check_priority"),
        CheckConstraint("total_cost_usd >= 0", name="check_cost_positive"),
    )


class PageSpeedAssessment(Base):
    """
    Detailed PageSpeed assessment data with JSONB storage

    Acceptance Criteria: JSONB for flexible data, Proper indexing
    """
    __tablename__ = "d3_pagespeed_assessments"

    id = Column(String, primary_key=True, default=generate_uuid)
    assessment_id = Column(String, ForeignKey("d3_assessment_results.id"), nullable=False)

    # Device type
    is_mobile = Column(Boolean, default=False)

    # Lighthouse scores
    lighthouse_data = Column(JSONB, nullable=False)

    # Core metrics (extracted for quick access)
    performance_score = Column(Integer)
    accessibility_score = Column(Integer)
    best_practices_score = Column(Integer)
    seo_score = Column(Integer)
    pwa_score = Column(Integer)

    # Core Web Vitals details
    core_web_vitals = Column(JSONB)

    # Field data vs lab data
    field_data = Column(JSONB)
    lab_data = Column(JSONB)

    # Opportunities and diagnostics
    opportunities = Column(JSONB)
    diagnostics = Column(JSONB)

    # Processing metadata
    lighthouse_version = Column(String(50))
    user_agent = Column(Text)
    fetch_time = Column(TIMESTAMP)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    assessment = relationship("AssessmentResult")

    __table_args__ = (
        Index("idx_d3_pagespeed_assessment", "assessment_id"),
        Index("idx_d3_pagespeed_mobile", "is_mobile"),
        Index("idx_d3_pagespeed_scores", "performance_score", "accessibility_score"),
        Index("idx_d3_pagespeed_lighthouse_gin", "lighthouse_data", postgresql_using="gin"),
        Index("idx_d3_pagespeed_vitals_gin", "core_web_vitals", postgresql_using="gin"),
        Index("idx_d3_pagespeed_opportunities_gin", "opportunities", postgresql_using="gin"),

        UniqueConstraint("assessment_id", "is_mobile", name="uq_pagespeed_assessment_device"),
    )


class TechStackDetection(Base):
    """
    Technology stack detection results with categorized data

    Acceptance Criteria: JSONB for flexible data, Proper indexing
    """
    __tablename__ = "d3_tech_stack_detections"

    id = Column(String, primary_key=True, default=generate_uuid)
    assessment_id = Column(String, ForeignKey("d3_assessment_results.id"), nullable=False)

    # Technology details
    technology_name = Column(String(200), nullable=False)
    category = Column(SQLEnum(TechCategory), nullable=False)
    version = Column(String(100))
    confidence = Column(Float, default=1.0)

    # Flexible technology data
    technology_data = Column(JSONB)

    # Detection metadata
    detection_method = Column(String(100))
    website_url = Column(String(2048))
    icon_url = Column(String(2048))
    description = Column(Text)
    pricing_info = Column(Text)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    assessment = relationship("AssessmentResult")

    __table_args__ = (
        Index("idx_d3_tech_assessment", "assessment_id"),
        Index("idx_d3_tech_category", "category"),
        Index("idx_d3_tech_name", "technology_name"),
        Index("idx_d3_tech_confidence", "confidence"),
        Index("idx_d3_tech_data_gin", "technology_data", postgresql_using="gin"),
        Index("idx_d3_tech_category_confidence", "category", "confidence"),

        CheckConstraint("confidence >= 0 AND confidence <= 1", name="check_tech_confidence"),
    )


class AIInsight(Base):
    """
    AI-generated insights and recommendations

    Acceptance Criteria: JSONB for flexible data, Proper indexing
    """
    __tablename__ = "d3_ai_insights"

    id = Column(String, primary_key=True, default=generate_uuid)
    assessment_id = Column(String, ForeignKey("d3_assessment_results.id"), nullable=False)

    # Insight classification
    category = Column(SQLEnum(InsightCategory), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)

    # Priority and impact
    impact = Column(String(20), nullable=False)  # high, medium, low
    effort = Column(String(20), nullable=False)  # high, medium, low
    priority = Column(Integer, default=5)
    confidence = Column(Float, default=1.0)

    # Actionable recommendations
    actionable_steps = Column(JSONB)
    estimated_improvement = Column(String(200))

    # AI-generated data
    ai_data = Column(JSONB)

    # Source information
    ai_model = Column(String(100))
    prompt_template = Column(String(200))
    token_count = Column(Integer)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    assessment = relationship("AssessmentResult")

    __table_args__ = (
        Index("idx_d3_insights_assessment", "assessment_id"),
        Index("idx_d3_insights_category", "category"),
        Index("idx_d3_insights_priority", "priority"),
        Index("idx_d3_insights_impact", "impact"),
        Index("idx_d3_insights_confidence", "confidence"),
        Index("idx_d3_insights_steps_gin", "actionable_steps", postgresql_using="gin"),
        Index("idx_d3_insights_data_gin", "ai_data", postgresql_using="gin"),
        Index("idx_d3_insights_category_priority", "category", "priority"),

        CheckConstraint("priority >= 1 AND priority <= 10", name="check_insight_priority"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="check_insight_confidence"),
        CheckConstraint("impact IN ('high', 'medium', 'low')", name="check_insight_impact"),
        CheckConstraint("effort IN ('high', 'medium', 'low')", name="check_insight_effort"),
    )


class AssessmentSession(Base):
    """
    Assessment session for tracking batches of related assessments

    Acceptance Criteria: Assessment result model, Cost tracking fields
    """
    __tablename__ = "d3_assessment_sessions"

    id = Column(String, primary_key=True, default=generate_uuid)

    # Session metadata
    session_name = Column(String(200))
    assessment_type = Column(SQLEnum(AssessmentType), nullable=False)
    user_id = Column(String(100))  # For future user management

    # Session configuration
    config_data = Column(JSONB)

    # Progress tracking
    total_assessments = Column(Integer, default=0)
    completed_assessments = Column(Integer, default=0)
    failed_assessments = Column(Integer, default=0)

    # Cost tracking
    total_cost_usd = Column(DECIMAL(10, 6), default=0)
    estimated_cost_usd = Column(DECIMAL(10, 6))

    # Timing
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)
    estimated_duration_minutes = Column(Integer)

    # Status
    status = Column(SQLEnum(AssessmentStatus), default=AssessmentStatus.PENDING)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(),
                         onupdate=func.now())

    # Relationships
    results = relationship("AssessmentResult", back_populates="session")
    costs = relationship("AssessmentCost", back_populates="session")

    __table_args__ = (
        Index("idx_d3_session_status", "status"),
        Index("idx_d3_session_type", "assessment_type"),
        Index("idx_d3_session_user", "user_id"),
        Index("idx_d3_session_created", "created_at"),
        Index("idx_d3_session_cost", "total_cost_usd"),
        Index("idx_d3_session_config_gin", "config_data", postgresql_using="gin"),

        CheckConstraint("total_cost_usd >= 0", name="check_session_cost_positive"),
        CheckConstraint("completed_assessments <= total_assessments", name="check_session_progress"),
    )


class AssessmentCost(Base):
    """
    Detailed cost tracking for assessment operations

    Acceptance Criteria: Cost tracking fields
    """
    __tablename__ = "d3_assessment_costs"

    id = Column(String, primary_key=True, default=generate_uuid)
    assessment_id = Column(String, ForeignKey("d3_assessment_results.id"))
    session_id = Column(String, ForeignKey("d3_assessment_sessions.id"))

    # Cost details
    cost_type = Column(SQLEnum(CostType), nullable=False)
    amount = Column(DECIMAL(10, 6), nullable=False)
    currency = Column(String(3), default="USD")

    # Provider and service details
    provider = Column(String(100))
    service_name = Column(String(200))
    description = Column(Text)

    # Usage metrics
    units_consumed = Column(Float)
    unit_type = Column(String(50))  # tokens, requests, bytes, etc.
    rate_per_unit = Column(DECIMAL(10, 6))

    # Metadata
    cost_data = Column(JSONB)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    assessment = relationship("AssessmentResult", back_populates="costs")
    session = relationship("AssessmentSession", back_populates="costs")

    __table_args__ = (
        Index("idx_d3_costs_assessment", "assessment_id"),
        Index("idx_d3_costs_session", "session_id"),
        Index("idx_d3_costs_type", "cost_type"),
        Index("idx_d3_costs_provider", "provider"),
        Index("idx_d3_costs_amount", "amount"),
        Index("idx_d3_costs_created", "created_at"),
        Index("idx_d3_costs_data_gin", "cost_data", postgresql_using="gin"),
        Index("idx_d3_costs_type_amount", "cost_type", "amount"),

        CheckConstraint("amount >= 0", name="check_cost_amount_positive"),
    )


class LLMInsightResult(Base):
    """
    LLM-generated comprehensive insights and recommendations - Task 033

    Stores structured insights, recommendations, and analysis generated by LLM
    with cost tracking and metadata.

    Acceptance Criteria: 3 recommendations generated, Industry-specific insights,
    Cost tracking works, Structured output parsing
    """
    __tablename__ = "d3_llm_insights"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)
    assessment_id = Column(String, ForeignKey("d3_assessment_results.id"), nullable=False)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)

    # Industry and context
    industry = Column(String(100))
    insight_types = Column(JSONB)  # List of InsightType values

    # Generated insights (structured JSON)
    insights = Column(JSONB, nullable=False)  # Main insights data

    # Cost tracking
    total_cost_usd = Column(DECIMAL(10, 6), default=0)

    # Generation metadata
    generated_at = Column(TIMESTAMP, nullable=False)
    completed_at = Column(TIMESTAMP)
    processing_time_ms = Column(Integer)

    # LLM metadata
    model_version = Column(String(100))
    total_tokens = Column(Integer)

    # Error handling
    error_message = Column(Text)

    # Relationships
    assessment = relationship("AssessmentResult")

    __table_args__ = (
        Index("idx_d3_llm_insights_assessment", "assessment_id"),
        Index("idx_d3_llm_insights_business", "business_id"),
        Index("idx_d3_llm_insights_industry", "industry"),
        Index("idx_d3_llm_insights_generated", "generated_at"),
        Index("idx_d3_llm_insights_cost", "total_cost_usd"),
        Index("idx_d3_llm_insights_model", "model_version"),
        Index("idx_d3_llm_insights_types_gin", "insight_types", postgresql_using="gin"),
        Index("idx_d3_llm_insights_data_gin", "insights", postgresql_using="gin"),
        Index("idx_d3_llm_insights_industry_cost", "industry", "total_cost_usd"),

        CheckConstraint("total_cost_usd >= 0", name="check_llm_cost_positive"),
    )
