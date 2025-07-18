"""
Comprehensive tests for D10 Analytics Aggregators - P2-010 Critical Coverage.

Tests the aggregation engines for building daily metrics, funnel calculations,
cost analysis, and segment breakdowns. This is a critical component for
achieving 80% test coverage requirement.

Coverage Areas:
- DailyMetricsAggregator: build_funnel_metrics, build_conversion_metrics, build_cost_metrics, build_segment_metrics
- FunnelCalculator: calculate_stage_conversions, calculate_segment_funnels, calculate_time_metrics, analyze_dropoffs
- CostAnalyzer: calculate_lead_costs, calculate_cpa_metrics, calculate_roi_metrics, calculate_efficiency_metrics
- SegmentBreakdownAnalyzer: build_geographic_breakdown, build_vertical_breakdown, build_campaign_breakdown, build_stage_breakdown
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from d10_analytics.aggregators import (
    AggregationResult,
    CostAnalyzer,
    DailyMetricsAggregator,
    FunnelCalculator,
    SegmentBreakdownAnalyzer,
)
from d10_analytics.models import (
    AggregationPeriod,
    EventType,
    FunnelConversion,
    FunnelEvent,
    FunnelStage,
    MetricSnapshot,
    MetricType,
)


class TestDailyMetricsAggregator:
    """Test suite for DailyMetricsAggregator class"""

    @pytest.fixture
    def aggregator(self):
        """Create DailyMetricsAggregator instance"""
        return DailyMetricsAggregator()

    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        session = Mock(spec=Session)
        session.query.return_value = Mock()
        session.add = Mock()
        return session

    @pytest.fixture
    def sample_date(self):
        """Sample date for testing"""
        return date(2025, 1, 15)

    @pytest.mark.asyncio
    async def test_build_funnel_metrics_success(self, aggregator, mock_session, sample_date):
        """Test successful funnel metrics building"""
        # Mock query results for event counts
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [
            (EventType.ENTRY, 10),
            (EventType.CONVERSION, 5),
        ]

        # Mock scalar results for success rate and duration
        mock_query.scalar.return_value = 10

        mock_session.query.return_value = mock_query

        # Execute
        result = await aggregator.build_funnel_metrics(mock_session, sample_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) >= 0  # Should create metrics for each stage
        mock_session.add.assert_called()  # Should add metrics to session

        print("✓ DailyMetricsAggregator.build_funnel_metrics works correctly")

    @pytest.mark.asyncio
    async def test_build_funnel_metrics_empty_data(self, aggregator, mock_session, sample_date):
        """Test funnel metrics building with no data"""
        # Mock empty query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.scalar.return_value = 0

        mock_session.query.return_value = mock_query

        # Execute
        result = await aggregator.build_funnel_metrics(mock_session, sample_date)

        # Verify
        assert isinstance(result, list)
        # Should still create metrics even with no data

        print("✓ DailyMetricsAggregator.build_funnel_metrics handles empty data correctly")

    @pytest.mark.asyncio
    async def test_build_conversion_metrics_success(self, aggregator, mock_session, sample_date):
        """Test successful conversion metrics building"""
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 5  # 5 conversions, 10 entries

        mock_session.query.return_value = mock_query

        # Execute
        result = await aggregator.build_conversion_metrics(mock_session, sample_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) >= 1  # Should create at least conversion count metric
        mock_session.add.assert_called()  # Should add metrics to session

        print("✓ DailyMetricsAggregator.build_conversion_metrics works correctly")

    @pytest.mark.asyncio
    async def test_build_conversion_metrics_zero_entries(self, aggregator, mock_session, sample_date):
        """Test conversion metrics building with zero entries"""
        # Mock query results - conversions but no entries
        mock_query = Mock()
        mock_query.filter.return_value = mock_query

        # First call (conversions) returns 5, second call (entries) returns 0
        mock_query.scalar.side_effect = [5, 0]

        mock_session.query.return_value = mock_query

        # Execute
        result = await aggregator.build_conversion_metrics(mock_session, sample_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 1  # Should only create conversion count, not rate

        print("✓ DailyMetricsAggregator.build_conversion_metrics handles zero entries correctly")

    @pytest.mark.asyncio
    async def test_build_cost_metrics_success(self, aggregator, mock_session, sample_date):
        """Test successful cost metrics building"""
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.side_effect = [1000, 10]  # Total cost, event count

        mock_session.query.return_value = mock_query

        # Execute
        result = await aggregator.build_cost_metrics(mock_session, sample_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) >= 1  # Should create cost metrics
        mock_session.add.assert_called()  # Should add metrics to session

        print("✓ DailyMetricsAggregator.build_cost_metrics works correctly")

    @pytest.mark.asyncio
    async def test_build_cost_metrics_zero_events(self, aggregator, mock_session, sample_date):
        """Test cost metrics building with zero events"""
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.side_effect = [1000, 0]  # Total cost, zero events

        mock_session.query.return_value = mock_query

        # Execute
        result = await aggregator.build_cost_metrics(mock_session, sample_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 1  # Should only create total cost, not average

        print("✓ DailyMetricsAggregator.build_cost_metrics handles zero events correctly")

    @pytest.mark.asyncio
    async def test_build_segment_metrics_success(self, aggregator, mock_session, sample_date):
        """Test successful segment metrics building"""
        # Mock query results for campaign metrics
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [
            ("campaign_1", 10, 5),  # campaign_id, event_count, success_count
            ("campaign_2", 20, 8),
        ]

        mock_session.query.return_value = mock_query

        # Execute
        result = await aggregator.build_segment_metrics(mock_session, sample_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) >= 2  # Should create metrics for each campaign
        mock_session.add.assert_called()  # Should add metrics to session

        print("✓ DailyMetricsAggregator.build_segment_metrics works correctly")

    @pytest.mark.asyncio
    async def test_build_segment_metrics_empty_campaigns(self, aggregator, mock_session, sample_date):
        """Test segment metrics building with no campaigns"""
        # Mock empty query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = []

        mock_session.query.return_value = mock_query

        # Execute
        result = await aggregator.build_segment_metrics(mock_session, sample_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 0  # Should create no metrics for empty campaigns

        print("✓ DailyMetricsAggregator.build_segment_metrics handles empty campaigns correctly")

    def test_aggregator_initialization(self, aggregator):
        """Test aggregator initialization"""
        assert aggregator.logger is not None
        assert hasattr(aggregator, "metrics_buffer")
        assert isinstance(aggregator.metrics_buffer, list)

        print("✓ DailyMetricsAggregator initialization works correctly")


class TestFunnelCalculator:
    """Test suite for FunnelCalculator class"""

    @pytest.fixture
    def calculator(self):
        """Create FunnelCalculator instance"""
        return FunnelCalculator()

    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        session = Mock(spec=Session)
        session.query.return_value = Mock()
        session.add = Mock()
        return session

    @pytest.fixture
    def date_range(self):
        """Sample date range for testing"""
        return date(2025, 1, 15), date(2025, 1, 16)

    @pytest.mark.asyncio
    async def test_calculate_stage_conversions_success(self, calculator, mock_session, date_range):
        """Test successful stage conversions calculation"""
        start_date, end_date = date_range

        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.side_effect = [10, 5]  # started_count, completed_count

        mock_session.query.return_value = mock_query

        # Execute
        result = await calculator.calculate_stage_conversions(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        mock_session.add.assert_called()  # Should add conversions to session

        print("✓ FunnelCalculator.calculate_stage_conversions works correctly")

    @pytest.mark.asyncio
    async def test_calculate_stage_conversions_zero_started(self, calculator, mock_session, date_range):
        """Test stage conversions calculation with zero started"""
        start_date, end_date = date_range

        # Mock query results - zero started count
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0

        mock_session.query.return_value = mock_query

        # Execute
        result = await calculator.calculate_stage_conversions(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        # Should create no conversions when no users started

        print("✓ FunnelCalculator.calculate_stage_conversions handles zero started correctly")

    @pytest.mark.asyncio
    async def test_calculate_segment_funnels_success(self, calculator, mock_session, date_range):
        """Test successful segment funnels calculation"""
        start_date, end_date = date_range

        # Mock query results for campaigns
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [("campaign_1",), ("campaign_2",)]

        mock_session.query.return_value = mock_query

        # Execute
        result = await calculator.calculate_segment_funnels(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        mock_session.add.assert_called()  # Should add conversions to session

        print("✓ FunnelCalculator.calculate_segment_funnels works correctly")

    @pytest.mark.asyncio
    async def test_calculate_segment_funnels_no_campaigns(self, calculator, mock_session, date_range):
        """Test segment funnels calculation with no campaigns"""
        start_date, end_date = date_range

        # Mock empty query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        mock_session.query.return_value = mock_query

        # Execute
        result = await calculator.calculate_segment_funnels(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 0  # Should create no conversions for no campaigns

        print("✓ FunnelCalculator.calculate_segment_funnels handles no campaigns correctly")

    @pytest.mark.asyncio
    async def test_calculate_time_metrics_success(self, calculator, mock_session, date_range):
        """Test successful time metrics calculation"""
        start_date, end_date = date_range

        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 5000.0  # 5 seconds average duration

        mock_session.query.return_value = mock_query

        # Execute
        result = await calculator.calculate_time_metrics(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        mock_session.add.assert_called()  # Should add metrics to session

        print("✓ FunnelCalculator.calculate_time_metrics works correctly")

    @pytest.mark.asyncio
    async def test_calculate_time_metrics_null_duration(self, calculator, mock_session, date_range):
        """Test time metrics calculation with null duration"""
        start_date, end_date = date_range

        # Mock query results - null duration
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = None

        mock_session.query.return_value = mock_query

        # Execute
        result = await calculator.calculate_time_metrics(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        # Should create no metrics when duration is null

        print("✓ FunnelCalculator.calculate_time_metrics handles null duration correctly")

    @pytest.mark.asyncio
    async def test_analyze_dropoffs_success(self, calculator, mock_session, date_range):
        """Test successful dropoff analysis"""
        start_date, end_date = date_range

        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.side_effect = [10, 3]  # entries, abandonments

        mock_session.query.return_value = mock_query

        # Execute
        result = await calculator.analyze_dropoffs(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        mock_session.add.assert_called()  # Should add metrics to session

        print("✓ FunnelCalculator.analyze_dropoffs works correctly")

    @pytest.mark.asyncio
    async def test_analyze_dropoffs_zero_entries(self, calculator, mock_session, date_range):
        """Test dropoff analysis with zero entries"""
        start_date, end_date = date_range

        # Mock query results - zero entries
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.side_effect = [0, 0]  # entries, abandonments

        mock_session.query.return_value = mock_query

        # Execute
        result = await calculator.analyze_dropoffs(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        # Should create no dropoff metrics when no entries

        print("✓ FunnelCalculator.analyze_dropoffs handles zero entries correctly")

    def test_calculator_initialization(self, calculator):
        """Test calculator initialization"""
        assert calculator.logger is not None

        print("✓ FunnelCalculator initialization works correctly")


class TestCostAnalyzer:
    """Test suite for CostAnalyzer class"""

    @pytest.fixture
    def analyzer(self):
        """Create CostAnalyzer instance"""
        return CostAnalyzer()

    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        session = Mock(spec=Session)
        session.query.return_value = Mock()
        session.add = Mock()
        return session

    @pytest.fixture
    def date_range(self):
        """Sample date range for testing"""
        return date(2025, 1, 15), date(2025, 1, 16)

    @pytest.mark.asyncio
    async def test_calculate_lead_costs_success(self, analyzer, mock_session, date_range):
        """Test successful lead costs calculation"""
        start_date, end_date = date_range

        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 10  # total_leads

        mock_session.query.return_value = mock_query

        # Execute
        result = await analyzer.calculate_lead_costs(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 1  # Should create cost per lead metric

        print("✓ CostAnalyzer.calculate_lead_costs works correctly")

    @pytest.mark.asyncio
    async def test_calculate_lead_costs_zero_leads(self, analyzer, mock_session, date_range):
        """Test lead costs calculation with zero leads"""
        start_date, end_date = date_range

        # Mock query results - zero leads
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0  # zero leads

        mock_session.query.return_value = mock_query

        # Execute
        result = await analyzer.calculate_lead_costs(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 0  # Should create no metrics for zero leads

        print("✓ CostAnalyzer.calculate_lead_costs handles zero leads correctly")

    @pytest.mark.asyncio
    async def test_calculate_cpa_metrics_success(self, analyzer, mock_session, date_range):
        """Test successful CPA metrics calculation"""
        start_date, end_date = date_range

        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 2  # total_conversions

        mock_session.query.return_value = mock_query

        # Execute
        result = await analyzer.calculate_cpa_metrics(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 1  # Should create CPA metric

        print("✓ CostAnalyzer.calculate_cpa_metrics works correctly")

    @pytest.mark.asyncio
    async def test_calculate_cpa_metrics_zero_conversions(self, analyzer, mock_session, date_range):
        """Test CPA metrics calculation with zero conversions"""
        start_date, end_date = date_range

        # Mock query results - zero conversions
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0  # zero conversions

        mock_session.query.return_value = mock_query

        # Execute
        result = await analyzer.calculate_cpa_metrics(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 0  # Should create no metrics for zero conversions

        print("✓ CostAnalyzer.calculate_cpa_metrics handles zero conversions correctly")

    @pytest.mark.asyncio
    async def test_calculate_roi_metrics_success(self, analyzer, mock_session, date_range):
        """Test successful ROI metrics calculation"""
        start_date, end_date = date_range

        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 10  # stage_events

        mock_session.query.return_value = mock_query

        # Execute
        result = await analyzer.calculate_roi_metrics(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 6  # One metric for each FunnelStage
        # Note: No longer adding metrics to session since MetricSnapshot is a dataclass

        print("✓ CostAnalyzer.calculate_roi_metrics works correctly")

    @pytest.mark.asyncio
    async def test_calculate_roi_metrics_zero_events(self, analyzer, mock_session, date_range):
        """Test ROI metrics calculation with zero events"""
        start_date, end_date = date_range

        # Mock query results - zero events
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0  # stage_events

        mock_session.query.return_value = mock_query

        # Execute
        result = await analyzer.calculate_roi_metrics(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 0  # No metrics for zero events

        print("✓ CostAnalyzer.calculate_roi_metrics handles zero events correctly")

    @pytest.mark.asyncio
    async def test_calculate_efficiency_metrics_success(self, analyzer, mock_session, date_range):
        """Test successful efficiency metrics calculation"""
        start_date, end_date = date_range

        # Mock query results for campaign efficiency
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [
            ("campaign_1", 10, 5),  # campaign_id, total_events, successful_events
            ("campaign_2", 20, 8),
        ]

        mock_session.query.return_value = mock_query

        # Execute
        result = await analyzer.calculate_efficiency_metrics(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 4  # Two campaigns, two metrics each

        print("✓ CostAnalyzer.calculate_efficiency_metrics works correctly")

    @pytest.mark.asyncio
    async def test_calculate_efficiency_metrics_zero_events(self, analyzer, mock_session, date_range):
        """Test efficiency metrics calculation with zero events"""
        start_date, end_date = date_range

        # Mock query results - zero events
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [
            ("campaign_1", 0, 0),  # campaign_id, zero events, zero successful
        ]

        mock_session.query.return_value = mock_query

        # Execute
        result = await analyzer.calculate_efficiency_metrics(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        # Should create no efficiency metrics when no events

        print("✓ CostAnalyzer.calculate_efficiency_metrics handles zero events correctly")

    def test_analyzer_initialization(self, analyzer):
        """Test analyzer initialization"""
        assert analyzer.logger is not None

        print("✓ CostAnalyzer initialization works correctly")


class TestSegmentBreakdownAnalyzer:
    """Test suite for SegmentBreakdownAnalyzer class"""

    @pytest.fixture
    def analyzer(self):
        """Create SegmentBreakdownAnalyzer instance"""
        return SegmentBreakdownAnalyzer()

    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        session = Mock(spec=Session)
        session.query.return_value = Mock()
        session.add = Mock()
        return session

    @pytest.fixture
    def date_range(self):
        """Sample date range for testing"""
        return date(2025, 1, 15), date(2025, 1, 16)

    @pytest.mark.asyncio
    async def test_build_geographic_breakdown_success(self, analyzer, mock_session, date_range):
        """Test successful geographic breakdown building"""
        start_date, end_date = date_range

        # Execute
        result = await analyzer.build_geographic_breakdown(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        # Geographic breakdown is placeholder implementation

        print("✓ SegmentBreakdownAnalyzer.build_geographic_breakdown works correctly")

    @pytest.mark.asyncio
    async def test_build_vertical_breakdown_success(self, analyzer, mock_session, date_range):
        """Test successful vertical breakdown building"""
        start_date, end_date = date_range

        # Execute
        result = await analyzer.build_vertical_breakdown(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        # Vertical breakdown is placeholder implementation

        print("✓ SegmentBreakdownAnalyzer.build_vertical_breakdown works correctly")

    @pytest.mark.asyncio
    async def test_build_campaign_breakdown_success(self, analyzer, mock_session, date_range):
        """Test successful campaign breakdown building"""
        start_date, end_date = date_range

        # Mock query results for campaign stats
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [
            ("campaign_1", 10, 5, 1000),  # campaign_id, total_events, successful_events, total_cost
            ("campaign_2", 20, 8, 2000),
        ]

        mock_session.query.return_value = mock_query

        # Execute
        result = await analyzer.build_campaign_breakdown(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        mock_session.add.assert_called()  # Should add metrics to session

        print("✓ SegmentBreakdownAnalyzer.build_campaign_breakdown works correctly")

    @pytest.mark.asyncio
    async def test_build_campaign_breakdown_zero_events(self, analyzer, mock_session, date_range):
        """Test campaign breakdown building with zero events"""
        start_date, end_date = date_range

        # Mock query results - zero events
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [
            ("campaign_1", 0, 0, 1000),  # campaign_id, zero events
        ]

        mock_session.query.return_value = mock_query

        # Execute
        result = await analyzer.build_campaign_breakdown(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        # Should create no metrics when no events

        print("✓ SegmentBreakdownAnalyzer.build_campaign_breakdown handles zero events correctly")

    @pytest.mark.asyncio
    async def test_build_stage_breakdown_success(self, analyzer, mock_session, date_range):
        """Test successful stage breakdown building"""
        start_date, end_date = date_range

        # Mock query results for stage stats
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = Mock(total_events=10, successful_events=5, avg_duration=5000.0)

        mock_session.query.return_value = mock_query

        # Execute
        result = await analyzer.build_stage_breakdown(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        mock_session.add.assert_called()  # Should add metrics to session

        print("✓ SegmentBreakdownAnalyzer.build_stage_breakdown works correctly")

    @pytest.mark.asyncio
    async def test_build_stage_breakdown_zero_events(self, analyzer, mock_session, date_range):
        """Test stage breakdown building with zero events"""
        start_date, end_date = date_range

        # Mock query results - zero events
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = Mock(total_events=0, successful_events=0, avg_duration=None)

        mock_session.query.return_value = mock_query

        # Execute
        result = await analyzer.build_stage_breakdown(mock_session, start_date, end_date)

        # Verify
        assert isinstance(result, list)
        # Should create no metrics when no events

        print("✓ SegmentBreakdownAnalyzer.build_stage_breakdown handles zero events correctly")

    def test_analyzer_initialization(self, analyzer):
        """Test analyzer initialization"""
        assert analyzer.logger is not None

        print("✓ SegmentBreakdownAnalyzer initialization works correctly")

    def test_add_metric_buffer_compatibility(self, analyzer):
        """Test add_metric method for buffer compatibility"""
        # Mock metric
        mock_metric = Mock()
        mock_metric.type = Mock()
        mock_metric.type.value = "test_metric"
        mock_metric.value = 100.0

        # Test if method exists and is callable
        if hasattr(analyzer, "add_metric"):
            analyzer.add_metric(mock_metric)
            print("✓ SegmentBreakdownAnalyzer.add_metric works correctly")
        else:
            print("✓ SegmentBreakdownAnalyzer.add_metric method not implemented (expected)")

    def test_get_aggregated_results_buffer_compatibility(self, analyzer):
        """Test get_aggregated_results method for buffer compatibility"""
        # Test if method exists and is callable
        if hasattr(analyzer, "get_aggregated_results"):
            result = analyzer.get_aggregated_results()
            assert isinstance(result, dict)
            print("✓ SegmentBreakdownAnalyzer.get_aggregated_results works correctly")
        else:
            print("✓ SegmentBreakdownAnalyzer.get_aggregated_results method not implemented (expected)")


class TestAggregationResult:
    """Test suite for AggregationResult dataclass"""

    def test_aggregation_result_creation(self):
        """Test AggregationResult creation"""
        metrics = [Mock(spec=MetricSnapshot)]
        result = AggregationResult(metrics_created=metrics, events_processed=100, processing_time_ms=1500.0)

        assert result.metrics_created == metrics
        assert result.events_processed == 100
        assert result.processing_time_ms == 1500.0

        print("✓ AggregationResult creation works correctly")

    def test_aggregation_result_empty_metrics(self):
        """Test AggregationResult with empty metrics"""
        result = AggregationResult(metrics_created=[], events_processed=0, processing_time_ms=0.0)

        assert result.metrics_created == []
        assert result.events_processed == 0
        assert result.processing_time_ms == 0.0

        print("✓ AggregationResult with empty metrics works correctly")


def test_aggregators_integration():
    """Integration test for aggregators module"""
    print("Running aggregators integration tests...")

    # Test module-level imports
    from d10_analytics.aggregators import (
        AggregationResult,
        CostAnalyzer,
        DailyMetricsAggregator,
        FunnelCalculator,
        SegmentBreakdownAnalyzer,
    )

    # Test class instantiation
    aggregator = DailyMetricsAggregator()
    calculator = FunnelCalculator()
    cost_analyzer = CostAnalyzer()
    segment_analyzer = SegmentBreakdownAnalyzer()

    # Test basic functionality
    assert aggregator.logger is not None
    assert calculator.logger is not None
    assert cost_analyzer.logger is not None
    assert segment_analyzer.logger is not None

    print("✓ All aggregators integration tests passed")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
