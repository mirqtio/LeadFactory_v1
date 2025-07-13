"""
Database models for Batch Report Runner

Tracks batch processing state, progress, and individual lead results
with proper indexing for performance.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Integer, DECIMAL, TIMESTAMP, Boolean, Text, JSON, ForeignKey
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


def generate_uuid():
    """Generate a new UUID"""
    return str(uuid.uuid4())


class BatchStatus(str, enum.Enum):
    """Status of batch processing"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LeadProcessingStatus(str, enum.Enum):
    """Status of individual lead processing"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BatchReport(Base):
    """Batch report processing tracking table"""
    __tablename__ = "batch_reports"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)

    # Batch configuration
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    template_version = Column(String(50), nullable=False, default="v1")

    # Processing state
    status = Column(SQLEnum(BatchStatus), nullable=False, default=BatchStatus.PENDING, index=True)
    total_leads = Column(Integer, nullable=False, default=0)
    processed_leads = Column(Integer, nullable=False, default=0)
    successful_leads = Column(Integer, nullable=False, default=0)
    failed_leads = Column(Integer, nullable=False, default=0)

    # Cost tracking
    estimated_cost_usd = Column(DECIMAL(10, 4), nullable=True)
    actual_cost_usd = Column(DECIMAL(10, 4), nullable=True)
    cost_approved = Column(Boolean, nullable=False, default=False)

    # Progress tracking
    progress_percentage = Column(DECIMAL(5, 2), nullable=False, default=0.0)
    current_lead_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timing
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), index=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    # User tracking
    created_by = Column(String(255), nullable=True)

    # Processing configuration
    max_concurrent = Column(Integer, nullable=False, default=5)
    retry_failed = Column(Boolean, nullable=False, default=True)
    retry_count = Column(Integer, nullable=False, default=3)

    # Results metadata
    results_summary = Column(JSON, nullable=True)
    websocket_url = Column(String(500), nullable=True)

    # Relationships
    lead_results = relationship("BatchReportLead", back_populates="batch", cascade="all, delete-orphan")

    # Additional indexes for performance
    __table_args__ = (
        Index('ix_batch_reports_status_created', 'status', 'created_at'),
        Index('ix_batch_reports_created_by_status', 'created_by', 'status'),
        Index('ix_batch_reports_template_status', 'template_version', 'status'),
    )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate processing duration in seconds"""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.processed_leads == 0:
            return 0.0
        return (self.successful_leads / self.processed_leads) * 100

    def update_progress(self, processed: int, successful: int, failed: int, current_lead_id: Optional[str] = None):
        """Update batch progress counters"""
        self.processed_leads = processed
        self.successful_leads = successful
        self.failed_leads = failed
        self.current_lead_id = current_lead_id

        if self.total_leads > 0:
            self.progress_percentage = (processed / self.total_leads) * 100

        self.updated_at = datetime.utcnow()


class BatchReportLead(Base):
    """Individual lead processing results within a batch"""
    __tablename__ = "batch_report_leads"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)
    batch_id = Column(String, ForeignKey("batch_reports.id"), nullable=False, index=True)
    lead_id = Column(String, nullable=False, index=True)  # Reference to leads table

    # Processing state
    status = Column(SQLEnum(LeadProcessingStatus), nullable=False, default=LeadProcessingStatus.PENDING, index=True)
    order_index = Column(Integer, nullable=False)  # Processing order within batch

    # Processing results
    report_generated = Column(Boolean, nullable=False, default=False)
    report_url = Column(String(1000), nullable=True)
    report_size_bytes = Column(Integer, nullable=True)
    processing_duration_ms = Column(Integer, nullable=True)

    # Cost tracking
    estimated_cost_usd = Column(DECIMAL(10, 4), nullable=True)
    actual_cost_usd = Column(DECIMAL(10, 4), nullable=True)
    cost_breakdown = Column(JSON, nullable=True)  # Per-provider costs

    # Error handling
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)

    # Timing
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)

    # Processing metadata
    provider_results = Column(JSON, nullable=True)  # Results from each provider
    quality_score = Column(DECIMAL(3, 2), nullable=True)  # Report quality score

    # Relationships
    batch = relationship("BatchReport", back_populates="lead_results")

    # Additional indexes for performance
    __table_args__ = (
        Index('ix_batch_report_leads_batch_status', 'batch_id', 'status'),
        Index('ix_batch_report_leads_batch_order', 'batch_id', 'order_index'),
        Index('ix_batch_report_leads_lead_batch', 'lead_id', 'batch_id'),
        Index('ix_batch_report_leads_status_created', 'status', 'created_at'),
    )

    @property
    def processing_duration_seconds(self) -> Optional[float]:
        """Calculate processing duration in seconds"""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()

    @property
    def is_retryable(self) -> bool:
        """Check if lead can be retried"""
        return (
            self.status == LeadProcessingStatus.FAILED and
            self.retry_count < self.max_retries
        )

    def mark_started(self):
        """Mark lead processing as started"""
        self.status = LeadProcessingStatus.PROCESSING
        self.started_at = datetime.utcnow()

    def mark_completed(self, report_url: Optional[str] = None, actual_cost: Optional[float] = None,
                      quality_score: Optional[float] = None):
        """Mark lead processing as completed successfully"""
        self.status = LeadProcessingStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.report_generated = True

        if report_url:
            self.report_url = report_url
        if actual_cost is not None:
            self.actual_cost_usd = actual_cost
        if quality_score is not None:
            self.quality_score = quality_score

        if self.started_at:
            duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000
            self.processing_duration_ms = int(duration_ms)

    def mark_failed(self, error_message: str, error_code: Optional[str] = None):
        """Mark lead processing as failed"""
        self.status = LeadProcessingStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        self.error_code = error_code

        if self.started_at:
            duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000
            self.processing_duration_ms = int(duration_ms)

    def increment_retry(self):
        """Increment retry count and reset for next attempt"""
        self.retry_count += 1
        self.status = LeadProcessingStatus.PENDING
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        self.error_code = None
