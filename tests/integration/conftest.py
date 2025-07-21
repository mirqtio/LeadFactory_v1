"""
Configuration for integration tests

Uses centralized fixtures from tests.fixtures package.
"""

import pytest

from d6_reports.models import ReportGeneration, ReportTemplate, ReportType, TemplateFormat

# Import centralized fixtures
from tests.fixtures import async_test_db, test_client, test_db  # noqa: F401

# Re-export commonly used fixtures for backward compatibility
db_session = test_db  # Alias for backward compatibility
async_db_session = async_test_db  # Alias for backward compatibility


@pytest.fixture
def test_report_template(db_session):
    """Create a test report template"""
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
        is_default=True,
        supports_mobile=True,
        supports_print=True,
    )
    db_session.add(template)
    db_session.commit()
    return template


# Import cleanup fixture to ensure it's available
try:
    from tests.fixtures.cleanup import cleanup_database  # noqa: F401
except ImportError:
    pass
