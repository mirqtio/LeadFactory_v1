"""
D6 Reports Models - Task 050

Report generation tracking models for audit report creation and delivery.
Supports template-based report generation with mobile and print optimization.

Acceptance Criteria:
- Report generation tracked ✓
- Template structure defined ✓
- Mobile-responsive HTML ✓
- Print-optimized CSS ✓
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    DECIMAL,
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base

# Import lineage models to ensure they're registered
from d6_reports.lineage.models import ReportLineage, ReportLineageAudit  # noqa: F401


def generate_uuid():
    """Generate a new UUID"""
    return str(uuid.uuid4())


class ReportStatus(Enum):
    """Report generation status enumeration"""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    DELIVERED = "delivered"
    ARCHIVED = "archived"


class ReportType(Enum):
    """Report type enumeration"""

    BUSINESS_AUDIT = "business_audit"
    WEBSITE_ANALYSIS = "website_analysis"
    COMPETITIVE_INSIGHTS = "competitive_insights"
    GROWTH_RECOMMENDATIONS = "growth_recommendations"
    CUSTOM = "custom"


class TemplateFormat(Enum):
    """Template format enumeration"""

    HTML = "html"
    PDF = "pdf"
    EMAIL = "email"
    PRINT = "print"


class DeliveryMethod(Enum):
    """Report delivery method enumeration"""

    EMAIL = "email"
    DOWNLOAD = "download"
    API = "api"
    WEBHOOK = "webhook"


class ReportGeneration(Base):
    """
    Report generation tracking model

    Acceptance Criteria: Report generation tracked
    """

    __tablename__ = "d6_report_generations"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(
        String, nullable=False
    )  # Reference to business (FK removed for now)
    user_id = Column(String, nullable=True)  # Customer who requested report
    order_id = Column(String, nullable=True)  # Associated purchase order

    # Report metadata
    report_type = Column(
        SQLEnum(ReportType), nullable=False, default=ReportType.BUSINESS_AUDIT
    )
    status = Column(SQLEnum(ReportStatus), nullable=False, default=ReportStatus.PENDING)
    template_id = Column(String, ForeignKey("d6_report_templates.id"), nullable=False)

    # Generation tracking
    requested_at = Column(DateTime, nullable=False, default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)

    # Report content and configuration
    report_data = Column(JSON, nullable=True)  # Source data used for report
    configuration = Column(JSON, nullable=True)  # Report generation settings
    sections_included = Column(JSON, nullable=True)  # List of included section IDs
    customizations = Column(JSON, nullable=True)  # Customer-specific customizations

    # Output information
    output_format = Column(String, nullable=False, default="pdf")
    file_path = Column(String, nullable=True)  # Path to generated report file
    file_size_bytes = Column(Integer, nullable=True)
    page_count = Column(Integer, nullable=True)

    # Quality and performance metrics
    generation_time_seconds = Column(Float, nullable=True)
    data_freshness_hours = Column(Float, nullable=True)  # How fresh was the data used
    quality_score = Column(DECIMAL(5, 2), nullable=True)  # Report completeness score

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)

    # Audit fields
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    created_by = Column(String, nullable=True)

    # Relationships
    template = relationship("ReportTemplate", back_populates="generations")
    deliveries = relationship("ReportDelivery", back_populates="report_generation")

    # Indexes
    __table_args__ = (
        Index("idx_report_gen_business_id", "business_id"),
        Index("idx_report_gen_status", "status"),
        Index("idx_report_gen_type", "report_type"),
        Index("idx_report_gen_requested_at", "requested_at"),
        Index("idx_report_gen_user_order", "user_id", "order_id"),
        CheckConstraint("retry_count >= 0", name="check_retry_count_non_negative"),
        CheckConstraint(
            "generation_time_seconds >= 0", name="check_generation_time_positive"
        ),
        CheckConstraint(
            "quality_score >= 0 AND quality_score <= 100",
            name="check_quality_score_range",
        ),
    )

    def __repr__(self):
        return (
            f"<ReportGeneration(id='{self.id}', business_id='{self.business_id}', "
            f"status='{self.status.value}')>"
        )

    @property
    def is_completed(self) -> bool:
        """Check if report generation is completed"""
        return self.status == ReportStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if report generation failed"""
        return self.status == ReportStatus.FAILED

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate generation duration if completed"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class ReportTemplate(Base):
    """
    Report template model for defining report structure and formatting

    Acceptance Criteria: Template structure defined, Mobile-responsive HTML, Print-optimized CSS
    """

    __tablename__ = "d6_report_templates"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Template metadata
    template_type = Column(SQLEnum(ReportType), nullable=False)
    format = Column(
        SQLEnum(TemplateFormat), nullable=False, default=TemplateFormat.HTML
    )
    version = Column(String, nullable=False, default="1.0.0")

    # Template content
    html_template = Column(Text, nullable=True)  # HTML template content
    css_styles = Column(Text, nullable=True)  # CSS styling
    mobile_css = Column(Text, nullable=True)  # Mobile-specific CSS
    print_css = Column(Text, nullable=True)  # Print-optimized CSS

    # Template configuration
    default_sections = Column(JSON, nullable=True)  # Default sections to include
    required_data_fields = Column(JSON, nullable=True)  # Required data fields
    optional_data_fields = Column(JSON, nullable=True)  # Optional data fields
    customization_options = Column(JSON, nullable=True)  # Available customizations

    # Template settings
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    supports_mobile = Column(Boolean, nullable=False, default=True)  # Mobile-responsive
    supports_print = Column(Boolean, nullable=False, default=True)  # Print-optimized

    # Performance settings
    max_pages = Column(Integer, nullable=True)
    estimated_generation_time = Column(Float, nullable=True)  # Seconds

    # Audit fields
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    created_by = Column(String, nullable=True)

    # Relationships
    generations = relationship("ReportGeneration", back_populates="template")
    sections = relationship("ReportSection", back_populates="template")

    # Indexes
    __table_args__ = (
        Index("idx_template_type", "template_type"),
        Index("idx_template_active", "is_active"),
        Index("idx_template_default", "is_default"),
        UniqueConstraint("name", "version", name="uq_template_name_version"),
    )

    def __repr__(self):
        return (
            f"<ReportTemplate(id='{self.id}', name='{self.name}', "
            f"type='{self.template_type.value}')>"
        )

    @property
    def is_mobile_responsive(self) -> bool:
        """Check if template supports mobile devices"""
        return self.supports_mobile and self.mobile_css is not None

    @property
    def is_print_optimized(self) -> bool:
        """Check if template is optimized for printing"""
        return self.supports_print and self.print_css is not None


class ReportSection(Base):
    """
    Report section model for defining individual sections within reports

    Acceptance Criteria: Template structure defined
    """

    __tablename__ = "d6_report_sections"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)
    template_id = Column(String, ForeignKey("d6_report_templates.id"), nullable=False)

    # Section metadata
    name = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    section_order = Column(Integer, nullable=False)

    # Section content
    html_content = Column(Text, nullable=True)  # Section HTML template
    css_styles = Column(Text, nullable=True)  # Section-specific CSS
    data_query = Column(Text, nullable=True)  # Data extraction query/logic

    # Section configuration
    is_required = Column(Boolean, nullable=False, default=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    data_requirements = Column(JSON, nullable=True)  # Required data fields
    conditional_logic = Column(JSON, nullable=True)  # When to include section

    # Rendering settings
    page_break_before = Column(Boolean, nullable=False, default=False)
    page_break_after = Column(Boolean, nullable=False, default=False)
    max_content_length = Column(Integer, nullable=True)

    # Audit fields
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    template = relationship("ReportTemplate", back_populates="sections")

    # Indexes
    __table_args__ = (
        Index("idx_section_template_id", "template_id"),
        Index("idx_section_order", "template_id", "section_order"),
        Index("idx_section_enabled", "is_enabled"),
        UniqueConstraint("template_id", "name", name="uq_section_template_name"),
    )

    def __repr__(self):
        return f"<ReportSection(id='{self.id}', name='{self.name}', order={self.section_order})>"


class ReportDelivery(Base):
    """
    Report delivery tracking model for managing report distribution

    Acceptance Criteria: Report generation tracked
    """

    __tablename__ = "d6_report_deliveries"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)
    report_generation_id = Column(
        String, ForeignKey("d6_report_generations.id"), nullable=False
    )

    # Delivery metadata
    delivery_method = Column(SQLEnum(DeliveryMethod), nullable=False)
    recipient_email = Column(String, nullable=True)
    recipient_name = Column(String, nullable=True)

    # Delivery tracking
    scheduled_at = Column(DateTime, nullable=True)
    attempted_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)

    # Delivery details
    delivery_status = Column(String, nullable=False, default="pending")
    download_url = Column(String, nullable=True)
    download_expires_at = Column(DateTime, nullable=True)
    download_count = Column(Integer, nullable=False, default=0)

    # Tracking and analytics
    opened_at = Column(DateTime, nullable=True)
    open_count = Column(Integer, nullable=False, default=0)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)

    # Audit fields
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    report_generation = relationship("ReportGeneration", back_populates="deliveries")

    # Indexes
    __table_args__ = (
        Index("idx_delivery_report_id", "report_generation_id"),
        Index("idx_delivery_method", "delivery_method"),
        Index("idx_delivery_status", "delivery_status"),
        Index("idx_delivery_scheduled", "scheduled_at"),
        Index("idx_delivery_recipient", "recipient_email"),
        CheckConstraint("retry_count >= 0", name="check_delivery_retry_non_negative"),
        CheckConstraint(
            "download_count >= 0", name="check_download_count_non_negative"
        ),
        CheckConstraint("open_count >= 0", name="check_open_count_non_negative"),
    )

    def __repr__(self):
        return (
            f"<ReportDelivery(id='{self.id}', method='{self.delivery_method.value}', "
            f"status='{self.delivery_status}')>"
        )

    @property
    def is_delivered(self) -> bool:
        """Check if report was successfully delivered"""
        return self.delivery_status == "delivered" and self.delivered_at is not None

    @property
    def is_expired(self) -> bool:
        """Check if download link has expired"""
        if self.download_expires_at:
            return datetime.utcnow() > self.download_expires_at
        return False
