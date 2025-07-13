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
from enum import Enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    JSON,
    TIMESTAMP,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


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


class FunnelEvent(Base):
    __tablename__ = "funnel_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)
    session_id = Column(String, nullable=False, index=True)
    stage = Column(Enum(FunnelStage), nullable=False)
    event_type = Column(Enum(EventType), nullable=False)
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
        Index(
            'ix_time_series_data_tags',
            tags,
            postgresql_using='gin'
        )
    )
