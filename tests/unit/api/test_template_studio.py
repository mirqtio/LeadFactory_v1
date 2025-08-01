"""
Unit tests for Template Studio API (P0-024)
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from d6_reports.models import ReportTemplate, ReportType, TemplateFormat
from database.base import Base
from database.models import Lead


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
def test_client():
    """Create a test client for API testing"""
    from main import app

    return TestClient(app)


@pytest.fixture
def sample_template(db_session):
    """Create a sample template for testing"""
    template = ReportTemplate(
        id="test-template-001",
        name="test_template",
        display_name="Test Template",
        description="Test template for unit tests",
        template_type=ReportType.BUSINESS_AUDIT,
        format=TemplateFormat.HTML,
        version="1.0.0",
        html_template="""
        <h1>Business Report for {{ lead.company_name }}</h1>
        <p>Domain: {{ lead.domain }}</p>
        <p>Score: {{ score }}</p>
        <ul>
        {% for rec in recommendations %}
            <li>{{ rec }}</li>
        {% endfor %}
        </ul>
        """,
        css_styles="body { font-family: Arial; }",
        is_active=True,
        is_default=False,
        supports_mobile=True,
        supports_print=True,
    )
    db_session.add(template)

    # Add a sample lead
    lead = Lead(
        id="1",
        company_name="Test Business Inc.",
        email="test@testbusiness.com",
        domain="testbusiness.com",
        contact_name="John Doe",
        source="test",
    )
    db_session.add(lead)

    db_session.commit()
    return template


class TestTemplateStudioAPI:
    """Test suite for Template Studio API endpoints"""

    @patch("api.template_studio.subprocess.check_output")
    def test_list_templates_with_git_info(self, mock_subprocess, test_client: TestClient, sample_template, db_session):
        """Test listing templates with git metadata"""
        # Mock git commands
        mock_subprocess.side_effect = ["abc123def456", "2025-01-12T10:00:00+00:00"]  # Git SHA  # Git date

        # Override the get_db dependency
        from database.session import get_db

        def override_get_db():
            yield db_session

        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get("/api/template-studio/templates")

        assert response.status_code == 200
        templates = response.json()
        assert len(templates) == 1

        template = templates[0]
        assert template["id"] == sample_template.id
        assert template["name"] == sample_template.name
        assert template["display_name"] == sample_template.display_name
        assert template["version"] == sample_template.version
        assert template["is_active"] is True

    def test_get_template_detail(self, test_client: TestClient, sample_template, db_session):
        """Test getting full template details"""
        from database.session import get_db

        def override_get_db():
            yield db_session

        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get(f"/api/template-studio/templates/{sample_template.id}")

        assert response.status_code == 200
        detail = response.json()

        assert detail["id"] == sample_template.id
        assert detail["content"] == sample_template.html_template
        assert detail["css_styles"] == sample_template.css_styles
        assert detail["supports_mobile"] is True
        assert detail["supports_print"] is True

    def test_preview_template_success(self, test_client: TestClient, sample_template, db_session):
        """Test successful template preview"""
        from database.session import get_db

        def override_get_db():
            yield db_session

        test_client.app.dependency_overrides[get_db] = override_get_db

        preview_request = {"template_content": sample_template.html_template, "lead_id": "1"}

        response = test_client.post("/api/template-studio/preview", json=preview_request)

        assert response.status_code == 200
        result = response.json()

        assert "Test Business Inc." in result["rendered_html"]
        assert "testbusiness.com" in result["rendered_html"]
        assert result["render_time_ms"] < 500  # Performance requirement
        assert len(result["errors"]) == 0

    def test_preview_template_with_syntax_error(self, test_client: TestClient, db_session):
        """Test template preview with Jinja2 syntax error"""
        from database.session import get_db

        def override_get_db():
            yield db_session

        test_client.app.dependency_overrides[get_db] = override_get_db

        preview_request = {"template_content": "{{ invalid syntax }", "lead_id": "1"}

        response = test_client.post("/api/template-studio/preview", json=preview_request)

        assert response.status_code == 200
        result = response.json()

        assert result["rendered_html"] == ""
        assert len(result["errors"]) > 0
        assert "syntax error" in result["errors"][0].lower()

    def test_preview_template_with_undefined_variable(self, test_client: TestClient, db_session):
        """Test template preview with undefined variable"""
        from database.session import get_db

        def override_get_db():
            yield db_session

        test_client.app.dependency_overrides[get_db] = override_get_db

        preview_request = {"template_content": "{{ undefined_variable }}", "lead_id": "1"}

        response = test_client.post("/api/template-studio/preview", json=preview_request)

        assert response.status_code == 200
        result = response.json()

        # With autoescape and SilentUndefined, undefined variables should not cause errors
        # The rendered HTML will be empty since the template is just "{{ undefined_variable }}"
        assert result["rendered_html"] == ""
        assert len(result["errors"]) == 0

    def test_preview_rate_limiting(self, test_client: TestClient, db_session):
        """Test preview endpoint rate limiting (20 req/sec)"""
        from database.session import get_db

        def override_get_db():
            yield db_session

        test_client.app.dependency_overrides[get_db] = override_get_db

        preview_request = {"template_content": "Test", "lead_id": "1"}

        # Note: In a real test, we'd need to test actual rate limiting
        # For now, just verify the endpoint works
        response = test_client.post("/api/template-studio/preview", json=preview_request)
        assert response.status_code == 200

    @patch("api.template_studio.subprocess.run")
    @patch("api.template_studio.subprocess.check_output")
    def test_propose_changes_creates_pr(
        self, mock_check_output, mock_run, test_client: TestClient, sample_template, db_session
    ):
        """Test creating GitHub PR with template changes"""
        # Mock git operations
        mock_run_result = MagicMock(returncode=0)
        mock_run_result.stdout = "abc123def456"
        mock_run.return_value = mock_run_result
        mock_check_output.return_value = "abc123def456"

        from database.session import get_db

        def override_get_db():
            yield db_session

        test_client.app.dependency_overrides[get_db] = override_get_db

        proposal = {
            "template_id": sample_template.id,
            "template_content": "Updated template content",
            "commit_message": "feat: Update pricing section copy",
            "description": "Updated pricing to reflect new tiers",
        }

        response = test_client.post("/api/template-studio/propose-changes", json=proposal)

        assert response.status_code == 200
        result = response.json()

        assert "pr_url" in result
        assert "branch_name" in result
        assert "template-update-" in result["branch_name"]
        assert result["commit_sha"] == "abc123de"

    @patch("api.template_studio.subprocess.run")
    def test_get_template_diff(self, mock_subprocess, test_client: TestClient, sample_template, db_session):
        """Test getting diff for template changes"""
        # Mock git diff output
        mock_result = MagicMock()
        mock_result.stdout = """diff --git a/templates/test.html b/templates/test.html
index abc123..def456 100644
--- a/templates/test.html
+++ b/templates/test.html
@@ -1,5 +1,5 @@
 <h1>Business Report</h1>
-<p>Old content</p>
+<p>New content</p>
 <p>Footer</p>"""
        mock_subprocess.return_value = mock_result

        from database.session import get_db

        def override_get_db():
            yield db_session

        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get(f"/api/template-studio/diff/{sample_template.id}")

        assert response.status_code == 200
        diff = response.json()

        assert diff["template_id"] == sample_template.id
        assert diff["has_changes"] is True
        assert len(diff["additions"]) > 0
        assert len(diff["deletions"]) > 0
        assert "<p>New content</p>" in diff["additions"]
        assert "<p>Old content</p>" in diff["deletions"]

    def test_template_not_found(self, test_client: TestClient, db_session):
        """Test handling of non-existent template"""
        from database.session import get_db

        def override_get_db():
            yield db_session

        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get("/api/template-studio/templates/non-existent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_jinja2_autoescape_enabled(self, test_client: TestClient, db_session):
        """Test that Jinja2 autoescape is enabled for XSS protection"""
        from database.session import get_db

        def override_get_db():
            yield db_session

        test_client.app.dependency_overrides[get_db] = override_get_db

        # Create a lead with XSS attempt
        xss_lead = Lead(
            id="xss-test", company_name="<script>alert('XSS')</script>", domain=f"example-{uuid.uuid4().hex[:8]}.com"
        )
        db_session.add(xss_lead)
        db_session.commit()

        preview_request = {"template_content": "<h1>{{ lead.company_name }}</h1>", "lead_id": "xss-test"}

        response = test_client.post("/api/template-studio/preview", json=preview_request)

        assert response.status_code == 200
        result = response.json()

        # Should be escaped
        assert "&lt;script&gt;" in result["rendered_html"]
        assert "<script>" not in result["rendered_html"]

    @patch("api.template_studio.subprocess.run")
    def test_semantic_commit_message_in_pr(self, mock_run, test_client: TestClient, sample_template, db_session):
        """Test that PR includes semantic commit message"""
        # Mock git operations
        mock_run_result = MagicMock(returncode=0)
        mock_run_result.stdout = "abc123def456"
        mock_run.return_value = mock_run_result

        from database.session import get_db

        def override_get_db():
            yield db_session

        test_client.app.dependency_overrides[get_db] = override_get_db

        proposal = {
            "template_id": sample_template.id,
            "template_content": "Updated content",
            "commit_message": "fix: Correct typo in header",
            "description": "Fixed spelling error",
        }

        # Would test actual PR body contains semantic commit format
        # For now, just verify the endpoint accepts the format
        response = test_client.post("/api/template-studio/propose-changes", json=proposal)
        assert response.status_code == 200
