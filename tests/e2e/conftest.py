"""
End-to-end test configuration and fixtures - Task 080

Provides test environment setup, data seeding, cleanup automation,
and parallel test support for end-to-end testing.

Acceptance Criteria:
- Test environment setup ✓
- Data seeding works ✓
- Cleanup automated ✓  
- Parallel test support ✓
"""

import asyncio
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import MagicMock, patch

import pytest
import requests
import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.config import get_settings
from database.base import Base
from database.session import get_db
from stubs.server import app as stub_app

# Import fixtures from fixtures.py to make them available
from tests.e2e.fixtures import *

# Import all models to ensure foreign key references are available
try:
    import database.models  # Main database models
    import d1_targeting.models  # D1 targeting models
    import d2_sourcing.models  # D2 sourcing models
    import d3_assessment.models  # D3 assessment models
    import d4_enrichment.models  # D4 enrichment models
    import d5_scoring.models  # D5 scoring models
    import d6_reports.models  # D6 reports models
    import d7_storefront.models  # D7 storefront models
    import d8_personalization.models  # D8 personalization models
    import d9_delivery.models  # D9 delivery models
    import d10_analytics.models  # D10 analytics models
    import d11_orchestration.models  # D11 orchestration models
except ImportError:
    # If imports fail, models will be registered when tests import them
    pass


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings():
    """Test environment setup - Configure test environment settings"""
    settings = get_settings()

    # Override settings for testing
    test_settings = settings.copy(
        update={
            "environment": "test",
            "database_url": "sqlite:///./test_e2e.db",
            "use_stubs": True,
            "log_level": "DEBUG",
            "redis_url": "redis://localhost:6379/15",  # Use test database
            "external_api_timeout": 5,
            "rate_limit_enabled": False,  # Disable rate limiting in tests
        }
    )

    return test_settings


@pytest.fixture(scope="session")
def test_database_engine(test_settings):
    """Create test database engine with proper isolation"""
    # Create in-memory SQLite database for each test session
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
        echo=test_settings.log_level == "DEBUG",
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db_session(test_database_engine):
    """Cleanup automated - Provide clean database session for each test"""
    SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_database_engine
    )
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def test_db_override(test_db_session):
    """Override database dependency for testing"""

    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    return override_get_db


@pytest.fixture(scope="session")
def stub_server():
    """Start stub server for external API mocking"""
    import threading

    import uvicorn

    from stubs.server import app as stub_app

    # Start stub server in background thread
    def run_server():
        uvicorn.run(stub_app, host="127.0.0.1", port=5010, log_level="error")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get("http://127.0.0.1:5010/health", timeout=1)
            if response.status_code == 200:
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.1)
    else:
        pytest.fail("Stub server failed to start within timeout")

    yield "http://127.0.0.1:5010"

    # Server cleanup happens automatically when thread ends


@pytest.fixture(scope="function")
def clean_test_environment(test_settings, test_db_session):
    """Cleanup automated - Ensure clean state before and after each test"""

    # Pre-test cleanup
    _cleanup_test_data(test_db_session)
    _cleanup_temp_files()

    yield

    # Post-test cleanup
    _cleanup_test_data(test_db_session)
    _cleanup_temp_files()


def _cleanup_test_data(session):
    """Clean up all test data from database"""
    # Import the actual models that exist
    from d11_orchestration.models import (
        Experiment,
        ExperimentMetric,
        ExperimentVariant,
        PipelineRun,
        VariantAssignment,
    )
    from database.models import (
        Batch,
        Business,
        Email,
        EmailClick,
        EmailSuppression,
        GatewayUsage,
        Purchase,
        ScoringResult,
        Target,
        WebhookEvent,
    )

    # Delete in reverse dependency order
    try:
        # Clean up orchestration models first
        session.query(ExperimentMetric).delete()
        session.query(VariantAssignment).delete()
        session.query(ExperimentVariant).delete()
        session.query(Experiment).delete()
        session.query(PipelineRun).delete()

        # Clean up main models
        session.query(EmailClick).delete()
        session.query(EmailSuppression).delete()
        session.query(Email).delete()
        session.query(Purchase).delete()
        session.query(ScoringResult).delete()
        session.query(Business).delete()
        session.query(Batch).delete()
        session.query(Target).delete()
        session.query(WebhookEvent).delete()
        session.query(GatewayUsage).delete()

        session.commit()
    except Exception as e:
        session.rollback()
        # Continue with cleanup even if some tables don't exist


def _cleanup_temp_files():
    """Clean up temporary files and directories"""
    temp_dirs = ["./tmp", "./test_tmp", "./logs/test", "./test_reports"]

    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass  # Continue cleanup even if some files are locked


@pytest.fixture(scope="session")
def parallel_test_config():
    """Parallel test support - Configure pytest-xdist for parallel execution"""
    return {
        "worker_id": os.environ.get("PYTEST_XDIST_WORKER", "master"),
        "worker_count": int(os.environ.get("PYTEST_XDIST_WORKER_COUNT", "1")),
        "is_parallel": os.environ.get("PYTEST_XDIST_WORKER") is not None,
    }


@pytest.fixture(scope="function")
def isolated_test_workspace(parallel_test_config):
    """Create isolated workspace for parallel test execution"""
    worker_id = parallel_test_config["worker_id"]

    # Create worker-specific temporary directory
    base_temp = tempfile.gettempdir()
    worker_temp = os.path.join(base_temp, f"leadfactory_test_{worker_id}")
    os.makedirs(worker_temp, exist_ok=True)

    # Set worker-specific environment variables
    original_env = {}
    test_env = {
        "LEADFACTORY_TEST_WORKSPACE": worker_temp,
        "LEADFACTORY_TEST_WORKER": worker_id,
        "PYTEST_CURRENT_TEST": os.environ.get("PYTEST_CURRENT_TEST", "unknown"),
    }

    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    yield worker_temp

    # Cleanup workspace
    try:
        shutil.rmtree(worker_temp)
    except Exception:
        pass  # Continue even if cleanup fails

    # Restore environment
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture(scope="function")
def mock_external_services(stub_server):
    """Mock external services for reliable testing"""
    with patch.dict(
        os.environ,
        {
            "YELP_API_URL": f"{stub_server}/yelp",
            "OPENAI_API_URL": f"{stub_server}/openai",
            "SENDGRID_API_URL": f"{stub_server}/sendgrid",
            "STRIPE_API_URL": f"{stub_server}/stripe",
            "PAGESPEED_API_URL": f"{stub_server}/pagespeed",
        },
    ):
        yield stub_server


@pytest.fixture(scope="function")
def performance_monitor():
    """Monitor test performance for benchmarking"""
    start_time = time.time()
    memory_usage = []

    def get_memory_usage():
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            return 0

    initial_memory = get_memory_usage()

    yield {
        "start_time": start_time,
        "get_memory": get_memory_usage,
        "initial_memory": initial_memory,
    }

    end_time = time.time()
    final_memory = get_memory_usage()
    duration = end_time - start_time
    memory_delta = final_memory - initial_memory

    # Log performance metrics
    print(f"\nTest Performance: {duration:.2f}s, Memory: {memory_delta:+.1f}MB")


def pytest_configure(config):
    """Configure pytest for e2e testing"""
    # Add custom markers
    config.addinivalue_line("markers", "e2e: end-to-end integration tests")
    config.addinivalue_line("markers", "slow: slow running tests")
    config.addinivalue_line("markers", "external: tests requiring external services")

    # Configure parallel testing
    if hasattr(config.option, "numprocesses") and config.option.numprocesses:
        print(f"Running e2e tests with {config.option.numprocesses} parallel workers")


def pytest_collection_modifyitems(config, items):
    """Modify test collection for e2e tests"""
    for item in items:
        # Mark all tests in e2e directory
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)

        # Mark slow tests
        if "slow" in item.name or item.get_closest_marker("slow"):
            item.add_marker(pytest.mark.slow)


# Pytest hooks for better test reporting
def pytest_runtest_setup(item):
    """Setup hook for each test"""
    if "e2e" in str(item.fspath):
        print(f"\n→ Starting e2e test: {item.name}")


def pytest_runtest_teardown(item, nextitem):
    """Teardown hook for each test"""
    if "e2e" in str(item.fspath):
        print(f"✓ Completed e2e test: {item.name}")
