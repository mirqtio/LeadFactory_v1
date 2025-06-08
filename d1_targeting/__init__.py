"""
D1 Targeting - Geo × vertical campaign management

Manages geographic and vertical market segmentation for lead generation campaigns.
Provides target universe definition and batch scheduling capabilities.
"""

from database.models import Target, Batch
from .models import TargetUniverse, Campaign, GeographicBoundary
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
    # Types
    'VerticalMarket',
    'GeographyLevel',
    'TargetingCriteria',
    'CampaignStatus',
    'BatchSchedule',
    'TargetMetrics'
]