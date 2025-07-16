"""
Account Management Database Models
Comprehensive user, organization, team, and RBAC models for P2-000
"""
import enum
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


def generate_uuid():
    """Generate a new UUID"""
    return str(uuid.uuid4())


def generate_api_key():
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)


# Enums
class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class TeamRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class PermissionAction(str, enum.Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"


class ResourceType(str, enum.Enum):
    LEAD = "lead"
    REPORT = "report"
    CAMPAIGN = "campaign"
    ASSESSMENT = "assessment"
    EMAIL = "email"
    PURCHASE = "purchase"
    ANALYTICS = "analytics"
    SETTINGS = "settings"
    USER = "user"
    TEAM = "team"
    ORGANIZATION = "organization"
    API_KEY = "api_key"
    BILLING = "billing"


class AuthProvider(str, enum.Enum):
    LOCAL = "local"
    GOOGLE = "google"
    GITHUB = "github"
    SAML = "saml"


# Association tables
team_users = Table(
    "team_users",
    Base.metadata,
    Column("team_id", String, ForeignKey("teams.id", ondelete="CASCADE")),
    Column("user_id", String, ForeignKey("account_users.id", ondelete="CASCADE")),
    Column("role", SQLEnum(TeamRole), nullable=False, default=TeamRole.MEMBER),
    Column("joined_at", TIMESTAMP, server_default=func.now()),
    UniqueConstraint("team_id", "user_id", name="uq_team_users"),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String, ForeignKey("roles.id", ondelete="CASCADE")),
    Column("permission_id", String, ForeignKey("permissions.id", ondelete="CASCADE")),
    UniqueConstraint("role_id", "permission_id", name="uq_role_permissions"),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String, ForeignKey("account_users.id", ondelete="CASCADE")),
    Column("role_id", String, ForeignKey("roles.id", ondelete="CASCADE")),
    Column("organization_id", String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
    Column("team_id", String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True),
    UniqueConstraint("user_id", "role_id", "organization_id", "team_id", name="uq_user_roles"),
)


# Core Models
class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    
    # Billing info
    stripe_customer_id = Column(String(255), nullable=True, unique=True)
    billing_email = Column(String(255), nullable=True)
    
    # Settings
    settings = Column(JSON, nullable=False, default=dict)
    
    # Limits
    max_users = Column(Integer, nullable=False, default=5)
    max_teams = Column(Integer, nullable=False, default=3)
    max_api_keys = Column(Integer, nullable=False, default=10)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    trial_ends_at = Column(Date, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    users = relationship("AccountUser", back_populates="organization", cascade="all, delete-orphan")
    teams = relationship("Team", back_populates="organization", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="organization", cascade="all, delete-orphan")
    audit_logs = relationship("AccountAuditLog", back_populates="organization", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_organizations_stripe_customer", "stripe_customer_id"),
        Index("ix_organizations_active", "is_active"),
    )


class AccountUser(Base):
    __tablename__ = "account_users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String(255), nullable=False, unique=True, index=True)
    username = Column(String(100), nullable=True, unique=True, index=True)
    
    # Authentication
    password_hash = Column(String(255), nullable=True)  # Nullable for OAuth users
    auth_provider = Column(SQLEnum(AuthProvider), nullable=False, default=AuthProvider.LOCAL)
    auth_provider_id = Column(String(255), nullable=True)
    
    # Profile
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    phone = Column(String(20), nullable=True)
    timezone = Column(String(50), nullable=False, default="UTC")
    locale = Column(String(10), nullable=False, default="en_US")
    
    # Organization
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    
    # Status
    status = Column(SQLEnum(UserStatus), nullable=False, default=UserStatus.ACTIVE, index=True)
    email_verified = Column(Boolean, nullable=False, default=False)
    email_verified_at = Column(TIMESTAMP, nullable=True)
    
    # Security
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    mfa_secret = Column(String(255), nullable=True)
    last_login_at = Column(TIMESTAMP, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(TIMESTAMP, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(TIMESTAMP, nullable=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="users")
    teams = relationship("Team", secondary=team_users, back_populates="users")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AccountAuditLog", back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_users_organization_status", "organization_id", "status"),
        Index("ix_users_auth_provider", "auth_provider", "auth_provider_id"),
    )


class Team(Base):
    __tablename__ = "teams"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Organization
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    # Settings
    settings = Column(JSON, nullable=False, default=dict)
    is_default = Column(Boolean, nullable=False, default=False)
    
    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    organization = relationship("Organization", back_populates="teams")
    users = relationship("AccountUser", secondary=team_users, back_populates="teams")
    
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_team_org_slug"),
        Index("ix_teams_organization", "organization_id"),
    )


class Role(Base):
    __tablename__ = "roles"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Scope
    is_system = Column(Boolean, nullable=False, default=False)  # Built-in roles
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    
    __table_args__ = (
        UniqueConstraint("name", "organization_id", name="uq_role_name_org"),
        Index("ix_roles_system", "is_system"),
        Index("ix_roles_organization", "organization_id"),
    )


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(String, primary_key=True, default=generate_uuid)
    resource = Column(SQLEnum(ResourceType), nullable=False)
    action = Column(SQLEnum(PermissionAction), nullable=False)
    description = Column(Text, nullable=True)
    
    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
    
    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
        Index("ix_permissions_resource", "resource"),
    )


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    key_prefix = Column(String(10), nullable=False)  # First 8 chars for identification
    
    # Ownership
    user_id = Column(String, ForeignKey("account_users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    # Permissions
    scopes = Column(JSON, nullable=False, default=list)  # List of permission strings
    
    # Usage tracking
    last_used_at = Column(TIMESTAMP, nullable=True)
    last_used_ip = Column(String(45), nullable=True)
    usage_count = Column(Integer, nullable=False, default=0)
    
    # Validity
    expires_at = Column(TIMESTAMP, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())
    revoked_at = Column(TIMESTAMP, nullable=True)
    
    # Relationships
    user = relationship("AccountUser", back_populates="api_keys")
    organization = relationship("Organization", back_populates="api_keys")
    
    __table_args__ = (
        Index("ix_api_keys_organization_active", "organization_id", "is_active"),
        Index("ix_api_keys_user", "user_id"),
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("account_users.id", ondelete="CASCADE"), nullable=False)
    
    # Session data
    session_token_hash = Column(String(255), nullable=False, unique=True, index=True)
    refresh_token_hash = Column(String(255), nullable=True, unique=True, index=True)
    
    # Client info
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    device_id = Column(String(255), nullable=True)
    
    # Validity
    expires_at = Column(TIMESTAMP, nullable=False)
    refresh_expires_at = Column(TIMESTAMP, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    last_activity_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    revoked_at = Column(TIMESTAMP, nullable=True)
    
    # Relationships
    user = relationship("AccountUser", back_populates="sessions")
    
    __table_args__ = (
        Index("ix_sessions_user_active", "user_id", "is_active"),
        Index("ix_sessions_expires", "expires_at"),
    )


class AccountAuditLog(Base):
    __tablename__ = "account_audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Actor
    user_id = Column(String, ForeignKey("account_users.id", ondelete="SET NULL"), nullable=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    # Action
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(String, nullable=True)
    
    # Details
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    
    # Timestamp
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("AccountUser", back_populates="audit_logs")
    organization = relationship("Organization", back_populates="audit_logs")
    
    __table_args__ = (
        Index("ix_audit_logs_organization_created", "organization_id", "created_at"),
        Index("ix_audit_logs_user", "user_id"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("account_users.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(TIMESTAMP, nullable=False)
    used_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("AccountUser")
    
    __table_args__ = (
        Index("ix_verification_tokens_user", "user_id"),
        Index("ix_verification_tokens_expires", "expires_at"),
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("account_users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(TIMESTAMP, nullable=False)
    used_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("AccountUser")
    
    __table_args__ = (
        Index("ix_reset_tokens_user", "user_id"),
        Index("ix_reset_tokens_expires", "expires_at"),
    )