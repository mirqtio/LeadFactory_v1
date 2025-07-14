"""
D1 Targeting - Geo × vertical campaign management

Manages geographic and vertical market segmentation for lead generation campaigns.
Provides target universe definition and batch scheduling capabilities.
"""

from database.models import Batch, Target

from .api import router as api_router
from .batch_scheduler import BatchScheduler
from .bucket_loader import BucketFeatureLoader
from .geo_validator import GeoConflict, GeoValidator
from .models import Campaign, GeographicBoundary, TargetUniverse
from .quota_tracker import QuotaTracker
from .target_universe import TargetUniverseManager
from .types import BatchSchedule, CampaignStatus, GeographyLevel, TargetingCriteria, TargetMetrics, VerticalMarket

__all__ = [
    # Models
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
]
