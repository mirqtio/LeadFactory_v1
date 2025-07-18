"""
Unit tests for unit economics helper functions and utilities.

Tests helper functions, CSV generation, mock data generation, and other utility functions
that support the unit economics API functionality.
"""

import io
import random
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from d10_analytics.api import (
    _generate_csv_content,
    _generate_export_content,
    _generate_unit_econ_csv,
    _get_unit_economics_from_view,
    _get_unit_economics_mock_data,
    create_error_response,
)


class TestUnitEconomicsHelperFunctions:
    """Test helper functions for unit economics API"""

    def test_generate_unit_econ_csv(self):
        """Test unit economics CSV generation"""
        # Test data
        daily_data = [
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

        summary = {
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

        # Generate CSV
        csv_content = _generate_unit_econ_csv(daily_data, summary)

        # Verify CSV structure
        assert "# Unit Economics Summary" in csv_content
        assert "Total Cost (cents)" in csv_content
        assert "Total Revenue (cents)" in csv_content
        assert "Total Profit (cents)" in csv_content
        assert "# Daily Data" in csv_content
        assert "date" in csv_content
        assert "total_cost_cents" in csv_content
        assert "total_revenue_cents" in csv_content

        # Verify data is present
        assert "2500" in csv_content  # Total cost
        assert "119700" in csv_content  # Total revenue
        assert "2025-01-15" in csv_content  # Date
        assert "2025-01-16" in csv_content  # Date

        print("✓ Unit economics CSV generation works correctly")

    def test_generate_unit_econ_csv_empty_data(self):
        """Test unit economics CSV generation with empty data"""
        daily_data = []
        summary = {
            "total_cost_cents": 0,
            "total_revenue_cents": 0,
            "total_profit_cents": 0,
            "total_leads": 0,
            "total_conversions": 0,
            "avg_cpl_cents": None,
            "avg_cac_cents": None,
            "overall_roi_percentage": None,
            "avg_ltv_cents": None,
            "conversion_rate_pct": 0,
        }

        # Generate CSV
        csv_content = _generate_unit_econ_csv(daily_data, summary)

        # Verify CSV structure
        assert "# Unit Economics Summary" in csv_content
        assert "Total Cost (cents)" in csv_content
        assert "0" in csv_content  # Zero values
        assert "N/A" in csv_content  # None values

        print("✓ Unit economics CSV generation with empty data works correctly")

    def test_generate_csv_content_with_records(self):
        """Test generic CSV content generation with records"""
        data = {
            "records": [
                {"date": "2025-01-15", "value": 100, "type": "test"},
                {"date": "2025-01-16", "value": 200, "type": "test"},
            ]
        }

        csv_content = _generate_csv_content(data)

        # Verify CSV structure
        assert "date" in csv_content
        assert "value" in csv_content
        assert "type" in csv_content
        assert "2025-01-15" in csv_content
        assert "2025-01-16" in csv_content
        assert "100" in csv_content
        assert "200" in csv_content

        print("✓ Generic CSV content generation with records works correctly")

    def test_generate_csv_content_with_list(self):
        """Test generic CSV content generation with list"""
        data = [
            {"date": "2025-01-15", "value": 100},
            {"date": "2025-01-16", "value": 200},
        ]

        csv_content = _generate_csv_content(data)

        # Verify CSV structure
        assert "date" in csv_content
        assert "value" in csv_content
        assert "2025-01-15" in csv_content
        assert "2025-01-16" in csv_content

        print("✓ Generic CSV content generation with list works correctly")

    def test_generate_csv_content_with_simple_data(self):
        """Test generic CSV content generation with simple data"""
        data = "simple_value"

        csv_content = _generate_csv_content(data)

        # Verify CSV structure
        assert "value" in csv_content
        assert "simple_value" in csv_content

        print("✓ Generic CSV content generation with simple data works correctly")

    def test_generate_export_content_csv(self):
        """Test export content generation for CSV format"""
        data = {"records": [{"date": "2025-01-15", "value": 100}]}

        content = _generate_export_content(data, "csv")

        # Verify CSV content
        assert "date" in content
        assert "value" in content
        assert "2025-01-15" in content

        print("✓ Export content generation for CSV works correctly")

    def test_generate_export_content_json(self):
        """Test export content generation for JSON format"""
        data = {"records": [{"date": "2025-01-15", "value": 100}]}

        content = _generate_export_content(data, "json")

        # Verify JSON content
        assert '"records"' in content
        assert '"date"' in content
        assert '"2025-01-15"' in content
        assert '"value"' in content

        print("✓ Export content generation for JSON works correctly")

    def test_generate_export_content_excel(self):
        """Test export content generation for Excel format (falls back to CSV)"""
        data = {"records": [{"date": "2025-01-15", "value": 100}]}

        content = _generate_export_content(data, "excel")

        # Verify CSV content (fallback)
        assert "date" in content
        assert "value" in content
        assert "2025-01-15" in content

        print("✓ Export content generation for Excel works correctly")

    def test_generate_export_content_invalid_format(self):
        """Test export content generation with invalid format"""
        data = {"records": [{"date": "2025-01-15", "value": 100}]}

        with pytest.raises(ValueError, match="Unsupported file format"):
            _generate_export_content(data, "invalid_format")

        print("✓ Export content generation with invalid format raises error correctly")

    def test_get_unit_economics_mock_data(self):
        """Test unit economics mock data generation"""
        start_date = date(2025, 1, 15)
        end_date = date(2025, 1, 17)

        # Use fixed seed for reproducible tests
        with patch("random.randint") as mock_randint:
            mock_randint.side_effect = [
                50,
                5,
                2000,
                75,
                7,
                3000,
                100,
                10,
                4000,
            ]  # leads, conversions, cost for each day

            mock_data = _get_unit_economics_mock_data(start_date, end_date)

            # Verify data structure
            assert len(mock_data) == 3  # 3 days

            for i, record in enumerate(mock_data):
                expected_date = start_date + timedelta(days=i)
                assert record["date"] == expected_date.isoformat()
                assert "total_cost_cents" in record
                assert "total_revenue_cents" in record
                assert "total_leads" in record
                assert "total_conversions" in record
                assert "cpl_cents" in record
                assert "cac_cents" in record
                assert "roi_percentage" in record
                assert "ltv_cents" in record
                assert "profit_cents" in record
                assert "lead_to_conversion_rate_pct" in record

        print("✓ Unit economics mock data generation works correctly")

    def test_get_unit_economics_mock_data_calculations(self):
        """Test that mock data calculations are correct"""
        start_date = date(2025, 1, 15)
        end_date = date(2025, 1, 15)  # Single day

        # Use fixed values for predictable calculations
        with patch("random.randint") as mock_randint:
            mock_randint.side_effect = [50, 5, 2000]  # leads, conversions, cost

            mock_data = _get_unit_economics_mock_data(start_date, end_date)

            record = mock_data[0]
            leads = record["total_leads"]
            conversions = record["total_conversions"]
            cost = record["total_cost_cents"]
            revenue = record["total_revenue_cents"]

            # Verify calculations
            assert record["cpl_cents"] == cost / leads
            assert record["cac_cents"] == cost / conversions
            assert record["roi_percentage"] == round(((revenue - cost) / cost) * 100, 2)
            assert record["ltv_cents"] == round(revenue / conversions, 2)
            assert record["profit_cents"] == revenue - cost
            assert record["lead_to_conversion_rate_pct"] == round((conversions / leads) * 100, 2)

        print("✓ Unit economics mock data calculations are correct")

    @pytest.mark.asyncio
    async def test_get_unit_economics_from_view_success(self):
        """Test successful unit economics data retrieval from view"""
        start_date = date(2025, 1, 15)
        end_date = date(2025, 1, 16)

        # Mock database session and query result
        with patch("d10_analytics.api.SessionLocal") as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session

            # Mock query result
            mock_result = Mock()
            mock_row = Mock()
            mock_row.date = date(2025, 1, 15)
            mock_row.total_cost_cents = 1000
            mock_row.total_revenue_cents = 39900
            mock_row.total_leads = 50
            mock_row.total_conversions = 1
            mock_row.cpl_cents = 20.0
            mock_row.cac_cents = 1000.0
            mock_row.roi_percentage = 3890.0
            mock_row.ltv_cents = 39900.0
            mock_row.profit_cents = 38900
            mock_row.lead_to_conversion_rate_pct = 2.0

            mock_result.__iter__ = Mock(return_value=iter([mock_row]))
            mock_session.execute.return_value = mock_result

            # Call function
            result = await _get_unit_economics_from_view(start_date, end_date)

            # Verify result
            assert len(result) == 1
            record = result[0]
            assert record["date"] == "2025-01-15"
            assert record["total_cost_cents"] == 1000
            assert record["total_revenue_cents"] == 39900
            assert record["total_leads"] == 50
            assert record["total_conversions"] == 1

        print("✓ Unit economics data retrieval from view works correctly")

    @pytest.mark.asyncio
    async def test_get_unit_economics_from_view_database_error(self):
        """Test unit economics data retrieval with database error"""
        start_date = date(2025, 1, 15)
        end_date = date(2025, 1, 16)

        # Mock database session to raise error
        with patch("d10_analytics.api.SessionLocal") as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            mock_session.execute.side_effect = Exception("Database connection error")

            # Mock the fallback function
            with patch("d10_analytics.api._get_unit_economics_mock_data") as mock_fallback:
                mock_fallback.return_value = [{"date": "2025-01-15", "total_cost_cents": 0}]

                # Call function
                result = await _get_unit_economics_from_view(start_date, end_date)

                # Verify fallback was called
                mock_fallback.assert_called_once_with(start_date, end_date)
                assert len(result) == 1

        print("✓ Unit economics data retrieval with database error falls back correctly")

    @pytest.mark.asyncio
    async def test_get_unit_economics_from_view_data_conversion_error(self):
        """Test unit economics data retrieval with data conversion error"""
        start_date = date(2025, 1, 15)
        end_date = date(2025, 1, 16)

        # Mock database session with invalid data
        with patch("d10_analytics.api.SessionLocal") as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value = mock_session

            # Mock query result with invalid data
            mock_result = Mock()
            mock_row = Mock()
            mock_row.date = date(2025, 1, 15)
            mock_row.total_cost_cents = "invalid_integer"  # Invalid data type
            mock_row.total_revenue_cents = 39900
            mock_row.total_leads = 50
            mock_row.total_conversions = 1
            mock_row.cpl_cents = 20.0
            mock_row.cac_cents = 1000.0
            mock_row.roi_percentage = 3890.0
            mock_row.ltv_cents = 39900.0
            mock_row.profit_cents = 38900
            mock_row.lead_to_conversion_rate_pct = 2.0

            mock_result.__iter__ = Mock(return_value=iter([mock_row]))
            mock_session.execute.return_value = mock_result

            # Call function
            result = await _get_unit_economics_from_view(start_date, end_date)

            # Verify that invalid rows are skipped
            assert len(result) == 0  # Invalid row should be skipped

        print("✓ Unit economics data retrieval with data conversion error handled correctly")

    def test_create_error_response(self):
        """Test error response creation"""
        error_type = "validation_error"
        message = "Invalid input data"
        details = {"field": "date", "issue": "format"}
        status_code = 400

        error_response = create_error_response(error_type, message, details, status_code)

        # Verify error response structure
        assert error_response.status_code == status_code
        assert error_response.detail["error"] == error_type
        assert error_response.detail["message"] == message
        assert error_response.detail["details"] == details
        assert "request_id" in error_response.detail

        print("✓ Error response creation works correctly")

    def test_create_error_response_minimal(self):
        """Test error response creation with minimal parameters"""
        error_type = "internal_error"
        message = "Something went wrong"

        error_response = create_error_response(error_type, message)

        # Verify error response structure
        assert error_response.status_code == 400  # Default status code
        assert error_response.detail["error"] == error_type
        assert error_response.detail["message"] == message
        assert error_response.detail["details"] is None
        assert "request_id" in error_response.detail

        print("✓ Error response creation with minimal parameters works correctly")


def test_unit_economics_helpers_integration():
    """Integration test for unit economics helper functions"""
    print("Running unit economics helper functions integration tests...")

    # Test CSV generation
    daily_data = [{"date": "2025-01-15", "total_cost_cents": 1000, "total_revenue_cents": 39900}]
    summary = {"total_cost_cents": 1000, "total_revenue_cents": 39900}
    csv_content = _generate_unit_econ_csv(daily_data, summary)
    assert "1000" in csv_content
    assert "39900" in csv_content
    print("✓ CSV generation integration test passed")

    # Test mock data generation
    mock_data = _get_unit_economics_mock_data(date(2025, 1, 15), date(2025, 1, 15))
    assert len(mock_data) == 1
    assert "date" in mock_data[0]
    print("✓ Mock data generation integration test passed")

    # Test export content generation
    data = {"records": [{"date": "2025-01-15", "value": 100}]}
    csv_content = _generate_export_content(data, "csv")
    json_content = _generate_export_content(data, "json")
    assert "date" in csv_content
    assert '"date"' in json_content
    print("✓ Export content generation integration test passed")

    print("✓ All unit economics helper functions integration tests passed")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
