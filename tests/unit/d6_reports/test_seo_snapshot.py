"""
Test SEO Snapshot functionality for P1-010

Verifies that SEMrush data appears in the PDF report as "SEO Snapshot" section.
"""

import asyncio
from datetime import datetime

import pytest

from d6_reports.generator import ReportGenerator
from d6_reports.template_engine import TemplateData, TemplateEngine


class TestSEOSnapshot:
    """Test SEO Snapshot section in PDF reports"""

    def test_template_includes_seo_snapshot(self):
        """Test that template includes SEO Snapshot section when SEMrush data is present"""
        engine = TemplateEngine()

        # Create test data with SEMrush information
        template_data = TemplateData(
            business={
                "name": "Test Business",
                "url": "https://testbusiness.com",
            },
            assessment={
                "performance_score": 75,
                "accessibility_score": 80,
                "seo_score": 70,
                "semrush_data": {
                    "domain": "testbusiness.com",
                    "organic_keywords": 1500,
                    "organic_traffic": 25000,
                    "organic_cost": 8500.50,
                    "adwords_keywords": 50,
                    "domain_authority": 42,
                    "site_health": 88,
                    "backlink_toxicity": 3,
                    "site_issues": 8,
                },
            },
            findings=[],
            top_issues=[],
            quick_wins=[],
            metadata={"generated_at": datetime.now().isoformat()},
        )

        # Render template
        html = engine.render_template("basic_report", template_data)

        # Verify SEO Snapshot section is present
        assert "SEO Snapshot" in html
        assert "Organic Keywords" in html
        assert "1,500" in html  # Formatted number
        assert "Monthly Organic Traffic" in html
        assert "25,000" in html  # Formatted number
        assert "Domain Authority" in html
        assert "42" in html
        assert "Site Health" in html
        assert "88%" in html

        # Verify SEO Performance Indicators subsection
        assert "SEO Performance Indicators" in html
        assert "Organic Value:" in html
        assert "$8,500" in html  # Formatted currency
        assert "Paid Keywords:" in html
        assert "50" in html
        assert "Backlink Toxicity:" in html
        assert "3%" in html
        assert "Site Issues:" in html
        assert "8 found" in html

    def test_template_hides_seo_snapshot_without_data(self):
        """Test that template hides SEO Snapshot when no SEMrush data"""
        engine = TemplateEngine()

        # Create test data without SEMrush information
        template_data = TemplateData(
            business={
                "name": "Test Business",
                "url": "https://testbusiness.com",
            },
            assessment={
                "performance_score": 75,
                "accessibility_score": 80,
                "seo_score": 70,
                # No semrush_data key
            },
            findings=[],
            top_issues=[],
            quick_wins=[],
            metadata={"generated_at": datetime.now().isoformat()},
        )

        # Render template
        html = engine.render_template("basic_report", template_data)

        # Verify SEO Snapshot section is NOT present
        assert "SEO Snapshot" not in html
        assert "Organic Keywords" not in html
        assert "Monthly Organic Traffic" not in html

    def test_format_number_filter(self):
        """Test the format_number filter works correctly"""
        engine = TemplateEngine()

        # Test various number formats
        test_cases = [
            (1000, "1,000"),
            (25000, "25,000"),
            (1500000, "1,500,000"),
            (0, "0"),
            (None, "0"),
            (12.5, "12"),  # Decimals are truncated
        ]

        for value, expected in test_cases:
            result = engine.env.filters["format_number"](value)
            assert result == expected, f"format_number({value}) should be {expected}, got {result}"

    @pytest.mark.asyncio
    async def test_generator_includes_semrush_data(self):
        """Test that report generator includes SEMrush data in assessment"""
        generator = ReportGenerator()

        # Generate report (uses mock data)
        result = await generator.generate_html_only("test-business-123")

        assert result.success
        assert result.html_content is not None

        # Verify SEMrush data is included in the generated HTML
        assert "SEO Snapshot" in result.html_content
        assert "1,250" in result.html_content  # Mock organic keywords
        assert "45,000" in result.html_content  # Mock organic traffic
        assert "Domain Authority" in result.html_content
        assert "45" in result.html_content  # Mock DA score

    def test_seo_snapshot_partial_data(self):
        """Test SEO Snapshot handles partial data gracefully"""
        engine = TemplateEngine()

        # Create test data with only basic SEMrush fields
        template_data = TemplateData(
            business={
                "name": "Test Business",
                "url": "https://testbusiness.com",
            },
            assessment={
                "performance_score": 75,
                "accessibility_score": 80,
                "seo_score": 70,
                "semrush_data": {
                    "domain": "testbusiness.com",
                    "organic_keywords": 500,
                    "organic_traffic": 10000,
                    "organic_cost": 2500.00,
                    # No extended metrics like domain_authority, site_health, etc.
                },
            },
            findings=[],
            top_issues=[],
            quick_wins=[],
            metadata={"generated_at": datetime.now().isoformat()},
        )

        # Render template
        html = engine.render_template("basic_report", template_data)

        # Verify basic metrics are shown
        assert "SEO Snapshot" in html
        assert "500" in html  # Organic keywords
        assert "10,000" in html  # Organic traffic

        # Verify optional metrics are not shown
        assert "Domain Authority" not in html  # Not in data
        assert "Site Health" not in html  # Not in data
        assert "Backlink Toxicity" not in html  # Not in data

    def test_seo_snapshot_zero_keywords(self):
        """Test SEO Snapshot handles domains with no organic presence"""
        engine = TemplateEngine()

        template_data = TemplateData(
            business={
                "name": "Test Business",
                "url": "https://testbusiness.com",
            },
            assessment={
                "performance_score": 75,
                "accessibility_score": 80,
                "seo_score": 70,
                "semrush_data": {
                    "domain": "testbusiness.com",
                    "organic_keywords": 0,
                    "organic_traffic": 0,
                    "organic_cost": 0,
                },
            },
            findings=[],
            top_issues=[],
            quick_wins=[],
            metadata={"generated_at": datetime.now().isoformat()},
        )

        # Render template
        html = engine.render_template("basic_report", template_data)

        # Verify section is shown but performance indicators are hidden
        assert "SEO Snapshot" in html
        assert "Organic Keywords" in html
        assert "SEO Performance Indicators" not in html  # Hidden when no keywords


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
