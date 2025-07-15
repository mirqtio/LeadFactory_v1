"""
Test configuration for lineage unit tests
"""

import os

# Set test environment before any other imports
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["USE_STUBS"] = "true"
os.environ["TESTING"] = "true"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from d6_reports.lineage.models import ReportLineage, ReportLineageAudit  # noqa: F401

# Import models needed for lineage tests
from d6_reports.models import ReportGeneration, ReportTemplate, ReportType, TemplateFormat  # noqa: F401
from database.base import Base

# Import all models to ensure tables are created
import database.models  # noqa: F401
import d1_targeting.models  # noqa: F401 
import d2_sourcing.models  # noqa: F401
import d3_assessment.models  # noqa: F401
import d4_enrichment.models  # noqa: F401
import d5_scoring.models  # noqa: F401
import d7_storefront.models  # noqa: F401
import d10_analytics.models  # noqa: F401


@pytest.fixture(scope="function")
def db_session():
    """Create a database session for testing"""
    engine = create_engine(
        "sqlite:///:memory:", echo=False, poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    # Enable foreign key constraints for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    Session = scoped_session(sessionmaker(bind=engine))
    session = Session()

    yield session

    session.close()
    Session.remove()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def test_report_template(db_session):
    """Create a test report template"""
    template = ReportTemplate(
        id="test-template-001",
        name="test_template",
        display_name="Test Template",
        description="Test template for unit tests",
        template_type=ReportType.BUSINESS_AUDIT,
        format=TemplateFormat.HTML,
        version="1.0.0",
        html_template="<html>{{content}}</html>",
        css_styles="body { font-family: Arial; }",
        is_active=True,
        is_default=True,
        supports_mobile=True,
        supports_print=True,
    )
    db_session.add(template)
    db_session.commit()
    return template


@pytest.fixture
def test_client(db_session):
    """Create a test client for API testing"""
    from main import app
    from database import session as db_module
    
    # Monkey-patch SessionLocal to use our test engine
    original_session_local = db_module.SessionLocal
    db_module.SessionLocal = lambda: db_session
    
    # Override the dependency to use our test session
    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # Don't close the session, let the fixture handle it
    
    from database.session import get_db
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as client:
        yield client
        
    # Clean up
    app.dependency_overrides.clear()
    db_module.SessionLocal = original_session_local


