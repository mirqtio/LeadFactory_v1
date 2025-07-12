"""
Database models for Lead Explorer

Defines Lead and AuditLogLead models with proper indexing,
constraints, and audit trail capabilities.
"""
import enum
import hashlib
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import validates
from sqlalchemy.sql import func

from database.base import Base
from database.models import generate_uuid


class EnrichmentStatus(str, enum.Enum):
    """Status of lead enrichment process"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"


class AuditAction(str, enum.Enum):
    """Types of audit actions"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class Lead(Base):
    """
    Lead model for managing prospect data with enrichment tracking.
    
    Supports manual entry via Lead Explorer and automatic enrichment
    through the pipeline.
    """
    __tablename__ = "leads"
    
    # Primary identification
    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Core lead data
    email = Column(String(255), nullable=True, index=True)
    domain = Column(String(255), nullable=True, index=True)
    company_name = Column(String(500), nullable=True)
    contact_name = Column(String(255), nullable=True)
    
    # Enrichment tracking
    enrichment_status = Column(
        SQLEnum(EnrichmentStatus),
        nullable=False,
        default=EnrichmentStatus.PENDING,
        index=True
    )
    enrichment_task_id = Column(String(255), nullable=True, index=True)
    enrichment_error = Column(Text, nullable=True)
    
    # Metadata
    is_manual = Column(Boolean, nullable=False, default=False, index=True)
    source = Column(String(100), nullable=True)  # "manual", "csv_upload", etc.
    
    # Soft delete
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)
    
    # User tracking
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    deleted_by = Column(String(255), nullable=True)
    
    # Additional indexes for performance
    __table_args__ = (
        Index('ix_leads_email_domain', 'email', 'domain'),
        Index('ix_leads_enrichment_lookup', 'enrichment_status', 'enrichment_task_id'),
        Index('ix_leads_active_manual', 'is_deleted', 'is_manual'),
        Index('ix_leads_created_status', 'created_at', 'enrichment_status'),
        UniqueConstraint('email', name='uq_leads_email'),
        UniqueConstraint('domain', name='uq_leads_domain'),
    )
    
    @validates('email')
    def validate_email(self, key: str, email: Optional[str]) -> Optional[str]:
        """Validate email format"""
        if email:
            email = email.lower().strip()
            # Basic email validation - more comprehensive validation in schemas
            if '@' not in email or len(email) > 255:
                raise ValueError("Invalid email format")
        return email
    
    @validates('domain')
    def validate_domain(self, key: str, domain: Optional[str]) -> Optional[str]:
        """Validate domain format"""
        if domain:
            domain = domain.lower().strip()
            # Basic domain validation - more comprehensive validation in schemas
            if '.' not in domain or len(domain) > 255:
                raise ValueError("Invalid domain format")
        return domain
    
    def __repr__(self) -> str:
        return f"<Lead(id={self.id}, email={self.email}, domain={self.domain})>"


class AuditLogLead(Base):
    """
    Immutable audit log for all Lead mutations.
    
    Captures complete change history with user context and tamper detection.
    """
    __tablename__ = "audit_log_leads"
    
    # Primary key
    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Reference to the lead
    lead_id = Column(String, nullable=False, index=True)
    
    # Audit metadata
    action = Column(SQLEnum(AuditAction), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)
    
    # User context
    user_id = Column(String(255), nullable=True)
    user_ip = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)
    
    # Change data
    old_values = Column(Text, nullable=True)  # JSON string of old values
    new_values = Column(Text, nullable=True)  # JSON string of new values
    
    # Tamper detection
    checksum = Column(String(64), nullable=False)  # SHA-256 hash
    
    # Performance indexes
    __table_args__ = (
        Index('ix_audit_leads_lead_id_timestamp', 'lead_id', 'timestamp'),
        Index('ix_audit_leads_action_timestamp', 'action', 'timestamp'),
        Index('ix_audit_leads_user_timestamp', 'user_id', 'timestamp'),
    )
    
    def calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum for tamper detection"""
        data = {
            'lead_id': self.lead_id,
            'action': self.action.value if self.action else None,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user_id': self.user_id,
            'old_values': self.old_values,
            'new_values': self.new_values,
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def verify_checksum(self) -> bool:
        """Verify audit log integrity"""
        return self.checksum == self.calculate_checksum()
    
    def __repr__(self) -> str:
        return f"<AuditLogLead(id={self.id}, lead_id={self.lead_id}, action={self.action})>"