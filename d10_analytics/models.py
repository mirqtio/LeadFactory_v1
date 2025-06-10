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
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from sqlalchemy import (DECIMAL, JSON, TIMESTAMP, Boolean, CheckConstraint,
                        Column, Date, DateTime)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import (Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


def generate_uuid():
    """Generate a new UUID"""
    return str(uuid.uuid4())


# Enums for analytics


class FunnelStage(str, enum.Enum):
    """Stages in the lead generation funnel"""

    TARGETING = "targeting"  # Business targeting phase
    SOURCING = "sourcing"  # Lead sourcing phase
    ASSESSMENT = "assessment"  # Website assessment phase
    ENRICHMENT = "enrichment"  # Data enrichment phase
    SCORING = "scoring"  # Lead scoring phase
    REPORTING = "reporting"  # Report generation phase
    DELIVERY = "delivery"  # Report delivery phase
    CONVERSION = "conversion"  # Customer conversion phase


class EventType(str, enum.Enum):
    """Types of funnel events"""

    ENTRY = "entry"  # Entered funnel stage
    PROGRESS = "progress"  # Progress within stage
    COMPLETION = "completion"  # Completed stage
    ERROR = "error"  # Error in stage
    RETRY = "retry"  # Retry attempt
    ABANDONMENT = "abandonment"  # Abandoned stage
    CONVERSION = "conversion"  # Converted to customer


class MetricType(str, enum.Enum):
    """Types of metrics to track"""

    COUNT = "count"  # Simple counts
    DURATION = "duration"  # Time-based metrics
    COST = "cost"  # Cost metrics
    SUCCESS_RATE = "success_rate"  # Success percentage
    CONVERSION_RATE = "conversion_rate"  # Conversion percentage
    REVENUE = "revenue"  # Revenue metrics
    QUALITY_SCORE = "quality_score"  # Quality metrics


class AggregationPeriod(str, enum.Enum):
    """Time periods for metric aggregation"""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


# Analytics Models


class FunnelEvent(Base):
    """
    Funnel event model - Track events in the lead generation funnel

    Captures every significant event that occurs as leads move through
    the funnel stages, enabling detailed tracking and analysis.
    """

    __tablename__ = "funnel_events"

    # Primary identification
    event_id = Column(String, primary_key=True, default=generate_uuid)

    # Funnel tracking
    funnel_stage = Column(SQLEnum(FunnelStage), nullable=False, index=True)
    event_type = Column(SQLEnum(EventType), nullable=False, index=True)

    # Related entities
    business_id = Column(String, nullable=True, index=True)
    campaign_id = Column(String, nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)  # User session tracking
    user_id = Column(String, nullable=True, index=True)  # User identification

    # Event details
    event_name = Column(String(255), nullable=False)
    event_description = Column(Text, nullable=True)
    event_properties = Column(JSON, nullable=True)  # Additional event data

    # Performance metrics
    duration_ms = Column(Integer, nullable=True)  # Event duration in milliseconds
    cost_cents = Column(Integer, nullable=True)  # Event cost in cents
    success = Column(Boolean, nullable=True)  # Event success status
    error_message = Column(Text, nullable=True)  # Error details if failed

    # Timestamps - Time series support
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=func.now(), index=True
    )
    occurred_at = Column(
        DateTime(timezone=True), nullable=False, index=True
    )  # When event actually occurred

    # Context
    source = Column(String(100), nullable=True)  # Event source system
    version = Column(String(50), nullable=True)  # System version
    environment = Column(String(50), nullable=True)  # Environment (prod, test, etc)

    # Note: Relationships would be defined here in production with proper foreign keys

    # Efficient indexing for query performance
    __table_args__ = (
        # Composite indexes for common query patterns
        Index("idx_funnel_events_stage_type", "funnel_stage", "event_type"),
        Index("idx_funnel_events_business_time", "business_id", "occurred_at"),
        Index("idx_funnel_events_session_time", "session_id", "occurred_at"),
        Index("idx_funnel_events_campaign_stage", "campaign_id", "funnel_stage"),
        Index("idx_funnel_events_time_stage", "occurred_at", "funnel_stage"),
        Index("idx_funnel_events_success_time", "success", "occurred_at"),
        # Note: Partial indexes would be used in PostgreSQL production
        # Constraints
        CheckConstraint("duration_ms >= 0", name="ck_funnel_events_duration_positive"),
        CheckConstraint("cost_cents >= 0", name="ck_funnel_events_cost_positive"),
    )


class MetricSnapshot(Base):
    """
    Metrics aggregation model - Support for aggregating metrics across different dimensions

    Pre-calculated metrics aggregated by various dimensions and time periods
    for fast dashboard queries and reporting.
    """

    __tablename__ = "metric_snapshots"

    # Primary identification
    snapshot_id = Column(String, primary_key=True, default=generate_uuid)

    # Metric definition
    metric_name = Column(String(255), nullable=False, index=True)
    metric_type = Column(SQLEnum(MetricType), nullable=False, index=True)

    # Aggregation dimensions
    funnel_stage = Column(SQLEnum(FunnelStage), nullable=True, index=True)
    campaign_id = Column(String, nullable=True, index=True)
    business_vertical = Column(String(100), nullable=True, index=True)
    geography = Column(String(100), nullable=True, index=True)

    # Time dimension - Time series support
    period_type = Column(SQLEnum(AggregationPeriod), nullable=False, index=True)
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False, index=True)
    period_date = Column(
        Date, nullable=False, index=True
    )  # Date for daily aggregations

    # Metric values
    value = Column(DECIMAL(20, 4), nullable=False)
    count = Column(Integer, nullable=False, default=0)
    sum = Column(DECIMAL(20, 4), nullable=True)
    avg = Column(DECIMAL(20, 4), nullable=True)
    min = Column(DECIMAL(20, 4), nullable=True)
    max = Column(DECIMAL(20, 4), nullable=True)

    # Additional statistics
    stddev = Column(DECIMAL(20, 4), nullable=True)
    percentile_25 = Column(DECIMAL(20, 4), nullable=True)
    percentile_50 = Column(DECIMAL(20, 4), nullable=True)
    percentile_75 = Column(DECIMAL(20, 4), nullable=True)
    percentile_95 = Column(DECIMAL(20, 4), nullable=True)

    # Metadata
    data_points = Column(
        Integer, nullable=False, default=0
    )  # Number of data points aggregated
    calculation_method = Column(String(100), nullable=True)  # How metric was calculated
    metric_metadata = Column(JSON, nullable=True)  # Additional metric metadata

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()
    )
    calculated_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Data quality
    is_estimated = Column(Boolean, nullable=False, default=False)
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0

    # Efficient indexing for query performance
    __table_args__ = (
        # Composite indexes for common aggregation queries
        Index(
            "idx_metrics_name_period_stage",
            "metric_name",
            "period_type",
            "funnel_stage",
        ),
        Index(
            "idx_metrics_date_name_type", "period_date", "metric_name", "metric_type"
        ),
        Index(
            "idx_metrics_campaign_period", "campaign_id", "period_start", "period_end"
        ),
        Index("idx_metrics_vertical_period", "business_vertical", "period_date"),
        Index("idx_metrics_geo_period", "geography", "period_date"),
        Index("idx_metrics_time_series", "metric_name", "funnel_stage", "period_start"),
        # Unique constraint for aggregation uniqueness
        UniqueConstraint(
            "metric_name",
            "funnel_stage",
            "campaign_id",
            "business_vertical",
            "geography",
            "period_type",
            "period_start",
            name="uq_metric_snapshot_dimensions",
        ),
        # Constraints
        CheckConstraint("value >= 0", name="ck_metrics_value_positive"),
        CheckConstraint("count >= 0", name="ck_metrics_count_positive"),
        CheckConstraint("data_points >= 0", name="ck_metrics_data_points_positive"),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_metrics_confidence_range",
        ),
        CheckConstraint("period_end > period_start", name="ck_metrics_period_valid"),
    )


class TimeSeriesData(Base):
    """
    Time series support - Handle time-based data for trend analysis

    High-frequency time series data for detailed trend analysis and
    real-time monitoring of key metrics.
    """

    __tablename__ = "time_series_data"

    # Primary identification
    series_id = Column(String, primary_key=True, default=generate_uuid)

    # Series identification
    metric_name = Column(String(255), nullable=False, index=True)
    series_name = Column(
        String(255), nullable=False, index=True
    )  # Unique series identifier
    tags = Column(JSON, nullable=True, index=True)  # Series tags for filtering

    # Time dimension
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Data values
    value = Column(DECIMAL(20, 4), nullable=False)

    # Additional dimensions
    dimensions = Column(JSON, nullable=True)  # Flexible dimensions

    # Data quality
    quality_score = Column(Float, nullable=True)  # 0.0 to 1.0
    is_interpolated = Column(Boolean, nullable=False, default=False)
    is_anomaly = Column(Boolean, nullable=False, default=False)

    # Metadata
    source_system = Column(String(100), nullable=True)
    collection_method = Column(String(100), nullable=True)
    series_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Efficient indexing for time series queries
    __table_args__ = (
        # Time series specific indexes
        Index("idx_timeseries_metric_time", "metric_name", "timestamp"),
        Index("idx_timeseries_series_time", "series_name", "timestamp"),
        Index("idx_timeseries_timestamp_desc", "timestamp"),
        # Anomaly detection indexes
        Index("idx_timeseries_anomalies", "timestamp"),
        Index("idx_timeseries_quality", "quality_score", "timestamp"),
        # Unique constraint for time series uniqueness
        UniqueConstraint("series_name", "timestamp", name="uq_timeseries_series_time"),
        # Constraints
        CheckConstraint(
            "quality_score >= 0 AND quality_score <= 1",
            name="ck_timeseries_quality_range",
        ),
    )


class DashboardMetric(Base):
    """
    Dashboard metrics model for real-time analytics display

    Optimized for fast dashboard queries with pre-calculated values
    and efficient caching.
    """

    __tablename__ = "dashboard_metrics"

    # Primary identification
    metric_id = Column(String, primary_key=True, default=generate_uuid)

    # Dashboard organization
    dashboard_name = Column(String(255), nullable=False, index=True)
    widget_name = Column(String(255), nullable=False, index=True)
    metric_name = Column(String(255), nullable=False, index=True)
    display_order = Column(Integer, nullable=False, default=0)

    # Current value
    current_value = Column(DECIMAL(20, 4), nullable=False)
    previous_value = Column(DECIMAL(20, 4), nullable=True)
    change_value = Column(DECIMAL(20, 4), nullable=True)
    change_percentage = Column(DECIMAL(10, 4), nullable=True)

    # Display formatting
    display_format = Column(
        String(50), nullable=True
    )  # currency, percentage, number, etc.
    display_units = Column(String(20), nullable=True)  # $, %, count, etc.
    decimal_places = Column(Integer, nullable=False, default=2)

    # Status and alerting
    status = Column(String(20), nullable=True)  # good, warning, critical
    threshold_warning = Column(DECIMAL(20, 4), nullable=True)
    threshold_critical = Column(DECIMAL(20, 4), nullable=True)

    # Time context
    time_period = Column(
        String(50), nullable=False
    )  # last_hour, today, this_week, etc.
    last_calculated = Column(DateTime(timezone=True), nullable=False, index=True)
    next_calculation = Column(DateTime(timezone=True), nullable=True, index=True)

    # Caching and performance
    cache_ttl_seconds = Column(
        Integer, nullable=False, default=300
    )  # 5 minutes default
    is_stale = Column(Boolean, nullable=False, default=False)
    calculation_duration_ms = Column(Integer, nullable=True)

    # Configuration
    config = Column(JSON, nullable=True)  # Widget configuration

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()
    )

    # Efficient indexing for dashboard queries
    __table_args__ = (
        # Dashboard query optimization
        Index(
            "idx_dashboard_metrics_dashboard_order", "dashboard_name", "display_order"
        ),
        Index("idx_dashboard_metrics_widget_order", "widget_name", "display_order"),
        Index("idx_dashboard_metrics_stale", "is_stale", "next_calculation"),
        Index("idx_dashboard_metrics_calculated", "last_calculated"),
        # Unique constraint for dashboard organization
        UniqueConstraint(
            "dashboard_name",
            "widget_name",
            "metric_name",
            name="uq_dashboard_widget_metric",
        ),
        # Constraints
        CheckConstraint(
            "decimal_places >= 0 AND decimal_places <= 10",
            name="ck_dashboard_decimal_places",
        ),
        CheckConstraint(
            "cache_ttl_seconds > 0", name="ck_dashboard_cache_ttl_positive"
        ),
        CheckConstraint(
            "calculation_duration_ms >= 0", name="ck_dashboard_duration_positive"
        ),
    )


class FunnelConversion(Base):
    """
    Funnel conversion tracking model

    Tracks conversion rates between funnel stages for optimization analysis.
    """

    __tablename__ = "funnel_conversions"

    # Primary identification
    conversion_id = Column(String, primary_key=True, default=generate_uuid)

    # Conversion tracking
    from_stage = Column(SQLEnum(FunnelStage), nullable=False, index=True)
    to_stage = Column(SQLEnum(FunnelStage), nullable=False, index=True)

    # Cohort tracking
    cohort_date = Column(Date, nullable=False, index=True)
    campaign_id = Column(String, nullable=True, index=True)
    business_vertical = Column(String(100), nullable=True, index=True)

    # Conversion metrics
    started_count = Column(Integer, nullable=False, default=0)
    completed_count = Column(Integer, nullable=False, default=0)
    conversion_rate = Column(DECIMAL(10, 4), nullable=False, default=0)

    # Time metrics
    avg_time_to_convert_hours = Column(DECIMAL(10, 2), nullable=True)
    median_time_to_convert_hours = Column(DECIMAL(10, 2), nullable=True)

    # Value metrics
    avg_value = Column(DECIMAL(20, 4), nullable=True)
    total_value = Column(DECIMAL(20, 4), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()
    )

    # Efficient indexing for conversion analysis
    __table_args__ = (
        # Conversion analysis indexes
        Index("idx_conversions_stages_date", "from_stage", "to_stage", "cohort_date"),
        Index("idx_conversions_campaign_date", "campaign_id", "cohort_date"),
        Index("idx_conversions_vertical_date", "business_vertical", "cohort_date"),
        Index("idx_conversions_rate_date", "conversion_rate", "cohort_date"),
        # Unique constraint for conversion tracking
        UniqueConstraint(
            "from_stage",
            "to_stage",
            "cohort_date",
            "campaign_id",
            "business_vertical",
            name="uq_funnel_conversion_dimensions",
        ),
        # Constraints
        CheckConstraint("started_count >= 0", name="ck_conversions_started_positive"),
        CheckConstraint(
            "completed_count >= 0", name="ck_conversions_completed_positive"
        ),
        CheckConstraint(
            "completed_count <= started_count", name="ck_conversions_completed_valid"
        ),
        CheckConstraint(
            "conversion_rate >= 0 AND conversion_rate <= 1",
            name="ck_conversions_rate_range",
        ),
        CheckConstraint(
            "avg_time_to_convert_hours >= 0", name="ck_conversions_time_positive"
        ),
    )
