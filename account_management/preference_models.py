"""
User Preferences and Saved Searches Database Models
Extends account management with personalization capabilities for P2-020
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, TIMESTAMP, Boolean, Column
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


def generate_uuid():
    """Generate a new UUID"""
    return str(uuid.uuid4())


class PreferenceCategory(str, enum.Enum):
    """Categories for user preferences"""

    DASHBOARD = "dashboard"
    REPORTS = "reports"
    NOTIFICATIONS = "notifications"
    SEARCH = "search"
    DISPLAY = "display"
    ANALYTICS = "analytics"
    EXPORT = "export"
    WORKFLOW = "workflow"


class SearchType(str, enum.Enum):
    """Types of saved searches"""

    LEAD_SEARCH = "lead_search"
    REPORT_SEARCH = "report_search"
    ANALYTICS_SEARCH = "analytics_search"
    CAMPAIGN_SEARCH = "campaign_search"
    ASSESSMENT_SEARCH = "assessment_search"


class UserPreference(Base):
    """User preference storage with hierarchical structure"""

    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("account_users.id", ondelete="CASCADE"), nullable=False)

    # Preference categorization
    category = Column(SQLEnum(PreferenceCategory), nullable=False, index=True)
    key = Column(String(255), nullable=False, index=True)

    # Preference value (JSON for complex structures)
    value = Column(JSON, nullable=False)

    # Metadata
    is_default = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=True)

    # Scope (for organization or team-level preferences)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    team_id = Column(String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("AccountUser")
    organization = relationship("Organization")
    team = relationship("Team")

    __table_args__ = (
        UniqueConstraint("user_id", "category", "key", name="uq_user_preference"),
        Index("ix_preferences_user_category", "user_id", "category"),
        Index("ix_preferences_org_team", "organization_id", "team_id"),
    )


class SavedSearch(Base):
    """Saved search queries with metadata and sharing capabilities"""

    __tablename__ = "saved_searches"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("account_users.id", ondelete="CASCADE"), nullable=False)

    # Search metadata
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    search_type = Column(SQLEnum(SearchType), nullable=False, index=True)

    # Search configuration
    query_params = Column(JSON, nullable=False)  # Search parameters and filters
    sort_config = Column(JSON, nullable=True)  # Sort configuration
    display_config = Column(JSON, nullable=True)  # Display/column configuration

    # Sharing and permissions
    is_public = Column(Boolean, nullable=False, default=False)
    is_default = Column(Boolean, nullable=False, default=False)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    team_id = Column(String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)

    # Usage tracking
    usage_count = Column(Integer, nullable=False, default=0)
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("AccountUser")
    organization = relationship("Organization")
    team = relationship("Team")

    __table_args__ = (
        Index("ix_saved_searches_user_type", "user_id", "search_type"),
        Index("ix_saved_searches_org_team", "organization_id", "team_id"),
        Index("ix_saved_searches_public", "is_public", "search_type"),
        Index("ix_saved_searches_usage", "usage_count", "last_used_at"),
    )


class UserDashboardLayout(Base):
    """User dashboard layout and widget configuration"""

    __tablename__ = "user_dashboard_layouts"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("account_users.id", ondelete="CASCADE"), nullable=False)

    # Layout identification
    name = Column(String(255), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)

    # Layout configuration
    layout_config = Column(JSON, nullable=False)  # Widget positions, sizes, etc.
    widget_config = Column(JSON, nullable=False)  # Widget-specific settings

    # Scope
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("AccountUser")
    organization = relationship("Organization")

    __table_args__ = (
        Index("ix_dashboard_layouts_user", "user_id"),
        Index("ix_dashboard_layouts_default", "user_id", "is_default"),
    )


class UserNotificationPreference(Base):
    """User notification preferences for different event types"""

    __tablename__ = "user_notification_preferences"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("account_users.id", ondelete="CASCADE"), nullable=False)

    # Notification type
    event_type = Column(String(100), nullable=False, index=True)

    # Notification channels
    email_enabled = Column(Boolean, nullable=False, default=True)
    in_app_enabled = Column(Boolean, nullable=False, default=True)
    sms_enabled = Column(Boolean, nullable=False, default=False)
    push_enabled = Column(Boolean, nullable=False, default=False)

    # Frequency and timing
    frequency = Column(String(50), nullable=False, default="immediate")  # immediate, daily, weekly, never
    quiet_hours_start = Column(String(5), nullable=True)  # HH:MM format
    quiet_hours_end = Column(String(5), nullable=True)  # HH:MM format

    # Additional configuration
    config = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("AccountUser")

    __table_args__ = (
        UniqueConstraint("user_id", "event_type", name="uq_user_notification_preference"),
        Index("ix_notification_prefs_user", "user_id"),
    )


class UserRecentActivity(Base):
    """Track user's recent activities for quick access and recommendations"""

    __tablename__ = "user_recent_activities"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("account_users.id", ondelete="CASCADE"), nullable=False)

    # Activity details
    activity_type = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(String, nullable=True)

    # Activity metadata
    activity_metadata = Column(JSON, nullable=True)
    context = Column(JSON, nullable=True)  # Additional context for recommendations

    # Frequency tracking
    access_count = Column(Integer, nullable=False, default=1)

    # Timestamps
    first_accessed_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_accessed_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("AccountUser")

    __table_args__ = (
        UniqueConstraint("user_id", "activity_type", "resource_type", "resource_id", name="uq_user_recent_activity"),
        Index("ix_recent_activities_user", "user_id"),
        Index("ix_recent_activities_type", "activity_type", "resource_type"),
        Index("ix_recent_activities_accessed", "last_accessed_at"),
    )
