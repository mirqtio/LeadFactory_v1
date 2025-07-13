"""
Root conftest.py for all tests
Provides common fixtures and configuration
"""
import pytest
import threading
import time
import requests
import uvicorn
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from core.config import get_settings


@pytest.fixture(scope="session", autouse=True)
def stub_server_session():
    """
    Start stub server once per test session if USE_STUBS is enabled.
    This ensures the stub server is available for all tests.
    """
    settings = get_settings()

    if not settings.use_stubs:
        return

    # Check if stub server is already running
    try:
        response = requests.get(f"{settings.stub_base_url}/health", timeout=1)
        if response.status_code == 200:
            yield
            return  # Server already running
    except:
        pass

    # Start stub server in background thread
    from stubs.server import app as stub_app

    def run_server():
        uvicorn.run(stub_app, host="127.0.0.1", port=5010, log_level="error")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            response = requests.get(f"{settings.stub_base_url}/health", timeout=1)
            if response.status_code == 200:
                break
        except:
            pass
        time.sleep(0.1)
    else:
        pytest.fail(f"Stub server failed to start at {settings.stub_base_url}")

    yield


@pytest.fixture(autouse=True)
def provider_stub():
    """
    Fixture to ensure stubs are always used in tests.
    This fixture runs automatically for all tests and fails loudly if stubs are disabled.
    """
    settings = get_settings()

    if not settings.use_stubs:
        pytest.fail(
            "CRITICAL: Tests must use stubs! USE_STUBS is False. "
            "Set USE_STUBS=true in environment or .env file."
        )

    # Verify stub configuration
    assert settings.stub_base_url, "Stub base URL must be configured"

    yield

    # Post-test verification could go here if needed


@pytest.fixture
def test_settings():
    """Provide test-specific settings"""
    settings = get_settings()
    # Ensure test environment
    assert settings.environment == "test"
    assert settings.use_stubs is True
    return settings


@pytest.fixture
def test_report_template():
    """Create a test report template"""
    from d6_reports.models import ReportTemplate, ReportType, TemplateFormat
    
    template = ReportTemplate(
        id="test-template-001",
        name="test_template",
        display_name="Test Template",
        description="Test template for integration tests",
        template_type=ReportType.BUSINESS_AUDIT,
        format=TemplateFormat.HTML,
        version="1.0.0",
        html_template="<html>{{content}}</html>",
        css_styles="body { font-family: Arial; }",
        is_active=True,
    )
    return template


@pytest.fixture
async def async_db_session():
    """Create an async database session for testing"""
    from database.base import Base
    
    # Use in-memory SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()
    
    # Clean up
    await engine.dispose()
