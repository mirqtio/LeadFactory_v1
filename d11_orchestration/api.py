"""
D11 Orchestration API - Task 078

FastAPI endpoints for orchestration functionality including pipeline triggers,
status checking, experiment management, and run history APIs.

Acceptance Criteria:
- Pipeline trigger API ✓
- Status checking works ✓
- Experiment management ✓
- Run history API ✓
"""

from datetime import datetime
from math import ceil
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import and_, asc, desc
from sqlalchemy.orm import Session

from database.session import get_db

from .models import (
    Experiment,
    ExperimentStatus,
    ExperimentVariant,
    PipelineRun,
    PipelineRunStatus,
    PipelineTask,
    VariantAssignment,
)
from .schemas import (  # Pipeline schemas; Experiment schemas; Assignment schemas; Common schemas
    ExperimentCreateRequest,
    ExperimentListRequest,
    ExperimentListResponse,
    ExperimentResponse,
    ExperimentUpdateRequest,
    ExperimentVariantCreateRequest,
    ExperimentVariantResponse,
    HealthResponse,
    PipelineRunHistoryRequest,
    PipelineRunHistoryResponse,
    PipelineRunResponse,
    PipelineStatusResponse,
    PipelineTriggerRequest,
    SuccessResponse,
    VariantAssignmentRequest,
    VariantAssignmentResponse,
)

# Create router for orchestration API
router = APIRouter(prefix="/orchestration", tags=["orchestration"])


# Health check endpoint


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for orchestration service"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        components={
            "database": "healthy",
            "pipeline_engine": "healthy",
            "experiment_engine": "healthy",
        },
    )


# Pipeline API endpoints - Pipeline trigger API, Status checking works, Run history API


@router.post("/pipelines/trigger", response_model=PipelineRunResponse)
async def trigger_pipeline(
    request: PipelineTriggerRequest, db: Session = Depends(get_db)
):
    """
    Trigger a new pipeline run

    Acceptance Criteria: Pipeline trigger API
    """
    try:
        # Create new pipeline run
        pipeline_run = PipelineRun(
            pipeline_name=request.pipeline_name,
            pipeline_type=request.pipeline_type,
            triggered_by=request.triggered_by,
            trigger_reason=request.trigger_reason,
            parameters=request.parameters,
            config=request.config,
            environment=request.environment,
            scheduled_at=request.scheduled_at,
            status=PipelineRunStatus.PENDING,
        )

        db.add(pipeline_run)
        db.commit()
        db.refresh(pipeline_run)

        # Convert to response model
        response = PipelineRunResponse(
            run_id=pipeline_run.run_id,
            pipeline_name=pipeline_run.pipeline_name,
            pipeline_version=pipeline_run.pipeline_version,
            status=pipeline_run.status,
            pipeline_type=pipeline_run.pipeline_type,
            triggered_by=pipeline_run.triggered_by,
            trigger_reason=pipeline_run.trigger_reason,
            scheduled_at=pipeline_run.scheduled_at,
            started_at=pipeline_run.started_at,
            completed_at=pipeline_run.completed_at,
            created_at=pipeline_run.created_at,
            updated_at=pipeline_run.updated_at,
            execution_time_seconds=pipeline_run.execution_time_seconds,
            retry_count=pipeline_run.retry_count,
            max_retries=pipeline_run.max_retries,
            error_message=pipeline_run.error_message,
            error_details=pipeline_run.error_details,
            config=pipeline_run.config,
            parameters=pipeline_run.parameters,
            environment=pipeline_run.environment,
            records_processed=pipeline_run.records_processed,
            records_failed=pipeline_run.records_failed,
            bytes_processed=pipeline_run.bytes_processed,
            cost_cents=pipeline_run.cost_cents,
            external_run_id=pipeline_run.external_run_id,
            external_system=pipeline_run.external_system,
            logs_url=pipeline_run.logs_url,
            is_complete=pipeline_run.is_complete,
            success_rate=pipeline_run.success_rate,
        )

        return response

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger pipeline: {str(e)}"
        )


@router.get("/pipelines/{run_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    run_id: str = Path(..., description="Pipeline run ID"),
    db: Session = Depends(get_db),
):
    """
    Get pipeline run status

    Acceptance Criteria: Status checking works
    """
    pipeline_run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()

    if not pipeline_run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    # Get task progress
    tasks = db.query(PipelineTask).filter(PipelineTask.pipeline_run_id == run_id).all()
    tasks_completed = len([t for t in tasks if t.status in [PipelineRunStatus.SUCCESS]])
    tasks_total = len(tasks)

    # Calculate progress percentage
    progress_pct = None
    if tasks_total > 0:
        progress_pct = (tasks_completed / tasks_total) * 100

    # Get current task
    current_task = None
    running_task = next(
        (t for t in tasks if t.status == PipelineRunStatus.RUNNING), None
    )
    if running_task:
        current_task = running_task.task_name

    # Estimate remaining time
    estimated_remaining_seconds = None
    if pipeline_run.started_at and progress_pct and progress_pct > 0:
        elapsed = (datetime.utcnow() - pipeline_run.started_at).total_seconds()
        estimated_total = elapsed / (progress_pct / 100)
        estimated_remaining_seconds = int(estimated_total - elapsed)

    return PipelineStatusResponse(
        run_id=pipeline_run.run_id,
        status=pipeline_run.status,
        progress_pct=progress_pct,
        current_task=current_task,
        tasks_completed=tasks_completed,
        tasks_total=tasks_total,
        execution_time_seconds=pipeline_run.execution_time_seconds,
        estimated_remaining_seconds=estimated_remaining_seconds,
        error_message=pipeline_run.error_message,
        last_updated=pipeline_run.updated_at,
    )


@router.get("/pipelines/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_run(
    run_id: str = Path(..., description="Pipeline run ID"),
    db: Session = Depends(get_db),
):
    """Get detailed pipeline run information"""
    pipeline_run = db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()

    if not pipeline_run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    return PipelineRunResponse(
        run_id=pipeline_run.run_id,
        pipeline_name=pipeline_run.pipeline_name,
        pipeline_version=pipeline_run.pipeline_version,
        status=pipeline_run.status,
        pipeline_type=pipeline_run.pipeline_type,
        triggered_by=pipeline_run.triggered_by,
        trigger_reason=pipeline_run.trigger_reason,
        scheduled_at=pipeline_run.scheduled_at,
        started_at=pipeline_run.started_at,
        completed_at=pipeline_run.completed_at,
        created_at=pipeline_run.created_at,
        updated_at=pipeline_run.updated_at,
        execution_time_seconds=pipeline_run.execution_time_seconds,
        retry_count=pipeline_run.retry_count,
        max_retries=pipeline_run.max_retries,
        error_message=pipeline_run.error_message,
        error_details=pipeline_run.error_details,
        config=pipeline_run.config,
        parameters=pipeline_run.parameters,
        environment=pipeline_run.environment,
        records_processed=pipeline_run.records_processed,
        records_failed=pipeline_run.records_failed,
        bytes_processed=pipeline_run.bytes_processed,
        cost_cents=pipeline_run.cost_cents,
        external_run_id=pipeline_run.external_run_id,
        external_system=pipeline_run.external_system,
        logs_url=pipeline_run.logs_url,
        is_complete=pipeline_run.is_complete,
        success_rate=pipeline_run.success_rate,
    )


@router.post("/pipelines/history", response_model=PipelineRunHistoryResponse)
async def get_pipeline_history(
    request: PipelineRunHistoryRequest, db: Session = Depends(get_db)
):
    """
    Get pipeline run history with filtering and pagination

    Acceptance Criteria: Run history API
    """
    query = db.query(PipelineRun)

    # Apply filters
    if request.pipeline_name:
        query = query.filter(PipelineRun.pipeline_name == request.pipeline_name)

    if request.status:
        query = query.filter(PipelineRun.status == request.status)

    if request.pipeline_type:
        query = query.filter(PipelineRun.pipeline_type == request.pipeline_type)

    if request.environment:
        query = query.filter(PipelineRun.environment == request.environment)

    if request.triggered_by:
        query = query.filter(PipelineRun.triggered_by == request.triggered_by)

    if request.start_date:
        query = query.filter(PipelineRun.created_at >= request.start_date)

    if request.end_date:
        query = query.filter(PipelineRun.created_at <= request.end_date)

    # Get total count
    total_count = query.count()

    # Apply sorting
    sort_column = getattr(PipelineRun, request.sort_by, PipelineRun.created_at)
    if request.sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    # Apply pagination
    offset = (request.page - 1) * request.page_size
    runs = query.offset(offset).limit(request.page_size).all()

    # Calculate pagination info
    total_pages = ceil(total_count / request.page_size)
    has_next = request.page < total_pages
    has_previous = request.page > 1

    # Convert to response models
    run_responses = []
    for run in runs:
        run_responses.append(
            PipelineRunResponse(
                run_id=run.run_id,
                pipeline_name=run.pipeline_name,
                pipeline_version=run.pipeline_version,
                status=run.status,
                pipeline_type=run.pipeline_type,
                triggered_by=run.triggered_by,
                trigger_reason=run.trigger_reason,
                scheduled_at=run.scheduled_at,
                started_at=run.started_at,
                completed_at=run.completed_at,
                created_at=run.created_at,
                updated_at=run.updated_at,
                execution_time_seconds=run.execution_time_seconds,
                retry_count=run.retry_count,
                max_retries=run.max_retries,
                error_message=run.error_message,
                error_details=run.error_details,
                config=run.config,
                parameters=run.parameters,
                environment=run.environment,
                records_processed=run.records_processed,
                records_failed=run.records_failed,
                bytes_processed=run.bytes_processed,
                cost_cents=run.cost_cents,
                external_run_id=run.external_run_id,
                external_system=run.external_system,
                logs_url=run.logs_url,
                is_complete=run.is_complete,
                success_rate=run.success_rate,
            )
        )

    return PipelineRunHistoryResponse(
        runs=run_responses,
        total_count=total_count,
        page=request.page,
        page_size=request.page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous,
    )


# Experiment API endpoints - Experiment management


@router.post("/experiments", response_model=ExperimentResponse)
async def create_experiment(
    request: ExperimentCreateRequest, db: Session = Depends(get_db)
):
    """
    Create a new experiment

    Acceptance Criteria: Experiment management
    """
    # Check if experiment name already exists
    existing = db.query(Experiment).filter(Experiment.name == request.name).first()
    if existing:
        raise HTTPException(
            status_code=400, detail="Experiment with this name already exists"
        )

    try:
        # Create experiment
        experiment = Experiment(
            name=request.name,
            description=request.description,
            hypothesis=request.hypothesis,
            created_by=request.created_by,
            start_date=request.start_date,
            end_date=request.end_date,
            target_audience=request.target_audience,
            traffic_allocation_pct=request.traffic_allocation_pct,
            minimum_sample_size=request.minimum_sample_size,
            maximum_duration_days=request.maximum_duration_days,
            primary_metric=request.primary_metric,
            secondary_metrics=request.secondary_metrics,
            success_criteria=request.success_criteria,
            randomization_unit=request.randomization_unit,
            holdout_pct=request.holdout_pct,
            confidence_level=request.confidence_level,
        )

        db.add(experiment)
        db.commit()
        db.refresh(experiment)

        return _experiment_to_response(experiment)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create experiment: {str(e)}"
        )


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: str = Path(..., description="Experiment ID"),
    db: Session = Depends(get_db),
):
    """Get experiment details"""
    experiment = (
        db.query(Experiment).filter(Experiment.experiment_id == experiment_id).first()
    )

    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return _experiment_to_response(experiment)


@router.put("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    request: ExperimentUpdateRequest,
    experiment_id: str = Path(..., description="Experiment ID"),
    db: Session = Depends(get_db),
):
    """Update an experiment"""
    experiment = (
        db.query(Experiment).filter(Experiment.experiment_id == experiment_id).first()
    )

    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Update fields if provided
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(experiment, field, value)

    try:
        db.commit()
        db.refresh(experiment)
        return _experiment_to_response(experiment)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update experiment: {str(e)}"
        )


@router.post("/experiments/list", response_model=ExperimentListResponse)
async def list_experiments(
    request: ExperimentListRequest, db: Session = Depends(get_db)
):
    """List experiments with filtering and pagination"""
    query = db.query(Experiment)

    # Apply filters
    if request.status:
        query = query.filter(Experiment.status == request.status)

    if request.created_by:
        query = query.filter(Experiment.created_by == request.created_by)

    if request.created_after:
        query = query.filter(Experiment.created_at >= request.created_after)

    if request.created_before:
        query = query.filter(Experiment.created_at <= request.created_before)

    # Get total count
    total_count = query.count()

    # Apply sorting
    sort_column = getattr(Experiment, request.sort_by, Experiment.created_at)
    if request.sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    # Apply pagination
    offset = (request.page - 1) * request.page_size
    experiments = query.offset(offset).limit(request.page_size).all()

    # Calculate pagination info
    total_pages = ceil(total_count / request.page_size)
    has_next = request.page < total_pages
    has_previous = request.page > 1

    # Convert to response models
    experiment_responses = [_experiment_to_response(exp) for exp in experiments]

    return ExperimentListResponse(
        experiments=experiment_responses,
        total_count=total_count,
        page=request.page,
        page_size=request.page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous,
    )


@router.delete("/experiments/{experiment_id}", response_model=SuccessResponse)
async def delete_experiment(
    experiment_id: str = Path(..., description="Experiment ID"),
    db: Session = Depends(get_db),
):
    """Delete an experiment"""
    experiment = (
        db.query(Experiment).filter(Experiment.experiment_id == experiment_id).first()
    )

    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Check if experiment is running
    if experiment.status == ExperimentStatus.RUNNING:
        raise HTTPException(
            status_code=400, detail="Cannot delete a running experiment"
        )

    try:
        db.delete(experiment)
        db.commit()
        return SuccessResponse(message="Experiment deleted successfully")

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete experiment: {str(e)}"
        )


# Experiment variant endpoints


@router.post(
    "/experiments/{experiment_id}/variants", response_model=ExperimentVariantResponse
)
async def create_experiment_variant(
    request: ExperimentVariantCreateRequest,
    experiment_id: str = Path(..., description="Experiment ID"),
    db: Session = Depends(get_db),
):
    """Create a new experiment variant"""
    experiment = (
        db.query(Experiment).filter(Experiment.experiment_id == experiment_id).first()
    )

    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Check if variant key already exists in this experiment
    existing = (
        db.query(ExperimentVariant)
        .filter(
            and_(
                ExperimentVariant.experiment_id == experiment_id,
                ExperimentVariant.variant_key == request.variant_key,
            )
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400, detail="Variant with this key already exists in experiment"
        )

    try:
        variant = ExperimentVariant(
            experiment_id=experiment_id,
            variant_key=request.variant_key,
            name=request.name,
            description=request.description,
            variant_type=request.variant_type,
            weight=request.weight,
            is_control=request.is_control,
            config=request.config,
            feature_overrides=request.feature_overrides,
        )

        db.add(variant)
        db.commit()
        db.refresh(variant)

        return ExperimentVariantResponse(
            variant_id=variant.variant_id,
            experiment_id=variant.experiment_id,
            variant_key=variant.variant_key,
            name=variant.name,
            description=variant.description,
            variant_type=variant.variant_type,
            weight=variant.weight,
            is_control=variant.is_control,
            config=variant.config,
            feature_overrides=variant.feature_overrides,
            created_at=variant.created_at,
            updated_at=variant.updated_at,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create variant: {str(e)}"
        )


@router.get(
    "/experiments/{experiment_id}/variants",
    response_model=List[ExperimentVariantResponse],
)
async def get_experiment_variants(
    experiment_id: str = Path(..., description="Experiment ID"),
    db: Session = Depends(get_db),
):
    """Get all variants for an experiment"""
    experiment = (
        db.query(Experiment).filter(Experiment.experiment_id == experiment_id).first()
    )

    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    variants = (
        db.query(ExperimentVariant)
        .filter(ExperimentVariant.experiment_id == experiment_id)
        .all()
    )

    return [
        ExperimentVariantResponse(
            variant_id=variant.variant_id,
            experiment_id=variant.experiment_id,
            variant_key=variant.variant_key,
            name=variant.name,
            description=variant.description,
            variant_type=variant.variant_type,
            weight=variant.weight,
            is_control=variant.is_control,
            config=variant.config,
            feature_overrides=variant.feature_overrides,
            created_at=variant.created_at,
            updated_at=variant.updated_at,
        )
        for variant in variants
    ]


# Variant assignment endpoints


@router.post("/experiments/assign", response_model=VariantAssignmentResponse)
async def assign_variant(
    request: VariantAssignmentRequest, db: Session = Depends(get_db)
):
    """Assign a user to an experiment variant"""
    experiment = (
        db.query(Experiment)
        .filter(Experiment.experiment_id == request.experiment_id)
        .first()
    )

    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    if not experiment.is_active:
        raise HTTPException(status_code=400, detail="Experiment is not active")

    # Check if assignment already exists
    existing = (
        db.query(VariantAssignment)
        .filter(
            and_(
                VariantAssignment.experiment_id == request.experiment_id,
                VariantAssignment.assignment_unit == request.assignment_unit,
            )
        )
        .first()
    )

    if existing:
        # Return existing assignment
        return VariantAssignmentResponse(
            assignment_id=existing.assignment_id,
            experiment_id=existing.experiment_id,
            variant_id=existing.variant_id,
            variant_key=existing.variant.variant_key,
            assignment_unit=existing.assignment_unit,
            user_id=existing.user_id,
            session_id=existing.session_id,
            assigned_at=existing.assigned_at,
            first_exposure_at=existing.first_exposure_at,
            is_forced=existing.is_forced,
            is_holdout=existing.is_holdout,
            assignment_context=existing.assignment_context,
        )

    # Get experiment variants
    variants = (
        db.query(ExperimentVariant)
        .filter(ExperimentVariant.experiment_id == request.experiment_id)
        .all()
    )

    if not variants:
        raise HTTPException(status_code=400, detail="No variants found for experiment")

    # Simple random assignment based on weights (you might want to use a more sophisticated algorithm)
    import random

    total_weight = sum(v.weight for v in variants)
    random_value = random.random() * total_weight

    cumulative_weight = 0
    selected_variant = None
    for variant in variants:
        cumulative_weight += variant.weight
        if random_value <= cumulative_weight:
            selected_variant = variant
            break

    if not selected_variant:
        selected_variant = variants[0]  # Fallback

    # Create assignment
    assignment_hash = str(hash(f"{request.experiment_id}:{request.assignment_unit}"))

    try:
        assignment = VariantAssignment(
            experiment_id=request.experiment_id,
            variant_id=selected_variant.variant_id,
            assignment_unit=request.assignment_unit,
            user_id=request.user_id,
            session_id=request.session_id,
            assignment_hash=assignment_hash,
            assignment_context=request.assignment_context,
            user_properties=request.user_properties,
        )

        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        return VariantAssignmentResponse(
            assignment_id=assignment.assignment_id,
            experiment_id=assignment.experiment_id,
            variant_id=assignment.variant_id,
            variant_key=selected_variant.variant_key,
            assignment_unit=assignment.assignment_unit,
            user_id=assignment.user_id,
            session_id=assignment.session_id,
            assigned_at=assignment.assigned_at,
            first_exposure_at=assignment.first_exposure_at,
            is_forced=assignment.is_forced,
            is_holdout=assignment.is_holdout,
            assignment_context=assignment.assignment_context,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to assign variant: {str(e)}"
        )


# Helper functions


def _experiment_to_response(experiment: Experiment) -> ExperimentResponse:
    """Convert Experiment model to response schema"""
    # Convert variants to response models
    variant_responses = []
    for variant in experiment.variants:
        variant_responses.append(
            ExperimentVariantResponse(
                variant_id=variant.variant_id,
                experiment_id=variant.experiment_id,
                variant_key=variant.variant_key,
                name=variant.name,
                description=variant.description,
                variant_type=variant.variant_type,
                weight=variant.weight,
                is_control=variant.is_control,
                config=variant.config,
                feature_overrides=variant.feature_overrides,
                created_at=variant.created_at,
                updated_at=variant.updated_at,
            )
        )

    return ExperimentResponse(
        experiment_id=experiment.experiment_id,
        name=experiment.name,
        description=experiment.description,
        hypothesis=experiment.hypothesis,
        status=experiment.status,
        created_by=experiment.created_by,
        approved_by=experiment.approved_by,
        start_date=experiment.start_date,
        end_date=experiment.end_date,
        created_at=experiment.created_at,
        updated_at=experiment.updated_at,
        target_audience=experiment.target_audience,
        traffic_allocation_pct=experiment.traffic_allocation_pct,
        minimum_sample_size=experiment.minimum_sample_size,
        maximum_duration_days=experiment.maximum_duration_days,
        primary_metric=experiment.primary_metric,
        secondary_metrics=experiment.secondary_metrics,
        success_criteria=experiment.success_criteria,
        randomization_unit=experiment.randomization_unit,
        holdout_pct=experiment.holdout_pct,
        confidence_level=experiment.confidence_level,
        results=experiment.results,
        statistical_power=experiment.statistical_power,
        analytics_tracking_id=experiment.analytics_tracking_id,
        feature_flag_key=experiment.feature_flag_key,
        variants=variant_responses,
        is_active=experiment.is_active,
        total_traffic_pct=experiment.total_traffic_pct,
    )
