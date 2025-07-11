"""
Tests for D0 Gateway Client Factory
"""
import threading
from unittest.mock import MagicMock, Mock, patch

import pytest

from d0_gateway.base import BaseAPIClient
from d0_gateway.factory import (
    GatewayClientFactory,
    create_client,
    get_available_providers,
    get_gateway_factory,
    register_provider,
)
from d0_gateway.providers.openai import OpenAIClient
from d0_gateway.providers.pagespeed import PageSpeedClient
from d0_gateway.providers.sendgrid import SendGridClient
from d0_gateway.providers.stripe import StripeClient
# YelpClient removed - Yelp has been removed from the codebase


class TestGatewayClientFactory:
    """Test suite for Gateway Client Factory"""

    @pytest.fixture
    def factory(self):
        """Create a fresh factory instance for testing"""
        # Reset singleton
        GatewayClientFactory._instance = None
        GatewayClientFactory._initialized = False

        with patch("d0_gateway.factory.get_settings") as mock_settings:
            # Mock settings
            mock_settings.return_value = Mock(
                # yelp_api_key removed - Yelp has been removed from the codebase
                pagespeed_api_key="test-pagespeed-key",
                openai_api_key="test-openai-key",
                sendgrid_api_key="test-sendgrid-key",
                stripe_api_key="test-stripe-key",
                stripe_secret_key="test-stripe-key",  # Stripe uses both
                data_axle_api_key="test-dataaxle-key",
                hunter_api_key="test-hunter-key",
                api_timeout=30,
                api_max_retries=3,
                debug=False,
            )
            return GatewayClientFactory()

    def test_singleton_pattern(self):
        """Test that factory follows singleton pattern"""
        factory1 = get_gateway_factory()
        factory2 = get_gateway_factory()
        assert factory1 is factory2

    def test_thread_safe_singleton(self):
        """Test thread-safe singleton creation"""
        GatewayClientFactory._instance = None
        GatewayClientFactory._initialized = False

        factories = []

        def create_factory():
            factories.append(get_gateway_factory())

        # Create multiple threads trying to create factory
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_factory)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # All should be the same instance
        assert all(f is factories[0] for f in factories)

    def test_all_providers_registered(self, factory):
        """Test that all providers are registered including SendGrid and Stripe"""
        providers = factory.get_provider_names()

        # Check all expected providers are registered
        expected_providers = [
            # "yelp" removed - Yelp has been removed from the codebase
            "pagespeed",
            "openai",
            "sendgrid",
            "stripe",
            "dataaxle",
            "hunter",
        ]
        for provider in expected_providers:
            assert provider in providers

        assert len(providers) == 6

    def test_create_sendgrid_client(self, factory):
        """Test creating SendGrid client through factory"""
        client = factory.create_client("sendgrid")

        assert isinstance(client, SendGridClient)
        assert client.provider == "sendgrid"
        # In test environment, stub config may override the API key
        assert client.api_key in ["test-sendgrid-key", "stub-sendgrid-key"]

    def test_create_stripe_client(self, factory):
        """Test creating Stripe client through factory"""
        client = factory.create_client("stripe")

        assert isinstance(client, StripeClient)
        assert client.provider == "stripe"
        # In test environment, stub config may override the API key
        assert client.api_key in ["test-stripe-key", "stub-stripe-key"]

    def test_create_all_provider_clients(self, factory):
        """Test that factory can create all registered provider instances"""
        provider_classes = {
            # "yelp": YelpClient, - removed
            "pagespeed": PageSpeedClient,
            "openai": OpenAIClient,
            "sendgrid": SendGridClient,
            "stripe": StripeClient,
        }

        for provider_name, expected_class in provider_classes.items():
            client = factory.create_client(provider_name)
            assert isinstance(client, expected_class)
            assert client.provider == provider_name

    def test_client_caching(self, factory):
        """Test that clients are cached when use_cache=True"""
        # First call creates new client
        client1 = factory.create_client("sendgrid", use_cache=True)

        # Second call should return cached instance
        client2 = factory.create_client("sendgrid", use_cache=True)

        assert client1 is client2

        # Without cache should create new instance
        client3 = factory.create_client("sendgrid", use_cache=False)
        assert client3 is not client1

    def test_invalid_provider_raises_error(self, factory):
        """Test that invalid provider name raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            factory.create_client("invalid_provider")

        assert "Unknown provider 'invalid_provider'" in str(exc_info.value)
        assert (
            "Available: pagespeed, openai, sendgrid, stripe, dataaxle, hunter"
            in str(exc_info.value)
        )

    def test_register_custom_provider(self, factory):
        """Test registering a custom provider"""

        class CustomClient(BaseAPIClient):
            def __init__(self, api_key=None):
                super().__init__(provider="custom", api_key=api_key)

            def _get_base_url(self):
                return "https://api.custom.com"

            def _get_headers(self):
                return {"Authorization": f"Bearer {self.api_key}"}

            def get_rate_limit(self):
                return {"daily_limit": 1000, "burst_limit": 10}

            def calculate_cost(self, operation, **kwargs):
                return 0.001

        factory.register_provider("custom", CustomClient)

        # Should be able to create the custom client
        client = factory.create_client("custom")
        assert isinstance(client, CustomClient)
        assert "custom" in factory.get_provider_names()

    def test_invalidate_cache(self, factory):
        """Test cache invalidation"""
        # Create cached clients
        client1 = factory.create_client("sendgrid", use_cache=True)
        client2 = factory.create_client("stripe", use_cache=True)

        # Invalidate specific provider
        factory.invalidate_cache("sendgrid")

        # SendGrid should create new instance
        new_sendgrid = factory.create_client("sendgrid", use_cache=True)
        assert new_sendgrid is not client1

        # Stripe should still be cached
        cached_stripe = factory.create_client("stripe", use_cache=True)
        assert cached_stripe is client2

        # Invalidate all
        factory.invalidate_cache()
        new_stripe = factory.create_client("stripe", use_cache=True)
        assert new_stripe is not client2

    def test_get_client_status(self, factory):
        """Test getting factory status"""
        # Create some clients
        factory.create_client("sendgrid", use_cache=True)
        factory.create_client("stripe", use_cache=True)

        status = factory.get_client_status()

        assert status["total_providers"] == 6
        assert sorted(status["registered_providers"]) == [
            "dataaxle",
            "hunter",
            "openai",
            "pagespeed",
            "sendgrid",
            "stripe",
            # "yelp" removed
        ]
        assert "sendgrid" in status["cached_clients"]
        assert "stripe" in status["cached_clients"]
        assert status["cached_count"] == 2
        assert status["factory_initialized"] is True

    def test_health_check(self, factory):
        """Test factory health check"""
        with patch.object(factory, "create_client") as mock_create:
            # Mock successful client creation
            mock_create.return_value = Mock()

            health = factory.health_check()

            assert health["factory_healthy"] is True
            assert health["overall_status"] == "healthy"

            # Should check all providers
            assert len(health["providers"]) == 6
            for provider in [
                # "yelp" removed
                "pagespeed",
                "openai",
                "sendgrid",
                "stripe",
                "dataaxle",
                "hunter",
            ]:
                assert provider in health["providers"]
                assert health["providers"][provider]["status"] == "healthy"

    def test_provider_config_includes_sendgrid_stripe(self, factory):
        """Test that provider config includes SendGrid and Stripe API keys"""
        sendgrid_config = factory._get_provider_config("sendgrid")
        assert sendgrid_config["api_key"] == "test-sendgrid-key"
        assert sendgrid_config["timeout"] == 30
        assert sendgrid_config["max_retries"] == 3

        stripe_config = factory._get_provider_config("stripe")
        assert stripe_config["api_key"] == "test-stripe-key"
        assert stripe_config["timeout"] == 30
        assert stripe_config["max_retries"] == 3

    def test_convenience_functions(self):
        """Test module-level convenience functions"""
        # Reset singleton
        GatewayClientFactory._instance = None
        GatewayClientFactory._initialized = False

        with patch("d0_gateway.factory.get_settings") as mock_settings:
            mock_settings.return_value = Mock(
                sendgrid_api_key="test-key",
                stripe_api_key="test-key",
                api_timeout=30,
                api_max_retries=3,
                debug=False,
            )

            # Test create_client convenience function
            client = create_client("sendgrid")
            assert isinstance(client, SendGridClient)

            # Test get_available_providers
            providers = get_available_providers()
            assert "sendgrid" in providers
            assert "stripe" in providers


class TestFactoryIntegration:
    """Integration tests for factory with actual provider instances"""

    @pytest.fixture
    def real_factory(self):
        """Create factory with real settings"""
        # Reset singleton
        GatewayClientFactory._instance = None
        GatewayClientFactory._initialized = False
        return get_gateway_factory()

    def test_real_provider_creation(self, real_factory):
        """Test creating real provider instances"""
        # This will use actual settings from environment
        for provider in ["sendgrid", "stripe"]:
            try:
                client = real_factory.create_client(provider)
                assert client is not None
                assert hasattr(client, "get_rate_limit")
                assert hasattr(client, "calculate_cost")
            except Exception as e:
                # It's okay if it fails due to missing API keys in test env
                if "api_key" not in str(e).lower():
                    raise
