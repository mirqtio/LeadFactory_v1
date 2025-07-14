"""
Lineage tracking models for report generation
"""

import uuid
from typing import Optional

from sqlalchemy import (
    DECIMAL,
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


def generate_uuid():
    """Generate a new UUID"""
    return str(uuid.uuid4())


class ReportLineage(Base):
    """
    Report lineage tracking model
    Tracks the complete lineage of report generation including:
    - Lead ID
    - Pipeline run ID
    - Template version
    - Pipeline logs
    - Raw inputs (compressed)
    """

    __tablename__ = "report_lineage"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)
    report_generation_id = Column(
        String,
        ForeignKey("d6_report_generations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    lead_id = Column(String, nullable=False)
    pipeline_run_id = Column(String, nullable=False)
    template_version_id = Column(String, nullable=False)

    # Lineage data
    pipeline_start_time = Column(DateTime, nullable=False)
    pipeline_end_time = Column(DateTime, nullable=False)
    pipeline_logs = Column(JSON, nullable=True)
    raw_inputs_compressed = Column(LargeBinary, nullable=True)
    raw_inputs_size_bytes = Column(Integer, nullable=True)
    compression_ratio = Column(DECIMAL(5, 2), nullable=True)

    # Audit fields
    created_at = Column(DateTime, nullable=False, default=func.now())
    last_accessed_at = Column(DateTime, nullable=True)
    access_count = Column(Integer, nullable=False, default=0)

    # Relationships
    report_generation = relationship(
        "ReportGeneration",
        backref="lineage",
        uselist=False,
    )
    audit_logs = relationship(
        "ReportLineageAudit",
        back_populates="lineage",
        cascade="all, delete-orphan",
    )

    # Indexes and constraints
    __table_args__ = (
        Index("idx_lineage_report_id", "report_generation_id"),
        Index("idx_lineage_lead_id", "lead_id"),
        Index("idx_lineage_pipeline_run", "pipeline_run_id"),
        Index("idx_lineage_created_at", "created_at"),
        CheckConstraint("raw_inputs_size_bytes >= 0", name="check_raw_inputs_size_non_negative"),
        CheckConstraint(
            "compression_ratio >= 0 AND compression_ratio <= 100",
            name="check_compression_ratio_range",
        ),
        CheckConstraint("access_count >= 0", name="check_access_count_non_negative"),
    )

    def __repr__(self):
        return (
            f"<ReportLineage(id='{self.id}', lead_id='{self.lead_id}', " f"pipeline_run_id='{self.pipeline_run_id}')>"
        )

    @property
    def pipeline_duration_seconds(self) -> float:
        """Calculate pipeline duration in seconds"""
        if self.pipeline_start_time and self.pipeline_end_time:
            return (self.pipeline_end_time - self.pipeline_start_time).total_seconds()
        return 0.0

    def record_access(self, user_id: Optional[str] = None, ip_address: Optional[str] = None):
        """Update access tracking fields"""
        self.last_accessed_at = func.now()
        self.access_count += 1


class ReportLineageAudit(Base):
    """
    Audit log for lineage access
    Tracks who accessed lineage data and when
    """

    __tablename__ = "report_lineage_audit"

    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)
    lineage_id = Column(
        String,
        ForeignKey("report_lineage.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Audit data
    action = Column(String(50), nullable=False)  # view, download, etc.
    user_id = Column(String, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    accessed_at = Column(DateTime, nullable=False, default=func.now())

    # Relationships
    lineage = relationship("ReportLineage", back_populates="audit_logs")

    # Indexes
    __table_args__ = (
        Index("idx_lineage_audit_lineage_id", "lineage_id"),
        Index("idx_lineage_audit_user_id", "user_id"),
        Index("idx_lineage_audit_accessed_at", "accessed_at"),
    )

    def __repr__(self):
        return (
            f"<ReportLineageAudit(id='{self.id}', action='{self.action}', "
            f"user_id='{self.user_id}', accessed_at='{self.accessed_at}')>"
        )
