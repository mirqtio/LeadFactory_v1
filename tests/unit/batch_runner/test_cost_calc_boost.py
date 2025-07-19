"""
Simple cost calculator tests to boost coverage
Focus on basic functionality and initialization
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from batch_runner.cost_calculator import CostRates


class TestCostRatesBasic:
    """Basic cost rates functionality"""

    def test_cost_rates_initialization_default(self):
        """Test default initialization"""
        rates = CostRates()
        assert rates.config_path == "config/batch_costs.json"
        assert rates._rates_cache is None
        assert rates._cache_timestamp is None
        assert rates._cache_ttl == 300

    def test_cost_rates_initialization_custom_path(self):
        """Test initialization with custom path"""
        custom_path = "/custom/path/costs.json"
        rates = CostRates(config_path=custom_path)
        assert rates.config_path == custom_path

    def test_get_default_rates(self):
        """Test default rates structure"""
        rates = CostRates()
        default_rates = rates._get_default_rates()

        assert isinstance(default_rates, dict)
        assert "report_generation" in default_rates
        assert "providers" in default_rates
        assert "discounts" in default_rates

        # Check report generation structure
        report_gen = default_rates["report_generation"]
        assert "base_cost" in report_gen
        assert "complexity_multiplier" in report_gen
        assert isinstance(report_gen["base_cost"], float)

        # Check providers structure
        providers = default_rates["providers"]
        assert "dataaxle" in providers
        assert "hunter" in providers
        assert "openai" in providers

        # Verify provider structure
        for provider_name, provider_config in providers.items():
            assert isinstance(provider_config, dict)
            # Each provider should have some cost parameters
            assert len(provider_config) > 0

    def test_load_rates_from_file_success(self):
        """Test successful loading from file"""
        # Create a temporary config file
        test_config = {
            "report_generation": {"base_cost": 0.10},
            "providers": {"test_provider": {"per_lead": 0.20}},
            "discounts": {"volume_tiers": {}},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
            json.dump(test_config, temp_file)
            temp_path = temp_file.name

        try:
            rates = CostRates(config_path=temp_path)
            loaded_rates = rates._load_rates_from_file()

            assert loaded_rates == test_config
            assert loaded_rates["report_generation"]["base_cost"] == 0.10
            assert "test_provider" in loaded_rates["providers"]
        finally:
            Path(temp_path).unlink()

    def test_load_rates_from_file_not_found(self):
        """Test loading from non-existent file falls back to defaults"""
        rates = CostRates(config_path="/nonexistent/path/costs.json")
        loaded_rates = rates._load_rates_from_file()

        # Should return default rates
        default_rates = rates._get_default_rates()
        assert loaded_rates == default_rates

    @patch("batch_runner.cost_calculator.logger")
    def test_load_rates_from_file_json_error(self, mock_logger):
        """Test handling of invalid JSON file"""
        # Create a temporary file with invalid JSON
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
            temp_file.write("invalid json content {")
            temp_path = temp_file.name

        try:
            rates = CostRates(config_path=temp_path)
            loaded_rates = rates._load_rates_from_file()

            # Should fall back to defaults and log warning
            default_rates = rates._get_default_rates()
            assert loaded_rates == default_rates
            mock_logger.warning.assert_called_once()
        finally:
            Path(temp_path).unlink()

    def test_rates_cache_attributes(self):
        """Test cache-related attributes"""
        rates = CostRates()

        # Initial state
        assert rates._rates_cache is None
        assert rates._cache_timestamp is None
        assert rates._cache_ttl == 300

        # Verify these are mutable
        rates._rates_cache = {"test": "data"}
        rates._cache_timestamp = 123456

        assert rates._rates_cache == {"test": "data"}
        assert rates._cache_timestamp == 123456


class TestCostRatesDefaults:
    """Test default rate values and structure"""

    def test_default_complexity_multipliers(self):
        """Test complexity multiplier values"""
        rates = CostRates()
        defaults = rates._get_default_rates()

        multipliers = defaults["report_generation"]["complexity_multiplier"]
        assert multipliers["simple"] == 1.0
        assert multipliers["standard"] == 1.5
        assert multipliers["comprehensive"] == 2.0

    def test_default_provider_rates(self):
        """Test default provider rates"""
        rates = CostRates()
        defaults = rates._get_default_rates()

        providers = defaults["providers"]

        # DataAxle
        assert providers["dataaxle"]["per_lead"] == 0.15
        assert providers["dataaxle"]["confidence_threshold"] == 0.75

        # Hunter
        assert providers["hunter"]["per_lead"] == 0.10
        assert providers["hunter"]["confidence_threshold"] == 0.85

        # OpenAI
        assert providers["openai"]["per_assessment"] == 0.25
        assert providers["openai"]["per_1k_tokens"] == 0.002

    def test_default_base_costs(self):
        """Test default base cost values"""
        rates = CostRates()
        defaults = rates._get_default_rates()

        assert defaults["report_generation"]["base_cost"] == 0.05
        assert isinstance(defaults["report_generation"]["base_cost"], float)
        assert defaults["report_generation"]["base_cost"] > 0

    def test_discounts_structure_exists(self):
        """Test that discounts structure exists"""
        rates = CostRates()
        defaults = rates._get_default_rates()

        assert "discounts" in defaults
        assert "volume_tiers" in defaults["discounts"]
        assert isinstance(defaults["discounts"]["volume_tiers"], dict)
