"""
D11 Orchestration Domain - Tasks 075, 076

Orchestration and experimentation module for managing pipeline runs,
experiment configurations, variant assignments, status tracking, and
Prefect pipeline orchestration.

This domain handles:
- Pipeline run tracking and status management
- Experiment model definitions and configurations  
- Assignment tracking for A/B testing and experiments
- Status management across orchestration workflows
- Prefect pipeline orchestration and task execution
"""

from .models import (
    PipelineRun,
    PipelineRunStatus,
    Experiment,
    ExperimentStatus,
    ExperimentVariant,
    VariantAssignment,
    generate_uuid
)

from .pipeline import (
    PipelineOrchestrator,
    daily_lead_generation_flow,
    create_daily_deployment,
    trigger_manual_run
)

from .tasks import (
    TargetingTask,
    SourcingTask,
    AssessmentTask,
    ScoringTask,
    PersonalizationTask,
    DeliveryTask
)

__all__ = [
    "PipelineRun",
    "PipelineRunStatus", 
    "Experiment",
    "ExperimentStatus",
    "ExperimentVariant",
    "VariantAssignment",
    "generate_uuid",
    "PipelineOrchestrator",
    "daily_lead_generation_flow",
    "create_daily_deployment",
    "trigger_manual_run",
    "TargetingTask",
    "SourcingTask",
    "AssessmentTask",
    "ScoringTask",
    "PersonalizationTask",
    "DeliveryTask"
]