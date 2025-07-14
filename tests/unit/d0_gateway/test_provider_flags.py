"""
Tests for provider feature flags
Ensures providers respect ENABLE_* flags from configuration
"""
import pytest
from unittest.mock import patch, MagicMock
from core.config import Settings
from d0_gateway.providers.google_places import GooglePlacesClient
from d0_gateway.providers.pagespeed import PageSpeedClient
from d0_gateway.providers.sendgrid import SendGridClient
from d0_gateway.providers.openai import OpenAIClient


class TestProviderFeatureFlags:
    """Test that providers respect their feature flags"""

    def test_google_places_respects_enable_flag(self):
        """Test that GooglePlacesClient raises error when ENABLE_GBP=false"""
        with patch('core.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                enable_gbp=False,
                use_stubs=True,
                stub_base_url="http://localhost:5010"
            )
            
            with pytest.raises(RuntimeError) as exc_info:
                GooglePlacesClient()
            
            assert "GBP client initialized but ENABLE_GBP=false" in str(exc_info.value)

    def test_google_places_initializes_with_flag_enabled(self):
        """Test that GooglePlacesClient initializes correctly when ENABLE_GBP=true"""
        with patch('core.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                enable_gbp=True,
                use_stubs=True,
                stub_base_url="http://localhost:5010",
                get_api_key=MagicMock(return_value="stub-google-places-key")
            )
            
            # Mock the parent class initialization
            with patch('d0_gateway.providers.google_places.BaseAPIClient.__init__'):
                client = GooglePlacesClient()
                assert client._base_url == "http://localhost:5010/maps/api/place"

    def test_google_places_uses_real_url_without_stubs(self):
        """Test that GooglePlacesClient uses real URL when not using stubs"""
        with patch('core.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                enable_gbp=True,
                use_stubs=False,
                get_api_key=MagicMock(return_value="real-api-key")
            )
            
            # Mock the parent class initialization
            with patch('d0_gateway.providers.google_places.BaseAPIClient.__init__'):
                client = GooglePlacesClient()
                assert client._base_url == "https://maps.googleapis.com/maps/api/place"

    def test_pagespeed_respects_enable_flag(self):
        """Test that PageSpeedClient raises error when ENABLE_PAGESPEED=false"""
        with patch('core.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                enable_pagespeed=False,
                use_stubs=True
            )
            
            with pytest.raises(RuntimeError) as exc_info:
                PageSpeedClient()
            
            assert "PageSpeed client initialized but ENABLE_PAGESPEED=false" in str(exc_info.value)

    def test_pagespeed_initializes_with_flag_enabled(self):
        """Test that PageSpeedClient initializes correctly when ENABLE_PAGESPEED=true"""
        with patch('core.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                enable_pagespeed=True,
                use_stubs=True,
                stub_base_url="http://localhost:5010",
                get_api_key=MagicMock(return_value="stub-pagespeed-key")
            )
            
            # Mock the parent class initialization
            with patch('d0_gateway.providers.pagespeed.BaseAPIClient.__init__'):
                client = PageSpeedClient()
                # Just verify it initializes without error
                assert client is not None

    def test_sendgrid_respects_enable_flag(self):
        """Test that SendGridClient raises error when ENABLE_SENDGRID=false"""
        with patch('core.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                enable_sendgrid=False,
                use_stubs=True
            )
            
            with pytest.raises(RuntimeError) as exc_info:
                SendGridClient()
            
            assert "SendGrid client initialized but ENABLE_SENDGRID=false" in str(exc_info.value)

    def test_sendgrid_initializes_with_flag_enabled(self):
        """Test that SendGridClient initializes correctly when ENABLE_SENDGRID=true"""
        with patch('core.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                enable_sendgrid=True,
                use_stubs=True,
                stub_base_url="http://localhost:5010",
                get_api_key=MagicMock(return_value="stub-sendgrid-key")
            )
            
            # Mock the parent class initialization
            with patch('d0_gateway.providers.sendgrid.BaseAPIClient.__init__'):
                client = SendGridClient()
                assert client is not None

    def test_openai_respects_enable_flag(self):
        """Test that OpenAIClient raises error when ENABLE_OPENAI=false"""
        with patch('core.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                enable_openai=False,
                use_stubs=True
            )
            
            with pytest.raises(RuntimeError) as exc_info:
                OpenAIClient()
            
            assert "OpenAI client initialized but ENABLE_OPENAI=false" in str(exc_info.value)

    def test_openai_initializes_with_flag_enabled(self):
        """Test that OpenAIClient initializes correctly when ENABLE_OPENAI=true"""
        with patch('core.config.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                enable_openai=True,
                use_stubs=True,
                stub_base_url="http://localhost:5010",
                get_api_key=MagicMock(return_value="stub-openai-key")
            )
            
            # Mock the parent class initialization
            with patch('d0_gateway.providers.openai.BaseAPIClient.__init__'):
                client = OpenAIClient()
                assert client is not None

    def test_all_providers_disabled_scenario(self):
        """Test scenario where all providers are disabled"""
        settings = Settings(
            use_stubs=True,  # This auto-disables all providers
            enable_gbp=True,
            enable_pagespeed=True,
            enable_sendgrid=True,
            enable_openai=True
        )
        
        # All should be False
        assert settings.enable_gbp is False
        assert settings.enable_pagespeed is False
        assert settings.enable_sendgrid is False
        assert settings.enable_openai is False

    def test_selective_provider_enabling(self):
        """Test enabling only specific providers"""
        from pydantic import SecretStr
        settings = Settings(
            environment="development",
            use_stubs=False,
            enable_gbp=True,
            enable_pagespeed=False,
            enable_sendgrid=True,
            enable_openai=False,
            google_api_key=SecretStr("test-key"),
            sendgrid_api_key=SecretStr("test-key")
        )
        
        assert settings.enable_gbp is True
        assert settings.enable_pagespeed is False
        assert settings.enable_sendgrid is True
        assert settings.enable_openai is False

    @pytest.mark.parametrize("provider,flag_name,client_class,error_msg", [
        ("google_places", "enable_gbp", GooglePlacesClient, "GBP client initialized but ENABLE_GBP=false"),
        ("pagespeed", "enable_pagespeed", PageSpeedClient, "PageSpeed client initialized but ENABLE_PAGESPEED=false"),
        ("sendgrid", "enable_sendgrid", SendGridClient, "SendGrid client initialized but ENABLE_SENDGRID=false"),
        ("openai", "enable_openai", OpenAIClient, "OpenAI client initialized but ENABLE_OPENAI=false"),
    ])
    def test_provider_initialization_with_flag_disabled(self, provider, flag_name, client_class, error_msg):
        """Parameterized test for all providers with disabled flags"""
        with patch('core.config.get_settings') as mock_settings:
            settings_mock = MagicMock()
            setattr(settings_mock, flag_name, False)
            settings_mock.use_stubs = True
            mock_settings.return_value = settings_mock
            
            with pytest.raises(RuntimeError) as exc_info:
                client_class()
            
            assert error_msg in str(exc_info.value)