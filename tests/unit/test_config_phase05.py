"""
Tests for Phase 0.5 configuration updates
"""
import os
import pytest
from pydantic import ValidationError

from core.config import Settings, get_settings

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)


class TestPhase05Config:
    """Test Phase 0.5 configuration additions"""

    def test_data_axle_config_from_env(self, monkeypatch):
        """Test Data Axle configuration from environment"""
        monkeypatch.setenv("DATA_AXLE_API_KEY", "test-data-axle-key")
        monkeypatch.setenv("DATA_AXLE_BASE_URL", "https://api.test.com")
        monkeypatch.setenv("DATA_AXLE_RATE_LIMIT_PER_MIN", "300")

        settings = Settings()
        assert settings.data_axle_api_key == "test-data-axle-key"
        assert settings.data_axle_base_url == "https://api.test.com"
        assert settings.data_axle_rate_limit_per_min == 300

    def test_hunter_config_from_env(self, monkeypatch):
        """Test Hunter configuration from environment"""
        monkeypatch.setenv("HUNTER_API_KEY", "test-hunter-key")
        monkeypatch.setenv("HUNTER_RATE_LIMIT_PER_MIN", "25")

        settings = Settings()
        assert settings.hunter_api_key == "test-hunter-key"
        assert settings.hunter_rate_limit_per_min == 25

    def test_feature_flags_from_env(self, monkeypatch):
        """Test Phase 0.5 feature flags from environment"""
        monkeypatch.setenv("PROVIDERS_DATA_AXLE_ENABLED", "false")
        monkeypatch.setenv("PROVIDERS_HUNTER_ENABLED", "true")
        monkeypatch.setenv("LEAD_FILTER_MIN_SCORE", "0.5")
        monkeypatch.setenv("ASSESSMENT_OPTIONAL", "false")

        settings = Settings()
        assert settings.providers_data_axle_enabled is False
        assert settings.providers_hunter_enabled is True
        assert settings.lead_filter_min_score == 0.5
        assert settings.assessment_optional is False

    def test_cost_control_from_env(self, monkeypatch):
        """Test cost control configuration from environment"""
        monkeypatch.setenv("COST_BUDGET_USD", "5000.50")

        settings = Settings()
        assert settings.cost_budget_usd == 5000.50

    def test_default_values(self, monkeypatch):
        """Test default values for Phase 0.5 config"""
        # Don't read .env file
        monkeypatch.setattr("core.config.Settings.model_config", {"env_file": None})
        settings = Settings()

        # Data Axle defaults
        assert settings.data_axle_api_key is None
        assert settings.data_axle_base_url == "https://api.data-axle.com/v2"
        assert settings.data_axle_rate_limit_per_min == 200

        # Hunter defaults
        assert settings.hunter_api_key is None
        assert settings.hunter_rate_limit_per_min == 30

        # Feature flag defaults
        assert settings.providers_data_axle_enabled is True
        assert settings.providers_hunter_enabled is False
        assert settings.lead_filter_min_score == 0.0
        assert settings.assessment_optional is True

        # Cost control default
        assert settings.cost_budget_usd == 1000.0

    def test_api_base_urls_include_new_providers(self):
        """Test that API base URLs include new providers"""
        settings = Settings(use_stubs=False)
        urls = settings.api_base_urls

        assert "dataaxle" in urls
        assert urls["dataaxle"] == "https://api.data-axle.com/v2"
        assert "hunter" in urls
        assert urls["hunter"] == "https://api.hunter.io"

    def test_api_base_urls_stub_mode(self):
        """Test that stub mode includes new providers"""
        settings = Settings(use_stubs=True, stub_base_url="http://test:5000")
        urls = settings.api_base_urls

        assert urls["dataaxle"] == "http://test:5000"
        assert urls["hunter"] == "http://test:5000"

    def test_get_api_key_new_providers(self):
        """Test get_api_key method with new providers"""
        settings = Settings(
            use_stubs=False,
            data_axle_api_key="test-da-key",
            hunter_api_key="test-h-key",
        )

        assert settings.get_api_key("dataaxle") == "test-da-key"
        assert settings.get_api_key("hunter") == "test-h-key"

    def test_get_api_key_missing_new_providers(self):
        """Test get_api_key raises error when keys not configured"""
        settings = Settings(use_stubs=False)

        with pytest.raises(ValueError, match="API key not configured for dataaxle"):
            settings.get_api_key("dataaxle")

        with pytest.raises(ValueError, match="API key not configured for hunter"):
            settings.get_api_key("hunter")

    def test_get_api_key_stub_mode_new_providers(self):
        """Test get_api_key in stub mode for new providers"""
        settings = Settings(use_stubs=True)

        assert settings.get_api_key("dataaxle") == "stub-dataaxle-key"
        assert settings.get_api_key("hunter") == "stub-hunter-key"

    def test_boolean_env_parsing(self, monkeypatch):
        """Test boolean environment variable parsing"""
        # Test various boolean representations
        monkeypatch.setenv("PROVIDERS_DATA_AXLE_ENABLED", "True")
        assert Settings().providers_data_axle_enabled is True

        monkeypatch.setenv("PROVIDERS_DATA_AXLE_ENABLED", "true")
        assert Settings().providers_data_axle_enabled is True

        monkeypatch.setenv("PROVIDERS_DATA_AXLE_ENABLED", "1")
        assert Settings().providers_data_axle_enabled is True

        monkeypatch.setenv("PROVIDERS_DATA_AXLE_ENABLED", "False")
        assert Settings().providers_data_axle_enabled is False

        monkeypatch.setenv("PROVIDERS_DATA_AXLE_ENABLED", "false")
        assert Settings().providers_data_axle_enabled is False

        monkeypatch.setenv("PROVIDERS_DATA_AXLE_ENABLED", "0")
        assert Settings().providers_data_axle_enabled is False

    def test_numeric_env_parsing(self, monkeypatch):
        """Test numeric environment variable parsing"""
        monkeypatch.setenv("LEAD_FILTER_MIN_SCORE", "0.75")
        assert Settings().lead_filter_min_score == 0.75

        monkeypatch.setenv("COST_BUDGET_USD", "2500")
        assert Settings().cost_budget_usd == 2500.0

        monkeypatch.setenv("DATA_AXLE_RATE_LIMIT_PER_MIN", "500")
        assert Settings().data_axle_rate_limit_per_min == 500
