"""
Governance models for RBAC and audit logging (P0-026)

Provides role-based access control and immutable audit trail
"""
import enum
import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, String, DateTime, Enum, Text, Index, Boolean, 
    UniqueConstraint, CheckConstraint, Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from database.base import Base


class UserRole(str, enum.Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    VIEWER = "viewer"


class User(Base):
    """User model with role-based access control"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.VIEWER)
    api_key_hash = Column(String(255), nullable=True)  # For API access
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Audit fields
    created_by = Column(UUID(as_uuid=True), nullable=True)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    deactivated_by = Column(UUID(as_uuid=True), nullable=True)
    
    __table_args__ = (
        Index('idx_users_email_active', 'email', 'is_active'),
        CheckConstraint('email ~* \'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}$\'', name='valid_email'),
    )


class AuditLog(Base):
    """Immutable audit log for all mutations"""
    __tablename__ = "audit_log_global"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_email = Column(String(255), nullable=False)  # Denormalized for historical accuracy
    user_role = Column(Enum(UserRole), nullable=False)  # Role at time of action
    
    # Action details
    action = Column(String(50), nullable=False)  # CREATE, UPDATE, DELETE, etc.
    method = Column(String(10), nullable=False)  # POST, PUT, DELETE, etc.
    endpoint = Column(String(255), nullable=False)  # API endpoint
    object_type = Column(String(100), nullable=False)  # Model/resource type
    object_id = Column(String(255), nullable=True)  # ID of affected object
    
    # Request/response data
    request_data = Column(Text, nullable=True)  # JSON of request body (PII masked)
    response_status = Column(Integer, nullable=False)  # HTTP status code
    response_data = Column(Text, nullable=True)  # JSON of response (PII masked)
    
    # Audit trail integrity
    content_hash = Column(String(64), nullable=False)  # SHA256 of all fields
    checksum = Column(String(64), nullable=False)  # SHA256 including previous entry
    
    # Performance tracking
    duration_ms = Column(Integer, nullable=True)  # Request duration in milliseconds
    
    # Additional context
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)
    details = Column(Text, nullable=True)  # Additional JSON context
    
    __table_args__ = (
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_object', 'object_type', 'object_id'),
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_action', 'action', 'timestamp'),
        # Prevent any updates to audit logs
        CheckConstraint('false', name='no_update_allowed'),
    )
    
    def calculate_content_hash(self) -> str:
        """Calculate SHA256 hash of audit entry content"""
        content = {
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user_id': str(self.user_id),
            'user_email': self.user_email,
            'user_role': self.user_role.value if self.user_role else None,
            'action': self.action,
            'method': self.method,
            'endpoint': self.endpoint,
            'object_type': self.object_type,
            'object_id': self.object_id,
            'request_data': self.request_data,
            'response_status': self.response_status,
            'response_data': self.response_data,
            'duration_ms': self.duration_ms,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'details': self.details
        }
        content_str = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def calculate_checksum(self, previous_checksum: Optional[str] = None) -> str:
        """Calculate chained checksum including previous entry"""
        if previous_checksum:
            combined = f"{previous_checksum}:{self.content_hash}"
        else:
            combined = f"GENESIS:{self.content_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()


class RoleChangeLog(Base):
    """Track all role changes for compliance"""
    __tablename__ = "role_change_log"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    changed_by_id = Column(UUID(as_uuid=True), nullable=False)
    old_role = Column(Enum(UserRole), nullable=False)
    new_role = Column(Enum(UserRole), nullable=False)
    reason = Column(Text, nullable=False)
    
    __table_args__ = (
        Index('idx_role_change_user', 'user_id', 'timestamp'),
        # Prevent any updates
        CheckConstraint('false', name='no_update_allowed'),
    )