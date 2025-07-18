"""
Comprehensive unit tests for Unit Economics PDF Service.

Tests PDF generation, chart creation, recommendations, and error handling
for the executive-grade PDF reports.
"""

import base64
from datetime import date
from unittest.mock import Mock, patch

import pytest

from d10_analytics.pdf_service import UnitEconomicsPDFService


class TestUnitEconomicsPDFServiceComprehensive:
    """Comprehensive test suite for PDF service"""

    @pytest.fixture
    def pdf_service(self):
        """Create PDF service instance"""
        return UnitEconomicsPDFService()

    @pytest.fixture
    def sample_unit_econ_data(self):
        """Sample unit economics data for testing"""
        return [
            {
                "date": "2025-01-15",
                "total_cost_cents": 1000,
                "total_revenue_cents": 39900,
                "total_leads": 50,
                "total_conversions": 1,
                "cpl_cents": 20.0,
                "cac_cents": 1000.0,
                "roi_percentage": 3890.0,
                "ltv_cents": 39900.0,
                "profit_cents": 38900,
                "lead_to_conversion_rate_pct": 2.0,
            },
            {
                "date": "2025-01-16",
                "total_cost_cents": 1500,
                "total_revenue_cents": 79800,
                "total_leads": 75,
                "total_conversions": 2,
                "cpl_cents": 20.0,
                "cac_cents": 750.0,
                "roi_percentage": 5220.0,
                "ltv_cents": 39900.0,
                "profit_cents": 78300,
                "lead_to_conversion_rate_pct": 2.67,
            },
        ]

    @pytest.fixture
    def sample_summary(self):
        """Sample summary data for testing"""
        return {
            "total_cost_cents": 2500,
            "total_revenue_cents": 119700,
            "total_profit_cents": 117200,
            "total_leads": 125,
            "total_conversions": 3,
            "avg_cpl_cents": 20.0,
            "avg_cac_cents": 833.33,
            "overall_roi_percentage": 4588.0,
            "avg_ltv_cents": 39900.0,
            "conversion_rate_pct": 2.4,
        }

    @pytest.fixture
    def sample_date_range(self):
        """Sample date range for testing"""
        return {"start_date": "2025-01-15", "end_date": "2025-01-16"}

    def test__generate_charts_creates_all_charts(self, pdf_service, sample_unit_econ_data):
        """Test that all required charts are created"""
        with patch("matplotlib.pyplot.subplots") as mock_subplots:
            mock_fig = Mock()
            mock_ax = Mock()
            mock_subplots.return_value = (mock_fig, mock_ax)

            with patch("io.BytesIO") as mock_bytesio:
                mock_buffer = Mock()
                mock_bytesio.return_value = mock_buffer
                mock_buffer.getvalue.return_value = b"fake_chart_data"

                charts = pdf_service._generate_charts(sample_unit_econ_data)

                # Verify all required charts are created
                assert "cost_trend" in charts
                assert "revenue_trend" in charts
                assert "roi_trend" in charts
                assert "conversion_metrics" in charts
                assert "unit_economics_summary" in charts

                # Verify chart data is base64 encoded
                for chart_name, chart_data in charts.items():
                    assert isinstance(chart_data, str)
                    # Should be base64 encoded
                    try:
                        base64.b64decode(chart_data)
                    except Exception:
                        pytest.fail(f"Chart {chart_name} is not valid base64")

        print("✓ All required charts are created correctly")

    def test__generate_charts_handles_empty_data(self, pdf_service):
        """Test chart generation with empty data"""
        empty_data = []

        with patch("matplotlib.pyplot.subplots") as mock_subplots:
            mock_fig = Mock()
            mock_ax = Mock()
            mock_subplots.return_value = (mock_fig, mock_ax)

            with patch("io.BytesIO") as mock_bytesio:
                mock_buffer = Mock()
                mock_bytesio.return_value = mock_buffer
                mock_buffer.getvalue.return_value = b"empty_chart_data"

                charts = pdf_service._generate_charts(empty_data)

                # Should still create charts, even with empty data
                assert len(charts) > 0
                assert "cost_trend" in charts

        print("✓ Chart generation handles empty data correctly")

    def test__generate_charts_error_handling(self, pdf_service, sample_unit_econ_data):
        """Test chart generation error handling"""
        with patch("matplotlib.pyplot.subplots") as mock_subplots:
            mock_subplots.side_effect = Exception("Chart generation error")

            # Should not raise exception, but return empty charts
            charts = pdf_service._generate_charts(sample_unit_econ_data)

            # Should return empty dict on error
            assert charts == {}

        print("✓ Chart generation error handling works correctly")

    def test__generate_recommendations_high_performance(self, pdf_service, sample_summary):
        """Test recommendations for high-performance metrics"""
        # High ROI scenario
        high_roi_summary = sample_summary.copy()
        high_roi_summary["overall_roi_percentage"] = 5000.0  # 50x ROI
        high_roi_summary["conversion_rate_pct"] = 5.0  # 5% conversion rate

        recommendations = pdf_service._generate_recommendations(high_roi_summary)

        # Verify recommendations structure
        assert "executive_summary" in recommendations
        assert "key_insights" in recommendations
        assert "action_items" in recommendations
        assert "risk_factors" in recommendations

        # Verify content for high performance
        assert "strong performance" in recommendations["executive_summary"].lower()
        assert len(recommendations["key_insights"]) > 0
        assert len(recommendations["action_items"]) > 0

        print("✓ High performance recommendations generated correctly")

    def test__generate_recommendations_low_roi(self, pdf_service, sample_summary):
        """Test recommendations for low ROI scenario"""
        # Low ROI scenario
        low_roi_summary = sample_summary.copy()
        low_roi_summary["overall_roi_percentage"] = 50.0  # 50% ROI
        low_roi_summary["conversion_rate_pct"] = 0.5  # 0.5% conversion rate

        recommendations = pdf_service._generate_recommendations(low_roi_summary)

        # Verify recommendations structure
        assert "executive_summary" in recommendations
        assert "key_insights" in recommendations
        assert "action_items" in recommendations
        assert "risk_factors" in recommendations

        # Verify content for low performance
        assert "improvement" in recommendations["executive_summary"].lower()
        assert len(recommendations["action_items"]) > 0

        print("✓ Low ROI recommendations generated correctly")

    def test__generate_recommendations_negative_roi(self, pdf_service, sample_summary):
        """Test recommendations for negative ROI scenario"""
        # Negative ROI scenario
        negative_roi_summary = sample_summary.copy()
        negative_roi_summary["overall_roi_percentage"] = -25.0  # -25% ROI
        negative_roi_summary["total_profit_cents"] = -50000  # Loss

        recommendations = pdf_service._generate_recommendations(negative_roi_summary)

        # Verify recommendations structure
        assert "executive_summary" in recommendations
        assert "key_insights" in recommendations
        assert "action_items" in recommendations
        assert "risk_factors" in recommendations

        # Verify content for negative ROI
        assert (
            "loss" in recommendations["executive_summary"].lower()
            or "negative" in recommendations["executive_summary"].lower()
        )
        assert len(recommendations["action_items"]) > 0

        print("✓ Negative ROI recommendations generated correctly")

    def test__generate_recommendations_zero_conversions(self, pdf_service, sample_summary):
        """Test recommendations for zero conversions scenario"""
        # Zero conversions scenario
        zero_conv_summary = sample_summary.copy()
        zero_conv_summary["total_conversions"] = 0
        zero_conv_summary["conversion_rate_pct"] = 0.0
        zero_conv_summary["total_revenue_cents"] = 0

        recommendations = pdf_service._generate_recommendations(zero_conv_summary)

        # Verify recommendations structure
        assert "executive_summary" in recommendations
        assert "key_insights" in recommendations
        assert "action_items" in recommendations
        assert "risk_factors" in recommendations

        # Verify content for zero conversions
        assert "conversion" in recommendations["executive_summary"].lower()
        assert len(recommendations["action_items"]) > 0

        print("✓ Zero conversions recommendations generated correctly")

    def test__generate_recommendations_error_handling(self, pdf_service):
        """Test recommendations error handling"""
        # Invalid summary data
        invalid_summary = None

        recommendations = pdf_service._generate_recommendations(invalid_summary)

        # Should return default recommendations structure
        assert "executive_summary" in recommendations
        assert "key_insights" in recommendations
        assert "action_items" in recommendations
        assert "risk_factors" in recommendations

        # Should contain error message
        assert "error" in recommendations["executive_summary"].lower()

        print("✓ Recommendations error handling works correctly")

    def test__html_to_pdf_success(self, pdf_service):
        """Test HTML to PDF conversion success"""
        html_content = """
        <html>
        <body>
            <h1>Unit Economics Report</h1>
            <p>This is a test report.</p>
        </body>
        </html>
        """

        with patch("weasyprint.HTML") as mock_html:
            mock_html_instance = Mock()
            mock_html.return_value = mock_html_instance
            mock_html_instance.write_pdf.return_value = b"fake_pdf_content"

            pdf_content = pdf_service._html_to_pdf(html_content)

            # Verify PDF content is returned
            assert pdf_content == b"fake_pdf_content"

            # Verify weasyprint was called correctly
            mock_html.assert_called_once()
            mock_html_instance.write_pdf.assert_called_once()

        print("✓ HTML to PDF conversion success works correctly")

    def test__html_to_pdf_error_handling(self, pdf_service):
        """Test HTML to PDF conversion error handling"""
        html_content = "<html><body><h1>Test</h1></body></html>"

        with patch("weasyprint.HTML") as mock_html:
            mock_html.side_effect = Exception("PDF generation error")

            pdf_content = pdf_service._html_to_pdf(html_content)

            # Should return None on error
            assert pdf_content is None

        print("✓ HTML to PDF conversion error handling works correctly")

    @pytest.mark.asyncio
    async def test_generate_pdf_success(self, pdf_service, sample_unit_econ_data, sample_summary, sample_date_range):
        """Test full PDF generation success"""
        with patch.object(pdf_service, "_generate_charts") as mock_charts:
            mock_charts.return_value = {
                "cost_trend": "fake_chart_data",
                "revenue_trend": "fake_chart_data",
                "roi_trend": "fake_chart_data",
                "conversion_metrics": "fake_chart_data",
                "unit_economics_summary": "fake_chart_data",
            }

            with patch.object(pdf_service, "_generate_recommendations") as mock_recommendations:
                mock_recommendations.return_value = {
                    "executive_summary": "Strong performance",
                    "key_insights": ["High ROI", "Good conversion rate"],
                    "action_items": ["Continue current strategy"],
                    "risk_factors": ["Market volatility"],
                }

                with patch.object(pdf_service, "_html_to_pdf") as mock__html_to_pdf:
                    mock__html_to_pdf.return_value = b"fake_pdf_content"

                    pdf_content = await pdf_service.generate_unit_economics_pdf(
                        unit_econ_data=sample_unit_econ_data,
                        summary=sample_summary,
                        date_range=sample_date_range,
                        request_id="test_request_123",
                        include_charts=True,
                        include_detailed_analysis=True,
                    )

                    # Verify PDF content is returned
                    assert pdf_content == b"fake_pdf_content"

                    # Verify all components were called
                    mock_charts.assert_called_once()
                    mock_recommendations.assert_called_once()
                    mock__html_to_pdf.assert_called_once()

        print("✓ Full PDF generation success works correctly")

    @pytest.mark.asyncio
    async def test_generate_pdf_no_charts(self, pdf_service, sample_unit_econ_data, sample_summary, sample_date_range):
        """Test PDF generation without charts"""
        with patch.object(pdf_service, "_generate_charts") as mock_charts:
            with patch.object(pdf_service, "_generate_recommendations") as mock_recommendations:
                mock_recommendations.return_value = {
                    "executive_summary": "Strong performance",
                    "key_insights": ["High ROI"],
                    "action_items": ["Continue strategy"],
                    "risk_factors": ["Market volatility"],
                }

                with patch.object(pdf_service, "_html_to_pdf") as mock__html_to_pdf:
                    mock__html_to_pdf.return_value = b"fake_pdf_content"

                    pdf_content = await pdf_service.generate_unit_economics_pdf(
                        unit_econ_data=sample_unit_econ_data,
                        summary=sample_summary,
                        date_range=sample_date_range,
                        request_id="test_request_123",
                        include_charts=False,
                        include_detailed_analysis=True,
                    )

                    # Verify PDF content is returned
                    assert pdf_content == b"fake_pdf_content"

                    # Verify charts were not called
                    mock_charts.assert_not_called()
                    mock_recommendations.assert_called_once()

        print("✓ PDF generation without charts works correctly")

    @pytest.mark.asyncio
    async def test_generate_pdf_no_detailed_analysis(
        self, pdf_service, sample_unit_econ_data, sample_summary, sample_date_range
    ):
        """Test PDF generation without detailed analysis"""
        with patch.object(pdf_service, "_generate_charts") as mock_charts:
            mock_charts.return_value = {"cost_trend": "fake_chart_data"}

            with patch.object(pdf_service, "_generate_recommendations") as mock_recommendations:
                with patch.object(pdf_service, "_html_to_pdf") as mock__html_to_pdf:
                    mock__html_to_pdf.return_value = b"fake_pdf_content"

                    pdf_content = await pdf_service.generate_unit_economics_pdf(
                        unit_econ_data=sample_unit_econ_data,
                        summary=sample_summary,
                        date_range=sample_date_range,
                        request_id="test_request_123",
                        include_charts=True,
                        include_detailed_analysis=False,
                    )

                    # Verify PDF content is returned
                    assert pdf_content == b"fake_pdf_content"

                    # Verify recommendations were not called
                    mock_charts.assert_called_once()
                    mock_recommendations.assert_not_called()

        print("✓ PDF generation without detailed analysis works correctly")

    @pytest.mark.asyncio
    async def test_generate_pdf_error_handling(
        self, pdf_service, sample_unit_econ_data, sample_summary, sample_date_range
    ):
        """Test PDF generation error handling"""
        with patch.object(pdf_service, "_generate_charts") as mock_charts:
            mock_charts.side_effect = Exception("Chart generation error")

            with patch.object(pdf_service, "_generate_recommendations") as mock_recommendations:
                mock_recommendations.return_value = {
                    "executive_summary": "Error in analysis",
                    "key_insights": [],
                    "action_items": [],
                    "risk_factors": [],
                }

                with patch.object(pdf_service, "_html_to_pdf") as mock__html_to_pdf:
                    mock__html_to_pdf.return_value = b"error_pdf_content"

                    pdf_content = await pdf_service.generate_unit_economics_pdf(
                        unit_econ_data=sample_unit_econ_data,
                        summary=sample_summary,
                        date_range=sample_date_range,
                        request_id="test_request_123",
                        include_charts=True,
                        include_detailed_analysis=True,
                    )

                    # Should still return PDF content despite chart error
                    assert pdf_content == b"error_pdf_content"

        print("✓ PDF generation error handling works correctly")

    @pytest.mark.asyncio
    async def test_generate_pdf_template_rendering(
        self, pdf_service, sample_unit_econ_data, sample_summary, sample_date_range
    ):
        """Test PDF template rendering with all data"""
        with patch.object(pdf_service, "_generate_charts") as mock_charts:
            mock_charts.return_value = {
                "cost_trend": "chart_data_1",
                "revenue_trend": "chart_data_2",
            }

            with patch.object(pdf_service, "_generate_recommendations") as mock_recommendations:
                mock_recommendations.return_value = {
                    "executive_summary": "Test summary",
                    "key_insights": ["Insight 1", "Insight 2"],
                    "action_items": ["Action 1", "Action 2"],
                    "risk_factors": ["Risk 1"],
                }

                with patch.object(pdf_service, "_html_to_pdf") as mock__html_to_pdf:
                    mock__html_to_pdf.return_value = b"template_pdf_content"

                    pdf_content = await pdf_service.generate_unit_economics_pdf(
                        unit_econ_data=sample_unit_econ_data,
                        summary=sample_summary,
                        date_range=sample_date_range,
                        request_id="test_request_123",
                        include_charts=True,
                        include_detailed_analysis=True,
                    )

                    # Verify PDF content is returned
                    assert pdf_content == b"template_pdf_content"

                    # Verify HTML content includes all data
                    html_call_args = mock__html_to_pdf.call_args[0][0]
                    assert "Test summary" in html_call_args
                    assert "Insight 1" in html_call_args
                    assert "Action 1" in html_call_args
                    assert "Risk 1" in html_call_args
                    assert "chart_data_1" in html_call_args
                    assert "chart_data_2" in html_call_args

        print("✓ PDF template rendering works correctly")


def test_pdf_service_integration():
    """Integration test for PDF service"""
    print("Running PDF service integration tests...")

    # Create service instance
    pdf_service = UnitEconomicsPDFService()

    # Test data
    sample_data = [
        {
            "date": "2025-01-15",
            "total_cost_cents": 1000,
            "total_revenue_cents": 39900,
            "total_leads": 50,
            "total_conversions": 1,
            "cpl_cents": 20.0,
            "cac_cents": 1000.0,
            "roi_percentage": 3890.0,
            "ltv_cents": 39900.0,
            "profit_cents": 38900,
            "lead_to_conversion_rate_pct": 2.0,
        }
    ]

    sample_summary = {
        "total_cost_cents": 1000,
        "total_revenue_cents": 39900,
        "total_profit_cents": 38900,
        "total_leads": 50,
        "total_conversions": 1,
        "avg_cpl_cents": 20.0,
        "avg_cac_cents": 1000.0,
        "overall_roi_percentage": 3890.0,
        "avg_ltv_cents": 39900.0,
        "conversion_rate_pct": 2.0,
    }

    # Test recommendations generation
    recommendations = pdf_service._generate_recommendations(sample_summary)
    assert "executive_summary" in recommendations
    print("✓ Recommendations generation integration test passed")

    # Test error handling
    error_recommendations = pdf_service._generate_recommendations(None)
    assert "error" in error_recommendations["executive_summary"].lower()
    print("✓ Error handling integration test passed")

    print("✓ All PDF service integration tests passed")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
