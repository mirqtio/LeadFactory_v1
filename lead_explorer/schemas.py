"""
Pydantic schemas for Lead Explorer API validation.

Provides request/response schemas with comprehensive validation
following RFC 5322 for emails and proper domain validation.
"""
import re
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, root_validator, validator


class EnrichmentStatusEnum(str, Enum):
    """Enrichment status values"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditActionEnum(str, Enum):
    """Audit action types"""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class BadgeTypeEnum(str, Enum):
    """Badge type enumeration"""

    PRIORITY = "priority"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    OPPORTUNITY = "opportunity"
    CUSTOMER = "customer"
    BLOCKED = "blocked"
    FOLLOW_UP = "follow_up"
    DEMO_SCHEDULED = "demo_scheduled"
    PROPOSAL_SENT = "proposal_sent"
    CUSTOM = "custom"


# Base schemas
class BaseResponseSchema(BaseModel):
    """Base response schema with common fields"""

    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Lead schemas
class CreateLeadSchema(BaseModel):
    """Schema for creating a new lead"""

    email: Optional[EmailStr] = Field(None, description="Contact email address")
    domain: Optional[str] = Field(None, min_length=3, max_length=255, description="Company domain")
    company_name: Optional[str] = Field(None, max_length=500, description="Company name")
    contact_name: Optional[str] = Field(None, max_length=255, description="Contact person name")
    is_manual: bool = Field(False, description="Whether this is a manually added lead")
    source: Optional[str] = Field(None, max_length=100, description="Lead source (manual, csv_upload, etc.)")

    @validator("domain")
    def validate_domain(cls, v):
        """Validate domain format"""
        if v is None:
            return v

        v = v.lower().strip()

        # Basic domain validation
        if not re.match(
            r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$", v
        ):
            raise ValueError("Invalid domain format")

        # Must contain at least one dot
        if "." not in v:
            raise ValueError("Domain must contain at least one dot")

        # Cannot start or end with dot
        if v.startswith(".") or v.endswith("."):
            raise ValueError("Domain cannot start or end with a dot")

        return v

    @root_validator(skip_on_failure=True)
    def validate_lead_data(cls, values):
        """Ensure at least email or domain is provided"""
        email = values.get("email")
        domain = values.get("domain")

        if not email and not domain:
            raise ValueError("Either email or domain must be provided")

        return values


class UpdateLeadSchema(BaseModel):
    """Schema for updating an existing lead"""

    email: Optional[EmailStr] = None
    domain: Optional[str] = Field(None, min_length=3, max_length=255)
    company_name: Optional[str] = Field(None, max_length=500)
    contact_name: Optional[str] = Field(None, max_length=255)
    source: Optional[str] = Field(None, max_length=100)

    @validator("domain")
    def validate_domain(cls, v):
        """Validate domain format"""
        if v is None:
            return v

        v = v.lower().strip()

        if not re.match(
            r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$", v
        ):
            raise ValueError("Invalid domain format")

        if "." not in v:
            raise ValueError("Domain must contain at least one dot")

        if v.startswith(".") or v.endswith("."):
            raise ValueError("Domain cannot start or end with a dot")

        return v


class LeadResponseSchema(BaseResponseSchema):
    """Schema for lead response data"""

    email: Optional[str]
    domain: Optional[str]
    company_name: Optional[str]
    contact_name: Optional[str]
    enrichment_status: EnrichmentStatusEnum
    enrichment_task_id: Optional[str]
    enrichment_error: Optional[str]
    is_manual: bool
    source: Optional[str]
    is_deleted: bool
    deleted_at: Optional[datetime]
    created_by: Optional[str]
    updated_by: Optional[str]
    deleted_by: Optional[str]


class QuickAddLeadSchema(BaseModel):
    """Schema for quick-add lead with immediate enrichment"""

    email: Optional[EmailStr] = None
    domain: Optional[str] = Field(None, min_length=3, max_length=255)
    company_name: Optional[str] = Field(None, max_length=500)
    contact_name: Optional[str] = Field(None, max_length=255)

    @validator("domain")
    def validate_domain(cls, v):
        """Validate domain format"""
        if v is None:
            return v

        v = v.lower().strip()

        if not re.match(
            r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$", v
        ):
            raise ValueError("Invalid domain format")

        if "." not in v:
            raise ValueError("Domain must contain at least one dot")

        if v.startswith(".") or v.endswith("."):
            raise ValueError("Domain cannot start or end with a dot")

        return v

    @root_validator(skip_on_failure=True)
    def validate_quick_add_data(cls, values):
        """Ensure at least email or domain is provided for enrichment"""
        email = values.get("email")
        domain = values.get("domain")

        if not email and not domain:
            raise ValueError("Either email or domain must be provided for enrichment")

        return values


class QuickAddResponseSchema(BaseModel):
    """Response schema for quick-add operation"""

    lead: LeadResponseSchema
    enrichment_task_id: str
    message: str = "Lead created and enrichment started"


# List and pagination schemas
class LeadFilterSchema(BaseModel):
    """Schema for filtering leads"""

    is_manual: Optional[bool] = None
    enrichment_status: Optional[EnrichmentStatusEnum] = None
    search: Optional[str] = Field(None, max_length=500, description="Search in email, domain, company, or contact name")
    # P0-021: Badge-based filtering
    badge_ids: Optional[List[str]] = Field(None, description="Filter by badge IDs")
    badge_types: Optional[List[BadgeTypeEnum]] = Field(None, description="Filter by badge types")
    has_badges: Optional[bool] = Field(None, description="Filter leads that have any badges")
    exclude_badge_ids: Optional[List[str]] = Field(None, description="Exclude leads with these badge IDs")


class PaginationSchema(BaseModel):
    """Schema for pagination parameters"""

    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(100, ge=1, le=1000, description="Number of records to return")
    sort_by: str = Field("created_at", description="Field to sort by")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")


class LeadListResponseSchema(BaseModel):
    """Schema for paginated lead list response"""

    leads: List[LeadResponseSchema]
    total_count: int = Field(description="Total number of leads matching filters")
    page_info: dict = Field(description="Pagination information")


# Audit log schemas
class AuditLogResponseSchema(BaseResponseSchema):
    """Schema for audit log response"""

    lead_id: str
    action: AuditActionEnum
    timestamp: datetime
    user_id: Optional[str]
    user_ip: Optional[str]
    user_agent: Optional[str]
    old_values: Optional[dict]
    new_values: Optional[dict]
    checksum: str


class AuditTrailResponseSchema(BaseModel):
    """Schema for audit trail response"""

    lead_id: str
    audit_logs: List[AuditLogResponseSchema]
    total_count: int


# Error schemas
class ErrorResponseSchema(BaseModel):
    """Schema for error responses"""

    error: str
    message: str
    details: Optional[dict] = None


class ValidationErrorSchema(BaseModel):
    """Schema for validation error responses"""

    error: str = "VALIDATION_ERROR"
    message: str
    validation_errors: List[dict]


# Health check schema
class HealthCheckResponseSchema(BaseModel):
    """Schema for health check response"""

    status: str = "ok"
    timestamp: datetime
    database: str = "connected"
    message: str = "Lead Explorer is healthy"


# P0-021: Badge Management Schemas
class CreateBadgeSchema(BaseModel):
    """Schema for creating a new badge"""

    name: str = Field(..., min_length=1, max_length=100, description="Badge name")
    description: Optional[str] = Field(None, max_length=1000, description="Badge description")
    badge_type: BadgeTypeEnum = Field(..., description="Badge type")
    color: str = Field("#007bff", pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    icon: Optional[str] = Field(None, max_length=50, description="Bootstrap icon name")
    is_system: bool = Field(False, description="Is this a system badge?")
    is_active: bool = Field(True, description="Is this badge active?")

    @validator("name")
    def validate_name(cls, v):
        """Validate badge name"""
        if not v.strip():
            raise ValueError("Badge name cannot be empty")
        return v.strip()


class UpdateBadgeSchema(BaseModel):
    """Schema for updating a badge"""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Badge name")
    description: Optional[str] = Field(None, max_length=1000, description="Badge description")
    badge_type: Optional[BadgeTypeEnum] = Field(None, description="Badge type")
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    icon: Optional[str] = Field(None, max_length=50, description="Bootstrap icon name")
    is_active: Optional[bool] = Field(None, description="Is this badge active?")

    @validator("name")
    def validate_name(cls, v):
        """Validate badge name"""
        if v is not None and not v.strip():
            raise ValueError("Badge name cannot be empty")
        return v.strip() if v else v


class BadgeResponseSchema(BaseResponseSchema):
    """Schema for badge response"""

    name: str
    description: Optional[str]
    badge_type: BadgeTypeEnum
    color: str
    icon: Optional[str]
    is_system: bool
    is_active: bool
    created_by: Optional[str]


class AssignBadgeSchema(BaseModel):
    """Schema for assigning a badge to a lead"""

    badge_id: str = Field(..., description="Badge ID to assign")
    notes: Optional[str] = Field(None, max_length=1000, description="Assignment notes")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date")


class RemoveBadgeSchema(BaseModel):
    """Schema for removing a badge from a lead"""

    badge_id: str = Field(..., description="Badge ID to remove")
    removal_reason: Optional[str] = Field(None, max_length=1000, description="Reason for removal")


class LeadBadgeResponseSchema(BaseModel):
    """Schema for lead badge association response"""

    id: str
    lead_id: str
    badge_id: str
    badge: BadgeResponseSchema
    assigned_by: Optional[str]
    assigned_at: datetime
    notes: Optional[str]
    expires_at: Optional[datetime]
    is_active: bool
    removed_at: Optional[datetime]
    removed_by: Optional[str]
    removal_reason: Optional[str]

    class Config:
        from_attributes = True


class BadgeListResponseSchema(BaseModel):
    """Schema for badge list response"""

    badges: List[BadgeResponseSchema]
    total_count: int
    page_info: Optional[dict] = None


class LeadBadgeListResponseSchema(BaseModel):
    """Schema for lead badge list response"""

    lead_badges: List[LeadBadgeResponseSchema]
    total_count: int


class BadgeAuditLogResponseSchema(BaseModel):
    """Schema for badge audit log response"""

    id: str
    lead_id: str
    badge_id: str
    lead_badge_id: Optional[str]
    action: str
    timestamp: datetime
    user_id: Optional[str]
    user_ip: Optional[str]
    user_agent: Optional[str]
    old_values: Optional[dict]
    new_values: Optional[dict]
    notes: Optional[str]
    meta_data: Optional[dict]

    class Config:
        from_attributes = True


class BadgeAuditTrailResponseSchema(BaseModel):
    """Schema for badge audit trail response"""

    lead_id: str
    badge_audit_logs: List[BadgeAuditLogResponseSchema]
    total_count: int


class BadgeFilterSchema(BaseModel):
    """Schema for filtering badges"""

    badge_type: Optional[BadgeTypeEnum] = None
    is_system: Optional[bool] = None
    is_active: Optional[bool] = None
    search: Optional[str] = Field(None, max_length=500, description="Search in name or description")
