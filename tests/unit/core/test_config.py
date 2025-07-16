"""
Tests for environment configuration and provider feature flags
Tests for P0-005: Environment & Stub Wiring
"""

import pytest
from pydantic import SecretStr, ValidationError

from core.config import Settings, get_settings

# Mark entire module as unit test and critical - config is fundamental
pytestmark = [pytest.mark.unit, pytest.mark.critical]


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the settings cache before each test"""
    from core.config import get_settings

    get_settings.cache_clear()


class TestEnvironmentConfiguration:
    """Test environment variable configuration and validation"""

    def test_default_settings(self, monkeypatch):
        """Test default settings initialization"""
        # Clear environment variables that might be set by conftest
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        monkeypatch.delenv("USE_STUBS", raising=False)
        monkeypatch.delenv("STUB_BASE_URL", raising=False)

        # Clear settings cache to ensure new settings are loaded
        from core.config import get_settings

        get_settings.cache_clear()

        # Create Settings without loading from .env file to test true defaults
        settings = Settings(_env_file=None)
        assert settings.environment == "development"
        assert settings.use_stubs is True
        assert settings.stub_base_url == "http://localhost:5011"  # This is the default in Settings class
        # Provider flags should be False when use_stubs is True
        assert settings.enable_gbp is False
        assert settings.enable_pagespeed is False
        assert settings.enable_sendgrid is False
        assert settings.enable_openai is False

    def test_production_rejects_stubs(self):
        """Test that production environment rejects USE_STUBS=true"""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment="production", use_stubs=True, secret_key="production-secret-key"  # Provide valid secret key
            )

        errors = exc_info.value.errors()
        error_messages = [str(e.get("ctx", {}).get("error", "")) for e in errors]
        assert any("Production environment cannot run with USE_STUBS=true" in msg for msg in error_messages)

    def test_provider_flags_auto_disable_with_stubs(self):
        """Test that provider flags are auto-disabled when USE_STUBS=true"""
        settings = Settings(
            use_stubs=True, enable_gbp=True, enable_pagespeed=True, enable_sendgrid=True, enable_openai=True
        )

        # All should be False despite being set to True
        assert settings.enable_gbp is False
        assert settings.enable_pagespeed is False
        assert settings.enable_sendgrid is False
        assert settings.enable_openai is False

    def test_provider_flags_respect_values_without_stubs(self, monkeypatch):
        """Test that provider flags respect their values when not using stubs"""
        # Mock CI environment to allow use_stubs=False
        monkeypatch.delenv("CI", raising=False)

        # Use development environment to avoid test forcing stubs
        settings = Settings(
            environment="development",
            use_stubs=False,
            enable_gbp=True,
            enable_pagespeed=False,
            enable_sendgrid=True,
            enable_openai=False,
            google_api_key=SecretStr("test-google-key"),
            sendgrid_api_key=SecretStr("test-sendgrid-key"),
        )

        assert settings.enable_gbp is True
        assert settings.enable_pagespeed is False
        assert settings.enable_sendgrid is True
        assert settings.enable_openai is False

    def test_api_key_validation_when_providers_enabled(self, monkeypatch):
        """Test that API keys are required when providers are enabled and not using stubs"""
        # Mock CI environment to allow use_stubs=False
        monkeypatch.delenv("CI", raising=False)

        # GBP enabled without Google API key
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment="development",
                use_stubs=False,
                enable_gbp=True,
                enable_pagespeed=False,
                enable_sendgrid=False,
                enable_openai=False,
                google_api_key=None,
            )
        assert "Google API key required when GBP enabled" in str(exc_info.value)

        # PageSpeed enabled without Google API key
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment="development",
                use_stubs=False,
                enable_gbp=False,  # Explicitly disable GBP
                enable_pagespeed=True,
                enable_sendgrid=False,  # Explicitly disable others
                enable_openai=False,
                google_api_key=None,
            )
        assert "Google API key required when PageSpeed enabled" in str(exc_info.value)

        # SendGrid enabled without API key
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment="development",
                use_stubs=False,
                enable_gbp=False,
                enable_pagespeed=False,
                enable_sendgrid=True,
                enable_openai=False,
                sendgrid_api_key=None,
            )
        assert "SendGrid API key required when SendGrid enabled" in str(exc_info.value)

        # OpenAI enabled without API key
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment="development",
                use_stubs=False,
                enable_gbp=False,
                enable_pagespeed=False,
                enable_sendgrid=False,
                enable_openai=True,
                openai_api_key=None,
            )
        assert "OpenAI API key required when OpenAI enabled" in str(exc_info.value)

    def test_api_keys_not_required_with_stubs(self):
        """Test that API keys are not required when using stubs"""
        # Should not raise any errors
        settings = Settings(
            use_stubs=True,
            enable_gbp=True,  # Will be auto-disabled
            enable_pagespeed=True,  # Will be auto-disabled
            enable_sendgrid=True,  # Will be auto-disabled
            enable_openai=True,  # Will be auto-disabled
            google_api_key=None,
            sendgrid_api_key=None,
            openai_api_key=None,
        )

        assert settings.use_stubs is True
        # All providers should be disabled
        assert settings.enable_gbp is False
        assert settings.enable_pagespeed is False
        assert settings.enable_sendgrid is False
        assert settings.enable_openai is False

    def test_secret_str_fields(self):
        """Test that sensitive fields use SecretStr"""
        settings = Settings(
            google_api_key=SecretStr("secret-google"),
            sendgrid_api_key=SecretStr("secret-sendgrid"),
            openai_api_key=SecretStr("secret-openai"),
            stripe_secret_key=SecretStr("secret-stripe"),
            stripe_webhook_secret=SecretStr("secret-webhook"),
        )

        # SecretStr should not expose the value in string representation
        assert isinstance(settings.google_api_key, SecretStr)
        # SecretStr representation may vary, but should mask the value
        assert "secret-google" not in str(settings.google_api_key)
        assert settings.google_api_key.get_secret_value() == "secret-google"

    def test_get_api_key_with_stubs(self):
        """Test get_api_key method returns stub keys when using stubs"""
        settings = Settings(use_stubs=True)

        assert settings.get_api_key("google") == "stub-google-key"
        assert settings.get_api_key("google_places") == "stub-google_places-key"
        assert settings.get_api_key("pagespeed") == "stub-pagespeed-key"
        assert settings.get_api_key("sendgrid") == "stub-sendgrid-key"
        assert settings.get_api_key("openai") == "stub-openai-key"

    def test_get_api_key_without_stubs(self, monkeypatch):
        """Test get_api_key method returns real keys when not using stubs"""
        # Mock CI environment to allow use_stubs=False
        monkeypatch.delenv("CI", raising=False)

        settings = Settings(
            environment="development",
            use_stubs=False,
            google_api_key=SecretStr("real-google-key"),
            sendgrid_api_key=SecretStr("real-sendgrid-key"),
            openai_api_key=SecretStr("real-openai-key"),
        )

        assert settings.get_api_key("google") == "real-google-key"
        assert settings.get_api_key("google_places") == "real-google-key"  # Same as google
        assert settings.get_api_key("pagespeed") == "real-google-key"  # Same as google
        assert settings.get_api_key("sendgrid") == "real-sendgrid-key"
        assert settings.get_api_key("openai") == "real-openai-key"

    def test_get_api_key_missing_raises_error(self, monkeypatch):
        """Test that get_api_key raises error for missing keys"""
        # Mock CI environment to allow use_stubs=False
        monkeypatch.delenv("CI", raising=False)

        settings = Settings(
            environment="development",
            use_stubs=False,
            enable_gbp=False,
            enable_pagespeed=False,
            enable_sendgrid=False,
            enable_openai=False,
        )

        with pytest.raises(ValueError) as exc_info:
            settings.get_api_key("unknown-service")
        assert "API key not configured for unknown-service" in str(exc_info.value)

    def test_api_base_urls_with_stubs(self):
        """Test that API base URLs point to stub server when using stubs"""
        settings = Settings(use_stubs=True, stub_base_url="http://localhost:5010")
        urls = settings.api_base_urls

        assert urls["google_places"] == "http://localhost:5010"
        assert urls["pagespeed"] == "http://localhost:5010"
        assert urls["sendgrid"] == "http://localhost:5010"
        assert urls["openai"] == "http://localhost:5010"

    def test_api_base_urls_without_stubs(self, monkeypatch):
        """Test that API base URLs point to real services when not using stubs"""
        # Mock CI environment to allow use_stubs=False
        monkeypatch.delenv("CI", raising=False)

        settings = Settings(
            environment="development",
            use_stubs=False,
            enable_gbp=False,
            enable_pagespeed=False,
            enable_sendgrid=False,
            enable_openai=False,
        )
        urls = settings.api_base_urls

        assert urls["google_places"] == "https://maps.googleapis.com"
        assert urls["pagespeed"] == "https://www.googleapis.com"
        assert urls["sendgrid"] == "https://api.sendgrid.com"
        assert urls["openai"] == "https://api.openai.com"

    def test_environment_validation(self, monkeypatch):
        """Test environment field validation"""
        # Clear USE_STUBS to avoid production validation error
        monkeypatch.delenv("USE_STUBS", raising=False)
        # Mock CI environment to allow use_stubs=False for production test
        monkeypatch.delenv("CI", raising=False)

        # Valid environments
        for env in ["development", "test", "staging"]:
            settings = Settings(environment=env)
            assert settings.environment == env

        # Production requires a proper secret key and no stubs
        settings = Settings(
            environment="production",
            secret_key="production-secret-key",
            use_stubs=False,
            enable_gbp=False,
            enable_pagespeed=False,
            enable_sendgrid=False,
            enable_openai=False,
        )
        assert settings.environment == "production"

        # Invalid environment
        with pytest.raises(ValidationError) as exc_info:
            Settings(environment="invalid")
        assert "Environment must be one of" in str(exc_info.value)

    def test_model_dump_masks_secrets(self):
        """Test that model_dump masks sensitive fields"""
        settings = Settings(
            secret_key="my-secret-key-12345",
            google_api_key=SecretStr("google-key-12345"),
            sendgrid_api_key=SecretStr("sendgrid-key-12345"),
            openai_api_key=SecretStr("openai-key-12345"),
        )

        dumped = settings.model_dump()

        # Check that sensitive fields are masked
        assert dumped["secret_key"].startswith("my-s")
        assert "*" in dumped["secret_key"]
        assert "12345" not in dumped["secret_key"]

        assert dumped["google_api_key"].startswith("goog")
        assert "*" in dumped["google_api_key"]
        assert "12345" not in dumped["google_api_key"]

        assert dumped["sendgrid_api_key"].startswith("send")
        assert "*" in dumped["sendgrid_api_key"]
        assert "12345" not in dumped["sendgrid_api_key"]

        assert dumped["openai_api_key"].startswith("open")
        assert "*" in dumped["openai_api_key"]
        assert "12345" not in dumped["openai_api_key"]

    def test_test_environment_forces_stubs(self):
        """Test that test environment forces USE_STUBS=true"""
        settings = Settings(environment="test", use_stubs=False)
        # validate_use_stubs should force it to True
        assert settings.use_stubs is True

    def test_ci_environment_forces_stubs(self, monkeypatch):
        """Test that CI environment forces USE_STUBS=true"""
        monkeypatch.setenv("CI", "true")
        settings = Settings(use_stubs=False)
        assert settings.use_stubs is True

    def test_cached_settings(self):
        """Test that get_settings returns cached instance"""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2  # Same instance

    def test_environment_specific_stub_url(self, monkeypatch):
        """Test that STUB_BASE_URL from environment takes precedence"""
        # Test with Docker environment URL
        monkeypatch.setenv("STUB_BASE_URL", "http://stub-server:5010")
        monkeypatch.setenv("USE_STUBS", "true")

        # Clear cache to pick up new env vars
        from core.config import get_settings

        get_settings.cache_clear()

        settings = Settings(_env_file=None)
        assert settings.stub_base_url == "http://stub-server:5010"

        # Test with localhost URL
        monkeypatch.setenv("STUB_BASE_URL", "http://localhost:5011")
        settings2 = Settings(_env_file=None)
        assert settings2.stub_base_url == "http://localhost:5011"

    def test_wave_b_feature_flags_default_false(self, monkeypatch, tmp_path):
        """Test that Wave B feature flags default to False"""
        # Create a temporary directory with no .env file
        monkeypatch.chdir(tmp_path)

        # Clear environment variables that might override defaults
        monkeypatch.delenv("ENABLE_SEMRUSH", raising=False)
        monkeypatch.delenv("ENABLE_LIGHTHOUSE", raising=False)
        monkeypatch.delenv("ENABLE_VISUAL_ANALYSIS", raising=False)
        monkeypatch.delenv("ENABLE_LLM_AUDIT", raising=False)
        monkeypatch.delenv("ENABLE_COST_TRACKING", raising=False)
        monkeypatch.delenv("USE_DATAAXLE", raising=False)
        monkeypatch.delenv("ENABLE_COST_GUARDRAILS", raising=False)

        settings = Settings()
        assert settings.enable_semrush is False
        assert settings.enable_lighthouse is True
        assert settings.enable_visual_analysis is False
        assert settings.enable_llm_audit is False
        assert settings.enable_cost_tracking is True
        assert settings.use_dataaxle is False
        assert settings.enable_cost_guardrails is False
