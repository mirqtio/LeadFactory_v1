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
from typing import Any

from sqlalchemy import DECIMAL, JSON, TIMESTAMP, Column, Date, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Index, Integer, String

from database.base import UUID, Base


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
    # Funnel event types
    ENTRY = "entry"
    CONVERSION = "conversion"
    ABANDONMENT = "abandonment"


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

    id = Column(UUID(), primary_key=True, default=generate_uuid)
    business_id = Column(UUID(), ForeignKey("businesses.id"), nullable=False)
    session_id = Column(String, nullable=False, index=True)
    campaign_id = Column(String, nullable=True, index=True)
    stage = Column(SQLEnum(FunnelStage), nullable=False)
    event_type = Column(SQLEnum(EventType), nullable=False)
    timestamp = Column(TIMESTAMP, default=datetime.utcnow)
    event_metadata = Column(JSON)

    # Note: Business relationship defined in database.models to avoid circular imports


class MetricsAggregation(Base):
    __tablename__ = "metrics_aggregations"

    id = Column(UUID(), primary_key=True, default=generate_uuid)
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
    tags = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_time_series_data_timestamp", timestamp.desc()),
        Index("ix_time_series_data_metric_name_timestamp", metric_name, timestamp.desc()),
        # Note: GIN index for tags is created separately for PostgreSQL only
    )


# Dataclass imports moved to top of file


@dataclass
class FunnelConversion:
    """Data class for funnel conversion metrics"""

    funnel_stage: FunnelStage
    total_count: int
    success_count: int
    conversion_rate: float
    avg_duration_seconds: float | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class MetricSnapshot:
    """Data class for metric snapshots"""

    metric_name: str
    metric_type: MetricType
    value: float
    timestamp: datetime
    period_type: AggregationPeriod | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    funnel_stage: FunnelStage | None = None
    campaign_id: str | None = None
    tags: dict[str, Any] | None = None


@dataclass
class DashboardMetric:
    """Data class for dashboard metrics display"""

    metric_name: str
    display_name: str
    value: float
    unit: str
    change_percentage: float | None = None
    trend: str | None = None
    period: str | None = None
    metadata: dict[str, Any] | None = None


# Backward compatibility class for tests
@dataclass
class D10Metric:
    """Backward compatibility metric class for tests"""

    type: MetricType  # Maps to metric_type in MetricSnapshot
    value: float
    timestamp: datetime
    dimensions: dict[str, Any] | None = None

    @property
    def metric_type(self) -> MetricType:
        """Alias for type property"""
        return self.type

    def to_metric_snapshot(self, metric_name: str = "test_metric") -> MetricSnapshot:
        """Convert to MetricSnapshot for compatibility"""
        return MetricSnapshot(
            metric_name=metric_name,
            metric_type=self.type,
            value=self.value,
            timestamp=self.timestamp,
            tags=self.dimensions,
        )
