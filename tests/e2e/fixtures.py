"""
End-to-end test fixtures - Task 080

Provides data seeding and test fixtures for comprehensive e2e testing
across all domains and workflows.

Acceptance Criteria:
- Test environment setup ✓
- Data seeding works ✓  
- Cleanup automated ✓
- Parallel test support ✓
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from faker import Faker

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import orchestration models
from d11_orchestration.models import (
    Experiment,
    ExperimentStatus,
    ExperimentVariant,
    PipelineRun,
    PipelineRunStatus,
    PipelineType,
    VariantType,
)

# Import models from the database models file
from database.models import (
    Business,
    Target,
)

fake = Faker()


@pytest.fixture
def sample_targeting_criteria(test_db_session):
    """Data seeding works - Create sample targeting criteria"""
    import random
    import uuid

    from database.models import GeoType

    # Generate unique values to avoid constraint violations
    unique_id = str(uuid.uuid4())[:8]
    cities = ["New York", "San Francisco", "Chicago", "Austin", "Boston", "Seattle"]
    verticals = ["restaurants", "retail", "services", "healthcare", "technology"]

    criteria = Target(
        id=f"test_criteria_{unique_id}",
        geo_type=GeoType.CITY,
        geo_value=f"{random.choice(cities)}_{unique_id}",
        vertical=f"{random.choice(verticals)}_{unique_id}",
        estimated_businesses=random.randint(50, 200),
        priority_score=round(random.uniform(0.7, 0.95), 2),
        is_active=True,
    )

    test_db_session.add(criteria)
    test_db_session.commit()
    test_db_session.refresh(criteria)
    return criteria


@pytest.fixture
def sample_yelp_businesses(test_db_session, sample_targeting_criteria):
    """Data seeding works - Create sample business data"""
    import random
    import uuid

    businesses = []
    base_id = str(uuid.uuid4())[:8]

    for i in range(5):
        unique_id = f"{base_id}_{i:03d}"

        business = Business(
            id=f"test_business_{unique_id}",
            name=f"{fake.company()} {unique_id}",
            phone=fake.phone_number(),
            website=f"https://{fake.domain_name()}",
            address=fake.street_address(),
            city=random.choice(["New York", "San Francisco", "Austin"]),
            state=fake.state_abbr(),
            zip_code=fake.zipcode(),
            latitude=float(fake.latitude()),
            longitude=float(fake.longitude()),
            vertical="restaurants",
            categories=["restaurant", "food"],
            rating=round(random.uniform(3.0, 5.0), 1),
            user_ratings_total=random.randint(10, 500),
        )

        businesses.append(business)
        test_db_session.add(business)

    test_db_session.commit()
    for business in businesses:
        test_db_session.refresh(business)

    return businesses


# Simplified fixtures using the actual models that exist


@pytest.fixture
def sample_pipeline_run(test_db_session):
    """Data seeding works - Create sample pipeline run"""
    pipeline_run = PipelineRun(
        pipeline_name="e2e_test_pipeline",
        pipeline_type=PipelineType.DAILY_BATCH,
        triggered_by="e2e_test_suite",
        trigger_reason="End-to-end testing",
        status=PipelineRunStatus.SUCCESS,
        started_at=datetime.utcnow() - timedelta(hours=2),
        completed_at=datetime.utcnow() - timedelta(hours=1),
        execution_time_seconds=3600,
        records_processed=100,
        records_failed=5,
        parameters={
            "target_region": "test_region",
            "batch_size": 100,
            "quality_threshold": 0.8,
        },
        config={"timeout_minutes": 120, "retry_count": 3, "parallel_workers": 4},
    )

    test_db_session.add(pipeline_run)
    test_db_session.commit()
    test_db_session.refresh(pipeline_run)
    return pipeline_run


@pytest.fixture
def sample_experiment(test_db_session):
    """Data seeding works - Create sample experiment"""
    from uuid import uuid4

    experiment = Experiment(
        name=f"e2e_test_experiment_{uuid4().hex[:8]}",
        description="Test experiment for e2e testing",
        hypothesis="E2E testing will improve system reliability",
        created_by="e2e_test_system",
        primary_metric="success_rate",
        secondary_metrics=["processing_time", "error_rate"],
        status=ExperimentStatus.RUNNING,
        start_date=date.today(),
        traffic_allocation_pct=100.0,
        holdout_pct=0.0,
        confidence_level=0.95,
        minimum_sample_size=100,
        maximum_duration_days=30,
        randomization_unit="business_id",
    )

    test_db_session.add(experiment)
    test_db_session.commit()
    test_db_session.refresh(experiment)
    return experiment


@pytest.fixture
def sample_experiment_variants(test_db_session, sample_experiment):
    """Data seeding works - Create sample experiment variants"""
    from d11_orchestration.models import generate_uuid

    variants = []

    # Control variant
    control_variant = ExperimentVariant(
        variant_id=generate_uuid(),
        experiment_id=sample_experiment.experiment_id,
        variant_key="control",
        name="Control Group",
        description="Standard processing workflow",
        variant_type=VariantType.CONTROL,
        weight=50.0,
        is_control=True,
        config={"processing_mode": "standard"},
    )

    # Treatment variant
    treatment_variant = ExperimentVariant(
        variant_id=generate_uuid(),
        experiment_id=sample_experiment.experiment_id,
        variant_key="optimized",
        name="Optimized Processing",
        description="Enhanced processing with optimizations",
        variant_type=VariantType.TREATMENT,
        weight=50.0,
        is_control=False,
        config={"processing_mode": "optimized", "cache_enabled": True},
    )

    variants.extend([control_variant, treatment_variant])

    for variant in variants:
        test_db_session.add(variant)

    test_db_session.commit()
    for variant in variants:
        test_db_session.refresh(variant)

    return variants


# Simple workflow data combining what we have
@pytest.fixture
def simple_workflow_data(
    test_db_session,
    sample_targeting_criteria,
    sample_yelp_businesses,
    sample_pipeline_run,
    sample_experiment,
    sample_experiment_variants,
):
    """Data seeding works - Basic end-to-end workflow data set"""
    return {
        "targeting_criteria": sample_targeting_criteria,
        "businesses": sample_yelp_businesses,
        "pipeline_run": sample_pipeline_run,
        "experiment": sample_experiment,
        "experiment_variants": sample_experiment_variants,
        "database_session": test_db_session,
    }


@pytest.fixture
def api_client_factory(test_db_override, mock_external_services):
    """Create API clients for testing different endpoints"""
    from fastapi.testclient import TestClient

    from database.session import get_db
    from main import app

    # Override database dependency
    app.dependency_overrides[get_db] = test_db_override

    def create_client(base_url: str = "http://testserver"):
        return TestClient(app, base_url=base_url)

    yield create_client

    # Cleanup
    app.dependency_overrides.clear()


# Basic workflow orchestrator for testing
