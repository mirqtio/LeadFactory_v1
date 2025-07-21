"""
Test suite for batch_runner cost calculator
Focus on achieving ≥80% total coverage for P0-022
"""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from batch_runner.cost_calculator import CostCalculator, get_cost_calculator


class TestCostCalculator:
    """Test suite for cost calculator"""

    @pytest.fixture
    def cost_calculator(self):
        """Create cost calculator instance"""
        with patch("batch_runner.cost_calculator.get_settings") as mock_settings:
            settings = Mock()
            settings.COST_CALCULATOR_CONFIG_PATH = "test_config.json"
            settings.DEFAULT_REPORT_COST = 0.50
            settings.DEFAULT_ENRICHMENT_COST = 0.25
            mock_settings.return_value = settings

            return CostCalculator()

    def test_cost_calculator_singleton(self):
        """Test cost calculator singleton pattern"""
        calc1 = get_cost_calculator()
        calc2 = get_cost_calculator()

        assert calc1 is calc2

    def test_cost_calculator_initialization(self, cost_calculator):
        """Test cost calculator initialization"""
        assert cost_calculator.rates is not None
        assert cost_calculator.settings is not None

        # Test that rates can be loaded
        rates = cost_calculator.rates.get_rates()
        assert "report_generation" in rates
        assert "providers" in rates

    def test_calculate_batch_preview_basic(self, cost_calculator):
        """Test basic batch cost preview calculation"""
        # Mock lead IDs for testing
        lead_ids = [f"lead-{i}" for i in range(10)]

        with patch("batch_runner.cost_calculator.SessionLocal") as mock_session:
            # Mock database session
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = []

            result = cost_calculator.calculate_batch_preview(lead_ids=lead_ids, template_version="v1")

        assert "cost_breakdown" in result
        assert "total_cost" in result["cost_breakdown"]
        assert "estimated_duration_minutes" in result
        assert "cost_per_lead" in result

    def test_calculate_batch_preview_large_batch(self, cost_calculator):
        """Test batch cost preview for large batch"""
        # Create 1000 mock lead IDs
        lead_ids = [f"lead-{i}" for i in range(1000)]

        with patch("batch_runner.cost_calculator.SessionLocal") as mock_session:
            # Mock database session
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchall.return_value = []

            result = cost_calculator.calculate_batch_preview(lead_ids=lead_ids, template_version="v1")

        total_cost = result["cost_breakdown"]["total_cost"]
        cost_per_lead = result["cost_per_lead"]

        assert total_cost > 0
        assert cost_per_lead > 0
        assert abs(total_cost - cost_per_lead * 1000) < 0.01  # Allow for floating point precision

    def test_calculate_batch_preview_zero_leads(self, cost_calculator):
        """Test batch cost preview with zero leads"""
        # Empty lead IDs list
        lead_ids = []

        with patch("batch_runner.cost_calculator.SessionLocal") as mock_session:
            result = cost_calculator.calculate_batch_preview(lead_ids=lead_ids, template_version="v1")

        assert result["cost_breakdown"]["total_cost"] == 0
        assert result["cost_per_lead"] == 0

    def test_calculate_batch_preview_with_provider_breakdown(self, cost_calculator):
        """Test cost preview with provider breakdown"""
        # Create 100 mock lead IDs
        lead_ids = [f"lead-{i}" for i in range(100)]

        with patch("batch_runner.cost_calculator.SessionLocal") as mock_session:
            # Mock database session
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock statistics query for provider breakdown
            mock_stats = Mock()
            mock_stats.total_leads = 100
            mock_stats.needs_email = 30
            mock_stats.has_domain = 80
            mock_stats.needs_enrichment = 50
            mock_db.execute.return_value.fetchone.return_value = mock_stats
            mock_db.execute.return_value.fetchall.return_value = []

            result = cost_calculator.calculate_batch_preview(lead_ids=lead_ids, template_version="v1")

        assert "provider_breakdown" in result
        assert len(result["provider_breakdown"]) >= 3

    def test_calculate_lead_provider_cost_completed_enrichment(self, cost_calculator):
        """Test individual lead cost calculation with completed enrichment"""
        rates_config = cost_calculator.rates.get_rates()

        # Mock lead with completed enrichment
        lead = Mock()
        lead.enrichment_status = "completed"
        lead.email = "test@test.com"
        lead.domain = "test.com"

        cost = cost_calculator._calculate_lead_provider_cost(lead, rates_config)

        # Should only include assessment costs (no enrichment)
        assert cost > 0
        assert isinstance(cost, Decimal)

    def test_calculate_lead_provider_cost_pending_enrichment(self, cost_calculator):
        """Test individual lead cost calculation with pending enrichment"""
        rates_config = cost_calculator.rates.get_rates()

        # Mock lead needing enrichment
        lead = Mock()
        lead.enrichment_status = "pending"
        lead.email = None  # Needs email enrichment
        lead.domain = "test.com"

        cost = cost_calculator._calculate_lead_provider_cost(lead, rates_config)

        # Should include both enrichment and assessment costs
        assert cost > 0
        assert isinstance(cost, Decimal)

    def test_validate_budget_within_limit(self, cost_calculator):
        """Test budget validation within limits"""
        with patch("batch_runner.cost_calculator.SessionLocal") as mock_session:
            # Mock database session for daily spending query
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_result = Mock()
            mock_result.spent_today = 25.0
            mock_db.execute.return_value.fetchone.return_value = mock_result

            result = cost_calculator.validate_budget(total_cost=50.0, daily_budget_override=100.0)

        assert result["is_within_budget"] is True
        assert result["warning_message"] is None

    def test_validate_budget_exceeds_limit(self, cost_calculator):
        """Test budget validation exceeding limits"""
        with patch("batch_runner.cost_calculator.SessionLocal") as mock_session:
            # Mock database session for daily spending query
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_result = Mock()
            mock_result.spent_today = 10.0  # Already spent 10, requesting 150 more, limit 100
            mock_db.execute.return_value.fetchone.return_value = mock_result

            result = cost_calculator.validate_budget(total_cost=150.0, daily_budget_override=100.0)

        assert result["is_within_budget"] is False
        assert "exceeds" in result["warning_message"].lower()

    def test_validate_budget_at_limit(self, cost_calculator):
        """Test budget validation at exact limit"""
        with patch("batch_runner.cost_calculator.SessionLocal") as mock_session:
            # Mock database session for daily spending query
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_result = Mock()
            mock_result.spent_today = 0.0  # No spending yet
            mock_db.execute.return_value.fetchone.return_value = mock_result

            result = cost_calculator.validate_budget(total_cost=100.0, daily_budget_override=100.0)

        assert result["is_within_budget"] is True

    def test_volume_discount_calculation(self, cost_calculator):
        """Test volume discount calculation"""
        rates_config = cost_calculator.rates.get_rates()

        # Test different volume tiers
        discount_10 = cost_calculator._calculate_volume_discount(10, rates_config)
        discount_100 = cost_calculator._calculate_volume_discount(100, rates_config)
        discount_1000 = cost_calculator._calculate_volume_discount(1000, rates_config)

        # Higher volumes should get better (lower) multipliers
        assert discount_100 <= discount_10
        assert discount_1000 <= discount_100
        assert isinstance(discount_10, Decimal)

    def test_estimate_duration_method(self, cost_calculator):
        """Test _estimate_duration method"""
        time_estimate = cost_calculator._estimate_duration(100, "v1")

        assert time_estimate > 0
        assert isinstance(time_estimate, int)

    def test_estimate_duration_zero_leads(self, cost_calculator):
        """Test processing time estimation with zero leads"""
        time_estimate = cost_calculator._estimate_duration(0, "v1")

        assert time_estimate >= 0
        assert isinstance(time_estimate, int)

    def test_estimate_duration_large_batch(self, cost_calculator):
        """Test processing time estimation for large batch"""
        time_small = cost_calculator._estimate_duration(10, "v1")
        time_large = cost_calculator._estimate_duration(1000, "v1")

        # Large batch should take more time
        assert time_large >= time_small

    def test_cost_rates_get_rates(self, cost_calculator):
        """Test getting cost rates"""
        rates = cost_calculator.rates.get_rates()

        assert isinstance(rates, dict)
        assert "providers" in rates
        assert "report_generation" in rates
        assert len(rates) > 0

    def test_overhead_calculation(self, cost_calculator):
        """Test overhead calculation"""
        rates_config = cost_calculator.rates.get_rates()
        base_cost = Decimal("100.0")

        overhead = cost_calculator._calculate_overhead(base_cost, rates_config)

        assert overhead > 0
        assert isinstance(overhead, Decimal)

    def test_base_cost_calculation(self, cost_calculator):
        """Test base cost calculation"""
        rates_config = cost_calculator.rates.get_rates()

        base_cost = cost_calculator._calculate_base_cost(10, "v1", rates_config)

        assert base_cost > 0
        assert isinstance(base_cost, Decimal)


class TestCostCalculatorEdgeCases:
    """Test edge cases and error conditions"""

    def test_cost_calculator_with_invalid_config(self):
        """Test cost calculator with invalid config path"""
        with patch("batch_runner.cost_calculator.get_settings") as mock_settings:
            settings = Mock()
            settings.cost_budget_usd = 100.0
            mock_settings.return_value = settings

            # Should handle gracefully and use default rates
            calc = CostCalculator()
            rates = calc.rates.get_rates()
            assert "providers" in rates
            assert "report_generation" in rates

    def test_calculate_batch_preview_empty_leads(self, cost_calculator):
        """Test batch preview with empty lead list"""
        with patch("batch_runner.cost_calculator.SessionLocal") as mock_session:
            result = cost_calculator.calculate_batch_preview(lead_ids=[], template_version="v1")
            # Empty list should result in zero cost
            assert result["cost_breakdown"]["total_cost"] == 0

    def test_validate_budget_negative_values(self, cost_calculator):
        """Test budget validation with negative values"""
        with patch("batch_runner.cost_calculator.SessionLocal") as mock_session:
            # Mock database session
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_result = Mock()
            mock_result.spent_today = 0.0
            mock_db.execute.return_value.fetchone.return_value = mock_result

            result = cost_calculator.validate_budget(total_cost=-10.0, daily_budget_override=100.0)

        # Should handle gracefully
        assert isinstance(result, dict)
        assert "is_within_budget" in result
