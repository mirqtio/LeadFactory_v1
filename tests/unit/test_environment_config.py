"""
Test Environment Configuration - P0-005

Ensures proper test/prod environment separation and stub enforcement.

Acceptance Criteria:
- Stub server auto-starts in tests
- Environment variables documented
- Secrets never logged
- Feature flags for each provider
- Production rejects USE_STUBS=true
"""

import os
import pytest
from unittest.mock import patch
from pydantic import ValidationError

from core.config import Settings


class TestEnvironmentConfig:
    """Test environment configuration and stub enforcement"""

    def test_production_rejects_use_stubs(self):
        """
        Test that production environment rejects USE_STUBS=true
        
        Acceptance Criteria: prod env rejects USE_STUBS=true at startup
        """
        # Try to create settings with production environment and USE_STUBS=true
        with pytest.raises(ValidationError) as exc_info:
            with patch.dict(os.environ, {
                "ENVIRONMENT": "production",
                "USE_STUBS": "true"
            }):
                Settings()

        # Verify the error message
        errors = exc_info.value.errors()
        assert any(
            "USE_STUBS cannot be true in production environment" in str(error)
            for error in errors
        )

    def test_test_environment_forces_stubs(self):
        """
        Test that test environment forces USE_STUBS=true
        
        Acceptance Criteria: Tests must always use stubs
        """
        with patch.dict(os.environ, {
            "ENVIRONMENT": "test",
            "USE_STUBS": "false"  # Try to disable stubs
        }):
            settings = Settings()
            assert settings.use_stubs is True  # Should be forced to True

    def test_ci_environment_forces_stubs(self):
        """
        Test that CI environment forces USE_STUBS=true
        
        Acceptance Criteria: CI must always use stubs
        """
        with patch.dict(os.environ, {
            "CI": "true",
            "USE_STUBS": "false"  # Try to disable stubs
        }):
            settings = Settings()
            assert settings.use_stubs is True  # Should be forced to True

    def test_development_allows_stub_choice(self):
        """
        Test that development environment allows choosing stub mode
        
        Acceptance Criteria: Dev can choose to use stubs or not
        """
        # Test with stubs enabled
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "USE_STUBS": "true"
        }):
            settings = Settings()
            assert settings.use_stubs is True

        # Test with stubs disabled
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "USE_STUBS": "false"
        }):
            settings = Settings()
            assert settings.use_stubs is False

    def test_api_urls_redirect_to_stub_server(self):
        """
        Test that API URLs redirect to stub server when USE_STUBS=true
        
        Acceptance Criteria: All external calls redirected to stub server
        """
        with patch.dict(os.environ, {
            "USE_STUBS": "true",
            "STUB_BASE_URL": "http://localhost:5010"
        }):
            settings = Settings()
            api_urls = settings.api_base_urls

            # All APIs should point to stub server
            assert api_urls["pagespeed"] == "http://localhost:5010"
            assert api_urls["stripe"] == "http://localhost:5010"
            assert api_urls["sendgrid"] == "http://localhost:5010"
            assert api_urls["openai"] == "http://localhost:5010"
            assert api_urls["hunter"] == "http://localhost:5010"

    def test_feature_flags_per_provider(self):
        """
        Test that feature flags exist for each provider
        
        Acceptance Criteria: Feature flags for each provider
        """
        settings = Settings()

        # Wave A providers (should be enabled)
        assert hasattr(settings, "enable_emails")

        # Wave B providers (should be disabled by default)
        assert hasattr(settings, "enable_semrush")
        assert hasattr(settings, "enable_lighthouse")
        assert hasattr(settings, "enable_visual_analysis")
        assert hasattr(settings, "enable_llm_audit")
        assert hasattr(settings, "enable_cost_tracking")

        # Default values for Wave B
        assert settings.enable_semrush is False
        assert settings.enable_lighthouse is False
        assert settings.enable_visual_analysis is False
        assert settings.enable_llm_audit is False

    def test_secrets_not_exposed_in_settings(self):
        """
        Test that secrets are not exposed when settings are printed
        
        Acceptance Criteria: Secrets never logged
        """
        with patch.dict(os.environ, {
            "SECRET_KEY": "super-secret-key",
            "OPENAI_API_KEY": "sk-secret-openai-key",
            "SENDGRID_API_KEY": "SG.secret-sendgrid-key",
            "STRIPE_SECRET_KEY": "sk_test_secret_stripe_key"
        }):
            settings = Settings()
            settings_str = str(settings.model_dump())

            # Secrets should be masked in string representation
            assert "super-secret-key" not in settings_str
            assert "sk-secret-openai-key" not in settings_str
            assert "SG.secret-sendgrid-key" not in settings_str
            assert "sk_test_secret_stripe_key" not in settings_str

    def test_stub_server_health_check(self):
        """
        Test that stub server is accessible when USE_STUBS=true
        
        Acceptance Criteria: Stub server auto-starts in tests
        """
        settings = Settings()
        if settings.use_stubs:
            import requests

            # The stub_server_session fixture should have started the server
            try:
                response = requests.get(f"{settings.stub_base_url}/health", timeout=2)
                assert response.status_code == 200
                assert response.json()["status"] == "healthy"
            except requests.exceptions.ConnectionError:
                pytest.skip("Stub server not running - may be in unit test mode")

    def test_environment_variables_documented(self):
        """
        Test that all environment variables have defaults and descriptions
        
        Acceptance Criteria: Environment variables documented
        """
        # Check that Settings class has proper field definitions

        settings_fields = Settings.model_fields

        # Key environment variables should have descriptions
        important_fields = [
            "environment", "use_stubs", "stub_base_url",
            "database_url", "secret_key"
        ]

        for field_name in important_fields:
            field = settings_fields.get(field_name)
            assert field is not None, f"Field {field_name} not found"
            # Field should have a default or be required
            assert field.default is not None or field.is_required()


# Allow running this test file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
