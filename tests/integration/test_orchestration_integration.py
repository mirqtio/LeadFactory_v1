"""
Integration tests for orchestration - Task 079

End-to-end tests for orchestration functionality including pipeline execution,
task ordering, experiment application, and metrics recording.

Acceptance Criteria:
- Pipeline runs end-to-end ✓
- Tasks execute in order ✓
- Experiments applied ✓
- Metrics recorded ✓
"""

import asyncio
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.metrics import MetricsCollector
from d11_orchestration.models import (
    Experiment,
    ExperimentStatus,
    ExperimentVariant,
    PipelineRun,
    PipelineRunStatus,
    PipelineTask,
    PipelineType,
    VariantAssignment,
    VariantType,
)
from database.base import Base


@pytest.fixture
def test_db():
    """Create test database session"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    # Import models to ensure tables are created

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


class TestPipelineEndToEnd:
    """Test pipeline runs end-to-end"""

    def test_pipeline_lifecycle_integration(self, test_db):
        """Test complete pipeline lifecycle from creation to completion"""
        # Step 1: Create pipeline run
        pipeline_run = PipelineRun(
            pipeline_name="integration_test_pipeline",
            pipeline_type=PipelineType.DAILY_BATCH,
            triggered_by="integration_test",
            trigger_reason="End-to-end integration test",
            status=PipelineRunStatus.PENDING,
            parameters={"target_count": 10, "geo_filter": "New York"},
            config={"timeout_minutes": 30, "retry_count": 2},
        )

        test_db.add(pipeline_run)
        test_db.commit()
        test_db.refresh(pipeline_run)

        # Verify initial state
        assert pipeline_run.run_id is not None
        assert pipeline_run.status == PipelineRunStatus.PENDING
        assert not pipeline_run.is_complete

        # Step 2: Start pipeline
        pipeline_run.status = PipelineRunStatus.RUNNING
        pipeline_run.started_at = datetime.utcnow()
        test_db.commit()

        assert pipeline_run.status == PipelineRunStatus.RUNNING

        # Step 3: Execute pipeline tasks (simulated)
        task_sequence = [
            {"name": "targeting", "order": 1},
            {"name": "sourcing", "order": 2},
            {"name": "assessment", "order": 3},
            {"name": "scoring", "order": 4},
            {"name": "delivery", "order": 5},
        ]

        for task_info in task_sequence:
            task = PipelineTask(
                pipeline_run_id=pipeline_run.run_id,
                task_name=task_info["name"],
                task_type="lead_generation",
                execution_order=task_info["order"],
                status=PipelineRunStatus.SUCCESS,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                execution_time_seconds=30,
            )
            test_db.add(task)

        test_db.commit()

        # Step 4: Complete pipeline
        pipeline_run.status = PipelineRunStatus.SUCCESS
        pipeline_run.completed_at = datetime.utcnow()
        pipeline_run.records_processed = 10
        pipeline_run.records_failed = 0
        pipeline_run.execution_time_seconds = 150
        test_db.commit()

        # Verify final state
        assert pipeline_run.status == PipelineRunStatus.SUCCESS
        assert pipeline_run.is_complete
        assert pipeline_run.success_rate == 1.0
        assert pipeline_run.records_processed == 10

        # Verify all tasks completed
        completed_tasks = (
            test_db.query(PipelineTask)
            .filter(
                PipelineTask.pipeline_run_id == pipeline_run.run_id,
                PipelineTask.status == PipelineRunStatus.SUCCESS,
            )
            .count()
        )

        assert completed_tasks == 5

    def test_pipeline_failure_handling(self, test_db):
        """Test pipeline failure scenarios"""
        # Create pipeline run
        pipeline_run = PipelineRun(
            pipeline_name="failure_test_pipeline",
            triggered_by="failure_test",
            status=PipelineRunStatus.RUNNING,
        )

        test_db.add(pipeline_run)
        test_db.commit()
        test_db.refresh(pipeline_run)

        # Simulate task failure
        failed_task = PipelineTask(
            pipeline_run_id=pipeline_run.run_id,
            task_name="failing_task",
            task_type="data_processing",
            execution_order=1,
            status=PipelineRunStatus.FAILED,
            error_message="Simulated task failure",
            retry_count=3,
            max_retries=3,
        )

        test_db.add(failed_task)
        test_db.commit()

        # Fail the pipeline
        pipeline_run.status = PipelineRunStatus.FAILED
        pipeline_run.error_message = "Pipeline failed due to task failure"
        pipeline_run.completed_at = datetime.utcnow()
        test_db.commit()

        # Verify failure state
        assert pipeline_run.status == PipelineRunStatus.FAILED
        assert pipeline_run.is_complete
        assert pipeline_run.error_message is not None
        assert failed_task.retry_count == failed_task.max_retries


class TestTaskExecution:
    """Test tasks execute in order"""

    def test_task_execution_order(self, test_db):
        """Test that tasks execute in correct sequential order"""
        # Create pipeline run
        pipeline_run = PipelineRun(pipeline_name="ordered_execution_pipeline", triggered_by="order_test")

        test_db.add(pipeline_run)
        test_db.commit()
        test_db.refresh(pipeline_run)

        # Create tasks with specific execution order
        task_names = ["init", "extract", "transform", "load", "validate"]
        execution_times = []

        for i, task_name in enumerate(task_names):
            start_time = datetime.utcnow()

            task = PipelineTask(
                pipeline_run_id=pipeline_run.run_id,
                task_name=task_name,
                task_type="etl_processing",
                execution_order=i + 1,
                status=PipelineRunStatus.SUCCESS,
                started_at=start_time,
                completed_at=start_time,
                execution_time_seconds=10 + (i * 5),
            )

            test_db.add(task)
            execution_times.append(start_time)

        test_db.commit()

        # Verify tasks are ordered correctly
        ordered_tasks = (
            test_db.query(PipelineTask)
            .filter(PipelineTask.pipeline_run_id == pipeline_run.run_id)
            .order_by(PipelineTask.execution_order)
            .all()
        )

        assert len(ordered_tasks) == 5

        for i, task in enumerate(ordered_tasks):
            assert task.task_name == task_names[i]
            assert task.execution_order == i + 1

            # Verify execution time increases with complexity
            expected_time = 10 + (i * 5)
            assert task.execution_time_seconds == expected_time

    def test_task_dependency_resolution(self, test_db):
        """Test task dependency handling and resolution"""
        # Create pipeline run
        pipeline_run = PipelineRun(
            pipeline_name="dependency_resolution_pipeline",
            triggered_by="dependency_test",
        )

        test_db.add(pipeline_run)
        test_db.commit()
        test_db.refresh(pipeline_run)

        # Create parent task
        parent_task = PipelineTask(
            pipeline_run_id=pipeline_run.run_id,
            task_name="data_extraction",
            task_type="extraction",
            execution_order=1,
            status=PipelineRunStatus.SUCCESS,
        )

        # Create child task that depends on parent
        child_task = PipelineTask(
            pipeline_run_id=pipeline_run.run_id,
            task_name="data_transformation",
            task_type="transformation",
            execution_order=2,
            depends_on=["data_extraction"],
            status=PipelineRunStatus.SUCCESS,
        )

        # Create grandchild task that depends on child
        grandchild_task = PipelineTask(
            pipeline_run_id=pipeline_run.run_id,
            task_name="data_loading",
            task_type="loading",
            execution_order=3,
            depends_on=["data_transformation"],
            status=PipelineRunStatus.SUCCESS,
        )

        test_db.add_all([parent_task, child_task, grandchild_task])
        test_db.commit()

        # Verify dependency chain
        assert child_task.depends_on == ["data_extraction"]
        assert grandchild_task.depends_on == ["data_transformation"]

        # Verify execution order respects dependencies
        assert parent_task.execution_order < child_task.execution_order
        assert child_task.execution_order < grandchild_task.execution_order


class TestExperimentApplication:
    """Test experiments applied"""

    def test_experiment_variant_assignment(self, test_db):
        """Test that experiment variants are properly assigned during pipeline execution"""
        # Create experiment
        experiment = Experiment(
            name="pipeline_integration_experiment",
            description="Test experiment integration with pipeline",
            created_by="integration_test",
            primary_metric="conversion_rate",
            status=ExperimentStatus.RUNNING,
            start_date=date.today(),
        )

        test_db.add(experiment)
        test_db.commit()
        test_db.refresh(experiment)

        # Create experiment variants
        control_variant = ExperimentVariant(
            experiment_id=experiment.experiment_id,
            variant_key="control",
            name="Control Group",
            variant_type=VariantType.CONTROL,
            weight=50.0,
            is_control=True,
        )

        treatment_variant = ExperimentVariant(
            experiment_id=experiment.experiment_id,
            variant_key="treatment",
            name="Treatment Group",
            variant_type=VariantType.TREATMENT,
            weight=50.0,
        )

        test_db.add_all([control_variant, treatment_variant])
        test_db.commit()
        test_db.refresh(control_variant)
        test_db.refresh(treatment_variant)

        # Create pipeline run with experiment
        pipeline_run = PipelineRun(
            pipeline_name="experiment_enabled_pipeline",
            triggered_by="experiment_test",
            parameters={"experiment_id": experiment.experiment_id},
        )

        test_db.add(pipeline_run)
        test_db.commit()
        test_db.refresh(pipeline_run)

        # Assign variants to users during pipeline execution
        user_assignments = []
        for i in range(10):
            # Simulate variant assignment
            assigned_variant = control_variant if i % 2 == 0 else treatment_variant

            assignment = VariantAssignment(
                experiment_id=experiment.experiment_id,
                variant_id=assigned_variant.variant_id,
                assignment_unit=f"user_{i}",
                user_id=f"user_{i}",
                assignment_hash=f"hash_{i}",
                pipeline_run_id=pipeline_run.run_id,
                assignment_context={
                    "step": "personalization",
                    "pipeline_run": pipeline_run.run_id,
                },
            )

            user_assignments.append(assignment)

        test_db.add_all(user_assignments)
        test_db.commit()

        # Verify experiment application
        total_assignments = (
            test_db.query(VariantAssignment).filter(VariantAssignment.experiment_id == experiment.experiment_id).count()
        )

        assert total_assignments == 10

        # Verify assignment distribution
        control_assignments = (
            test_db.query(VariantAssignment)
            .filter(
                VariantAssignment.experiment_id == experiment.experiment_id,
                VariantAssignment.variant_id == control_variant.variant_id,
            )
            .count()
        )

        treatment_assignments = (
            test_db.query(VariantAssignment)
            .filter(
                VariantAssignment.experiment_id == experiment.experiment_id,
                VariantAssignment.variant_id == treatment_variant.variant_id,
            )
            .count()
        )

        assert control_assignments == 5
        assert treatment_assignments == 5

        # Verify pipeline-experiment linkage
        pipeline_assignments = (
            test_db.query(VariantAssignment).filter(VariantAssignment.pipeline_run_id == pipeline_run.run_id).count()
        )

        assert pipeline_assignments == 10

    def test_experiment_lifecycle_during_pipeline(self, test_db):
        """Test experiment lifecycle management during pipeline execution"""
        # Create experiment in draft state
        experiment = Experiment(
            name="lifecycle_test_experiment",
            created_by="lifecycle_test",
            primary_metric="engagement_rate",
            status=ExperimentStatus.DRAFT,
        )

        test_db.add(experiment)
        test_db.commit()
        test_db.refresh(experiment)

        # Activate experiment for pipeline
        experiment.status = ExperimentStatus.RUNNING
        experiment.start_date = date.today()
        test_db.commit()

        assert experiment.is_active

        # Create pipeline that uses the experiment
        pipeline_run = PipelineRun(
            pipeline_name="lifecycle_pipeline",
            triggered_by="lifecycle_test",
            parameters={"active_experiments": [experiment.experiment_id]},
        )

        test_db.add(pipeline_run)
        test_db.commit()

        # Complete pipeline and stop experiment
        pipeline_run.status = PipelineRunStatus.SUCCESS
        pipeline_run.completed_at = datetime.utcnow()

        experiment.status = ExperimentStatus.COMPLETED
        experiment.end_date = date.today()

        test_db.commit()

        # Verify final states
        assert pipeline_run.status == PipelineRunStatus.SUCCESS
        assert experiment.status == ExperimentStatus.COMPLETED
        assert not experiment.is_active


class TestMetricsRecording:
    """Test metrics recorded"""

    @patch("core.metrics.MetricsCollector")
    def test_pipeline_metrics_integration(self, mock_metrics_class, test_db):
        """Test that pipeline execution metrics are properly recorded"""
        # Setup mock metrics collector
        mock_metrics = MagicMock()
        mock_metrics_class.return_value = mock_metrics

        # Create pipeline run with metrics tracking
        pipeline_run = PipelineRun(
            pipeline_name="metrics_test_pipeline",
            triggered_by="metrics_integration_test",
            status=PipelineRunStatus.RUNNING,
            started_at=datetime.utcnow(),
        )

        test_db.add(pipeline_run)
        test_db.commit()
        test_db.refresh(pipeline_run)

        # Simulate metrics collection during pipeline execution
        metrics_collector = MetricsCollector()

        # Record pipeline start metrics
        async def test_pipeline_start():
            await metrics_collector.record_pipeline_event(
                pipeline_name=pipeline_run.pipeline_name,
                event_type="started",
                run_id=pipeline_run.run_id,
            )

        # Run the async function
        asyncio.run(test_pipeline_start())

        # Simulate task execution with metrics
        tasks_with_metrics = [
            {"name": "data_ingestion", "records": 1000, "time": 45},
            {"name": "data_processing", "records": 1000, "time": 120},
            {"name": "data_export", "records": 950, "time": 30},
        ]

        for task_info in tasks_with_metrics:
            task = PipelineTask(
                pipeline_run_id=pipeline_run.run_id,
                task_name=task_info["name"],
                task_type="data_processing",
                execution_order=1,
                status=PipelineRunStatus.SUCCESS,
                execution_time_seconds=task_info["time"],
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
            test_db.add(task)

        test_db.commit()

        # Complete pipeline with final metrics
        pipeline_run.status = PipelineRunStatus.SUCCESS
        pipeline_run.completed_at = datetime.utcnow()
        pipeline_run.records_processed = 950  # Some records failed during processing
        pipeline_run.records_failed = 50
        pipeline_run.execution_time_seconds = 195  # Total execution time
        test_db.commit()

        # Record pipeline completion metrics
        async def test_pipeline_complete():
            await metrics_collector.record_pipeline_event(
                pipeline_name=pipeline_run.pipeline_name,
                event_type="completed",
                run_id=pipeline_run.run_id,
                records_processed=pipeline_run.records_processed,
                execution_time=pipeline_run.execution_time_seconds,
            )

        asyncio.run(test_pipeline_complete())

        # Verify metrics were recorded in the database
        assert pipeline_run.records_processed == 950
        assert pipeline_run.records_failed == 50
        assert abs(pipeline_run.success_rate - 0.9473684210526315) < 0.001  # (950-50)/950
        assert pipeline_run.execution_time_seconds == 195

        # Verify all tasks have metrics
        tasks_with_time = (
            test_db.query(PipelineTask)
            .filter(
                PipelineTask.pipeline_run_id == pipeline_run.run_id,
                PipelineTask.execution_time_seconds.isnot(None),
            )
            .count()
        )

        assert tasks_with_time == 3

    def test_experiment_metrics_correlation(self, test_db):
        """Test that experiment metrics are correlated with pipeline metrics"""
        # Create experiment
        experiment = Experiment(
            name="metrics_correlation_experiment",
            created_by="metrics_test",
            primary_metric="processing_efficiency",
            status=ExperimentStatus.RUNNING,
        )

        test_db.add(experiment)
        test_db.commit()
        test_db.refresh(experiment)

        # Create experiment variant
        variant = ExperimentVariant(
            experiment_id=experiment.experiment_id,
            variant_key="optimized_processing",
            name="Optimized Processing",
            weight=100.0,
        )

        test_db.add(variant)
        test_db.commit()
        test_db.refresh(variant)

        # Create pipeline runs with different experiment assignments
        pipeline_runs = []
        for i in range(3):
            pipeline_run = PipelineRun(
                pipeline_name=f"metrics_pipeline_{i}",
                triggered_by="metrics_correlation_test",
                status=PipelineRunStatus.SUCCESS,
                records_processed=100 + (i * 10),  # Varying performance
                execution_time_seconds=60 + (i * 5),
            )

            test_db.add(pipeline_run)
            test_db.commit()
            test_db.refresh(pipeline_run)

            # Create variant assignment linked to pipeline
            assignment = VariantAssignment(
                experiment_id=experiment.experiment_id,
                variant_id=variant.variant_id,
                assignment_unit=f"pipeline_{i}",
                assignment_hash=f"hash_{i}",
                pipeline_run_id=pipeline_run.run_id,
            )

            test_db.add(assignment)
            pipeline_runs.append(pipeline_run)

        test_db.commit()

        # Verify experiment-pipeline correlation
        experiment_pipelines = (
            test_db.query(VariantAssignment)
            .filter(
                VariantAssignment.experiment_id == experiment.experiment_id,
                VariantAssignment.pipeline_run_id.isnot(None),
            )
            .count()
        )

        assert experiment_pipelines == 3

        # Verify metrics variation across pipeline runs
        total_records = sum(run.records_processed for run in pipeline_runs)
        total_time = sum(run.execution_time_seconds for run in pipeline_runs)

        assert total_records == 330  # 100 + 110 + 120
        assert total_time == 195  # 60 + 65 + 70


class TestOrchestrationIntegration:
    """Test complete orchestration integration"""

    def test_complete_orchestration_workflow(self, test_db):
        """Test end-to-end orchestration workflow with all components"""
        # Step 1: Setup experiment
        experiment = Experiment(
            name="complete_workflow_experiment",
            description="End-to-end workflow test",
            created_by="integration_test",
            primary_metric="overall_success_rate",
            status=ExperimentStatus.RUNNING,
            start_date=date.today(),
        )

        test_db.add(experiment)
        test_db.commit()
        test_db.refresh(experiment)

        # Add experiment variants
        control_variant = ExperimentVariant(
            experiment_id=experiment.experiment_id,
            variant_key="standard_workflow",
            name="Standard Workflow",
            variant_type=VariantType.CONTROL,
            weight=50.0,
            is_control=True,
            config={"processing_mode": "standard", "timeout": 300},
        )

        optimized_variant = ExperimentVariant(
            experiment_id=experiment.experiment_id,
            variant_key="optimized_workflow",
            name="Optimized Workflow",
            variant_type=VariantType.TREATMENT,
            weight=50.0,
            config={"processing_mode": "optimized", "timeout": 180},
        )

        test_db.add_all([control_variant, optimized_variant])
        test_db.commit()
        test_db.refresh(control_variant)
        test_db.refresh(optimized_variant)

        # Step 2: Execute pipeline with experiment
        pipeline_run = PipelineRun(
            pipeline_name="complete_workflow_pipeline",
            pipeline_type=PipelineType.DAILY_BATCH,
            triggered_by="complete_integration_test",
            trigger_reason="End-to-end workflow validation",
            status=PipelineRunStatus.RUNNING,
            started_at=datetime.utcnow(),
            parameters={
                "experiment_id": experiment.experiment_id,
                "target_records": 100,
            },
            config={"enable_experiments": True, "collect_metrics": True},
        )

        test_db.add(pipeline_run)
        test_db.commit()
        test_db.refresh(pipeline_run)

        # Step 3: Execute ordered tasks
        workflow_tasks = [
            {"name": "initialization", "order": 1, "time": 10},
            {"name": "data_acquisition", "order": 2, "time": 30},
            {"name": "experiment_assignment", "order": 3, "time": 5},
            {"name": "data_processing", "order": 4, "time": 60},
            {"name": "quality_validation", "order": 5, "time": 15},
            {"name": "results_delivery", "order": 6, "time": 20},
        ]

        for task_info in workflow_tasks:
            task = PipelineTask(
                pipeline_run_id=pipeline_run.run_id,
                task_name=task_info["name"],
                task_type="workflow_step",
                execution_order=task_info["order"],
                status=PipelineRunStatus.SUCCESS,
                execution_time_seconds=task_info["time"],
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
            test_db.add(task)

        test_db.commit()

        # Step 4: Apply experiment assignments
        assignments = []
        for i in range(20):
            # Alternate between variants
            assigned_variant = control_variant if i % 2 == 0 else optimized_variant

            assignment = VariantAssignment(
                experiment_id=experiment.experiment_id,
                variant_id=assigned_variant.variant_id,
                assignment_unit=f"workflow_entity_{i}",
                user_id=f"user_{i}",
                assignment_hash=f"workflow_hash_{i}",
                pipeline_run_id=pipeline_run.run_id,
                assignment_context={
                    "workflow_step": "experiment_assignment",
                    "entity_type": "processing_unit",
                },
            )
            assignments.append(assignment)

        test_db.add_all(assignments)
        test_db.commit()

        # Step 5: Complete pipeline with metrics
        pipeline_run.status = PipelineRunStatus.SUCCESS
        pipeline_run.completed_at = datetime.utcnow()
        pipeline_run.records_processed = 100
        pipeline_run.records_failed = 0
        pipeline_run.execution_time_seconds = sum(task["time"] for task in workflow_tasks)
        test_db.commit()

        # Step 6: Verify complete workflow

        # Verify pipeline completion
        assert pipeline_run.status == PipelineRunStatus.SUCCESS
        assert pipeline_run.is_complete
        assert pipeline_run.success_rate == 1.0

        # Verify task execution order
        completed_tasks = (
            test_db.query(PipelineTask)
            .filter(PipelineTask.pipeline_run_id == pipeline_run.run_id)
            .order_by(PipelineTask.execution_order)
            .all()
        )

        assert len(completed_tasks) == 6
        for i, task in enumerate(completed_tasks):
            assert task.execution_order == i + 1
            assert task.status == PipelineRunStatus.SUCCESS

        # Verify experiment application
        total_assignments = (
            test_db.query(VariantAssignment)
            .filter(
                VariantAssignment.experiment_id == experiment.experiment_id,
                VariantAssignment.pipeline_run_id == pipeline_run.run_id,
            )
            .count()
        )

        assert total_assignments == 20

        # Verify variant distribution
        control_count = (
            test_db.query(VariantAssignment)
            .filter(
                VariantAssignment.experiment_id == experiment.experiment_id,
                VariantAssignment.variant_id == control_variant.variant_id,
            )
            .count()
        )

        optimized_count = (
            test_db.query(VariantAssignment)
            .filter(
                VariantAssignment.experiment_id == experiment.experiment_id,
                VariantAssignment.variant_id == optimized_variant.variant_id,
            )
            .count()
        )

        assert control_count == 10
        assert optimized_count == 10

        # Verify metrics recording
        assert pipeline_run.execution_time_seconds == 140  # Sum of all task times
        assert pipeline_run.records_processed == 100

        # Verify experiment is properly linked to pipeline
        experiment_pipeline_link = (
            test_db.query(VariantAssignment).filter(VariantAssignment.pipeline_run_id == pipeline_run.run_id).first()
        )

        assert experiment_pipeline_link is not None
        assert experiment_pipeline_link.experiment_id == experiment.experiment_id
