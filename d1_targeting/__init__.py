"""
D1 Targeting - Geo × vertical campaign management

Manages geographic and vertical market segmentation for lead generation campaigns.
Provides target universe definition and batch scheduling capabilities.
"""

from database.models import Batch, Target

from .api import router as api_router
from .batch_scheduler import BatchScheduler
from .bucket_loader import BucketFeatureLoader

# P2-010: Collaborative Buckets
from .collaboration_api import router as collaboration_router
from .collaboration_models import (
    ActiveCollaboration,
    BucketActivity,
    BucketActivityType,
    BucketComment,
    BucketNotification,
    BucketPermission,
    BucketPermissionGrant,
    BucketShareLink,
    BucketTagDefinition,
    BucketVersion,
    CollaborativeBucket,
    LeadAnnotation,
    NotificationType,
)
from .collaboration_service import BucketCollaborationService, WebSocketManager
from .geo_validator import GeoConflict, GeoValidator
from .models import Campaign, GeographicBoundary, TargetUniverse
from .quota_tracker import QuotaTracker
from .target_universe import TargetUniverseManager
from .types import BatchSchedule, CampaignStatus, GeographyLevel, TargetingCriteria, TargetMetrics, VerticalMarket

__all__ = [
    # Models
    "Batch",
    "Target",
    "TargetUniverse",
    "Campaign",
    "GeographicBoundary",
    # Managers and Validators
    "TargetUniverseManager",
    "GeoValidator",
    "GeoConflict",
    "BatchScheduler",
    "QuotaTracker",
    "BucketFeatureLoader",
    # API
    "api_router",
    # Types
    "VerticalMarket",
    "GeographyLevel",
    "TargetingCriteria",
    "CampaignStatus",
    "BatchSchedule",
    "TargetMetrics",
    # P2-010: Collaborative Buckets
    "collaboration_router",
    "CollaborativeBucket",
    "BucketPermissionGrant",
    "BucketActivity",
    "BucketComment",
    "BucketVersion",
    "BucketNotification",
    "LeadAnnotation",
    "BucketTagDefinition",
    "BucketShareLink",
    "ActiveCollaboration",
    "BucketPermission",
    "BucketActivityType",
    "NotificationType",
    "BucketCollaborationService",
    "WebSocketManager",
]
