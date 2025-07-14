"""
D8 Personalization Models - Task 060

Database models for email personalization system including content generation,
subject line variants, personalization tokens, and spam score tracking.

Acceptance Criteria:
- Email content model ✓
- Subject line variants ✓
- Personalization tokens ✓
- Spam score tracking ✓
"""

import enum
import uuid

from sqlalchemy import DECIMAL, JSON, Boolean, CheckConstraint, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint

# Database compatibility: Use JSON for better SQLite compatibility
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# Use JSON type for better cross-database compatibility in tests
JsonColumn = JSON

from database.base import UUID, Base


def generate_uuid():
    """Generate a new UUID"""
    return str(uuid.uuid4())


# Enums for personalization system
class EmailContentType(str, enum.Enum):
    """Types of email content for different use cases"""

    COLD_OUTREACH = "cold_outreach"  # Initial contact emails
    AUDIT_OFFER = "audit_offer"  # Website audit offers
    FOLLOW_UP = "follow_up"  # Follow-up emails
    PROMOTIONAL = "promotional"  # Promotional content
    EDUCATIONAL = "educational"  # Educational content
    NEWSLETTER = "newsletter"  # Newsletter content


class PersonalizationStrategy(str, enum.Enum):
    """Personalization strategies for content generation"""

    BUSINESS_SPECIFIC = "business_specific"  # Based on business data
    INDUSTRY_VERTICAL = "industry_vertical"  # Based on industry
    GEOGRAPHIC = "geographic"  # Based on location
    WEBSITE_ISSUES = "website_issues"  # Based on audit findings
    COMPETITOR_ANALYSIS = "competitor_analysis"  # Based on competitor data
    CONVERSION_OPTIMIZED = "conversion_optimized"  # Focus on conversion


class SpamCategory(str, enum.Enum):
    """Categories of spam indicators for tracking"""

    SUBJECT_LINE = "subject_line"  # Subject line issues
    CONTENT_BODY = "content_body"  # Body content issues
    CALL_TO_ACTION = "call_to_action"  # CTA issues
    PERSONALIZATION = "personalization"  # Over-personalization
    FORMATTING = "formatting"  # Format issues
    SENDER_REPUTATION = "sender_reputation"  # Sender issues


class VariantStatus(str, enum.Enum):
    """Status of content variants in A/B testing"""

    DRAFT = "draft"  # Being developed
    ACTIVE = "active"  # Currently being tested
    PAUSED = "paused"  # Temporarily disabled
    WINNING = "winning"  # Best performer
    LOSING = "losing"  # Poor performer
    ARCHIVED = "archived"  # No longer used


class ContentStrategy(str, enum.Enum):
    """Content generation strategies"""

    PROBLEM_AGITATION = "problem_agitation"  # Problem -> Agitate -> Solution
    BEFORE_AFTER = "before_after"  # Before/After scenarios
    SOCIAL_PROOF = "social_proof"  # Testimonials/case studies
    URGENCY_SCARCITY = "urgency_scarcity"  # Time-sensitive offers
    EDUCATIONAL_VALUE = "educational_value"  # Value-first approach
    DIRECT_OFFER = "direct_offer"  # Straightforward offer


# Core personalization models
class EmailTemplate(Base):
    """Email templates for different personalization strategies - Acceptance Criteria"""

    __tablename__ = "email_templates"

    id = Column(UUID(), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    content_type = Column(SQLEnum(EmailContentType), nullable=False, index=True)
    strategy = Column(SQLEnum(PersonalizationStrategy), nullable=False, index=True)

    # Template content
    subject_template = Column(Text, nullable=False)
    body_template = Column(Text, nullable=False)  # HTML template
    text_template = Column(Text)  # Plain text version

    # Personalization configuration
    required_tokens = Column(JsonColumn)  # List of required personalization tokens
    optional_tokens = Column(JsonColumn)  # List of optional tokens with defaults
    variable_config = Column(JsonColumn)  # Configuration for dynamic variables

    # Performance tracking
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float)  # Conversion rate
    avg_spam_score = Column(Float)

    # Metadata
    is_active = Column(Boolean, default=True, index=True)
    created_by = Column(String(100))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    content_variants = relationship("ContentVariant", back_populates="template")
    subject_variants = relationship("SubjectLineVariant", back_populates="template")
    generation_logs = relationship("EmailGenerationLog", back_populates="template")

    __table_args__ = (
        Index("idx_email_templates_type_strategy", "content_type", "strategy"),
        Index("idx_email_templates_active_success", "is_active", "success_rate"),
    )


class SubjectLineVariant(Base):
    """Subject line variants for A/B testing - Acceptance Criteria"""

    __tablename__ = "subject_line_variants"

    id = Column(UUID(), primary_key=True, default=generate_uuid)
    template_id = Column(UUID(), ForeignKey("email_templates.id"), nullable=False)

    # Variant details
    variant_name = Column(String(100), nullable=False)
    subject_text = Column(String(200), nullable=False)  # Personalized subject line
    personalization_tokens = Column(JsonColumn)  # Tokens used in this variant

    # Testing configuration
    status = Column(SQLEnum(VariantStatus), default=VariantStatus.DRAFT, index=True)
    weight = Column(Float, default=1.0)  # A/B test weight
    target_audience = Column(String(100))  # Specific audience segment

    # Performance metrics
    sent_count = Column(Integer, default=0)
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    conversion_count = Column(Integer, default=0)
    spam_reports = Column(Integer, default=0)

    # Calculated metrics
    open_rate = Column(Float)
    click_rate = Column(Float)
    conversion_rate = Column(Float)
    spam_rate = Column(Float)

    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    template = relationship("EmailTemplate", back_populates="subject_variants")

    __table_args__ = (
        Index("idx_subject_variants_template_status", "template_id", "status"),
        Index("idx_subject_variants_performance", "open_rate", "conversion_rate"),
        UniqueConstraint("template_id", "variant_name", name="uq_template_variant_name"),
    )


class PersonalizationToken(Base):
    """Personalization tokens for dynamic content insertion - Acceptance Criteria"""

    __tablename__ = "personalization_tokens"

    id = Column(UUID(), primary_key=True, default=generate_uuid)

    # Token definition
    token_name = Column(String(100), nullable=False, unique=True, index=True)
    token_type = Column(String(50), nullable=False)  # business_name, industry, location, etc.
    description = Column(Text)

    # Token configuration
    data_source = Column(String(100))  # Where to get the data (business, assessment, etc.)
    field_path = Column(String(200))  # JSONPath to the data field
    default_value = Column(String(500))  # Fallback value
    transformation_rules = Column(JsonColumn)  # Rules for formatting the value

    # Usage tracking
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float)  # Rate of successful personalization

    # Validation rules
    max_length = Column(Integer)
    min_length = Column(Integer)
    required_format = Column(String(200))  # Regex pattern

    # Metadata
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    variables = relationship("PersonalizationVariable", back_populates="token")

    __table_args__ = (
        Index("idx_personalization_tokens_type_active", "token_type", "is_active"),
        CheckConstraint("usage_count >= 0", name="check_positive_usage_count"),
    )


class PersonalizationVariable(Base):
    """Generated personalization variables for specific businesses/campaigns"""

    __tablename__ = "personalization_variables"

    id = Column(UUID(), primary_key=True, default=generate_uuid)
    token_id = Column(UUID(), ForeignKey("personalization_tokens.id"), nullable=False)

    # Context identification
    business_id = Column(String(100), index=True)  # Business this variable is for
    campaign_id = Column(String(100), index=True)  # Campaign context
    context_hash = Column(String(64), index=True)  # Hash of personalization context

    # Generated content
    generated_value = Column(Text, nullable=False)
    backup_value = Column(Text)  # Fallback if primary fails
    confidence_score = Column(Float)  # Confidence in the personalization

    # Source data
    source_data = Column(JsonColumn)  # Raw data used for generation
    generation_method = Column(String(100))  # How this was generated

    # Quality metrics
    character_count = Column(Integer)
    word_count = Column(Integer)
    sentiment_score = Column(Float)
    readability_score = Column(Float)

    # Usage tracking
    times_used = Column(Integer, default=0)
    last_used_at = Column(DateTime)

    # Metadata
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)  # When this personalization expires

    # Relationships
    token = relationship("PersonalizationToken", back_populates="variables")

    __table_args__ = (
        Index("idx_personalization_vars_business", "business_id", "token_id"),
        Index("idx_personalization_vars_campaign", "campaign_id", "created_at"),
        Index("idx_personalization_vars_context", "context_hash"),
        Index("idx_personalization_vars_quality", "confidence_score", "sentiment_score"),
    )


class EmailContent(Base):
    """Generated email content with personalization applied - Acceptance Criteria"""

    __tablename__ = "email_content"

    id = Column(UUID(), primary_key=True, default=generate_uuid)
    template_id = Column(UUID(), ForeignKey("email_templates.id"), nullable=False)

    # Content identification
    business_id = Column(String(100), nullable=False, index=True)
    campaign_id = Column(String(100), index=True)
    generation_id = Column(String(100), index=True)  # Links to generation log

    # Generated content
    subject_line = Column(String(200), nullable=False)
    html_content = Column(Text, nullable=False)
    text_content = Column(Text)
    preview_text = Column(String(150))  # Email preview text

    # Personalization details
    personalization_data = Column(JsonColumn)  # All personalization tokens used
    personalization_strategy = Column(SQLEnum(PersonalizationStrategy), index=True)
    content_strategy = Column(SQLEnum(ContentStrategy), index=True)

    # Quality metrics
    content_length = Column(Integer)
    word_count = Column(Integer)
    readability_score = Column(Float)
    sentiment_score = Column(Float)
    call_to_action_count = Column(Integer)

    # Performance tracking
    times_sent = Column(Integer, default=0)
    delivery_rate = Column(Float)
    open_rate = Column(Float)
    click_rate = Column(Float)
    conversion_rate = Column(Float)
    unsubscribe_rate = Column(Float)

    # Metadata
    is_approved = Column(Boolean, default=False, index=True)
    approved_by = Column(String(100))
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    template = relationship("EmailTemplate")
    spam_scores = relationship("SpamScoreTracking", back_populates="email_content")

    __table_args__ = (
        Index("idx_email_content_business_campaign", "business_id", "campaign_id"),
        Index("idx_email_content_performance", "open_rate", "conversion_rate"),
        Index("idx_email_content_approval", "is_approved", "created_at"),
    )


class ContentVariant(Base):
    """Content variants for A/B testing different email bodies"""

    __tablename__ = "content_variants"

    id = Column(UUID(), primary_key=True, default=generate_uuid)
    template_id = Column(UUID(), ForeignKey("email_templates.id"), nullable=False)

    # Variant configuration
    variant_name = Column(String(100), nullable=False)
    content_strategy = Column(SQLEnum(ContentStrategy), nullable=False)
    status = Column(SQLEnum(VariantStatus), default=VariantStatus.DRAFT, index=True)

    # Content elements
    opening_hook = Column(Text)
    main_content = Column(Text, nullable=False)
    call_to_action = Column(Text)
    closing_content = Column(Text)

    # Testing configuration
    weight = Column(Float, default=1.0)
    target_segment = Column(String(100))
    min_sample_size = Column(Integer, default=100)

    # Performance metrics
    sent_count = Column(Integer, default=0)
    engagement_score = Column(Float)
    conversion_rate = Column(Float)
    avg_time_spent = Column(Float)

    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    template = relationship("EmailTemplate", back_populates="content_variants")

    __table_args__ = (
        Index("idx_content_variants_template_status", "template_id", "status"),
        Index("idx_content_variants_performance", "conversion_rate", "engagement_score"),
        UniqueConstraint("template_id", "variant_name", name="uq_template_content_variant"),
    )


class SpamScoreTracking(Base):
    """Spam score tracking for email content optimization - Acceptance Criteria"""

    __tablename__ = "spam_score_tracking"

    id = Column(UUID(), primary_key=True, default=generate_uuid)
    email_content_id = Column(UUID(), ForeignKey("email_content.id"), nullable=False)

    # Spam scoring details
    overall_score = Column(Float, nullable=False)  # 0-100, lower is better
    category_scores = Column(JsonColumn)  # Scores by category
    spam_indicators = Column(JsonColumn)  # List of detected issues

    # Analysis breakdown
    subject_line_score = Column(Float)
    content_body_score = Column(Float)
    call_to_action_score = Column(Float)
    formatting_score = Column(Float)
    personalization_score = Column(Float)

    # Specific issues
    flagged_words = Column(JsonColumn)  # Words triggering spam filters
    excessive_caps = Column(Boolean, default=False)
    too_many_exclamations = Column(Boolean, default=False)
    suspicious_links = Column(Integer, default=0)
    image_text_ratio = Column(Float)

    # Analysis engine details
    analyzer_version = Column(String(50))
    analysis_method = Column(String(100))  # rule_based, ml_model, etc.
    confidence_score = Column(Float)

    # Recommendations
    improvement_suggestions = Column(JsonColumn)  # List of suggested improvements
    risk_level = Column(String(20))  # low, medium, high, critical

    # Tracking
    analyzed_at = Column(DateTime, default=func.now())
    reanalysis_needed = Column(Boolean, default=False)

    # Relationships
    email_content = relationship("EmailContent", back_populates="spam_scores")

    __table_args__ = (
        Index("idx_spam_scores_content_score", "email_content_id", "overall_score"),
        Index("idx_spam_scores_risk_level", "risk_level", "analyzed_at"),
        CheckConstraint("overall_score >= 0 AND overall_score <= 100", name="check_valid_spam_score"),
    )


class EmailGenerationLog(Base):
    """Log of email generation attempts for debugging and optimization"""

    __tablename__ = "email_generation_logs"

    id = Column(UUID(), primary_key=True, default=generate_uuid)
    template_id = Column(UUID(), ForeignKey("email_templates.id"), nullable=False)

    # Generation context
    business_id = Column(String(100), nullable=False, index=True)
    campaign_id = Column(String(100), index=True)
    generation_request_id = Column(String(100), unique=True, index=True)

    # Input data
    input_data = Column(JsonColumn)  # Raw data used for personalization
    personalization_strategy = Column(SQLEnum(PersonalizationStrategy))
    content_strategy = Column(SQLEnum(ContentStrategy))

    # Generation process
    tokens_requested = Column(JsonColumn)  # List of tokens requested
    tokens_resolved = Column(JsonColumn)  # Successfully resolved tokens
    tokens_failed = Column(JsonColumn)  # Failed token resolutions

    # LLM interaction (if used)
    llm_model_used = Column(String(100))
    llm_tokens_consumed = Column(Integer)
    llm_cost_usd = Column(DECIMAL(10, 4))
    llm_response_time_ms = Column(Integer)

    # Generation results
    generation_successful = Column(Boolean, nullable=False, index=True)
    email_content_id = Column(UUID(), ForeignKey("email_content.id"))
    error_details = Column(JsonColumn)  # Error information if failed

    # Quality metrics
    personalization_completeness = Column(Float)  # % of tokens successfully resolved
    content_quality_score = Column(Float)
    generation_time_ms = Column(Integer)

    # Metadata
    generated_at = Column(DateTime, default=func.now())
    generated_by = Column(String(100))  # User or system that triggered generation

    # Relationships
    template = relationship("EmailTemplate", back_populates="generation_logs")
    email_content = relationship("EmailContent")

    __table_args__ = (
        Index("idx_generation_logs_business_date", "business_id", "generated_at"),
        Index("idx_generation_logs_success_date", "generation_successful", "generated_at"),
        Index("idx_generation_logs_campaign", "campaign_id", "generated_at"),
    )


# Utility functions for personalization models
def calculate_personalization_score(resolved_tokens: int, total_tokens: int) -> float:
    """Calculate personalization completeness score"""
    if total_tokens == 0:
        return 1.0
    return min(resolved_tokens / total_tokens, 1.0)


def determine_risk_level(spam_score: float) -> str:
    """Determine risk level based on spam score"""
    if spam_score < 25:
        return "low"
    elif spam_score < 50:
        return "medium"
    elif spam_score < 75:
        return "high"
    else:
        return "critical"


def generate_content_hash(subject: str, body: str) -> str:
    """Generate hash for content deduplication"""
    import hashlib

    content = f"{subject}|{body}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# Constants for personalization system
MAX_SUBJECT_LINE_LENGTH = 200
MAX_PREVIEW_TEXT_LENGTH = 150
DEFAULT_VARIANT_WEIGHT = 1.0
MIN_SAMPLE_SIZE_AB_TEST = 100
SPAM_SCORE_THRESHOLD_WARNING = 50
SPAM_SCORE_THRESHOLD_CRITICAL = 75
