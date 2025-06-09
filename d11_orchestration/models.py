"""
D11 Orchestration Models - Task 075

Database models for orchestration and experimentation including pipeline run tracking,
experiment configurations, variant assignments, and comprehensive status management.

Acceptance Criteria:
- Pipeline run tracking ✓
- Experiment models ✓  
- Assignment tracking ✓
- Status management ✓
"""

import uuid
import enum
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from decimal import Decimal

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
    DECIMAL, JSON, Date, TIMESTAMP, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.base import Base


def generate_uuid():
    """Generate a new UUID"""
    return str(uuid.uuid4())


# Enums for orchestration

class PipelineRunStatus(str, enum.Enum):
    """Status values for pipeline runs"""
    PENDING = "pending"           # Pipeline scheduled but not started
    RUNNING = "running"           # Pipeline currently executing
    SUCCESS = "success"           # Pipeline completed successfully
    FAILED = "failed"             # Pipeline failed with errors
    CANCELLED = "cancelled"       # Pipeline was cancelled by user
    TIMEOUT = "timeout"           # Pipeline exceeded time limit
    RETRYING = "retrying"         # Pipeline is being retried after failure
    PAUSED = "paused"             # Pipeline temporarily paused


class ExperimentStatus(str, enum.Enum):
    """Status values for experiments"""
    DRAFT = "draft"               # Experiment being designed
    SCHEDULED = "scheduled"       # Experiment scheduled to start
    RUNNING = "running"           # Experiment actively running
    PAUSED = "paused"             # Experiment temporarily paused
    COMPLETED = "completed"       # Experiment completed successfully
    STOPPED = "stopped"           # Experiment stopped early
    FAILED = "failed"             # Experiment failed to execute


class VariantType(str, enum.Enum):
    """Types of experiment variants"""
    CONTROL = "control"           # Control group baseline
    TREATMENT = "treatment"       # Treatment variant
    HOLDOUT = "holdout"           # Holdout group (no treatment)


class PipelineType(str, enum.Enum):
    """Types of orchestration pipelines"""
    DAILY_BATCH = "daily_batch"           # Daily batch processing
    REAL_TIME = "real_time"               # Real-time processing
    BACKFILL = "backfill"                 # Historical data backfill
    EXPERIMENT = "experiment"             # Experiment execution
    MANUAL = "manual"                     # Manual trigger
    SCHEDULED = "scheduled"               # Scheduled execution


# Core orchestration models

class PipelineRun(Base):
    """
    Pipeline run tracking model - Pipeline run tracking
    
    Tracks execution of orchestration pipelines including status, timing,
    configuration, and detailed execution metrics.
    """
    __tablename__ = "pipeline_runs"
    
    # Primary identification
    run_id = Column(String(36), primary_key=True, default=generate_uuid)
    pipeline_name = Column(String(255), nullable=False, index=True)
    pipeline_version = Column(String(50), nullable=False, default="1.0.0")
    
    # Execution metadata
    status = Column(SQLEnum(PipelineRunStatus), nullable=False, default=PipelineRunStatus.PENDING, index=True)
    pipeline_type = Column(SQLEnum(PipelineType), nullable=False, default=PipelineType.MANUAL)
    triggered_by = Column(String(255), nullable=True)  # User or system that triggered
    trigger_reason = Column(String(500), nullable=True)  # Why the pipeline was triggered
    
    # Timing information
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True, index=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # Execution details
    execution_time_seconds = Column(Integer, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Configuration and parameters
    config = Column(JSON, nullable=True)  # Pipeline configuration
    parameters = Column(JSON, nullable=True)  # Execution parameters
    environment = Column(String(50), nullable=False, default="production")
    
    # Metrics and performance
    records_processed = Column(Integer, nullable=True, default=0)
    records_failed = Column(Integer, nullable=True, default=0)
    bytes_processed = Column(Integer, nullable=True, default=0)
    cost_cents = Column(Integer, nullable=True, default=0)
    
    # External system integration
    external_run_id = Column(String(255), nullable=True)  # Prefect/Airflow run ID
    external_system = Column(String(100), nullable=True)  # e.g., "prefect", "airflow"
    logs_url = Column(String(1000), nullable=True)  # Link to execution logs
    
    # Relationships
    experiment_assignments = relationship("VariantAssignment", back_populates="pipeline_run")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_pipeline_runs_status_created', 'status', 'created_at'),
        Index('idx_pipeline_runs_name_started', 'pipeline_name', 'started_at'),
        Index('idx_pipeline_runs_type_environment', 'pipeline_type', 'environment'),
        CheckConstraint('retry_count <= max_retries', name='check_retry_count'),
        CheckConstraint('records_failed <= records_processed', name='check_failed_records'),
    )
    
    def __repr__(self):
        return f"<PipelineRun(run_id={self.run_id}, name={self.pipeline_name}, status={self.status})>"
    
    @property
    def is_complete(self) -> bool:
        """Check if pipeline run is in a terminal state"""
        return self.status in [
            PipelineRunStatus.SUCCESS,
            PipelineRunStatus.FAILED,
            PipelineRunStatus.CANCELLED,
            PipelineRunStatus.TIMEOUT
        ]
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate for processed records"""
        if self.records_processed == 0:
            return 0.0
        return (self.records_processed - (self.records_failed or 0)) / self.records_processed
    
    def calculate_duration(self) -> Optional[int]:
        """Calculate execution duration in seconds"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        return None


class Experiment(Base):
    """
    Experiment model for A/B testing and experimentation - Experiment models
    
    Defines experiment configurations including variants, traffic allocation,
    success metrics, and experiment lifecycle management.
    """
    __tablename__ = "experiments"
    
    # Primary identification
    experiment_id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    hypothesis = Column(Text, nullable=True)
    
    # Experiment lifecycle
    status = Column(SQLEnum(ExperimentStatus), nullable=False, default=ExperimentStatus.DRAFT, index=True)
    created_by = Column(String(255), nullable=False)
    approved_by = Column(String(255), nullable=True)
    
    # Timing
    start_date = Column(Date, nullable=True, index=True)
    end_date = Column(Date, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # Targeting and traffic
    target_audience = Column(JSON, nullable=True)  # Audience selection criteria
    traffic_allocation_pct = Column(Float, nullable=False, default=100.0)  # % of users in experiment
    minimum_sample_size = Column(Integer, nullable=True)
    maximum_duration_days = Column(Integer, nullable=True, default=30)
    
    # Metrics and success criteria
    primary_metric = Column(String(255), nullable=False)  # Main success metric
    secondary_metrics = Column(JSON, nullable=True)  # Additional metrics to track
    success_criteria = Column(JSON, nullable=True)  # Statistical significance criteria
    
    # Configuration
    randomization_unit = Column(String(100), nullable=False, default="user_id")  # unit for random assignment
    holdout_pct = Column(Float, nullable=False, default=0.0)  # % held out from experiment
    force_assignment = Column(JSON, nullable=True)  # Force specific users to variants
    
    # Results and analysis
    results = Column(JSON, nullable=True)  # Experiment results summary
    statistical_power = Column(Float, nullable=True)  # Statistical power achieved
    confidence_level = Column(Float, nullable=False, default=0.95)
    
    # External integration
    analytics_tracking_id = Column(String(255), nullable=True)
    feature_flag_key = Column(String(255), nullable=True)
    
    # Relationships
    variants = relationship("ExperimentVariant", back_populates="experiment", cascade="all, delete-orphan")
    assignments = relationship("VariantAssignment", back_populates="experiment", cascade="all, delete-orphan")
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_experiments_status_start', 'status', 'start_date'),
        Index('idx_experiments_created_by', 'created_by'),
        CheckConstraint('traffic_allocation_pct >= 0 AND traffic_allocation_pct <= 100', name='check_traffic_allocation'),
        CheckConstraint('holdout_pct >= 0 AND holdout_pct <= 100', name='check_holdout_pct'),
        CheckConstraint('confidence_level > 0 AND confidence_level < 1', name='check_confidence_level'),
        CheckConstraint('end_date IS NULL OR end_date >= start_date', name='check_date_range'),
    )
    
    def __repr__(self):
        return f"<Experiment(id={self.experiment_id}, name={self.name}, status={self.status})>"
    
    @property
    def is_active(self) -> bool:
        """Check if experiment is currently active"""
        return self.status == ExperimentStatus.RUNNING
    
    @property
    def total_traffic_pct(self) -> float:
        """Calculate total traffic percentage including holdout"""
        return self.traffic_allocation_pct + self.holdout_pct
    
    def get_variant_weights(self) -> Dict[str, float]:
        """Get normalized variant weights"""
        if not self.variants:
            return {}
        
        total_weight = sum(v.weight for v in self.variants)
        if total_weight == 0:
            return {}
        
        return {v.variant_key: v.weight / total_weight for v in self.variants}


class ExperimentVariant(Base):
    """
    Experiment variant configuration - part of Experiment models
    
    Defines individual variants within an experiment including configuration,
    traffic allocation, and variant-specific parameters.
    """
    __tablename__ = "experiment_variants"
    
    # Primary identification
    variant_id = Column(String(36), primary_key=True, default=generate_uuid)
    experiment_id = Column(String(36), ForeignKey('experiments.experiment_id'), nullable=False, index=True)
    variant_key = Column(String(100), nullable=False)  # e.g., "control", "treatment_a"
    
    # Variant configuration
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    variant_type = Column(SQLEnum(VariantType), nullable=False, default=VariantType.TREATMENT)
    
    # Traffic allocation
    weight = Column(Float, nullable=False, default=1.0)  # Relative weight for assignment
    is_control = Column(Boolean, nullable=False, default=False)
    
    # Variant parameters
    config = Column(JSON, nullable=True)  # Variant-specific configuration
    feature_overrides = Column(JSON, nullable=True)  # Feature flag overrides
    
    # Metrics
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    experiment = relationship("Experiment", back_populates="variants")
    assignments = relationship("VariantAssignment", back_populates="variant")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('experiment_id', 'variant_key', name='uq_experiment_variant_key'),
        Index('idx_variants_experiment_type', 'experiment_id', 'variant_type'),
        CheckConstraint('weight >= 0', name='check_weight_positive'),
    )
    
    def __repr__(self):
        return f"<ExperimentVariant(id={self.variant_id}, key={self.variant_key}, type={self.variant_type})>"


class VariantAssignment(Base):
    """
    Assignment tracking for experiments - Assignment tracking
    
    Tracks which users/sessions are assigned to which experiment variants
    with deterministic hashing and assignment persistence.
    """
    __tablename__ = "variant_assignments"
    
    # Primary identification
    assignment_id = Column(String(36), primary_key=True, default=generate_uuid)
    experiment_id = Column(String(36), ForeignKey('experiments.experiment_id'), nullable=False, index=True)
    variant_id = Column(String(36), ForeignKey('experiment_variants.variant_id'), nullable=False, index=True)
    
    # Assignment details
    user_id = Column(String(255), nullable=True, index=True)  # User identifier
    session_id = Column(String(255), nullable=True, index=True)  # Session identifier  
    assignment_unit = Column(String(255), nullable=False, index=True)  # The actual unit assigned
    assignment_hash = Column(String(64), nullable=False)  # Hash used for assignment
    
    # Assignment metadata
    assigned_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    first_exposure_at = Column(DateTime, nullable=True)  # When user first saw variant
    pipeline_run_id = Column(String(36), ForeignKey('pipeline_runs.run_id'), nullable=True, index=True)
    
    # Context information
    assignment_context = Column(JSON, nullable=True)  # Context data at assignment time
    user_properties = Column(JSON, nullable=True)  # User properties at assignment
    experiment_version = Column(String(50), nullable=True)  # Experiment version at assignment
    
    # Tracking
    is_forced = Column(Boolean, nullable=False, default=False)  # Whether assignment was forced
    is_holdout = Column(Boolean, nullable=False, default=False)  # Whether user is in holdout
    
    # Relationships
    experiment = relationship("Experiment", back_populates="assignments")
    variant = relationship("ExperimentVariant", back_populates="assignments")
    pipeline_run = relationship("PipelineRun", back_populates="experiment_assignments")
    
    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint('experiment_id', 'assignment_unit', name='uq_experiment_assignment_unit'),
        Index('idx_assignments_user_experiment', 'user_id', 'experiment_id'),
        Index('idx_assignments_session_experiment', 'session_id', 'experiment_id'),
        Index('idx_assignments_assigned_at', 'assigned_at'),
        Index('idx_assignments_hash', 'assignment_hash'),
    )
    
    def __repr__(self):
        return f"<VariantAssignment(id={self.assignment_id}, unit={self.assignment_unit}, variant={self.variant_id})>"
    
    @property
    def exposure_delay_seconds(self) -> Optional[int]:
        """Calculate delay between assignment and first exposure"""
        if self.first_exposure_at and self.assigned_at:
            return int((self.first_exposure_at - self.assigned_at).total_seconds())
        return None


# Helper models for orchestration status management

class PipelineTask(Base):
    """
    Individual task within a pipeline run - Status management
    
    Tracks status and execution details of individual tasks within
    larger pipeline runs for granular monitoring and debugging.
    """
    __tablename__ = "pipeline_tasks"
    
    # Primary identification
    task_id = Column(String(36), primary_key=True, default=generate_uuid)
    pipeline_run_id = Column(String(36), ForeignKey('pipeline_runs.run_id'), nullable=False, index=True)
    task_name = Column(String(255), nullable=False, index=True)
    task_type = Column(String(100), nullable=False)
    
    # Execution status
    status = Column(SQLEnum(PipelineRunStatus), nullable=False, default=PipelineRunStatus.PENDING, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # Task details
    execution_order = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    
    # Results and errors
    output = Column(JSON, nullable=True)  # Task output data
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Performance metrics
    execution_time_seconds = Column(Integer, nullable=True)
    memory_usage_mb = Column(Integer, nullable=True)
    cpu_usage_pct = Column(Float, nullable=True)
    
    # Dependencies
    depends_on = Column(JSON, nullable=True)  # List of task dependencies
    
    # Relationships
    pipeline_run = relationship("PipelineRun")
    
    # Indexes
    __table_args__ = (
        Index('idx_tasks_pipeline_order', 'pipeline_run_id', 'execution_order'),
        Index('idx_tasks_name_status', 'task_name', 'status'),
        CheckConstraint('execution_order >= 0', name='check_execution_order'),
        CheckConstraint('retry_count <= max_retries', name='check_task_retry_count'),
    )
    
    def __repr__(self):
        return f"<PipelineTask(id={self.task_id}, name={self.task_name}, status={self.status})>"


class ExperimentMetric(Base):
    """
    Experiment metric tracking - Status management
    
    Stores metric values and statistical analysis for experiments
    to support decision making and result evaluation.
    """
    __tablename__ = "experiment_metrics"
    
    # Primary identification
    metric_id = Column(String(36), primary_key=True, default=generate_uuid)
    experiment_id = Column(String(36), ForeignKey('experiments.experiment_id'), nullable=False, index=True)
    variant_id = Column(String(36), ForeignKey('experiment_variants.variant_id'), nullable=False, index=True)
    
    # Metric details
    metric_name = Column(String(255), nullable=False, index=True)
    metric_date = Column(Date, nullable=False, index=True)
    
    # Metric values
    value = Column(DECIMAL(20, 6), nullable=False)
    sample_size = Column(Integer, nullable=False)
    confidence_interval_lower = Column(DECIMAL(20, 6), nullable=True)
    confidence_interval_upper = Column(DECIMAL(20, 6), nullable=True)
    
    # Statistical analysis
    p_value = Column(DECIMAL(10, 8), nullable=True)
    statistical_significance = Column(Boolean, nullable=True)
    effect_size = Column(DECIMAL(10, 6), nullable=True)
    
    # Metadata
    calculation_method = Column(String(100), nullable=True)
    data_quality_score = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    experiment = relationship("Experiment")
    variant = relationship("ExperimentVariant")
    
    # Indexes and constraints
    __table_args__ = (
        UniqueConstraint('experiment_id', 'variant_id', 'metric_name', 'metric_date', 
                        name='uq_experiment_variant_metric_date'),
        Index('idx_metrics_experiment_date', 'experiment_id', 'metric_date'),
        Index('idx_metrics_name_date', 'metric_name', 'metric_date'),
        CheckConstraint('sample_size > 0', name='check_sample_size_positive'),
        CheckConstraint('p_value IS NULL OR (p_value >= 0 AND p_value <= 1)', name='check_p_value_range'),
    )
    
    def __repr__(self):
        return f"<ExperimentMetric(id={self.metric_id}, metric={self.metric_name}, value={self.value})>"