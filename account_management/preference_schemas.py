"""
User Preferences API Schemas
Pydantic schemas for user preferences and saved searches API endpoints
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from account_management.preference_models import PreferenceCategory, SearchType


class UserPreferenceRequest(BaseModel):
    """Request schema for creating/updating user preferences"""
    
    category: PreferenceCategory = Field(..., description="Preference category")
    key: str = Field(..., min_length=1, max_length=255, description="Preference key")
    value: Dict[str, Any] = Field(..., description="Preference value as JSON")
    description: Optional[str] = Field(None, description="Optional description")
    organization_id: Optional[str] = Field(None, description="Organization scope")
    team_id: Optional[str] = Field(None, description="Team scope")


class UserPreferenceResponse(BaseModel):
    """Response schema for user preferences"""
    
    id: str
    user_id: str
    category: PreferenceCategory
    key: str
    value: Dict[str, Any]
    is_default: bool
    description: Optional[str]
    organization_id: Optional[str]
    team_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SavedSearchRequest(BaseModel):
    """Request schema for creating/updating saved searches"""
    
    name: str = Field(..., min_length=1, max_length=255, description="Search name")
    description: Optional[str] = Field(None, description="Search description")
    search_type: SearchType = Field(..., description="Type of search")
    query_params: Dict[str, Any] = Field(..., description="Search parameters")
    sort_config: Optional[Dict[str, Any]] = Field(None, description="Sort configuration")
    display_config: Optional[Dict[str, Any]] = Field(None, description="Display configuration")
    is_public: bool = Field(False, description="Whether search is public")
    is_default: bool = Field(False, description="Whether search is default")
    organization_id: Optional[str] = Field(None, description="Organization scope")
    team_id: Optional[str] = Field(None, description="Team scope")


class SavedSearchUpdate(BaseModel):
    """Schema for updating saved searches"""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    query_params: Optional[Dict[str, Any]] = None
    sort_config: Optional[Dict[str, Any]] = None
    display_config: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None
    is_default: Optional[bool] = None


class SavedSearchResponse(BaseModel):
    """Response schema for saved searches"""
    
    id: str
    user_id: str
    name: str
    description: Optional[str]
    search_type: SearchType
    query_params: Dict[str, Any]
    sort_config: Optional[Dict[str, Any]]
    display_config: Optional[Dict[str, Any]]
    is_public: bool
    is_default: bool
    organization_id: Optional[str]
    team_id: Optional[str]
    usage_count: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DashboardLayoutRequest(BaseModel):
    """Request schema for dashboard layouts"""
    
    name: str = Field(..., min_length=1, max_length=255, description="Layout name")
    layout_config: Dict[str, Any] = Field(..., description="Layout configuration")
    widget_config: Dict[str, Any] = Field(..., description="Widget configuration")
    is_default: bool = Field(False, description="Whether layout is default")
    organization_id: Optional[str] = Field(None, description="Organization scope")


class DashboardLayoutResponse(BaseModel):
    """Response schema for dashboard layouts"""
    
    id: str
    user_id: str
    name: str
    layout_config: Dict[str, Any]
    widget_config: Dict[str, Any]
    is_default: bool
    organization_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationPreferenceRequest(BaseModel):
    """Request schema for notification preferences"""
    
    event_type: str = Field(..., min_length=1, max_length=100, description="Event type")
    email_enabled: bool = Field(True, description="Email notifications enabled")
    in_app_enabled: bool = Field(True, description="In-app notifications enabled")
    sms_enabled: bool = Field(False, description="SMS notifications enabled")
    push_enabled: bool = Field(False, description="Push notifications enabled")
    frequency: str = Field("immediate", description="Notification frequency")
    quiet_hours_start: Optional[str] = Field(None, description="Quiet hours start (HH:MM)")
    quiet_hours_end: Optional[str] = Field(None, description="Quiet hours end (HH:MM)")
    config: Optional[Dict[str, Any]] = Field(None, description="Additional configuration")

    @field_validator('frequency')
    @classmethod
    def validate_frequency(cls, v):
        valid_frequencies = ['immediate', 'daily', 'weekly', 'never']
        if v not in valid_frequencies:
            raise ValueError(f'Frequency must be one of: {valid_frequencies}')
        return v

    @field_validator('quiet_hours_start', 'quiet_hours_end')
    @classmethod
    def validate_time_format(cls, v):
        if v is not None:
            import re
            if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', v):
                raise ValueError('Time must be in HH:MM format')
        return v


class NotificationPreferenceResponse(BaseModel):
    """Response schema for notification preferences"""
    
    id: str
    user_id: str
    event_type: str
    email_enabled: bool
    in_app_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    frequency: str
    quiet_hours_start: Optional[str]
    quiet_hours_end: Optional[str]
    config: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecentActivityResponse(BaseModel):
    """Response schema for recent activities"""
    
    id: str
    user_id: str
    activity_type: str
    resource_type: str
    resource_id: Optional[str]
    activity_metadata: Optional[Dict[str, Any]]
    context: Optional[Dict[str, Any]]
    access_count: int
    first_accessed_at: datetime
    last_accessed_at: datetime

    class Config:
        from_attributes = True


class PreferencesListResponse(BaseModel):
    """Response schema for listing user preferences"""
    
    preferences: List[UserPreferenceResponse]
    total: int
    categories: List[PreferenceCategory]


class SavedSearchesListResponse(BaseModel):
    """Response schema for listing saved searches"""
    
    searches: List[SavedSearchResponse]
    total: int
    by_type: Dict[SearchType, int]