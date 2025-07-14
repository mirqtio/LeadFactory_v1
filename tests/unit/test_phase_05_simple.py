"""
Simplified tests for Phase 0.5 providers
Task TS-10: Basic tests for core functionality
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from core.exceptions import ValidationError
from d0_gateway.providers.dataaxle import DataAxleClient
from d0_gateway.providers.hunter import HunterClient

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


class TestDataAxleClientSimple:
    """Simple tests for Data Axle client"""

    @patch("d0_gateway.base.get_settings")
    def test_client_creation(self, mock_settings):
        """Test client can be created"""
        # Mock settings to disable stub mode
        mock_settings.return_value.use_stubs = False

        client = DataAxleClient(api_key="test-key")
        assert client.provider == "dataaxle"
        assert client.api_key == "test-key"

    def test_get_cost(self):
        """Test cost calculation"""
        client = DataAxleClient(api_key="test-key")

        # Match business costs $0.05
        cost = client.calculate_cost("match_business")
        assert cost == Decimal("0.05")

        # Unknown operation is free
        cost = client.calculate_cost("unknown")
        assert cost == Decimal("0.00")

    def test_missing_business_name_validation(self):
        """Test validation for missing business name"""
        client = DataAxleClient(api_key="test-key")

        with pytest.raises(ValidationError):
            import asyncio

            asyncio.run(client.match_business({}))

    @pytest.mark.asyncio
    @patch("d0_gateway.providers.dataaxle.DataAxleClient._post")
    async def test_match_business_no_results(self, mock_post):
        """Test when no match is found"""
        # Mock empty response
        mock_post.return_value = {"businesses": [], "totalRecords": 0}

        client = DataAxleClient(api_key="test-key")
        result = await client.match_business({"name": "Test Business"})

        assert result is None


class TestHunterClientSimple:
    """Simple tests for Hunter client"""

    @patch("d0_gateway.base.get_settings")
    def test_client_creation(self, mock_settings):
        """Test client can be created"""
        # Mock settings to disable stub mode
        mock_settings.return_value.use_stubs = False

        client = HunterClient(api_key="test-key")
        assert client.provider == "hunter"
        assert client.api_key == "test-key"

    def test_get_cost(self):
        """Test cost calculation"""
        client = HunterClient(api_key="test-key")

        # Find email costs $0.01
        cost = client.calculate_cost("find_email")
        assert cost == Decimal("0.01")

        # Unknown operation is free
        cost = client.calculate_cost("unknown")
        assert cost == Decimal("0.00")

    def test_missing_domain_and_company_validation(self):
        """Test validation for missing required fields"""
        client = HunterClient(api_key="test-key")

        with pytest.raises(ValidationError):
            import asyncio

            asyncio.run(client.find_email({}))

    @pytest.mark.asyncio
    @patch("d0_gateway.providers.hunter.HunterClient._get")
    async def test_find_email_not_found(self, mock_get):
        """Test when no email is found"""
        # Mock response with no email
        mock_get.return_value = {"data": {"email": None}}

        client = HunterClient(api_key="test-key")
        result = await client.find_email({"domain": "example.com"})

        assert result is None


class TestCostEmission:
    """Test cost tracking functionality"""

    @patch("database.session.get_db_sync")
    @patch("d0_gateway.base.get_settings")
    def test_emit_cost(self, mock_settings, mock_get_db):
        """Test cost emission works"""
        # Mock settings to disable stub mode
        mock_settings.return_value.use_stubs = False

        # Mock database session
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db

        # Create client and emit cost
        client = DataAxleClient(api_key="test-key")
        client.emit_cost(lead_id=123, cost_usd=0.05, operation="match_business")

        # Verify database add was called
        mock_db.add.assert_called_once()
