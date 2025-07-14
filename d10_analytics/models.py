"""
D10 Analytics Models - Task 070

Analytics and reporting models for tracking funnel events, metrics aggregation,
and time series data with efficient indexing for query performance.

Acceptance Criteria:
- Funnel event model ✓
- Metrics aggregation ✓  
- Time series support ✓
- Efficient indexing ✓
"""

import enum
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DECIMAL, JSON, TIMESTAMP, Column, Date, DateTime, Enum as SQLEnum, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


def generate_uuid() -> str:
    """Generate a UUID string for unique identifiers"""
    return str(uuid.uuid4())


class FunnelStage(enum.Enum):
    TARGETING = "Targeting"
    ASSESSMENT = "Assessment"
    SCORING = "Scoring"
    PRIORITIZATION = "Prioritization"
    REPORTING = "Reporting"
    PAYMENT = "Payment"


class AggregationPeriod(enum.Enum):
    """Time period for aggregations"""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class EventType(enum.Enum):
    PIPELINE_START = "pipeline_start"
    PIPELINE_SUCCESS = "pipeline_success"
    PIPELINE_FAILURE = "pipeline_failure"
    ASSESSMENT_START = "assessment_start"
    ASSESSMENT_SUCCESS = "assessment_success"
    ASSESSMENT_FAILURE = "assessment_failure"
    REPORT_GENERATED = "report_generated"
    PAYMENT_SUCCESS = "payment_success"


class MetricType(enum.Enum):
    """Types of metrics tracked in the analytics system"""

    COUNT = "count"
    SUCCESS_RATE = "success_rate"
    DURATION = "duration"
    COST = "cost"
    CONVERSION_RATE = "conversion_rate"
    LEAD_SCORE = "lead_score"
    ENGAGEMENT_RATE = "engagement_rate"


class FunnelEvent(Base):
    __tablename__ = "funnel_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    session_id = Column(String, nullable=False, index=True)
    stage = Column(SQLEnum(FunnelStage), nullable=False)
    event_type = Column(SQLEnum(EventType), nullable=False)
    timestamp = Column(TIMESTAMP, default=datetime.utcnow)
    event_metadata = Column(JSONB)

    business = relationship("Business")


class MetricsAggregation(Base):
    __tablename__ = "metrics_aggregations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = Column(String, nullable=False, index=True)
    aggregation_period = Column(String, nullable=False)  # e.g., 'daily', 'weekly'
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    value = Column(DECIMAL, nullable=False)
    conversion_metadata = Column(JSON)


class TimeSeriesData(Base):
    __tablename__ = "time_series_data"

    id = Column(Integer, primary_key=True)
    metric_name = Column(String(255), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    value = Column(Float, nullable=False)
    tags = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_time_series_data_timestamp", timestamp.desc()),
        Index("ix_time_series_data_metric_name_timestamp", metric_name, timestamp.desc()),
        Index("ix_time_series_data_tags", tags, postgresql_using="gin"),
    )


# Dataclass imports moved to top of file


@dataclass
class FunnelConversion:
    """Data class for funnel conversion metrics"""

    funnel_stage: FunnelStage
    total_count: int
    success_count: int
    conversion_rate: float
    avg_duration_seconds: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class MetricSnapshot:
    """Data class for metric snapshots"""

    metric_name: str
    metric_type: MetricType
    value: float
    timestamp: datetime
    period_type: Optional[AggregationPeriod] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    funnel_stage: Optional[FunnelStage] = None
    campaign_id: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None


@dataclass
class DashboardMetric:
    """Data class for dashboard metrics display"""

    metric_name: str
    display_name: str
    value: float
    unit: str
    change_percentage: Optional[float] = None
    trend: Optional[str] = None
    period: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
