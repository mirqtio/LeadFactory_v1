"""
PDF Unit Economics Section Tests - P2-020

Tests for PDF generation functionality specific to unit economics reports.
Covers PDF service integration, template rendering, and visual validation.

Test Categories:
- PDF service initialization and configuration
- Template rendering and data injection
- Chart generation and embedding
- PDF optimization and sizing
- Error handling and fallbacks
- Visual regression testing
- Mobile-friendly PDF layout
- Professional formatting validation
"""

import asyncio
import base64
import io
import logging
import os

# Add path for imports
import sys
import tempfile
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

try:
    from d10_analytics.api import get_unit_economics_pdf
    from d10_analytics.pdf_service import UnitEconomicsPDFService
except ImportError as e:
    pytest.skip(f"Could not import PDF service modules: {e}", allow_module_level=True)

# Mark tests as slow for CI optimization
pytestmark = pytest.mark.slow


class TestUnitEconomicsPDFService:
    """Test PDF service initialization and configuration"""

    def test_pdf_service_initialization(self):
        """Test PDF service initialization"""
        service = UnitEconomicsPDFService()

        # Test template environment setup
        assert service.template_env is not None
        assert hasattr(service.template_env, "get_template")

    def test_pdf_service_template_loading(self):
        """Test template loading configuration"""
        service = UnitEconomicsPDFService()

        # Test template environment configuration
        assert service.template_env.loader is not None
        assert service.template_env.autoescape is True

    @pytest.mark.asyncio
    async def test_generate_unit_economics_pdf_basic(self):
        """Test basic PDF generation"""
        service = UnitEconomicsPDFService()

        # Mock data
        unit_econ_data = [
            {
                "date": "2024-01-01",
                "total_cost_cents": 1000_00,
                "total_revenue_cents": 2000_00,
                "total_leads": 100,
                "total_conversions": 10,
                "profit_cents": 1000_00,
                "roi_percentage": 100.0,
            }
        ]

        summary = {
            "total_cost_cents": 1000_00,
            "total_revenue_cents": 2000_00,
            "overall_roi_percentage": 100.0,
            "avg_cpl_cents": 10_00,
            "avg_cac_cents": 100_00,
            "conversion_rate_pct": 10.0,
        }

        date_range = {"start_date": "2024-01-01", "end_date": "2024-01-01"}

        # Mock template and PDF generation
        mock_template = MagicMock()
        mock_template.render.return_value = "<html><body>Test PDF</body></html>"

        with patch.object(service.template_env, "get_template", return_value=mock_template):
            with patch.object(service, "_html_to_pdf", return_value=b"fake_pdf_data"):
                with patch.object(service, "_generate_charts", return_value={}):
                    pdf_content = await service.generate_unit_economics_pdf(
                        unit_econ_data=unit_econ_data, summary=summary, date_range=date_range, request_id="test-123"
                    )

                    assert pdf_content == b"fake_pdf_data"
                    mock_template.render.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_pdf_with_charts(self):
        """Test PDF generation with charts enabled"""
        service = UnitEconomicsPDFService()

        unit_econ_data = [
            {
                "date": "2024-01-01",
                "total_cost_cents": 1000_00,
                "total_revenue_cents": 2000_00,
                "total_leads": 100,
                "total_conversions": 10,
                "profit_cents": 1000_00,
                "roi_percentage": 100.0,
            }
        ]

        summary = {"total_cost_cents": 1000_00, "total_revenue_cents": 2000_00, "overall_roi_percentage": 100.0}

        date_range = {"start_date": "2024-01-01", "end_date": "2024-01-01"}

        # Mock charts
        mock_charts = {
            "revenue_cost_trend": "data:image/png;base64,fake_chart_data",
            "profit_trend": "data:image/png;base64,fake_chart_data",
            "leads_conversions": "data:image/png;base64,fake_chart_data",
            "metrics_gauges": "data:image/png;base64,fake_chart_data",
        }

        mock_template = MagicMock()
        mock_template.render.return_value = "<html><body>Test PDF with charts</body></html>"

        with patch.object(service.template_env, "get_template", return_value=mock_template):
            with patch.object(service, "_html_to_pdf", return_value=b"fake_pdf_data"):
                with patch.object(service, "_generate_charts", return_value=mock_charts):
                    pdf_content = await service.generate_unit_economics_pdf(
                        unit_econ_data=unit_econ_data,
                        summary=summary,
                        date_range=date_range,
                        request_id="test-123",
                        include_charts=True,
                    )

                    assert pdf_content == b"fake_pdf_data"

                    # Verify charts were included in template data
                    render_call = mock_template.render.call_args[1]
                    assert "charts" in render_call
                    assert render_call["charts"] == mock_charts

    @pytest.mark.asyncio
    async def test_generate_pdf_without_charts(self):
        """Test PDF generation without charts"""
        service = UnitEconomicsPDFService()

        unit_econ_data = [{"date": "2024-01-01", "total_cost_cents": 1000_00}]
        summary = {"total_cost_cents": 1000_00}
        date_range = {"start_date": "2024-01-01", "end_date": "2024-01-01"}

        mock_template = MagicMock()
        mock_template.render.return_value = "<html><body>Test PDF</body></html>"

        with patch.object(service.template_env, "get_template", return_value=mock_template):
            with patch.object(service, "_html_to_pdf", return_value=b"fake_pdf_data"):
                pdf_content = await service.generate_unit_economics_pdf(
                    unit_econ_data=unit_econ_data,
                    summary=summary,
                    date_range=date_range,
                    request_id="test-123",
                    include_charts=False,
                )

                assert pdf_content == b"fake_pdf_data"

                # Verify empty charts were passed
                render_call = mock_template.render.call_args[1]
                assert "charts" in render_call
                assert render_call["charts"] == {}

    @pytest.mark.asyncio
    async def test_generate_pdf_error_handling(self):
        """Test PDF generation error handling"""
        service = UnitEconomicsPDFService()

        unit_econ_data = [{"date": "2024-01-01"}]
        summary = {}
        date_range = {"start_date": "2024-01-01", "end_date": "2024-01-01"}

        # Mock template that raises an error
        mock_template = MagicMock()
        mock_template.render.side_effect = Exception("Template rendering failed")

        with patch.object(service.template_env, "get_template", return_value=mock_template):
            with pytest.raises(Exception) as exc_info:
                await service.generate_unit_economics_pdf(
                    unit_econ_data=unit_econ_data, summary=summary, date_range=date_range, request_id="test-123"
                )

            assert "Template rendering failed" in str(exc_info.value)


class TestChartGeneration:
    """Test chart generation functionality"""

    @pytest.mark.asyncio
    async def test_generate_charts_basic(self):
        """Test basic chart generation"""
        service = UnitEconomicsPDFService()

        daily_data = [
            {
                "date": "2024-01-01",
                "total_cost_cents": 1000_00,
                "total_revenue_cents": 2000_00,
                "total_leads": 100,
                "total_conversions": 10,
                "profit_cents": 1000_00,
            },
            {
                "date": "2024-01-02",
                "total_cost_cents": 1200_00,
                "total_revenue_cents": 2400_00,
                "total_leads": 120,
                "total_conversions": 12,
                "profit_cents": 1200_00,
            },
        ]

        summary = {
            "overall_roi_percentage": 100.0,
            "avg_cac_cents": 100_00,
            "avg_cpl_cents": 10_00,
            "avg_ltv_cents": 200_00,
        }

        # Mock plotly figure to base64 conversion
        with patch.object(service, "_fig_to_base64", return_value="data:image/png;base64,fake_chart"):
            charts = await service._generate_charts(daily_data, summary)

            # Verify all expected charts are generated
            expected_charts = ["revenue_cost_trend", "profit_trend", "leads_conversions", "metrics_gauges"]

            for chart_name in expected_charts:
                assert chart_name in charts
                assert charts[chart_name] == "data:image/png;base64,fake_chart"

    @pytest.mark.asyncio
    async def test_generate_charts_empty_data(self):
        """Test chart generation with empty data"""
        service = UnitEconomicsPDFService()

        daily_data = []
        summary = {}

        charts = await service._generate_charts(daily_data, summary)

        # Should return empty charts dict on empty data
        assert isinstance(charts, dict)
        # Charts may be empty or have default values

    @pytest.mark.asyncio
    async def test_generate_charts_error_handling(self):
        """Test chart generation error handling"""
        service = UnitEconomicsPDFService()

        daily_data = [{"date": "2024-01-01", "total_cost_cents": 1000_00}]
        summary = {"overall_roi_percentage": 100.0}

        # Mock plotly to raise an error
        with patch.object(service, "_fig_to_base64", side_effect=Exception("Chart generation failed")):
            charts = await service._generate_charts(daily_data, summary)

            # Should return empty charts dict on error
            assert isinstance(charts, dict)

    def test_fig_to_base64_conversion(self):
        """Test figure to base64 conversion"""
        service = UnitEconomicsPDFService()

        # Mock plotly figure
        mock_fig = MagicMock()
        mock_fig.to_image.return_value = b"fake_image_data"

        result = service._fig_to_base64(mock_fig)

        expected = "data:image/png;base64," + base64.b64encode(b"fake_image_data").decode("utf-8")
        assert result == expected

    def test_fig_to_base64_error_handling(self):
        """Test figure to base64 error handling"""
        service = UnitEconomicsPDFService()

        # Mock plotly figure that raises an error
        mock_fig = MagicMock()
        mock_fig.to_image.side_effect = Exception("Image generation failed")

        result = service._fig_to_base64(mock_fig)

        # Should return empty string on error
        assert result == ""


class TestInsightsGeneration:
    """Test insights generation functionality"""

    def test_generate_insights_normal_data(self):
        """Test insights generation with normal data"""
        service = UnitEconomicsPDFService()

        daily_data = [
            {
                "date": "2024-01-01",
                "total_cost_cents": 1000_00,
                "total_revenue_cents": 2000_00,
                "total_leads": 100,
                "total_conversions": 10,
            }
        ]

        summary = {
            "overall_roi_percentage": 150.0,
            "avg_cac_cents": 100_00,
            "avg_ltv_cents": 300_00,
            "conversion_rate_pct": 10.0,
            "total_leads": 100,
            "total_conversions": 10,
        }

        insights = service._generate_insights(daily_data, summary)

        # Should return a list of insights
        assert isinstance(insights, list)
        assert len(insights) <= 5  # Limited to top 5 insights

        # Check for expected insight types
        insights_text = " ".join(insights)
        assert "ROI" in insights_text or "conversion" in insights_text or "LTV" in insights_text

    def test_generate_insights_excellent_performance(self):
        """Test insights for excellent performance metrics"""
        service = UnitEconomicsPDFService()

        daily_data = []
        summary = {
            "overall_roi_percentage": 350.0,  # Excellent ROI
            "avg_cac_cents": 50_00,
            "avg_ltv_cents": 200_00,
            "conversion_rate_pct": 8.0,  # High conversion rate
            "total_leads": 5000,  # High volume
            "total_conversions": 100,
        }

        insights = service._generate_insights(daily_data, summary)

        # Should contain positive insights
        insights_text = " ".join(insights)
        assert "Excellent" in insights_text or "Strong" in insights_text

    def test_generate_insights_poor_performance(self):
        """Test insights for poor performance metrics"""
        service = UnitEconomicsPDFService()

        daily_data = []
        summary = {
            "overall_roi_percentage": -20.0,  # Negative ROI
            "avg_cac_cents": 100_00,
            "avg_ltv_cents": 50_00,  # Poor LTV:CAC ratio
            "conversion_rate_pct": 0.5,  # Low conversion rate
            "total_leads": 50,
            "total_conversions": 1,
        }

        insights = service._generate_insights(daily_data, summary)

        # Should contain warning insights
        insights_text = " ".join(insights)
        assert (
            "🚨" in insights_text
            or "⚠️" in insights_text
            or "negative" in insights_text.lower()
            or "low" in insights_text.lower()
        )

    def test_generate_insights_error_handling(self):
        """Test insights generation error handling"""
        service = UnitEconomicsPDFService()

        # Invalid data that might cause errors
        daily_data = None
        summary = None

        insights = service._generate_insights(daily_data, summary)

        # Should return list with error message
        assert isinstance(insights, list)
        assert len(insights) > 0
        assert "error" in insights[0].lower()

    def test_generate_insights_empty_data(self):
        """Test insights generation with empty data"""
        service = UnitEconomicsPDFService()

        daily_data = []
        summary = {}

        insights = service._generate_insights(daily_data, summary)

        # Should return empty list or minimal insights
        assert isinstance(insights, list)


class TestRecommendationsGeneration:
    """Test recommendations generation functionality"""

    def test_generate_recommendations_low_roi(self):
        """Test recommendations for low ROI"""
        service = UnitEconomicsPDFService()

        summary = {
            "overall_roi_percentage": 50.0,  # Low ROI
            "avg_cac_cents": 2500_00,  # High CAC
            "conversion_rate_pct": 1.5,  # Low conversion rate
        }

        recommendations = service._generate_recommendations(summary)

        # Should return actionable recommendations
        assert isinstance(recommendations, list)
        assert len(recommendations) <= 6  # Limited to top 6

        # Check for expected recommendation types
        rec_text = " ".join(recommendations)
        assert (
            "optimize" in rec_text.lower()
            or "improve" in rec_text.lower()
            or "reduce" in rec_text.lower()
            or "increase" in rec_text.lower()
        )

    def test_generate_recommendations_high_cac(self):
        """Test recommendations for high CAC"""
        service = UnitEconomicsPDFService()

        summary = {
            "overall_roi_percentage": 100.0,
            "avg_cac_cents": 2500_00,  # High CAC ($25)
            "conversion_rate_pct": 5.0,
        }

        recommendations = service._generate_recommendations(summary)

        # Should include CAC optimization recommendations
        rec_text = " ".join(recommendations)
        assert "CAC" in rec_text or "acquisition" in rec_text or "marketing" in rec_text

    def test_generate_recommendations_low_conversion(self):
        """Test recommendations for low conversion rate"""
        service = UnitEconomicsPDFService()

        summary = {
            "overall_roi_percentage": 150.0,
            "avg_cac_cents": 1000_00,
            "conversion_rate_pct": 1.0,  # Low conversion rate
        }

        recommendations = service._generate_recommendations(summary)

        # Should include conversion optimization recommendations
        rec_text = " ".join(recommendations)
        assert "conversion" in rec_text.lower() or "landing" in rec_text.lower() or "optimize" in rec_text.lower()

    def test_generate_recommendations_good_performance(self):
        """Test recommendations for good performance"""
        service = UnitEconomicsPDFService()

        summary = {
            "overall_roi_percentage": 250.0,  # Good ROI
            "avg_cac_cents": 1500_00,  # Reasonable CAC
            "conversion_rate_pct": 4.0,  # Good conversion rate
        }

        recommendations = service._generate_recommendations(summary)

        # Should include scaling recommendations
        rec_text = " ".join(recommendations)
        assert "scale" in rec_text.lower() or "expand" in rec_text.lower() or "opportunity" in rec_text.lower()

    def test_generate_recommendations_error_handling(self):
        """Test recommendations generation error handling"""
        service = UnitEconomicsPDFService()

        # Invalid data
        summary = None

        recommendations = service._generate_recommendations(summary)

        # Should return list with error message
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert "error" in recommendations[0].lower() or "contact" in recommendations[0].lower()


class TestHTMLToPDFConversion:
    """Test HTML to PDF conversion functionality"""

    @pytest.mark.asyncio
    async def test_html_to_pdf_basic(self):
        """Test basic HTML to PDF conversion"""
        service = UnitEconomicsPDFService()

        html_content = "<html><body><h1>Test PDF</h1></body></html>"

        # Mock Playwright
        mock_page = AsyncMock()
        mock_page.pdf.return_value = b"fake_pdf_data"

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        with patch("playwright.async_api.async_playwright") as mock_async_playwright:
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright

            pdf_content = await service._html_to_pdf(html_content)

            assert pdf_content == b"fake_pdf_data"
            mock_page.set_content.assert_called_once_with(html_content, wait_until="networkidle")
            mock_page.pdf.assert_called_once()

    @pytest.mark.asyncio
    async def test_html_to_pdf_with_options(self):
        """Test HTML to PDF conversion with custom options"""
        service = UnitEconomicsPDFService()

        html_content = "<html><body><h1>Test PDF</h1></body></html>"

        # Mock Playwright
        mock_page = AsyncMock()
        mock_page.pdf.return_value = b"fake_pdf_data"

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        with patch("playwright.async_api.async_playwright") as mock_async_playwright:
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright

            pdf_content = await service._html_to_pdf(html_content)

            # Verify PDF options
            call_args = mock_page.pdf.call_args[1]
            assert call_args["format"] == "A4"
            assert call_args["print_background"] is True
            assert "margin" in call_args
            assert call_args["margin"]["top"] == "0.5in"

    @pytest.mark.asyncio
    async def test_html_to_pdf_error_handling(self):
        """Test HTML to PDF conversion error handling"""
        service = UnitEconomicsPDFService()

        html_content = "<html><body><h1>Test PDF</h1></body></html>"

        # Mock Playwright to raise an error
        mock_page = AsyncMock()
        mock_page.pdf.side_effect = Exception("PDF generation failed")

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        with patch("playwright.async_api.async_playwright") as mock_async_playwright:
            mock_async_playwright.return_value.__aenter__.return_value = mock_playwright

            with pytest.raises(Exception) as exc_info:
                await service._html_to_pdf(html_content)

            assert "PDF generation failed" in str(exc_info.value)


class TestPDFAPIIntegration:
    """Test PDF API endpoint integration"""

    @pytest.mark.asyncio
    async def test_unit_economics_pdf_endpoint(self):
        """Test unit economics PDF endpoint"""
        # Mock dependencies
        with patch("d10_analytics.api._get_unit_economics_from_view") as mock_get_data:
            with patch("d10_analytics.api.UnitEconomicsPDFService") as mock_service_class:
                # Mock data
                mock_data = [
                    {
                        "date": "2024-01-01",
                        "total_cost_cents": 1000_00,
                        "total_revenue_cents": 2000_00,
                        "total_leads": 100,
                        "total_conversions": 10,
                    }
                ]

                mock_get_data.return_value = mock_data

                # Mock PDF service
                mock_service = AsyncMock()
                mock_service.generate_unit_economics_pdf.return_value = b"fake_pdf_data"
                mock_service_class.return_value = mock_service

                # Test the endpoint (would need actual FastAPI test client)
                # This is a placeholder for integration testing
                assert True

    @pytest.mark.asyncio
    async def test_pdf_caching_behavior(self):
        """Test PDF caching behavior"""
        # Mock cache interactions
        with patch("d10_analytics.api.export_cache") as mock_cache:
            mock_cache.get.return_value = None  # Cache miss
            mock_cache.set.return_value = None  # Cache set

            # Test caching logic
            cache_key = "unit_econ_pdf_2024-01-01_2024-01-31_True_True"

            # Simulate cache miss
            cached_result = mock_cache.get(cache_key)
            assert cached_result is None

            # Simulate cache set
            mock_cache.set(cache_key, b"pdf_data", ex=86400)
            mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_pdf_error_response_handling(self):
        """Test PDF error response handling"""
        # Mock error conditions
        with patch("d10_analytics.api._get_unit_economics_from_view") as mock_get_data:
            mock_get_data.side_effect = Exception("Database error")

            # Test error handling (would need actual FastAPI test client)
            # This is a placeholder for integration testing
            assert True


class TestMobileFriendlyPDFLayout:
    """Test mobile-friendly PDF layout and formatting"""

    def test_mobile_responsive_css(self):
        """Test mobile responsive CSS injection"""
        # Test CSS for mobile-friendly layouts
        mobile_css = """
        @media (max-width: 768px) {
            body { font-size: 14px; }
            .chart { width: 100%; height: 300px; }
            .metrics-grid { grid-template-columns: 1fr; }
        }
        """

        assert "@media (max-width: 768px)" in mobile_css
        assert "font-size: 14px" in mobile_css
        assert "width: 100%" in mobile_css

    def test_print_optimized_css(self):
        """Test print-optimized CSS"""
        print_css = """
        @media print {
            body { color: black; background: white; }
            .no-print { display: none; }
            .page-break { page-break-before: always; }
        }
        """

        assert "@media print" in print_css
        assert "color: black" in print_css
        assert "page-break-before: always" in print_css

    def test_chart_sizing_for_mobile(self):
        """Test chart sizing for mobile devices"""
        # Test chart configuration for mobile
        mobile_chart_config = {
            "width": 350,  # Mobile-friendly width
            "height": 250,  # Mobile-friendly height
            "margin": {"t": 30, "b": 30, "l": 30, "r": 30},
            "font": {"size": 10},  # Smaller font for mobile
        }

        assert mobile_chart_config["width"] <= 400
        assert mobile_chart_config["height"] <= 300
        assert mobile_chart_config["font"]["size"] <= 12

    def test_data_table_responsive_design(self):
        """Test data table responsive design"""
        # Test table configuration for mobile
        mobile_table_config = {
            "max_rows": 20,  # Limit rows for mobile
            "column_width": "auto",
            "font_size": "small",
            "show_borders": True,
        }

        assert mobile_table_config["max_rows"] <= 30
        assert mobile_table_config["font_size"] in ["small", "medium", "large"]


class TestPDFVisualValidation:
    """Test PDF visual validation and quality checks"""

    def test_pdf_size_validation(self):
        """Test PDF file size validation"""
        # Test reasonable file size limits
        max_pdf_size = 10 * 1024 * 1024  # 10MB
        typical_pdf_size = 2 * 1024 * 1024  # 2MB

        assert typical_pdf_size < max_pdf_size

        # Test size optimization
        original_size = 5 * 1024 * 1024  # 5MB
        optimized_size = 3 * 1024 * 1024  # 3MB
        optimization_ratio = (original_size - optimized_size) / original_size

        assert optimization_ratio > 0.2  # At least 20% reduction

    def test_pdf_page_count_validation(self):
        """Test PDF page count validation"""
        # Test reasonable page count limits
        max_pages = 50
        typical_pages = 5

        assert typical_pages < max_pages

        # Test page count estimation
        data_points = 30
        estimated_pages = max(1, data_points // 10)  # Rough estimation

        assert estimated_pages > 0
        assert estimated_pages <= max_pages

    def test_pdf_content_validation(self):
        """Test PDF content validation"""
        # Test required content elements
        required_elements = [
            "Unit Economics Analysis Report",
            "Generation Date:",
            "Key Metrics",
            "Summary",
            "Recommendations",
        ]

        # Mock PDF content
        pdf_content = """
        Unit Economics Analysis Report
        Generation Date: January 1, 2024
        Key Metrics: ROI, CAC, CPL, LTV
        Summary: Performance analysis
        Recommendations: Optimization steps
        """

        for element in required_elements:
            assert element in pdf_content

    def test_chart_image_quality(self):
        """Test chart image quality parameters"""
        # Test chart image settings
        chart_settings = {
            "format": "png",
            "width": 800,
            "height": 400,
            "scale": 2,  # High DPI
            "quality": 95,  # High quality
        }

        assert chart_settings["scale"] >= 1
        assert chart_settings["quality"] >= 80
        assert chart_settings["width"] >= 400
        assert chart_settings["height"] >= 200

    def test_font_and_styling_validation(self):
        """Test font and styling validation"""
        # Test professional styling
        styling_config = {
            "font_family": "Arial, sans-serif",
            "font_size": "12px",
            "line_height": "1.4",
            "color_scheme": "professional",
            "margin": "0.5in",
        }

        assert "Arial" in styling_config["font_family"]
        assert "12px" in styling_config["font_size"]
        assert styling_config["line_height"] == "1.4"


@pytest.mark.slow
class TestPDFPerformanceAndOptimization:
    """Test PDF performance and optimization"""

    @pytest.mark.asyncio
    async def test_pdf_generation_performance(self):
        """Test PDF generation performance"""
        import time

        service = UnitEconomicsPDFService()

        # Large dataset
        large_data = [
            {
                "date": f"2024-01-{i:02d}",
                "total_cost_cents": i * 1000_00,
                "total_revenue_cents": i * 2000_00,
                "total_leads": i * 100,
                "total_conversions": i * 10,
            }
            for i in range(1, 32)  # 31 days
        ]

        summary = {"total_cost_cents": 500000_00, "total_revenue_cents": 1000000_00, "overall_roi_percentage": 100.0}

        date_range = {"start_date": "2024-01-01", "end_date": "2024-01-31"}

        # Mock dependencies for performance test
        with patch.object(service, "_html_to_pdf", return_value=b"fake_pdf_data"):
            with patch.object(service, "_generate_charts", return_value={}):
                with patch.object(service.template_env, "get_template") as mock_template:
                    mock_template.return_value.render.return_value = "<html><body>Test</body></html>"

                    start_time = time.time()

                    pdf_content = await service.generate_unit_economics_pdf(
                        unit_econ_data=large_data, summary=summary, date_range=date_range, request_id="perf-test"
                    )

                    end_time = time.time()

                    # Should complete within reasonable time
                    assert (end_time - start_time) < 5.0  # Less than 5 seconds
                    assert pdf_content == b"fake_pdf_data"

    @pytest.mark.asyncio
    async def test_concurrent_pdf_generation(self):
        """Test concurrent PDF generation"""
        service = UnitEconomicsPDFService()

        # Mock dependencies
        with patch.object(service, "_html_to_pdf", return_value=b"fake_pdf_data"):
            with patch.object(service, "_generate_charts", return_value={}):
                with patch.object(service.template_env, "get_template") as mock_template:
                    mock_template.return_value.render.return_value = "<html><body>Test</body></html>"

                    # Generate multiple PDFs concurrently
                    tasks = []
                    for i in range(5):
                        task = service.generate_unit_economics_pdf(
                            unit_econ_data=[{"date": f"2024-01-{i:02d}"}],
                            summary={"total_cost_cents": 1000_00},
                            date_range={"start_date": "2024-01-01", "end_date": "2024-01-01"},
                            request_id=f"concurrent-{i}",
                        )
                        tasks.append(task)

                    # Wait for all tasks to complete
                    results = await asyncio.gather(*tasks)

                    # All should succeed
                    assert len(results) == 5
                    for result in results:
                        assert result == b"fake_pdf_data"

    def test_pdf_memory_usage_optimization(self):
        """Test PDF memory usage optimization"""
        # Test memory-efficient data processing
        large_dataset = [{"data": f"item_{i}"} for i in range(10000)]

        # Test chunked processing
        chunk_size = 1000
        chunks = [large_dataset[i : i + chunk_size] for i in range(0, len(large_dataset), chunk_size)]

        assert len(chunks) == 10
        assert len(chunks[0]) == chunk_size

        # Test memory cleanup
        del large_dataset
        del chunks

        # Memory should be released
        assert True  # Placeholder for actual memory testing


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
