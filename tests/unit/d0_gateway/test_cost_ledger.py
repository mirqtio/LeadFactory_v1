"""
Unit tests for d0_gateway.cost_ledger module
Tests cost tracking and aggregation functionality
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy.orm import Session

from d0_gateway.cost_ledger import CostLedger, cost_ledger
from database.models import APICost, DailyCostAggregate


class TestCostLedger:
    """Test CostLedger class functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.cost_ledger = CostLedger()

    @patch("d0_gateway.cost_ledger.get_db_sync")
    @patch("d0_gateway.cost_ledger.get_settings")
    def test_record_cost_success(self, mock_settings, mock_db):
        """Test successful cost recording"""
        # Mock settings
        mock_settings.return_value.enable_cost_tracking = True

        # Mock database session
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        # Mock the created cost record
        mock_cost_record = Mock()
        mock_cost_record.id = 1
        mock_session.refresh.return_value = mock_cost_record

        result = self.cost_ledger.record_cost(
            provider="dataaxle",
            operation="search",
            cost_usd=Decimal("5.50"),
            lead_id=123,
            campaign_id=456,
            request_id="req_123",
            metadata={"test": "data"},
        )

        # Verify database operations
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

        # Verify APICost creation
        added_cost = mock_session.add.call_args[0][0]
        assert isinstance(added_cost, APICost)
        assert added_cost.provider == "dataaxle"
        assert added_cost.operation == "search"
        assert added_cost.cost_usd == Decimal("5.50")
        assert added_cost.lead_id == 123
        assert added_cost.campaign_id == 456
        assert added_cost.request_id == "req_123"
        assert added_cost.meta_data == {"test": "data"}

    def test_record_cost_tracking_disabled(self):
        """Test cost recording when tracking is disabled"""
        # Patch the settings attribute directly on the instance
        print(f"Before: enable_cost_tracking = {self.cost_ledger.settings.enable_cost_tracking}")
        self.cost_ledger.settings.enable_cost_tracking = False
        print(f"After: enable_cost_tracking = {self.cost_ledger.settings.enable_cost_tracking}")

        result = self.cost_ledger.record_cost(provider="dataaxle", operation="search", cost_usd=Decimal("5.50"))
        print(f"Result: {result}")

        assert result is None

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_record_cost_minimal_args(self, mock_db):
        """Test cost recording with minimal arguments"""
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        result = self.cost_ledger.record_cost(provider="openai", operation="completion", cost_usd=Decimal("0.02"))

        added_cost = mock_session.add.call_args[0][0]
        assert added_cost.provider == "openai"
        assert added_cost.operation == "completion"
        assert added_cost.cost_usd == Decimal("0.02")
        assert added_cost.lead_id is None
        assert added_cost.campaign_id is None
        assert added_cost.request_id is None
        assert added_cost.meta_data == {}

    @patch("d0_gateway.cost_ledger.get_db_sync")
    @patch("d0_gateway.cost_ledger.datetime")
    def test_get_provider_costs_success(self, mock_datetime, mock_db):
        """Test successful provider costs retrieval"""
        # Mock current time
        mock_now = datetime(2025, 1, 31, 12, 0)
        mock_datetime.now.return_value = mock_now

        # Mock database session and query results
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        # Mock aggregate query result
        mock_result = Mock()
        mock_result.total_cost = Decimal("150.75")
        mock_result.request_count = 100
        mock_session.query.return_value.filter.return_value.first.return_value = mock_result

        # Mock operation breakdown results
        mock_op_results = [
            Mock(operation="search", total_cost=Decimal("120.50"), request_count=80),
            Mock(operation="match", total_cost=Decimal("30.25"), request_count=20),
        ]
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_op_results

        result = self.cost_ledger.get_provider_costs("dataaxle")

        assert result["provider"] == "dataaxle"
        assert result["total_cost"] == float(mock_result.total_cost)
        assert result["total_requests"] == mock_result.request_count
        assert "operations" in result
        assert len(result["operations"]) == 2

    @patch("d0_gateway.cost_ledger.get_db_sync")
    @patch("d0_gateway.cost_ledger.datetime")
    def test_get_provider_costs_no_data(self, mock_datetime, mock_db):
        """Test provider costs retrieval with no data"""
        mock_datetime.now.return_value = datetime(2025, 1, 31, 12, 0)

        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        # Mock no results
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = []

        result = self.cost_ledger.get_provider_costs("unknown_provider")

        assert result["provider"] == "unknown_provider"
        assert result["total_cost"] == 0.0
        assert result["total_requests"] == 0
        assert result["operations"] == {}

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_get_provider_costs_with_date_range(self, mock_db):
        """Test provider costs with specific date range"""
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 1, 31)

        self.cost_ledger.get_provider_costs("dataaxle", start_date=start_date, end_date=end_date)

        # Verify date filtering was applied
        mock_session.query.assert_called()

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_get_campaign_costs_success(self, mock_db):
        """Test successful campaign costs retrieval"""
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        # Mock aggregate query result
        mock_result = Mock()
        mock_result.total_cost = Decimal("250.00")
        mock_session.query.return_value.filter.return_value.first.return_value = mock_result

        # Mock provider breakdown
        mock_provider_results = [
            Mock(provider="dataaxle", total_cost=Decimal("150.00"), request_count=50),
            Mock(provider="hunter", total_cost=Decimal("100.00"), request_count=25),
        ]
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = (
            mock_provider_results
        )

        result = self.cost_ledger.get_campaign_costs(123)

        assert result["campaign_id"] == 123
        assert result["total_cost"] == 250.0
        assert "providers" in result
        assert len(result["providers"]) == 2

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_get_campaign_costs_no_data(self, mock_db):
        """Test campaign costs retrieval with no data"""
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = []

        result = self.cost_ledger.get_campaign_costs(999)

        assert result["campaign_id"] == 999
        assert result["total_cost"] == 0.0
        assert result["providers"] == {}

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_get_daily_costs_success(self, mock_db):
        """Test successful daily costs retrieval"""
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        mock_results = [
            Mock(
                date="2025-01-15",
                provider="dataaxle",
                operation="search",
                campaign_id=123,
                total_cost=Decimal("25.50"),
                request_count=10,
            ),
            Mock(
                date="2025-01-16",
                provider="hunter",
                operation="email",
                campaign_id=124,
                total_cost=Decimal("15.25"),
                request_count=5,
            ),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_results

        start_date = date(2025, 1, 15)
        result = self.cost_ledger.get_daily_costs(start_date=start_date)

        assert len(result) == 2
        assert result[0]["date"] == "2025-01-15"
        assert result[0]["provider"] == "dataaxle"
        assert result[0]["total_cost"] == 25.50

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_get_daily_costs_with_filters(self, mock_db):
        """Test daily costs retrieval with filters"""
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.all.return_value = []

        start_date = date(2025, 1, 1)
        end_date = date(2025, 1, 31)

        self.cost_ledger.get_daily_costs(start_date=start_date, end_date=end_date, provider="dataaxle", campaign_id=123)

        # Verify filtering was applied
        mock_session.query.assert_called()

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_aggregate_daily_costs_success(self, mock_db):
        """Test successful daily cost aggregation"""
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        # Mock cost records for aggregation
        mock_costs = [
            Mock(provider="dataaxle", operation="search", campaign_id=123, cost_usd=Decimal("10.00")),
            Mock(provider="dataaxle", operation="search", campaign_id=123, cost_usd=Decimal("15.00")),
            Mock(provider="hunter", operation="email", campaign_id=124, cost_usd=Decimal("5.00")),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = mock_costs

        target_date = date(2025, 1, 15)
        result = self.cost_ledger.aggregate_daily_costs(target_date)

        # Should create 2 aggregates (one per provider/operation/campaign combo)
        assert len(result) == 2

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_cleanup_old_records_success(self, mock_db):
        """Test successful cleanup of old records"""
        mock_session = MagicMock()
        mock_db.return_value.__enter__.return_value = mock_session

        # Mock deleted count
        mock_session.query.return_value.filter.return_value.delete.return_value = 50

        result = self.cost_ledger.cleanup_old_records(90)

        assert result == 50
        mock_session.commit.assert_called_once()


class TestCostLedgerIntegration:
    """Test cost ledger integration and module-level functions"""

    def test_module_cost_ledger_instance(self):
        """Test that module provides cost_ledger instance"""
        from d0_gateway.cost_ledger import cost_ledger as module_ledger

        assert isinstance(module_ledger, CostLedger)

    def test_cost_ledger_singleton_behavior(self):
        """Test that module always returns same instance"""
        from d0_gateway.cost_ledger import cost_ledger as ledger1
        from d0_gateway.cost_ledger import cost_ledger as ledger2

        assert ledger1 is ledger2

    def test_cost_ledger_initialization(self):
        """Test cost ledger initializes properly"""
        ledger = CostLedger()
        assert ledger.logger is not None
        assert ledger.settings is not None

    @patch("d0_gateway.cost_ledger.get_settings")
    def test_cost_ledger_settings_integration(self, mock_settings):
        """Test cost ledger integrates with settings"""
        mock_settings.return_value.enable_cost_tracking = True
        ledger = CostLedger()
        assert ledger.settings.enable_cost_tracking is True


class TestCostLedgerErrorHandling:
    """Test error handling in cost ledger"""

    def setup_method(self):
        """Setup test fixtures"""
        self.cost_ledger = CostLedger()

    @patch("d0_gateway.cost_ledger.get_db_sync")
    @patch("d0_gateway.cost_ledger.get_settings")
    def test_record_cost_database_error(self, mock_settings, mock_db):
        """Test cost recording handles database errors"""
        mock_settings.return_value.enable_cost_tracking = True
        mock_db.side_effect = Exception("Database connection failed")

        # Should not raise exception
        with pytest.raises(Exception):
            self.cost_ledger.record_cost(provider="test", operation="test", cost_usd=Decimal("1.00"))

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_get_provider_costs_database_error(self, mock_db):
        """Test provider costs handles database errors"""
        mock_db.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            self.cost_ledger.get_provider_costs("test_provider")

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_get_campaign_costs_database_error(self, mock_db):
        """Test campaign costs handles database errors"""
        mock_db.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            self.cost_ledger.get_campaign_costs(123)

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_get_daily_costs_database_error(self, mock_db):
        """Test daily costs handles database errors"""
        mock_db.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            self.cost_ledger.get_daily_costs(start_date=date.today())

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_aggregate_daily_costs_database_error(self, mock_db):
        """Test daily aggregation handles database errors"""
        mock_db.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            self.cost_ledger.aggregate_daily_costs(date.today())

    @patch("d0_gateway.cost_ledger.get_db_sync")
    def test_cleanup_old_records_database_error(self, mock_db):
        """Test cleanup handles database errors"""
        mock_db.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            self.cost_ledger.cleanup_old_records(90)
