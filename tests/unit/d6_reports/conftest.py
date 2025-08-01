"""
Test configuration for d6_reports unit tests
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from d6_reports.models import ReportTemplate, ReportType, TemplateFormat  # noqa: F401
from database.base import Base


@pytest.fixture(scope="function")
def db_session():
    """Create a database session for testing"""
    engine = create_engine(
        "sqlite:///:memory:", echo=False, poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
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
def test_client():
    """Create a test client for API testing"""
    from main import app

    return TestClient(app)
