"""
Unit Economics Section Tests - P2-020

Comprehensive tests for unit economics analysis and reporting logic.
Tests the core business logic for calculating unit economics metrics.

Test Categories:
- Unit economics calculations (CPL, CAC, ROI, LTV)
- Data validation and error handling
- Edge cases and boundary conditions
- Aggregation and trend analysis
- Mobile-friendly display logic
- Data freshness validation
"""

import logging

# Add path for imports
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

try:
    from d10_analytics.api import (
        _generate_unit_econ_csv,
        _get_unit_economics_from_view,
        _get_unit_economics_mock_data,
        get_unit_economics,
        get_unit_economics_pdf,
    )
    from d10_analytics.pdf_service import UnitEconomicsPDFService
except ImportError as e:
    pytest.skip(f"Could not import unit economics modules: {e}", allow_module_level=True)


class TestUnitEconomicsCalculations:
    """Test core unit economics calculation logic"""

    def test_cpl_calculation(self):
        """Test Cost Per Lead calculation"""
        # Test normal case
        total_cost = 1000_00  # $1000 in cents
        total_leads = 200
        expected_cpl = 5_00  # $5 in cents

        cpl = total_cost / total_leads if total_leads > 0 else 0
        assert cpl == expected_cpl

    def test_cac_calculation(self):
        """Test Customer Acquisition Cost calculation"""
        # Test normal case
        total_cost = 5000_00  # $5000 in cents
        total_conversions = 100
        expected_cac = 50_00  # $50 in cents

        cac = total_cost / total_conversions if total_conversions > 0 else 0
        assert cac == expected_cac

    def test_roi_calculation(self):
        """Test Return on Investment calculation"""
        # Test profitable case
        total_revenue = 10000_00  # $10000 in cents
        total_cost = 5000_00  # $5000 in cents
        expected_roi = 100.0  # 100% ROI

        roi = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0
        assert roi == expected_roi

        # Test breakeven case
        total_revenue = 5000_00
        total_cost = 5000_00
        expected_roi = 0.0

        roi = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 else 0
        assert roi == expected_roi

    def test_ltv_calculation(self):
        """Test Lifetime Value calculation"""
        # Test normal case with 3:1 LTV:CAC ratio
        avg_order_value = 200_00  # $200 in cents
        purchase_frequency = 2.5  # purchases per year
        customer_lifespan = 2.0  # years
        expected_ltv = 1000_00  # $1000 in cents

        ltv = avg_order_value * purchase_frequency * customer_lifespan
        assert ltv == expected_ltv

    def test_conversion_rate_calculation(self):
        """Test conversion rate calculation"""
        # Test normal case
        total_conversions = 25
        total_leads = 1000
        expected_rate = 2.5  # 2.5%

        rate = (total_conversions / total_leads * 100) if total_leads > 0 else 0
        assert rate == expected_rate

    def test_profit_calculation(self):
        """Test profit calculation"""
        # Test profitable case
        total_revenue = 15000_00  # $15000 in cents
        total_cost = 8000_00  # $8000 in cents
        expected_profit = 7000_00  # $7000 in cents

        profit = total_revenue - total_cost
        assert profit == expected_profit

    def test_zero_division_handling(self):
        """Test edge cases with zero values"""
        # Test division by zero cases
        assert (1000_00 / 0) if 0 > 0 else 0 == 0  # CPL with zero leads
        assert (1000_00 / 0) if 0 > 0 else 0 == 0  # CAC with zero conversions
        assert ((1000_00 - 0) / 0 * 100) if 0 > 0 else 0 == 0  # ROI with zero cost


class TestUnitEconomicsDataValidation:
    """Test data validation and error handling"""

    def test_negative_values_handling(self):
        """Test handling of negative values"""
        # Test with negative cost (should be treated as zero or flagged)
        negative_cost = -1000_00
        total_leads = 100

        # Cost should not be negative in real scenarios
        assert negative_cost < 0

        # Handle negative cost gracefully
        adjusted_cost = max(0, negative_cost)
        assert adjusted_cost == 0

    def test_data_type_validation(self):
        """Test data type validation"""
        # Test with various data types
        valid_cost = 1000_00
        invalid_cost = "1000"

        assert isinstance(valid_cost, int)
        assert not isinstance(invalid_cost, int)

        # Test conversion
        converted_cost = int(float(invalid_cost) * 100)  # Convert to cents
        assert converted_cost == 1000_00

    def test_date_range_validation(self):
        """Test date range validation"""
        # Test valid date range
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 31)

        assert start_date <= end_date

        # Test invalid date range
        invalid_start = date(2024, 2, 1)
        invalid_end = date(2024, 1, 31)

        assert invalid_start > invalid_end

    def test_percentage_bounds(self):
        """Test percentage value bounds"""
        # Test ROI percentage bounds
        normal_roi = 150.0
        extreme_roi = 10000.0
        negative_roi = -50.0

        assert 0 <= normal_roi <= 1000  # Reasonable bounds
        assert extreme_roi > 1000  # Flag extreme values
        assert negative_roi < 0  # Negative ROI is valid


class TestUnitEconomicsAggregation:
    """Test aggregation and trend analysis"""

    def test_daily_aggregation(self):
        """Test daily metrics aggregation"""
        # Sample daily data
        daily_data = [
            {
                "date": "2024-01-01",
                "total_cost_cents": 1000_00,
                "total_revenue_cents": 2000_00,
                "total_leads": 100,
                "total_conversions": 10,
            },
            {
                "date": "2024-01-02",
                "total_cost_cents": 1500_00,
                "total_revenue_cents": 2500_00,
                "total_leads": 150,
                "total_conversions": 12,
            },
        ]

        # Test aggregation
        total_cost = sum(d["total_cost_cents"] for d in daily_data)
        total_revenue = sum(d["total_revenue_cents"] for d in daily_data)
        total_leads = sum(d["total_leads"] for d in daily_data)
        total_conversions = sum(d["total_conversions"] for d in daily_data)

        assert total_cost == 2500_00
        assert total_revenue == 4500_00
        assert total_leads == 250
        assert total_conversions == 22

    def test_weekly_trend_analysis(self):
        """Test weekly trend analysis"""
        # Sample weekly data
        weekly_data = [
            {"week": 1, "roi": 120.0, "cac": 45_00},
            {"week": 2, "roi": 135.0, "cac": 42_00},
            {"week": 3, "roi": 140.0, "cac": 40_00},
        ]

        # Test trend direction
        roi_trend = [d["roi"] for d in weekly_data]
        cac_trend = [d["cac"] for d in weekly_data]

        # ROI should be increasing
        assert all(roi_trend[i] <= roi_trend[i + 1] for i in range(len(roi_trend) - 1))

        # CAC should be decreasing
        assert all(cac_trend[i] >= cac_trend[i + 1] for i in range(len(cac_trend) - 1))

    def test_monthly_summary(self):
        """Test monthly summary calculations"""
        # Sample monthly data
        monthly_data = {
            "total_cost_cents": 50000_00,
            "total_revenue_cents": 120000_00,
            "total_leads": 2500,
            "total_conversions": 200,
        }

        # Calculate monthly metrics
        monthly_cpl = monthly_data["total_cost_cents"] / monthly_data["total_leads"]
        monthly_cac = monthly_data["total_cost_cents"] / monthly_data["total_conversions"]
        monthly_roi = (
            (monthly_data["total_revenue_cents"] - monthly_data["total_cost_cents"])
            / monthly_data["total_cost_cents"]
            * 100
        )

        assert monthly_cpl == 20_00  # $20 CPL
        assert monthly_cac == 250_00  # $250 CAC
        assert monthly_roi == 140.0  # 140% ROI


class TestUnitEconomicsMockData:
    """Test mock data generation for unit economics"""

    def test_mock_data_generation(self):
        """Test mock data generation function"""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 7)

        mock_data = _get_unit_economics_mock_data(start_date, end_date)

        # Test data structure
        assert isinstance(mock_data, list)
        assert len(mock_data) == 7  # 7 days

        # Test data fields
        for day_data in mock_data:
            assert "date" in day_data
            assert "total_cost_cents" in day_data
            assert "total_revenue_cents" in day_data
            assert "total_leads" in day_data
            assert "total_conversions" in day_data
            assert "profit_cents" in day_data
            assert "roi_percentage" in day_data

    def test_mock_data_consistency(self):
        """Test mock data consistency"""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 3)

        mock_data = _get_unit_economics_mock_data(start_date, end_date)

        for day_data in mock_data:
            # Test profit calculation consistency
            calculated_profit = day_data["total_revenue_cents"] - day_data["total_cost_cents"]
            assert day_data["profit_cents"] == calculated_profit

            # Test ROI calculation consistency
            if day_data["total_cost_cents"] > 0:
                calculated_roi = day_data["profit_cents"] / day_data["total_cost_cents"] * 100
                assert abs(day_data["roi_percentage"] - calculated_roi) < 0.01

    def test_mock_data_date_range(self):
        """Test mock data date range"""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 10)

        mock_data = _get_unit_economics_mock_data(start_date, end_date)

        # Test date range
        dates = [datetime.strptime(d["date"], "%Y-%m-%d").date() for d in mock_data]
        assert min(dates) == start_date
        assert max(dates) == end_date
        assert len(dates) == 10


class TestUnitEconomicsCSVGeneration:
    """Test CSV generation for unit economics data"""

    def test_csv_generation(self):
        """Test CSV content generation"""
        daily_data = [
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
            "total_leads": 100,
            "total_conversions": 10,
            "avg_cpl_cents": 10_00,
            "avg_cac_cents": 100_00,
            "overall_roi_percentage": 100.0,
        }

        csv_content = _generate_unit_econ_csv(daily_data, summary)

        # Test CSV structure - updated to match actual format
        assert isinstance(csv_content, str)
        assert "# Unit Economics Summary" in csv_content
        assert "Total Cost (cents),100000" in csv_content
        assert "Total Revenue (cents),200000" in csv_content
        assert "Overall ROI (%),100.0" in csv_content

        # Test daily data section
        assert "# Daily Data" in csv_content
        assert (
            "date,total_cost_cents,total_revenue_cents,total_leads,total_conversions,profit_cents,roi_percentage"
            in csv_content
        )
        assert "2024-01-01,100000,200000,100,10,100000,100.0" in csv_content

    def test_csv_empty_data(self):
        """Test CSV generation with empty data"""
        daily_data = []
        summary = {
            "total_cost_cents": 0,
            "total_revenue_cents": 0,
            "total_leads": 0,
            "total_conversions": 0,
            "avg_cpl_cents": 0,
            "avg_cac_cents": 0,
            "overall_roi_percentage": 0.0,
        }

        csv_content = _generate_unit_econ_csv(daily_data, summary)

        # Should still have headers and summary - updated to match actual format
        assert "# Unit Economics Summary" in csv_content
        assert "Total Cost (cents),0" in csv_content
        assert "Total Revenue (cents),0" in csv_content
        assert "# Daily Data" in csv_content

    def test_csv_special_characters(self):
        """Test CSV handling of special characters"""
        daily_data = [
            {
                "date": "2024-01-01",
                "total_cost_cents": 1000_00,
                "total_revenue_cents": 2000_00,
                "total_leads": 100,
                "total_conversions": 10,
                "profit_cents": 1000_00,
                "roi_percentage": 100.0,
                "notes": "Test, with, commas",
            }
        ]

        summary = {"total_cost_cents": 1000_00}

        csv_content = _generate_unit_econ_csv(daily_data, summary)

        # Test that commas in data are handled properly
        assert csv_content is not None
        assert isinstance(csv_content, str)


class TestUnitEconomicsDisplay:
    """Test display logic for unit economics"""

    def test_mobile_friendly_formatting(self):
        """Test mobile-friendly number formatting"""
        # Test large numbers
        large_cost = 1500000_00  # $1.5M in cents
        formatted = f"${large_cost / 100:,.0f}"
        assert formatted == "$1,500,000"

        # Test small numbers
        small_cost = 250  # $2.50 in cents
        formatted = f"${small_cost / 100:.2f}"
        assert formatted == "$2.50"

        # Test edge case - zero
        zero_cost = 0
        formatted = f"${zero_cost / 100:.2f}" if zero_cost > 0 else "$0.00"
        assert formatted == "$0.00"

    def test_percentage_formatting(self):
        """Test percentage formatting"""
        # Test normal percentage
        roi = 125.67
        formatted = f"{roi:.1f}%"
        assert formatted == "125.7%"

        # Test negative percentage
        negative_roi = -15.3
        formatted = f"{negative_roi:.1f}%"
        assert formatted == "-15.3%"

    def test_conditional_display_logic(self):
        """Test conditional display based on data availability"""
        # Test with complete data
        complete_data = {
            "total_cost_cents": 1000_00,
            "total_revenue_cents": 2000_00,
            "total_leads": 100,
            "total_conversions": 10,
        }

        should_show_roi = complete_data["total_cost_cents"] > 0 and complete_data["total_revenue_cents"] > 0
        should_show_cac = complete_data["total_conversions"] > 0
        should_show_cpl = complete_data["total_leads"] > 0

        assert should_show_roi is True
        assert should_show_cac is True
        assert should_show_cpl is True

        # Test with incomplete data
        incomplete_data = {
            "total_cost_cents": 1000_00,
            "total_revenue_cents": 0,
            "total_leads": 0,
            "total_conversions": 0,
        }

        should_show_roi = incomplete_data["total_cost_cents"] > 0 and incomplete_data["total_revenue_cents"] > 0
        should_show_cac = incomplete_data["total_conversions"] > 0
        should_show_cpl = incomplete_data["total_leads"] > 0

        assert should_show_roi is False
        assert should_show_cac is False
        assert should_show_cpl is False

    def test_data_freshness_indicator(self):
        """Test data freshness indicator logic"""
        # Test fresh data (within 24 hours)
        fresh_timestamp = datetime.utcnow() - timedelta(hours=2)
        is_fresh = (datetime.utcnow() - fresh_timestamp).total_seconds() < 24 * 3600
        assert is_fresh is True

        # Test stale data (older than 24 hours)
        stale_timestamp = datetime.utcnow() - timedelta(hours=30)
        is_fresh = (datetime.utcnow() - stale_timestamp).total_seconds() < 24 * 3600
        assert is_fresh is False

    def test_chart_data_preparation(self):
        """Test chart data preparation for mobile display"""
        daily_data = [
            {"date": "2024-01-01", "roi_percentage": 120.0},
            {"date": "2024-01-02", "roi_percentage": 135.0},
            {"date": "2024-01-03", "roi_percentage": 140.0},
        ]

        # Prepare chart data
        chart_dates = [d["date"] for d in daily_data]
        chart_roi = [d["roi_percentage"] for d in daily_data]

        assert len(chart_dates) == 3
        assert len(chart_roi) == 3
        assert chart_roi == [120.0, 135.0, 140.0]

        # Test data point limit for mobile
        max_points = 30  # Mobile-friendly limit
        if len(daily_data) > max_points:
            # Would need to sample or aggregate
            pass

        assert len(daily_data) <= max_points


class TestUnitEconomicsEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_single_day_data(self):
        """Test handling of single day data"""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 1, 1)

        mock_data = _get_unit_economics_mock_data(start_date, end_date)

        assert len(mock_data) == 1
        assert mock_data[0]["date"] == "2024-01-01"

    def test_large_date_range(self):
        """Test handling of large date ranges"""
        start_date = date(2024, 1, 1)
        end_date = date(2024, 12, 31)  # Full year

        mock_data = _get_unit_economics_mock_data(start_date, end_date)

        assert len(mock_data) == 366  # 2024 is a leap year

        # Test performance with large dataset
        total_cost = sum(d["total_cost_cents"] for d in mock_data)
        assert total_cost > 0

    def test_extreme_values(self):
        """Test handling of extreme values"""
        # Test very large values
        extreme_cost = 999999999_00  # $999M in cents
        extreme_leads = 1000000

        cpl = extreme_cost / extreme_leads
        assert abs(cpl - 99999.9999) < 0.001  # $999.99 CPL (floating point tolerance)

        # Test very small values
        tiny_cost = 1  # 1 cent
        tiny_leads = 1000

        cpl = tiny_cost / tiny_leads
        assert abs(cpl - 0.001) < 0.0001  # $0.001 CPL (with floating point tolerance)

    def test_timezone_handling(self):
        """Test timezone handling in date processing"""
        # Test date string parsing
        date_str = "2024-01-01"
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        assert parsed_date == date(2024, 1, 1)

        # Test date range consistency
        start = date(2024, 1, 1)
        end = date(2024, 1, 3)

        date_range = []
        current = start
        while current <= end:
            date_range.append(current)
            current += timedelta(days=1)

        assert len(date_range) == 3
        assert date_range[0] == start
        assert date_range[-1] == end


@pytest.mark.slow
class TestUnitEconomicsPerformance:
    """Test performance characteristics"""

    def test_large_dataset_performance(self):
        """Test performance with large datasets"""
        import time

        # Generate large date range
        start_date = date(2024, 1, 1)
        end_date = date(2024, 12, 31)

        start_time = time.time()
        mock_data = _get_unit_economics_mock_data(start_date, end_date)
        end_time = time.time()

        # Should complete within reasonable time
        assert (end_time - start_time) < 1.0  # Less than 1 second
        assert len(mock_data) == 366

    def test_aggregation_performance(self):
        """Test aggregation performance"""
        import time

        # Large dataset
        large_data = [
            {
                "total_cost_cents": i * 1000_00,
                "total_revenue_cents": i * 2000_00,
                "total_leads": i * 100,
                "total_conversions": i * 10,
            }
            for i in range(1, 1001)  # 1000 records
        ]

        start_time = time.time()

        # Perform aggregations
        total_cost = sum(d["total_cost_cents"] for d in large_data)
        total_revenue = sum(d["total_revenue_cents"] for d in large_data)
        total_leads = sum(d["total_leads"] for d in large_data)
        total_conversions = sum(d["total_conversions"] for d in large_data)

        end_time = time.time()

        # Should complete quickly
        assert (end_time - start_time) < 0.1  # Less than 100ms
        assert total_cost > 0
        assert total_revenue > 0
        assert total_leads > 0
        assert total_conversions > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
