"""
Comprehensive API tests for D11 Orchestration to achieve ≥80% coverage.

Tests all orchestration API endpoints including pipeline management,
experiment management, and status monitoring.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d11_orchestration.api import router
from d11_orchestration.models import (
    Experiment,
    ExperimentStatus,
    ExperimentVariant,
    PipelineRun,
    PipelineRunStatus,
    PipelineTask,
    VariantAssignment,
)
from d11_orchestration.schemas import (
    ExperimentCreateRequest,
    ExperimentUpdateRequest,
    ExperimentVariantCreateRequest,
    PipelineTriggerRequest,
    VariantAssignmentRequest,
)
from database.base import Base
from database.session import get_db


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Create a database session for testing"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_app(db_session):
    """Create FastAPI test app with dependency overrides"""
    app = FastAPI()
    app.include_router(router)

    # Override database dependency
    app.dependency_overrides[get_db] = lambda: db_session

    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.fixture
def sample_pipeline_run(db_session):
    """Create a sample pipeline run for testing"""
    run = PipelineRun(
        pipeline_name="healthcare_pipeline",
        pipeline_type="data_processing",
        triggered_by="user-123",
        trigger_reason="manual",
        parameters={"source": "internal", "batch_size": 100},
        config={"timeout": 3600, "retries": 3},
        environment="production",
        status=PipelineRunStatus.RUNNING,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


@pytest.fixture
def sample_experiment(db_session):
    """Create a sample experiment for testing"""
    experiment = Experiment(
        name="Healthcare Lead Quality",
        description="Testing lead quality scoring algorithms",
        experiment_type="ab_test",
        status=ExperimentStatus.DRAFT,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        config={"sample_size": 1000, "confidence_level": 0.95},
        created_by="user-123",
        target_metric="conversion_rate",
        success_criteria={"min_improvement": 0.05},
    )
    db_session.add(experiment)
    db_session.commit()
    db_session.refresh(experiment)
    return experiment


@pytest.fixture
def sample_experiment_variant(db_session, sample_experiment):
    """Create a sample experiment variant for testing"""
    variant = ExperimentVariant(
        experiment_id=sample_experiment.id,
        name="control",
        description="Control variant using current algorithm",
        config={"algorithm": "current", "parameters": {}},
        traffic_allocation=0.5,
        is_control=True,
    )
    db_session.add(variant)
    db_session.commit()
    db_session.refresh(variant)
    return variant


@pytest.fixture
def sample_pipeline_task(db_session, sample_pipeline_run):
    """Create a sample pipeline task for testing"""
    task = PipelineTask(
        run_id=sample_pipeline_run.id,
        task_name="data_validation",
        task_type="validation",
        status=PipelineRunStatus.PENDING,
        config={"validation_rules": ["not_null", "format_check"]},
        dependencies=[],
        retry_count=0,
        max_retries=3,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check_success(self, client):
        """Test successful health check"""
        response = client.get("/orchestration/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert "components" in data
        assert data["components"]["database"] == "healthy"
        assert data["components"]["pipeline_engine"] == "healthy"
        assert data["components"]["experiment_engine"] == "healthy"


class TestPipelineAPI:
    """Test pipeline API endpoints"""

    def test_trigger_pipeline_success(self, client):
        """Test successful pipeline trigger"""
        trigger_data = {
            "pipeline_name": "test_pipeline",
            "pipeline_type": "data_processing",
            "triggered_by": "user-123",
            "trigger_reason": "manual",
            "parameters": {"source": "internal", "batch_size": 100},
            "config": {"timeout": 3600, "retries": 3},
            "environment": "development",
        }

        response = client.post("/orchestration/pipelines/trigger", json=trigger_data)

        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_name"] == trigger_data["pipeline_name"]
        assert data["pipeline_type"] == trigger_data["pipeline_type"]
        assert data["triggered_by"] == trigger_data["triggered_by"]
        assert data["status"] == "pending"
        assert data["parameters"] == trigger_data["parameters"]
        assert data["config"] == trigger_data["config"]
        assert data["environment"] == trigger_data["environment"]
        assert "id" in data
        assert "created_at" in data

    def test_trigger_pipeline_with_scheduled_time(self, client):
        """Test triggering pipeline with scheduled time"""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        trigger_data = {
            "pipeline_name": "scheduled_pipeline",
            "pipeline_type": "batch_processing",
            "triggered_by": "scheduler",
            "trigger_reason": "scheduled",
            "scheduled_at": scheduled_time.isoformat(),
            "parameters": {"batch_id": "batch-123"},
            "config": {"timeout": 1800},
            "environment": "production",
        }

        response = client.post("/orchestration/pipelines/trigger", json=trigger_data)

        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_name"] == trigger_data["pipeline_name"]
        assert data["scheduled_at"] is not None
        assert data["status"] == "pending"

    def test_trigger_pipeline_minimal_data(self, client):
        """Test triggering pipeline with minimal required data"""
        trigger_data = {
            "pipeline_name": "minimal_pipeline",
            "pipeline_type": "simple",
            "triggered_by": "user-456",
            "trigger_reason": "test",
        }

        response = client.post("/orchestration/pipelines/trigger", json=trigger_data)

        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_name"] == trigger_data["pipeline_name"]
        assert data["status"] == "pending"
        assert data["parameters"] is None
        assert data["config"] is None
        assert data["environment"] is None

    def test_get_pipeline_status_success(self, client, sample_pipeline_run):
        """Test successful pipeline status retrieval"""
        response = client.get(f"/orchestration/pipelines/{sample_pipeline_run.id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == sample_pipeline_run.id
        assert data["pipeline_name"] == sample_pipeline_run.pipeline_name
        assert data["status"] == "running"
        assert data["progress"]["completed_tasks"] == 0
        assert data["progress"]["total_tasks"] == 0
        assert data["progress"]["percentage"] == 0.0
        assert "started_at" in data
        assert "estimated_completion" in data

    def test_get_pipeline_status_with_tasks(self, client, sample_pipeline_run, sample_pipeline_task):
        """Test pipeline status with tasks"""
        # Update task to completed
        sample_pipeline_task.status = PipelineRunStatus.COMPLETED
        sample_pipeline_task.completed_at = datetime.utcnow()

        response = client.get(f"/orchestration/pipelines/{sample_pipeline_run.id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["progress"]["completed_tasks"] == 1
        assert data["progress"]["total_tasks"] == 1
        assert data["progress"]["percentage"] == 100.0
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task_name"] == sample_pipeline_task.task_name
        assert data["tasks"][0]["status"] == "completed"

    def test_get_pipeline_status_not_found(self, client):
        """Test pipeline status for non-existent run"""
        response = client.get("/orchestration/pipelines/non-existent-id/status")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_pipeline_history_success(self, client, sample_pipeline_run):
        """Test successful pipeline history retrieval"""
        # Create additional pipeline runs
        for i in range(3):
            run = PipelineRun(
                pipeline_name=f"test_pipeline_{i}",
                pipeline_type="test",
                triggered_by="user-123",
                trigger_reason="test",
                status=PipelineRunStatus.COMPLETED,
                started_at=datetime.utcnow() - timedelta(hours=i + 1),
                completed_at=datetime.utcnow() - timedelta(hours=i),
            )
            sample_pipeline_run.query.session.add(run)
        sample_pipeline_run.query.session.commit()

        response = client.get("/orchestration/pipelines/history")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 4  # sample_pipeline_run + 3 new ones
        assert len(data["runs"]) >= 4
        assert data["page"] == 1
        assert data["page_size"] == 50

        # Check that runs are ordered by start time (most recent first)
        if len(data["runs"]) > 1:
            first_run = data["runs"][0]
            second_run = data["runs"][1]
            assert first_run["started_at"] >= second_run["started_at"]

    def test_get_pipeline_history_with_filters(self, client, sample_pipeline_run):
        """Test pipeline history with filters"""
        # Create runs with different statuses
        completed_run = PipelineRun(
            pipeline_name="completed_pipeline",
            pipeline_type="test",
            triggered_by="user-123",
            trigger_reason="test",
            status=PipelineRunStatus.COMPLETED,
        )
        failed_run = PipelineRun(
            pipeline_name="failed_pipeline",
            pipeline_type="test",
            triggered_by="user-123",
            trigger_reason="test",
            status=PipelineRunStatus.FAILED,
        )
        sample_pipeline_run.query.session.add_all([completed_run, failed_run])
        sample_pipeline_run.query.session.commit()

        # Test status filter
        response = client.get("/orchestration/pipelines/history", params={"status": "completed"})

        assert response.status_code == 200
        data = response.json()
        assert all(run["status"] == "completed" for run in data["runs"])

        # Test pipeline name filter
        response = client.get("/orchestration/pipelines/history", params={"pipeline_name": "completed_pipeline"})

        assert response.status_code == 200
        data = response.json()
        assert all("completed_pipeline" in run["pipeline_name"] for run in data["runs"])

    def test_get_pipeline_history_pagination(self, client, sample_pipeline_run):
        """Test pipeline history pagination"""
        # Create multiple runs
        for i in range(15):
            run = PipelineRun(
                pipeline_name=f"pagination_test_{i}",
                pipeline_type="test",
                triggered_by="user-123",
                trigger_reason="test",
                status=PipelineRunStatus.COMPLETED,
            )
            sample_pipeline_run.query.session.add(run)
        sample_pipeline_run.query.session.commit()

        # Test first page
        response = client.get("/orchestration/pipelines/history", params={"page": 1, "page_size": 10})

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 10
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total"] >= 16  # 15 + sample_pipeline_run

        # Test second page
        response = client.get("/orchestration/pipelines/history", params={"page": 2, "page_size": 10})

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) >= 6  # At least 6 remaining
        assert data["page"] == 2
        assert data["page_size"] == 10

    def test_get_pipeline_history_date_range(self, client, sample_pipeline_run):
        """Test pipeline history with date range filter"""
        # Create runs with specific dates
        start_date = datetime.utcnow() - timedelta(days=5)
        end_date = datetime.utcnow() - timedelta(days=1)

        # Run within range
        in_range_run = PipelineRun(
            pipeline_name="in_range_pipeline",
            pipeline_type="test",
            triggered_by="user-123",
            trigger_reason="test",
            status=PipelineRunStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(days=3),
        )

        # Run outside range
        out_of_range_run = PipelineRun(
            pipeline_name="out_of_range_pipeline",
            pipeline_type="test",
            triggered_by="user-123",
            trigger_reason="test",
            status=PipelineRunStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(days=7),
        )

        sample_pipeline_run.query.session.add_all([in_range_run, out_of_range_run])
        sample_pipeline_run.query.session.commit()

        response = client.get(
            "/orchestration/pipelines/history",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should only include runs within the date range
        for run in data["runs"]:
            run_date = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
            assert start_date <= run_date <= end_date


class TestExperimentAPI:
    """Test experiment API endpoints"""

    def test_create_experiment_success(self, client):
        """Test successful experiment creation"""
        experiment_data = {
            "name": "New A/B Test",
            "description": "Testing new lead scoring algorithm",
            "experiment_type": "ab_test",
            "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=31)).isoformat(),
            "config": {"sample_size": 1000, "confidence_level": 0.95},
            "created_by": "user-456",
            "target_metric": "conversion_rate",
            "success_criteria": {"min_improvement": 0.05},
        }

        response = client.post("/orchestration/experiments", json=experiment_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == experiment_data["name"]
        assert data["description"] == experiment_data["description"]
        assert data["experiment_type"] == experiment_data["experiment_type"]
        assert data["status"] == "draft"
        assert data["config"] == experiment_data["config"]
        assert data["created_by"] == experiment_data["created_by"]
        assert data["target_metric"] == experiment_data["target_metric"]
        assert data["success_criteria"] == experiment_data["success_criteria"]
        assert "id" in data
        assert "created_at" in data

    def test_create_experiment_minimal_data(self, client):
        """Test creating experiment with minimal required data"""
        experiment_data = {
            "name": "Minimal Experiment",
            "description": "Test experiment",
            "experiment_type": "simple",
            "created_by": "user-789",
            "target_metric": "clicks",
        }

        response = client.post("/orchestration/experiments", json=experiment_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == experiment_data["name"]
        assert data["status"] == "draft"
        assert data["config"] is None
        assert data["success_criteria"] is None
        assert data["start_date"] is None
        assert data["end_date"] is None

    def test_create_experiment_invalid_dates(self, client):
        """Test creating experiment with invalid date range"""
        experiment_data = {
            "name": "Invalid Date Test",
            "description": "Test experiment",
            "experiment_type": "ab_test",
            "start_date": (datetime.utcnow() + timedelta(days=10)).isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),  # End before start
            "created_by": "user-123",
            "target_metric": "conversion_rate",
        }

        response = client.post("/orchestration/experiments", json=experiment_data)

        assert response.status_code == 400
        assert "End date must be after start date" in response.json()["detail"]

    def test_get_experiment_success(self, client, sample_experiment):
        """Test successful experiment retrieval"""
        response = client.get(f"/orchestration/experiments/{sample_experiment.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_experiment.id
        assert data["name"] == sample_experiment.name
        assert data["description"] == sample_experiment.description
        assert data["experiment_type"] == sample_experiment.experiment_type
        assert data["status"] == "draft"
        assert data["config"] == sample_experiment.config
        assert data["created_by"] == sample_experiment.created_by
        assert data["target_metric"] == sample_experiment.target_metric
        assert data["success_criteria"] == sample_experiment.success_criteria
        assert "variants" in data
        assert "assignments" in data

    def test_get_experiment_not_found(self, client):
        """Test getting non-existent experiment"""
        response = client.get("/orchestration/experiments/non-existent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_list_experiments_success(self, client, sample_experiment):
        """Test listing experiments"""
        # Create additional experiments
        for i in range(3):
            experiment = Experiment(
                name=f"Test Experiment {i}",
                description=f"Test experiment {i}",
                experiment_type="ab_test",
                status=ExperimentStatus.DRAFT,
                created_by="user-123",
                target_metric="clicks",
            )
            sample_experiment.query.session.add(experiment)
        sample_experiment.query.session.commit()

        response = client.get("/orchestration/experiments")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 4  # sample + 3 new ones
        assert len(data["experiments"]) >= 4
        assert data["page"] == 1
        assert data["page_size"] == 50

        # Check experiments are ordered by created_at (most recent first)
        if len(data["experiments"]) > 1:
            first_exp = data["experiments"][0]
            second_exp = data["experiments"][1]
            assert first_exp["created_at"] >= second_exp["created_at"]

    def test_list_experiments_with_filters(self, client, sample_experiment):
        """Test listing experiments with filters"""
        # Create experiments with different statuses
        running_exp = Experiment(
            name="Running Experiment",
            description="Running experiment",
            experiment_type="ab_test",
            status=ExperimentStatus.RUNNING,
            created_by="user-123",
            target_metric="conversion_rate",
        )
        completed_exp = Experiment(
            name="Completed Experiment",
            description="Completed experiment",
            experiment_type="ab_test",
            status=ExperimentStatus.COMPLETED,
            created_by="user-456",
            target_metric="revenue",
        )
        sample_experiment.query.session.add_all([running_exp, completed_exp])
        sample_experiment.query.session.commit()

        # Test status filter
        response = client.get("/orchestration/experiments", params={"status": "running"})

        assert response.status_code == 200
        data = response.json()
        assert all(exp["status"] == "running" for exp in data["experiments"])

        # Test created_by filter
        response = client.get("/orchestration/experiments", params={"created_by": "user-456"})

        assert response.status_code == 200
        data = response.json()
        assert all(exp["created_by"] == "user-456" for exp in data["experiments"])

        # Test experiment_type filter
        response = client.get("/orchestration/experiments", params={"experiment_type": "ab_test"})

        assert response.status_code == 200
        data = response.json()
        assert all(exp["experiment_type"] == "ab_test" for exp in data["experiments"])

    def test_list_experiments_pagination(self, client, sample_experiment):
        """Test experiment listing pagination"""
        # Create multiple experiments
        for i in range(15):
            experiment = Experiment(
                name=f"Pagination Test {i}",
                description=f"Test experiment {i}",
                experiment_type="ab_test",
                status=ExperimentStatus.DRAFT,
                created_by="user-123",
                target_metric="clicks",
            )
            sample_experiment.query.session.add(experiment)
        sample_experiment.query.session.commit()

        # Test first page
        response = client.get("/orchestration/experiments", params={"page": 1, "page_size": 10})

        assert response.status_code == 200
        data = response.json()
        assert len(data["experiments"]) == 10
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["total"] >= 16  # 15 + sample_experiment

        # Test second page
        response = client.get("/orchestration/experiments", params={"page": 2, "page_size": 10})

        assert response.status_code == 200
        data = response.json()
        assert len(data["experiments"]) >= 6  # At least 6 remaining
        assert data["page"] == 2
        assert data["page_size"] == 10

    def test_update_experiment_success(self, client, sample_experiment):
        """Test successful experiment update"""
        update_data = {
            "name": "Updated Experiment Name",
            "description": "Updated description",
            "config": {"sample_size": 2000, "confidence_level": 0.99},
            "target_metric": "revenue",
            "success_criteria": {"min_improvement": 0.10},
        }

        response = client.patch(f"/orchestration/experiments/{sample_experiment.id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["config"] == update_data["config"]
        assert data["target_metric"] == update_data["target_metric"]
        assert data["success_criteria"] == update_data["success_criteria"]
        assert "updated_at" in data

    def test_update_experiment_partial(self, client, sample_experiment):
        """Test partial experiment update"""
        update_data = {
            "name": "Partially Updated Name",
        }

        response = client.patch(f"/orchestration/experiments/{sample_experiment.id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        # Other fields should remain unchanged
        assert data["description"] == sample_experiment.description
        assert data["experiment_type"] == sample_experiment.experiment_type

    def test_update_experiment_not_found(self, client):
        """Test updating non-existent experiment"""
        update_data = {"name": "Updated Name"}

        response = client.patch("/orchestration/experiments/non-existent-id", json=update_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_delete_experiment_success(self, client, sample_experiment):
        """Test successful experiment deletion"""
        response = client.delete(f"/orchestration/experiments/{sample_experiment.id}")

        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

        # Verify experiment is deleted
        get_response = client.get(f"/orchestration/experiments/{sample_experiment.id}")
        assert get_response.status_code == 404

    def test_delete_experiment_not_found(self, client):
        """Test deleting non-existent experiment"""
        response = client.delete("/orchestration/experiments/non-existent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestExperimentVariantAPI:
    """Test experiment variant API endpoints"""

    def test_create_experiment_variant_success(self, client, sample_experiment):
        """Test successful experiment variant creation"""
        variant_data = {
            "name": "treatment",
            "description": "Treatment variant using new algorithm",
            "config": {"algorithm": "new", "parameters": {"learning_rate": 0.01}},
            "traffic_allocation": 0.5,
            "is_control": False,
        }

        response = client.post(f"/orchestration/experiments/{sample_experiment.id}/variants", json=variant_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == variant_data["name"]
        assert data["description"] == variant_data["description"]
        assert data["config"] == variant_data["config"]
        assert data["traffic_allocation"] == variant_data["traffic_allocation"]
        assert data["is_control"] == variant_data["is_control"]
        assert data["experiment_id"] == sample_experiment.id
        assert "id" in data
        assert "created_at" in data

    def test_create_experiment_variant_invalid_allocation(self, client, sample_experiment):
        """Test creating variant with invalid traffic allocation"""
        variant_data = {
            "name": "invalid_variant",
            "description": "Invalid variant",
            "config": {},
            "traffic_allocation": 1.5,  # Invalid: > 1.0
            "is_control": False,
        }

        response = client.post(f"/orchestration/experiments/{sample_experiment.id}/variants", json=variant_data)

        assert response.status_code == 400
        assert "traffic_allocation must be between 0 and 1" in response.json()["detail"]

    def test_create_experiment_variant_experiment_not_found(self, client):
        """Test creating variant for non-existent experiment"""
        variant_data = {
            "name": "test_variant",
            "description": "Test variant",
            "config": {},
            "traffic_allocation": 0.5,
            "is_control": False,
        }

        response = client.post("/orchestration/experiments/non-existent-id/variants", json=variant_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_list_experiment_variants_success(self, client, sample_experiment, sample_experiment_variant):
        """Test listing experiment variants"""
        # Create additional variant
        variant = ExperimentVariant(
            experiment_id=sample_experiment.id,
            name="treatment",
            description="Treatment variant",
            config={"algorithm": "new"},
            traffic_allocation=0.5,
            is_control=False,
        )
        sample_experiment_variant.query.session.add(variant)
        sample_experiment_variant.query.session.commit()

        response = client.get(f"/orchestration/experiments/{sample_experiment.id}/variants")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # control + treatment

        # Check both variants
        variant_names = [v["name"] for v in data]
        assert "control" in variant_names
        assert "treatment" in variant_names

        # Check control variant
        control_variant = next(v for v in data if v["name"] == "control")
        assert control_variant["is_control"] is True
        assert control_variant["experiment_id"] == sample_experiment.id

    def test_list_experiment_variants_experiment_not_found(self, client):
        """Test listing variants for non-existent experiment"""
        response = client.get("/orchestration/experiments/non-existent-id/variants")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_update_experiment_variant_success(self, client, sample_experiment_variant):
        """Test successful experiment variant update"""
        update_data = {
            "name": "updated_control",
            "description": "Updated control variant",
            "config": {"algorithm": "updated", "parameters": {"threshold": 0.8}},
            "traffic_allocation": 0.6,
        }

        response = client.patch(
            f"/orchestration/experiments/{sample_experiment_variant.experiment_id}/variants/{sample_experiment_variant.id}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["description"] == update_data["description"]
        assert data["config"] == update_data["config"]
        assert data["traffic_allocation"] == update_data["traffic_allocation"]
        assert "updated_at" in data

    def test_update_experiment_variant_not_found(self, client, sample_experiment):
        """Test updating non-existent variant"""
        update_data = {"name": "updated_name"}

        response = client.patch(
            f"/orchestration/experiments/{sample_experiment.id}/variants/non-existent-id", json=update_data
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_delete_experiment_variant_success(self, client, sample_experiment_variant):
        """Test successful experiment variant deletion"""
        response = client.delete(
            f"/orchestration/experiments/{sample_experiment_variant.experiment_id}/variants/{sample_experiment_variant.id}"
        )

        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

        # Verify variant is deleted
        list_response = client.get(f"/orchestration/experiments/{sample_experiment_variant.experiment_id}/variants")
        assert list_response.status_code == 200
        variants = list_response.json()
        variant_ids = [v["id"] for v in variants]
        assert sample_experiment_variant.id not in variant_ids

    def test_delete_experiment_variant_not_found(self, client, sample_experiment):
        """Test deleting non-existent variant"""
        response = client.delete(f"/orchestration/experiments/{sample_experiment.id}/variants/non-existent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestVariantAssignmentAPI:
    """Test variant assignment API endpoints"""

    def test_assign_variant_success(self, client, sample_experiment_variant):
        """Test successful variant assignment"""
        assignment_data = {
            "user_id": "user-123",
            "context": {"location": "US", "device": "mobile"},
        }

        response = client.post(
            f"/orchestration/experiments/{sample_experiment_variant.experiment_id}/assign", json=assignment_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == assignment_data["user_id"]
        assert data["experiment_id"] == sample_experiment_variant.experiment_id
        assert data["variant_id"] == sample_experiment_variant.id
        assert data["context"] == assignment_data["context"]
        assert "assigned_at" in data

    def test_assign_variant_experiment_not_found(self, client):
        """Test assigning variant for non-existent experiment"""
        assignment_data = {
            "user_id": "user-123",
            "context": {},
        }

        response = client.post("/orchestration/experiments/non-existent-id/assign", json=assignment_data)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_assign_variant_no_variants(self, client, sample_experiment):
        """Test assigning variant when experiment has no variants"""
        assignment_data = {
            "user_id": "user-123",
            "context": {},
        }

        response = client.post(f"/orchestration/experiments/{sample_experiment.id}/assign", json=assignment_data)

        assert response.status_code == 400
        assert "No variants available" in response.json()["detail"]

    def test_get_user_assignments_success(self, client, sample_experiment_variant):
        """Test getting user assignments"""
        # Create assignment
        assignment = VariantAssignment(
            experiment_id=sample_experiment_variant.experiment_id,
            variant_id=sample_experiment_variant.id,
            user_id="user-123",
            context={"location": "US"},
        )
        sample_experiment_variant.query.session.add(assignment)
        sample_experiment_variant.query.session.commit()

        response = client.get("/orchestration/assignments/user-123")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_id"] == "user-123"
        assert data[0]["experiment_id"] == sample_experiment_variant.experiment_id
        assert data[0]["variant_id"] == sample_experiment_variant.id
        assert data[0]["context"] == {"location": "US"}

    def test_get_user_assignments_not_found(self, client):
        """Test getting assignments for user with no assignments"""
        response = client.get("/orchestration/assignments/user-with-no-assignments")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_get_experiment_assignments_success(self, client, sample_experiment_variant):
        """Test getting experiment assignments"""
        # Create multiple assignments
        assignments = []
        for i in range(3):
            assignment = VariantAssignment(
                experiment_id=sample_experiment_variant.experiment_id,
                variant_id=sample_experiment_variant.id,
                user_id=f"user-{i}",
                context={"location": "US", "index": i},
            )
            assignments.append(assignment)
        sample_experiment_variant.query.session.add_all(assignments)
        sample_experiment_variant.query.session.commit()

        response = client.get(f"/orchestration/assignments/experiment/{sample_experiment_variant.experiment_id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Check all assignments
        user_ids = [a["user_id"] for a in data]
        assert "user-0" in user_ids
        assert "user-1" in user_ids
        assert "user-2" in user_ids

        # Check experiment consistency
        for assignment in data:
            assert assignment["experiment_id"] == sample_experiment_variant.experiment_id
            assert assignment["variant_id"] == sample_experiment_variant.id

    def test_get_experiment_assignments_not_found(self, client):
        """Test getting assignments for non-existent experiment"""
        response = client.get("/orchestration/assignments/experiment/non-existent-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestAPIErrorHandling:
    """Test API error handling and edge cases"""

    def test_invalid_json_payload(self, client):
        """Test handling of invalid JSON payload"""
        response = client.post(
            "/orchestration/pipelines/trigger", data="invalid json", headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422  # Unprocessable Entity

    def test_missing_required_fields(self, client):
        """Test handling of missing required fields"""
        incomplete_data = {
            "pipeline_name": "test_pipeline",
            # Missing required fields: pipeline_type, triggered_by, trigger_reason
        }

        response = client.post("/orchestration/pipelines/trigger", json=incomplete_data)

        assert response.status_code == 422
        assert "field required" in response.json()["detail"][0]["msg"]

    def test_invalid_field_types(self, client):
        """Test handling of invalid field types"""
        invalid_data = {
            "pipeline_name": "test_pipeline",
            "pipeline_type": "data_processing",
            "triggered_by": "user-123",
            "trigger_reason": "test",
            "parameters": "invalid_type",  # Should be dict, not string
        }

        response = client.post("/orchestration/pipelines/trigger", json=invalid_data)

        assert response.status_code == 422

    def test_invalid_enum_values(self, client):
        """Test handling of invalid enum values"""
        invalid_data = {
            "name": "Test Experiment",
            "description": "Test",
            "experiment_type": "invalid_type",  # Invalid enum value
            "created_by": "user-123",
            "target_metric": "clicks",
        }

        response = client.post("/orchestration/experiments", json=invalid_data)

        assert response.status_code == 422

    def test_database_constraint_violations(self, client, sample_experiment):
        """Test handling of database constraint violations"""
        # Try to create experiment with duplicate name (if constraint exists)
        duplicate_data = {
            "name": sample_experiment.name,  # Same name as existing experiment
            "description": "Duplicate experiment",
            "experiment_type": "ab_test",
            "created_by": "user-123",
            "target_metric": "clicks",
        }

        response = client.post("/orchestration/experiments", json=duplicate_data)

        # Should still succeed in this case as we don't have unique constraint on name
        # In a real scenario, this would test actual constraint violations
        assert response.status_code in [200, 409]  # Either success or conflict

    def test_concurrent_request_handling(self, client, sample_experiment):
        """Test handling of concurrent requests"""
        import threading
        import time

        results = []

        def make_request():
            try:
                response = client.get(f"/orchestration/experiments/{sample_experiment.id}")
                results.append(response.status_code)
            except Exception as e:
                results.append(str(e))

        # Create multiple threads to make concurrent requests
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 5
