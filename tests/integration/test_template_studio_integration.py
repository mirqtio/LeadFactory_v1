"""
Integration tests for Template Studio (P0-024)
"""

import pytest
from sqlalchemy.orm import Session

from d6_reports.models import ReportTemplate, ReportType, TemplateFormat
from database.models import Lead


class TestTemplateStudioIntegration:
    """Integration tests for Template Studio functionality"""

    @pytest.fixture
    def test_template(self, db_session: Session):
        """Create a test template"""
        template = ReportTemplate(
            id="integration-test-template",
            name="integration_test",
            display_name="Integration Test Template",
            description="Template for integration testing",
            template_type=ReportType.BUSINESS_AUDIT,
            format=TemplateFormat.HTML,
            version="1.0.0",
            html_template="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{{ lead.business_name }} Report</title>
                <style>{{ css_styles }}</style>
            </head>
            <body>
                <h1>Business Audit Report</h1>
                <h2>{{ lead.business_name }}</h2>
                <p>Website: <a href="{{ lead.website }}">{{ lead.website }}</a></p>
                <p>Score: {{ score }}%</p>
                
                <h3>Recommendations:</h3>
                <ul>
                {% for recommendation in recommendations %}
                    <li>{{ recommendation }}</li>
                {% endfor %}
                </ul>
                
                <footer>
                    <p>Report generated on {{ report_date }}</p>
                </footer>
            </body>
            </html>
            """,
            css_styles="""
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            h2 { color: #666; }
            a { color: #007bff; }
            """,
            is_active=True,
            supports_mobile=True,
            supports_print=True
        )
        db_session.add(template)
        db_session.commit()
        return template

    @pytest.fixture
    def test_lead(self, db_session: Session):
        """Create a test lead"""
        lead = Lead(
            id="integration-test-lead",
            business_name="Acme Corporation",
            website="https://acme.example.com",
            phone="(555) 987-6543",
            email="contact@acme.example.com",
            street_address="456 Business Blvd",
            city="Enterprise City",
            state="NY",
            zip_code="10001"
        )
        db_session.add(lead)
        db_session.commit()
        return lead

    def test_template_workflow(self, test_client, test_template, test_lead, db_session):
        """Test complete template editing workflow"""
        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        # 1. List templates
        response = test_client.get("/api/template-studio/templates")
        assert response.status_code == 200
        templates = response.json()
        assert any(t["id"] == test_template.id for t in templates)

        # 2. Get template details
        response = test_client.get(f"/api/template-studio/templates/{test_template.id}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["content"] == test_template.html_template

        # 3. Preview with modifications
        modified_content = detail["content"].replace(
            "Business Audit Report",
            "Premium Business Audit Report"
        )

        preview_request = {
            "template_content": modified_content,
            "lead_id": test_lead.id
        }

        response = test_client.post("/api/template-studio/preview", json=preview_request)
        assert response.status_code == 200
        preview = response.json()

        assert "Premium Business Audit Report" in preview["rendered_html"]
        assert "Acme Corporation" in preview["rendered_html"]
        assert preview["render_time_ms"] < 500
        assert len(preview["errors"]) == 0

    def test_template_syntax_validation(self, test_client, db_session):
        """Test template syntax validation catches errors"""
        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        # Test various syntax errors
        syntax_errors = [
            "{% for item in items %}{{ item }}",  # Missing endfor
            "{{ lead.business_name | undefined_filter }}",  # Unknown filter
            "{% if condition %}content{% endif",  # Malformed tag
        ]

        for template_content in syntax_errors:
            response = test_client.post("/api/template-studio/preview", json={
                "template_content": template_content,
                "lead_id": "1"
            })

            assert response.status_code == 200
            result = response.json()
            assert len(result["errors"]) > 0

    def test_xss_prevention(self, test_client, db_session):
        """Test XSS prevention in template rendering"""
        # Create a lead with potential XSS content
        xss_lead = Lead(
            id="xss-test-lead",
            business_name="<img src=x onerror=alert('XSS')>",
            website="javascript:alert('XSS')",
            email="test@example.com<script>alert('XSS')</script>"
        )
        db_session.add(xss_lead)
        db_session.commit()

        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        template_content = """
        <h1>{{ lead.business_name }}</h1>
        <p>Website: {{ lead.website }}</p>
        <p>Email: {{ lead.email }}</p>
        """

        response = test_client.post("/api/template-studio/preview", json={
            "template_content": template_content,
            "lead_id": "xss-test-lead"
        })

        assert response.status_code == 200
        result = response.json()

        # Check that dangerous content is escaped
        html = result["rendered_html"]
        assert "<img src=x onerror=alert" not in html
        assert "&lt;img" in html or "&#x3C;img" in html
        assert "javascript:alert" not in html
        assert "<script>" not in html
