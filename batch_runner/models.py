"""
Database models for Batch Report Runner

Tracks batch processing state, progress, and individual lead results
with proper indexing for performance.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DECIMAL, JSON, TIMESTAMP, Boolean, Column
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text
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
        Index("ix_batch_reports_status_created", "status", "created_at"),
        Index("ix_batch_reports_created_by_status", "created_by", "status"),
        Index("ix_batch_reports_template_status", "template_version", "status"),
    )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate processing duration in seconds"""
        if not self.started_at or not self.completed_at:
            return None
        return (self.completed_at - self.started_at).total_seconds()

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

    def to_dict(self) -> dict:
        """Convert batch report to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, BatchStatus) else self.status,
            "total_leads": self.total_leads,
            "processed_leads": self.processed_leads,
            "successful_leads": self.successful_leads,
            "failed_leads": self.failed_leads,
            "progress_percentage": float(self.progress_percentage) if self.progress_percentage else 0.0,
            "estimated_cost_usd": float(self.estimated_cost_usd) if self.estimated_cost_usd else None,
            "actual_cost_usd": float(self.actual_cost_usd) if self.actual_cost_usd else None,
            "template_version": self.template_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_by": self.created_by,
            "retry_count": self.retry_count,
        }

    @property
    def results_summary(self) -> dict:
        """Get results summary"""
        return {
            "successful": self.successful_leads,
            "failed": self.failed_leads,
            "total_cost": float(self.actual_cost_usd) if self.actual_cost_usd else 0.0,
            "success_rate": self.success_rate / 100 if self.processed_leads > 0 else 0.0,
        }

    def is_terminal_status(self) -> bool:
        """Check if batch is in terminal status"""
        return self.status in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED]


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
        Index("ix_batch_report_leads_batch_status", "batch_id", "status"),
        Index("ix_batch_report_leads_batch_order", "batch_id", "order_index"),
        Index("ix_batch_report_leads_lead_batch", "lead_id", "batch_id"),
        Index("ix_batch_report_leads_status_created", "status", "created_at"),
    )

    @property
    def processing_duration_seconds(self) -> Optional[float]:
        """Calculate processing duration in seconds"""
        if not self.started_at or not self.completed_at:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def is_retryable(self, max_retries: Optional[int] = None) -> bool:
        """Check if lead can be retried"""
        if max_retries is None:
            max_retries = self.max_retries
        return self.status == LeadProcessingStatus.FAILED and self.retry_count < max_retries

    def mark_processing(self):
        """Mark lead processing as started"""
        self.status = LeadProcessingStatus.PROCESSING
        self.started_at = datetime.utcnow()

    def mark_completed(
        self,
        report_url: Optional[str] = None,
        actual_cost: Optional[float] = None,
        quality_score: Optional[float] = None,
        processing_time_ms: Optional[int] = None,
    ):
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
        if processing_time_ms is not None:
            self.processing_duration_ms = processing_time_ms

        if self.started_at and processing_time_ms is None:
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

    def to_dict(self) -> dict:
        """Convert batch report lead to dictionary"""
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "lead_id": self.lead_id,
            "status": self.status.value if isinstance(self.status, LeadProcessingStatus) else self.status,
            "order_index": self.order_index,
            "report_generated": self.report_generated,
            "report_url": self.report_url,
            "processing_duration_ms": self.processing_duration_ms,
            "actual_cost_usd": float(self.actual_cost_usd) if self.actual_cost_usd else None,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "quality_score": float(self.quality_score) if self.quality_score else None,
        }

    def is_terminal_status(self) -> bool:
        """Check if lead is in terminal status"""
        return self.status in [LeadProcessingStatus.COMPLETED, LeadProcessingStatus.FAILED]

    def reset_for_retry(self):
        """Reset lead for retry attempt"""
        self.status = LeadProcessingStatus.PENDING
        self.error_message = None
        self.error_code = None
        self.completed_at = None
