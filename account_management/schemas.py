"""
Pydantic schemas for Account Management
Request/response validation models
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, SecretStr, validator

from account_management.models import AuthProvider, PermissionAction, ResourceType, TeamRole, UserStatus


# Base schemas
class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, regex="^[a-z0-9-]+$")
    billing_email: Optional[EmailStr] = None


class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = Field(None, min_length=3, max_length=100, regex="^[a-zA-Z0-9_-]+$")
    full_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    timezone: str = Field("UTC", max_length=50)
    locale: str = Field("en_US", max_length=10)


class TeamBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, regex="^[a-z0-9-]+$")
    description: Optional[str] = None


# Request schemas
class OrganizationCreate(OrganizationBase):
    max_users: int = Field(5, ge=1, le=1000)
    max_teams: int = Field(3, ge=1, le=100)
    max_api_keys: int = Field(10, ge=1, le=1000)


class UserRegister(UserBase):
    password: SecretStr = Field(..., min_length=8, max_length=128)
    organization_name: Optional[str] = Field(None, min_length=1, max_length=255)

    @validator("password")
    def validate_password(cls, v):
        password = v.get_secret_value()
        if not any(char.isdigit() for char in password):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in password):
            raise ValueError("Password must contain at least one lowercase letter")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: SecretStr
    device_id: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=100, regex="^[a-zA-Z0-9_-]+$")
    full_name: Optional[str] = Field(None, max_length=255)
    avatar_url: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)
    timezone: Optional[str] = Field(None, max_length=50)
    locale: Optional[str] = Field(None, max_length=10)


class PasswordChange(BaseModel):
    current_password: SecretStr
    new_password: SecretStr = Field(..., min_length=8, max_length=128)

    @validator("new_password")
    def validate_password(cls, v):
        password = v.get_secret_value()
        if not any(char.isdigit() for char in password):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in password):
            raise ValueError("Password must contain at least one lowercase letter")
        return v


class PasswordReset(BaseModel):
    token: str
    new_password: SecretStr = Field(..., min_length=8, max_length=128)


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class TeamMemberAdd(BaseModel):
    user_id: str
    role: TeamRole = TeamRole.MEMBER


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    permissions: List[str] = []  # List of permission IDs


class PermissionGrant(BaseModel):
    resource: ResourceType
    action: PermissionAction


class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    scopes: List[str] = []
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


# Response schemas
class OrganizationResponse(OrganizationBase):
    id: str
    stripe_customer_id: Optional[str]
    max_users: int
    max_teams: int
    max_api_keys: int
    is_active: bool
    trial_ends_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    id: str
    organization_id: Optional[str]
    status: UserStatus
    email_verified: bool
    email_verified_at: Optional[datetime]
    mfa_enabled: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserProfileResponse(UserResponse):
    organization: Optional[OrganizationResponse]
    teams: List["TeamResponse"] = []


class TeamResponse(TeamBase):
    id: str
    organization_id: str
    is_default: bool
    created_at: datetime
    updated_at: datetime
    member_count: int = 0

    class Config:
        from_attributes = True


class TeamDetailResponse(TeamResponse):
    members: List["TeamMemberResponse"] = []


class TeamMemberResponse(BaseModel):
    user_id: str
    email: str
    full_name: Optional[str]
    role: TeamRole
    joined_at: datetime

    class Config:
        from_attributes = True


class RoleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_system: bool
    permissions: List["PermissionResponse"] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PermissionResponse(BaseModel):
    id: str
    resource: ResourceType
    action: PermissionAction
    description: Optional[str]

    class Config:
        from_attributes = True


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: List[str]
    last_used_at: Optional[datetime]
    usage_count: int
    expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyCreateResponse(APIKeyResponse):
    key: str  # Only returned on creation


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 1800  # 30 minutes
    user: UserResponse


class SessionResponse(BaseModel):
    id: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    device_id: Optional[str]
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class EmailVerificationRequest(BaseModel):
    token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# Audit log response
class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str]
    user_email: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    ip_address: Optional[str]
    details: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


# Stats response
class OrganizationStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_teams: int
    total_api_keys: int
    active_api_keys: int
    storage_used_mb: float = 0
    api_calls_this_month: int = 0


# Error responses
class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict] = None


class ValidationErrorResponse(BaseModel):
    error: str = "validation_error"
    message: str = "Validation failed"
    errors: List[dict]


# Forward references
TeamResponse.model_rebuild()
TeamDetailResponse.model_rebuild()
UserProfileResponse.model_rebuild()
RoleResponse.model_rebuild()
