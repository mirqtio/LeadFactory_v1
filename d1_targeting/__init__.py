"""
D1 Targeting - Geo × vertical campaign management

Manages geographic and vertical market segmentation for lead generation campaigns.
Provides target universe definition and batch scheduling capabilities.
"""

from database.models import Target, Batch
from .models import TargetUniverse, Campaign, GeographicBoundary
from .target_universe import TargetUniverseManager
from .geo_validator import GeoValidator, GeoConflict
from .batch_scheduler import BatchScheduler
from .quota_tracker import QuotaTracker
from .api import router as api_router
from .types import (
    VerticalMarket,
    GeographyLevel,
    TargetingCriteria,
    CampaignStatus,
    BatchSchedule,
    TargetMetrics
)

__all__ = [
    # Models
    'Target',
    'TargetUniverse', 
    'Campaign',
    'GeographicBoundary',
    # Managers and Validators
    'TargetUniverseManager',
    'GeoValidator',
    'GeoConflict',
    'BatchScheduler',
    'QuotaTracker',
    # API
    'api_router',
    # Types
    'VerticalMarket',
    'GeographyLevel',
    'TargetingCriteria',
    'CampaignStatus',
    'BatchSchedule',
    'TargetMetrics'
]