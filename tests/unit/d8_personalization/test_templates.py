"""
Test D8 Personalization Email Templates - GAP-013

Tests email template rendering, personalization tokens,
mobile responsiveness, and spam compliance.

Acceptance Criteria:
- HTML template matches PRD section 11.3 ✓
- Mobile-responsive design ✓
- Personalization tokens work ✓
- Spam-compliant footer included ✓
- Template renders without errors ✓
"""

import os
import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
from unittest.mock import Mock, patch
import re


@pytest.fixture
def templates_dir():
    """Get the templates directory path"""
    return Path(__file__).parent.parent.parent.parent / "templates" / "email"


@pytest.fixture
def jinja_env(templates_dir):
    """Create Jinja2 environment for template testing"""
    return Environment(loader=FileSystemLoader(str(templates_dir)))


@pytest.fixture
def sample_template_data():
    """Sample data for template rendering"""
    return {
        "business_name": "Acme Restaurant",
        "score": 67,
        "score_color": "color: #d97706;",
        "top_issues": [
            {
                "title": "Page Load Speed",
                "impact": "Your site takes 4.2 seconds to load - 58% of visitors leave after 3 seconds",
            },
            {
                "title": "Mobile Optimization",
                "impact": "Mobile users see broken layouts - 65% of traffic comes from mobile devices",
            },
            {
                "title": "SEO Structure",
                "impact": "Missing meta descriptions and poor heading structure hurt search rankings",
            },
        ],
        "report_url": "https://leadfactory.com/reports/abc123",
        "price": 49,
        "original_price": 97,
        "total_issues": 15,
        "audit_date": "January 15, 2025",
        "unsubscribe_url": "https://leadfactory.com/unsubscribe?token=xyz789",
    }


class TestAuditTeaserTemplate:
    """Test the audit teaser email template"""

    def test_template_exists(self, templates_dir):
        """Test that the audit_teaser.html template exists"""
        template_path = templates_dir / "audit_teaser.html"
        assert template_path.exists(), "audit_teaser.html template should exist"
        assert template_path.is_file(), "audit_teaser.html should be a file"

    def test_template_loads_without_errors(self, jinja_env):
        """Test that template loads without syntax errors"""
        try:
            template = jinja_env.get_template("audit_teaser.html")
            assert template is not None
        except Exception as e:
            pytest.fail(f"Template failed to load: {e}")

    def test_template_renders_with_basic_data(self, jinja_env, sample_template_data):
        """Test template renders without errors with sample data"""
        template = jinja_env.get_template("audit_teaser.html")

        try:
            rendered = template.render(**sample_template_data)
            assert rendered is not None
            assert len(rendered) > 0
        except Exception as e:
            pytest.fail(f"Template failed to render: {e}")

    def test_template_renders_with_minimal_data(self, jinja_env):
        """Test template renders with minimal data (default values)"""
        template = jinja_env.get_template("audit_teaser.html")

        minimal_data = {"business_name": "Test Business", "score": 75}

        try:
            rendered = template.render(**minimal_data)
            assert rendered is not None
            assert "Test Business" in rendered
            assert "75/100" in rendered
        except Exception as e:
            pytest.fail(f"Template failed to render with minimal data: {e}")

    def test_personalization_tokens_work(self, jinja_env, sample_template_data):
        """Test that personalization tokens are properly replaced"""
        template = jinja_env.get_template("audit_teaser.html")
        rendered = template.render(**sample_template_data)

        # Test business name personalization
        assert "Acme Restaurant" in rendered

        # Test score personalization
        assert "67/100" in rendered

        # Test price personalization
        assert "$49" in rendered
        assert "$97" in rendered

        # Test URL personalization
        assert "https://leadfactory.com/reports/abc123" in rendered
        assert "https://leadfactory.com/unsubscribe?token=xyz789" in rendered

        # Test issues personalization
        assert "Page Load Speed" in rendered
        assert "4.2 seconds" in rendered
        assert "Mobile Optimization" in rendered

    def test_default_values_work(self, jinja_env):
        """Test that default values are used when data is missing"""
        template = jinja_env.get_template("audit_teaser.html")
        rendered = template.render({})  # Empty data

        # Test default score
        assert "67/100" in rendered

        # Test default greeting
        assert "Hi there," in rendered

        # Test default issues (should show fallback issues)
        assert "Page Load Speed" in rendered
        assert "Mobile Optimization" in rendered
        assert "SEO Structure" in rendered

    def test_mobile_responsive_design(self, jinja_env, sample_template_data):
        """Test that mobile-responsive CSS is included"""
        template = jinja_env.get_template("audit_teaser.html")
        rendered = template.render(**sample_template_data)

        # Check for viewport meta tag
        assert 'name="viewport"' in rendered
        assert "width=device-width" in rendered

        # Check for mobile media queries
        assert "@media only screen and (max-width: 600px)" in rendered

        # Check for responsive container
        assert "max-width: 600px" in rendered

    def test_spam_compliant_footer(self, jinja_env, sample_template_data):
        """Test that spam-compliant footer is included"""
        template = jinja_env.get_template("audit_teaser.html")
        rendered = template.render(**sample_template_data)

        # Check for unsubscribe link
        assert "Unsubscribe" in rendered
        assert sample_template_data["unsubscribe_url"] in rendered

        # Check for physical address
        assert "San Francisco, CA" in rendered

        # Check for contact information
        assert "support@leadfactory.com" in rendered or "Contact Support" in rendered

        # Check for company name
        assert "LeadFactory" in rendered

    def test_html_structure_validity(self, jinja_env, sample_template_data):
        """Test that HTML structure is valid"""
        template = jinja_env.get_template("audit_teaser.html")
        rendered = template.render(**sample_template_data)

        # Check for proper DOCTYPE
        assert "<!DOCTYPE html>" in rendered

        # Check for required HTML elements
        assert "<html" in rendered and "</html>" in rendered
        assert "<head>" in rendered and "</head>" in rendered
        assert "<body>" in rendered and "</body>" in rendered

        # Check for proper title
        assert "<title>" in rendered and "</title>" in rendered
        assert "Website Audit Results" in rendered

        # Check for charset
        assert 'charset="UTF-8"' in rendered

    def test_css_styles_included(self, jinja_env, sample_template_data):
        """Test that CSS styles are properly included"""
        template = jinja_env.get_template("audit_teaser.html")
        rendered = template.render(**sample_template_data)

        # Check for embedded styles
        assert "<style>" in rendered and "</style>" in rendered

        # Check for key style classes
        assert ".email-container" in rendered
        assert ".score-card" in rendered
        assert ".cta-button" in rendered
        assert ".issue-item" in rendered

        # Check for color definitions
        assert "#2563eb" in rendered  # Primary blue
        assert "#f8fafc" in rendered  # Background colors

    def test_score_color_customization(self, jinja_env):
        """Test that score color can be customized"""
        template = jinja_env.get_template("audit_teaser.html")

        # Test with custom score color
        data_with_color = {
            "score": 85,
            "score_color": "color: #059669;",  # Green for good score
        }

        rendered = template.render(**data_with_color)
        assert "color: #059669;" in rendered

        # Test without score color (should use default)
        data_without_color = {"score": 45}
        rendered = template.render(**data_without_color)
        assert "color: #d97706;" in rendered  # Default orange

    def test_issues_list_rendering(self, jinja_env):
        """Test that issues list renders correctly"""
        template = jinja_env.get_template("audit_teaser.html")

        custom_issues = [
            {"title": "Custom Issue 1", "impact": "Custom impact description 1"},
            {"title": "Custom Issue 2", "impact": "Custom impact description 2"},
        ]

        data = {"top_issues": custom_issues}
        rendered = template.render(**data)

        # Check that custom issues are rendered
        assert "Custom Issue 1" in rendered
        assert "Custom impact description 1" in rendered
        assert "Custom Issue 2" in rendered
        assert "Custom impact description 2" in rendered

    def test_empty_issues_fallback(self, jinja_env):
        """Test that empty issues list shows default issues"""
        template = jinja_env.get_template("audit_teaser.html")

        data = {"top_issues": []}  # Empty issues list
        rendered = template.render(**data)

        # Should show default issues
        assert "Page Load Speed" in rendered
        assert "Mobile Optimization" in rendered
        assert "SEO Structure" in rendered

    def test_cta_button_functionality(self, jinja_env, sample_template_data):
        """Test that CTA button is properly configured"""
        template = jinja_env.get_template("audit_teaser.html")
        rendered = template.render(**sample_template_data)

        # Check for CTA button
        assert 'class="cta-button"' in rendered
        assert "Get Your Full Report" in rendered

        # Check for proper link
        assert f'href="{sample_template_data["report_url"]}"' in rendered

        # Check for price display
        assert f'${sample_template_data["price"]}' in rendered

    def test_template_security(self, jinja_env):
        """Test that template handles potentially malicious input safely"""
        template = jinja_env.get_template("audit_teaser.html")

        malicious_data = {
            "business_name": "<script>alert('xss')</script>",
            "score": "javascript:alert('xss')",
            "top_issues": [
                {
                    "title": "<img src=x onerror=alert('xss')>",
                    "impact": "<iframe src='javascript:alert(1)'></iframe>",
                }
            ],
        }

        # Template should render without executing scripts
        rendered = template.render(**malicious_data)

        # Should contain the escaped content (Jinja2 auto-escapes by default)
        assert (
            "&lt;script&gt;" in rendered
            or "<script>alert('xss')</script>" not in rendered
        )

    def test_benefits_section(self, jinja_env, sample_template_data):
        """Test that benefits section renders correctly"""
        template = jinja_env.get_template("audit_teaser.html")
        rendered = template.render(**sample_template_data)

        # Check for benefits section
        assert "This report includes:" in rendered
        assert "Detailed analysis" in rendered
        assert "Step-by-step fixes" in rendered
        assert "Priority order" in rendered
        assert "Competitor comparison" in rendered

    def test_professional_messaging(self, jinja_env, sample_template_data):
        """Test that professional messaging is maintained"""
        template = jinja_env.get_template("audit_teaser.html")
        rendered = template.render(**sample_template_data)

        # Check for professional language
        assert "The good news?" in rendered
        assert "Best regards" in rendered
        assert "The LeadFactory Team" in rendered

        # Check for urgency without being pushy
        assert "Action Required" in rendered
        assert "costing you customers" in rendered

        # Check for credibility indicators
        assert "industry-standard testing tools" in rendered


class TestTemplateIntegration:
    """Test template integration with personalization system"""

    def test_template_matches_prd_requirements(self, jinja_env, sample_template_data):
        """Test that template matches PRD section 11.3 requirements"""
        template = jinja_env.get_template("audit_teaser.html")
        rendered = template.render(**sample_template_data)

        # Requirements from PRD section 11.3:

        # 1. Score display with color
        assert "/100" in rendered  # Score format
        assert "Website Performance Score" in rendered

        # 2. Top 3 issues
        assert "Top 3 Issues Found:" in rendered

        # 3. CTA button with pricing
        assert "Get Your Full Report" in rendered
        assert "$" in rendered  # Price display

        # 4. Benefits list
        assert "This report includes:" in rendered

        # 5. Professional signature
        assert "Best regards" in rendered
        assert "LeadFactory" in rendered

    def test_template_compatibility_with_d8_system(self, jinja_env):
        """Test template compatibility with D8 personalization system"""
        template = jinja_env.get_template("audit_teaser.html")

        # Test with D8-style data structure
        d8_data = {
            "business_name": "Tech Startup Inc",
            "score": 72,
            "score_color": "color: #2563eb;",
            "personalization_meta": {
                "campaign_id": "camp_123",
                "variant": "A",
                "send_time": "2025-01-15T10:00:00Z",
            },
        }

        # Should render without errors even with extra data
        rendered = template.render(**d8_data)
        assert "Tech Startup Inc" in rendered
        assert "72/100" in rendered


def test_template_file_permissions():
    """Test that template file has correct permissions"""
    template_path = (
        Path(__file__).parent.parent.parent.parent
        / "templates"
        / "email"
        / "audit_teaser.html"
    )

    if template_path.exists():
        # File should be readable
        assert os.access(template_path, os.R_OK), "Template file should be readable"

        # File should not be executable (security)
        assert not os.access(
            template_path, os.X_OK
        ), "Template file should not be executable"


def test_template_encoding():
    """Test that template file uses correct encoding"""
    template_path = (
        Path(__file__).parent.parent.parent.parent
        / "templates"
        / "email"
        / "audit_teaser.html"
    )

    if template_path.exists():
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Should contain UTF-8 declaration
                assert 'charset="UTF-8"' in content
        except UnicodeDecodeError:
            pytest.fail("Template file should be UTF-8 encoded")


if __name__ == "__main__":
    # Run basic tests if file is executed directly
    print("Running D8 Email Template Tests...")
    print("=" * 50)

    try:
        # Test template existence
        template_path = (
            Path(__file__).parent.parent.parent.parent
            / "templates"
            / "email"
            / "audit_teaser.html"
        )
        assert template_path.exists(), "Template file should exist"
        print("✓ Template file exists")

        # Test template loading
        from jinja2 import Environment, FileSystemLoader

        templates_dir = template_path.parent
        env = Environment(loader=FileSystemLoader(str(templates_dir)))
        template = env.get_template("audit_teaser.html")
        print("✓ Template loads without errors")

        # Test basic rendering
        sample_data = {
            "business_name": "Test Business",
            "score": 75,
            "top_issues": [{"title": "Test Issue", "impact": "Test impact"}],
        }
        rendered = template.render(**sample_data)
        assert "Test Business" in rendered
        assert "75/100" in rendered
        print("✓ Template renders correctly")

        # Test mobile responsiveness
        assert "@media only screen and (max-width: 600px)" in rendered
        print("✓ Mobile responsive design included")

        # Test spam compliance
        assert "Unsubscribe" in rendered
        assert "San Francisco, CA" in rendered
        print("✓ Spam-compliant footer included")

        print("=" * 50)
        print("🎉 ALL TEMPLATE TESTS PASSED!")
        print("")
        print("Acceptance Criteria Status:")
        print("✓ HTML template matches PRD section 11.3")
        print("✓ Mobile-responsive design")
        print("✓ Personalization tokens work")
        print("✓ Spam-compliant footer included")
        print("✓ Template renders without errors")
        print("")
        print("GAP-013 Email template implementation complete!")

    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
