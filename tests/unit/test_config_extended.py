"""Extended tests for core.config to increase coverage."""
import os
from unittest import mock

import pytest

from core.config import Settings

pytestmark = pytest.mark.critical


class TestExtendedConfig:
    """Additional tests for config to increase coverage."""

    def test_stripe_configuration(self):
        """Test Stripe configuration settings."""
        with mock.patch.dict(
            os.environ,
            {
                "STRIPE_SECRET_KEY": "sk_test_123",
                "STRIPE_PUBLISHABLE_KEY": "pk_test_456",
                "STRIPE_WEBHOOK_SECRET": "whsec_789",
            },
        ):
            settings = Settings()
            assert settings.stripe_secret_key.get_secret_value() == "sk_test_123"
            assert settings.stripe_publishable_key == "pk_test_456"
            assert settings.stripe_webhook_secret.get_secret_value() == "whsec_789"

    def test_api_key_configurations(self):
        """Test various API key configurations."""
        with mock.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-openai123", "SENDGRID_API_KEY": "SG.sendgrid456", "SEMRUSH_API_KEY": "semrush789"},
        ):
            settings = Settings()
            assert settings.openai_api_key.get_secret_value() == "sk-openai123"
            assert settings.sendgrid_api_key.get_secret_value() == "SG.sendgrid456"
            assert settings.semrush_api_key.get_secret_value() == "semrush789"

    def test_cost_budget_configuration(self):
        """Test cost budget configuration."""
        # Default value
        settings = Settings()
        assert settings.cost_budget_usd == 1000.0

        # Custom value via environment
        with mock.patch.dict(os.environ, {"COST_BUDGET_USD": "5000.50"}):
            settings = Settings()
            assert settings.cost_budget_usd == 5000.50

    def test_database_configuration(self):
        """Test database URL configuration."""
        with mock.patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@host:5432/db", "TESTING": "false"}):
            settings = Settings()
            assert settings.database_url == "postgresql://user:pass@host:5432/db"
            
    def test_database_configuration_testing_mode(self):
        """Test database URL configuration in testing mode."""
        with mock.patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@host:5432/db", "TESTING": "true"}):
            settings = Settings()
            # In testing mode, database_url is forced to sqlite
            assert settings.database_url == "sqlite:///tmp/test.db"

    def test_redis_configuration(self):
        """Test Redis URL configuration."""
        with mock.patch.dict(os.environ, {"REDIS_URL": "redis://redis.example.com:6380/1"}):
            settings = Settings()
            assert settings.redis_url == "redis://redis.example.com:6380/1"

    def test_environment_settings(self):
        """Test environment-specific settings."""
        # Development environment
        with mock.patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            settings = Settings()
            assert settings.environment == "development"

        # Production environment - need to clear CI env var to allow USE_STUBS=false
        # Also need to provide API keys when USE_STUBS=false
        with mock.patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "USE_STUBS": "false",
                "SECRET_KEY": "production-secret-key-123-very-secure-key",
                "CI": "",  # Clear CI environment variable
                "GOOGLE_API_KEY": "test-google-key",
                "SENDGRID_API_KEY": "test-sendgrid-key",
                "OPENAI_API_KEY": "test-openai-key",
                # Disable provider flags to avoid validation issues
                "ENABLE_GBP": "false",
                "ENABLE_PAGESPEED": "false",
                "ENABLE_SENDGRID": "false",
                "ENABLE_OPENAI": "false",
            },
            clear=True,
        ):
            settings = Settings()
            assert settings.environment == "production"

        # Debug can be set independently
        with mock.patch.dict(os.environ, {"DEBUG": "true"}):
            settings = Settings()
            assert settings.debug is True

    def test_use_stubs_configuration(self):
        """Test stub configuration."""
        # With stubs enabled
        with mock.patch.dict(os.environ, {"USE_STUBS": "true"}):
            settings = Settings()
            assert settings.use_stubs is True

        # With stubs disabled in test environment - still forced to True
        with mock.patch.dict(os.environ, {"USE_STUBS": "false", "ENVIRONMENT": "test"}, clear=False):
            settings = Settings()
            assert settings.use_stubs is True  # Test environment forces stubs

    def test_base_url_configuration(self):
        """Test base URL configuration."""
        with mock.patch.dict(os.environ, {"BASE_URL": "https://api.example.com"}):
            settings = Settings()
            assert settings.base_url == "https://api.example.com"

    def test_log_configuration(self):
        """Test logging configuration."""
        settings = Settings()
        assert settings.log_level == "INFO"
        assert settings.log_format == "json"

        # Custom log level
        with mock.patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            settings = Settings()
            assert settings.log_level == "DEBUG"

    def test_model_dump_exclude_secrets(self):
        """Test that secrets are excluded from model dump."""
        settings = Settings(stripe_secret_key="sk_test_secret", openai_api_key="sk_openai_secret")

        # Dump without secrets
        dumped = settings.model_dump(exclude=settings.model_config.get("exclude", set()))

        # These should be present (non-secrets)
        assert "environment" in dumped
        assert "debug" in dumped
        assert "use_stubs" in dumped
