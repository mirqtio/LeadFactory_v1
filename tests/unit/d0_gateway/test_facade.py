"""
Test D0 Gateway facade and factory
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from d0_gateway.base import BaseAPIClient
from d0_gateway.facade import GatewayFacade, get_gateway_facade
from d0_gateway.factory import GatewayClientFactory, create_client, get_gateway_factory, register_provider


class TestGatewayFactory:
    @pytest.fixture
    def factory(self):
        """Create a fresh factory instance for testing"""
        # Reset singleton state for testing
        GatewayClientFactory._instance = None
        GatewayClientFactory._initialized = False

        # Also reset module-level factory instance
        import d0_gateway.factory

        d0_gateway.factory._factory_instance = None

        return GatewayClientFactory()

    def test_thread_safe_singleton_pattern(self):
        """Test that factory implements thread-safe singleton"""
        # Reset singleton for test
        GatewayClientFactory._instance = None
        GatewayClientFactory._initialized = False

        # Also reset module-level factory instance
        import d0_gateway.factory

        d0_gateway.factory._factory_instance = None

        # Create multiple instances
        factory1 = GatewayClientFactory()
        factory2 = GatewayClientFactory()
        factory3 = get_gateway_factory()

        # Should all be the same instance
        assert factory1 is factory2
        assert factory2 is factory3

        # Should have singleton attributes
        assert hasattr(GatewayClientFactory, "_instance")
        assert hasattr(GatewayClientFactory, "_lock")

    def test_provider_registration_works(self, factory):
        """Test that provider registration works correctly"""

        # Create a mock client class
        class MockClient(BaseAPIClient):
            def __init__(self, **kwargs):
                super().__init__("mock", **kwargs)

            def _get_base_url(self):
                return "https://mock.api"

            def _get_headers(self):
                return {}

            def get_rate_limit(self):
                return {"daily_limit": 1000}

            def calculate_cost(self, operation, **kwargs):
                return 0.001

        # Register the provider
        factory.register_provider("mock", MockClient)

        # Verify registration
        assert "mock" in factory.get_provider_names()
        assert factory._providers["mock"] == MockClient

    def test_provider_registration_validation(self, factory):
        """Test provider registration validation"""

        # Try to register invalid class
        class InvalidClient:
            pass

        with pytest.raises(ValueError, match="must inherit from BaseAPIClient"):
            factory.register_provider("invalid", InvalidClient)

    def test_configuration_injection(self, factory):
        """Test that configuration is properly injected"""
        # Mock settings
        with patch.object(factory, "_get_provider_config") as mock_config:
            mock_config.return_value = {
                "api_key": "test-key",
                "timeout": 30,
                "debug": True,
            }

            # Mock client creation by patching the providers dict
            mock_client_class = Mock()
            with patch.dict(factory._providers, {"pagespeed": mock_client_class}):
                factory.create_client("pagespeed", extra_param="value")

                # Verify only api_key was passed to client constructor
                # (BaseAPIClient only accepts api_key in constructor)
                call_args = mock_client_class.call_args[1]
                assert call_args["api_key"] == "test-key"
                # Other config is stored internally but not passed to constructor
                assert "timeout" not in call_args
                assert "debug" not in call_args
                assert "extra_param" not in call_args

    def test_provider_config_generation(self, factory):
        """Test provider-specific configuration generation"""
        # Mock settings with API keys
        with patch.object(factory, "settings") as mock_settings:
            mock_settings.sendgrid_api_key = "sendgrid-key"
            mock_settings.pagespeed_api_key = "pagespeed-key"
            mock_settings.openai_api_key = "openai-key"
            mock_settings.api_timeout = 45
            mock_settings.api_max_retries = 5
            mock_settings.debug = False

            # Test SendGrid config
            sendgrid_config = factory._get_provider_config("sendgrid")
            assert sendgrid_config["api_key"] == "sendgrid-key"
            assert sendgrid_config["timeout"] == 45
            assert sendgrid_config["max_retries"] == 5

            # Test PageSpeed config
            pagespeed_config = factory._get_provider_config("pagespeed")
            assert pagespeed_config["api_key"] == "pagespeed-key"

            # Test OpenAI config
            openai_config = factory._get_provider_config("openai")
            assert openai_config["api_key"] == "openai-key"

    def test_client_caching(self, factory):
        """Test client instance caching"""
        # Mock client class
        mock_client_class = Mock()
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        with patch.dict(factory._providers, {"test": mock_client_class}), patch.object(
            factory, "_get_provider_config", return_value={}
        ):
            # First call should create new instance
            client1 = factory.create_client("test", use_cache=True)
            assert client1 is mock_client
            assert mock_client_class.call_count == 1

            # Second call should return cached instance
            client2 = factory.create_client("test", use_cache=True)
            assert client2 is mock_client
            assert client1 is client2
            assert mock_client_class.call_count == 1  # Not called again

            # Call with use_cache=False should create new instance
            mock_client_class.reset_mock()
            factory.create_client("test", use_cache=False)
            assert mock_client_class.call_count == 1

    def test_cache_invalidation(self, factory):
        """Test cache invalidation functionality"""
        # Set up cache with mock clients
        factory._client_cache = {"sendgrid": Mock(), "pagespeed": Mock(), "openai": Mock()}

        # Test specific provider invalidation
        factory.invalidate_cache("sendgrid")
        assert "sendgrid" not in factory._client_cache
        assert "pagespeed" in factory._client_cache
        assert "openai" in factory._client_cache

        # Test all providers invalidation
        factory.invalidate_cache()
        assert len(factory._client_cache) == 0

    def test_health_check_functionality(self, factory):
        """Test factory health check"""
        # Mock successful client creation
        with patch.object(factory, "create_client") as mock_create:
            mock_create.return_value = Mock()

            health = factory.health_check()

            assert health["factory_healthy"] is True
            assert health["overall_status"] == "healthy"
            assert "providers" in health

            # Should check each registered provider
            for provider in factory.get_provider_names():
                assert provider in health["providers"]
                assert health["providers"][provider]["status"] == "healthy"

    def test_health_check_with_failures(self, factory):
        """Test health check with provider failures"""
        # Mock client creation failure
        with patch.object(factory, "create_client") as mock_create:
            mock_create.side_effect = Exception("Connection failed")

            health = factory.health_check()

            assert health["overall_status"] == "degraded"

            # All providers should be marked unhealthy
            for provider in factory.get_provider_names():
                assert health["providers"][provider]["status"] == "unhealthy"
                assert "Connection failed" in health["providers"][provider]["error"]


class TestGatewayFacade:
    @pytest.fixture
    def mock_factory(self):
        """Create a mock factory for testing"""
        factory = Mock()
        factory.create_client.return_value = Mock()
        return factory

    @pytest.fixture
    def facade(self, mock_factory):
        """Create facade with mock factory"""
        return GatewayFacade(factory=mock_factory)

    def test_single_entry_point_for_all_apis_initialization(self, facade):
        """Test that facade provides single entry point for all APIs"""
        # Should have methods for all API providers
        assert hasattr(facade, "analyze_website")  # PageSpeed
        assert hasattr(facade, "get_core_web_vitals")  # PageSpeed
        assert hasattr(facade, "generate_website_insights")  # OpenAI
        assert hasattr(facade, "generate_personalized_email")  # OpenAI
        assert hasattr(facade, "send_email")  # SendGrid
        assert hasattr(facade, "send_bulk_emails")  # SendGrid
        assert hasattr(facade, "get_email_stats")  # SendGrid
        assert hasattr(facade, "get_bounces")  # SendGrid
        assert hasattr(facade, "delete_bounce")  # SendGrid
        assert hasattr(facade, "validate_email_address")  # SendGrid
        assert hasattr(facade, "get_webhook_stats")  # SendGrid
        assert hasattr(facade, "create_checkout_session")  # Stripe
        assert hasattr(facade, "create_payment_intent")  # Stripe
        assert hasattr(facade, "get_checkout_session")  # Stripe
        assert hasattr(facade, "get_payment_intent")  # Stripe
        assert hasattr(facade, "create_customer")  # Stripe
        assert hasattr(facade, "get_customer")  # Stripe
        assert hasattr(facade, "list_charges")  # Stripe
        assert hasattr(facade, "create_price")  # Stripe
        assert hasattr(facade, "create_webhook_endpoint")  # Stripe
        assert hasattr(facade, "construct_webhook_event")  # Stripe

        # Should have factory and metrics
        assert hasattr(facade, "factory")
        assert hasattr(facade, "metrics")

    @pytest.mark.asyncio
    async def test_pagespeed_api_integration(self, facade, mock_factory):
        """Test PageSpeed API integration through facade"""
        # Mock PageSpeed client
        mock_pagespeed_client = AsyncMock()
        mock_pagespeed_client.analyze_url.return_value = {
            "lighthouseResult": {"categories": {"performance": {"score": 0.85}}}
        }
        mock_factory.create_client.return_value = mock_pagespeed_client

        # Test website analysis
        result = await facade.analyze_website(url="https://example.com", strategy="mobile")

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("pagespeed")

        # Verify client method was called
        mock_pagespeed_client.analyze_url.assert_called_once_with(
            url="https://example.com", strategy="mobile", categories=None
        )

        # Verify result
        assert result["lighthouseResult"]["categories"]["performance"]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_openai_api_integration(self, facade, mock_factory):
        """Test OpenAI API integration through facade"""
        # Mock OpenAI client
        mock_openai_client = AsyncMock()
        mock_openai_client.analyze_website_performance.return_value = {
            "ai_recommendations": [{"issue": "Slow loading", "impact": "high"}]
        }
        mock_factory.create_client.return_value = mock_openai_client

        # Test insights generation
        pagespeed_data = {"lighthouseResult": {"categories": {}}}
        result = await facade.generate_website_insights(pagespeed_data)

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("openai")

        # Verify client method was called
        mock_openai_client.analyze_website_performance.assert_called_once_with(
            pagespeed_data=pagespeed_data, business_context=None
        )

        # Verify result
        assert len(result["ai_recommendations"]) == 1
        assert result["ai_recommendations"][0]["issue"] == "Slow loading"

    @pytest.mark.asyncio
    async def test_complete_business_analysis_workflow(self, facade, mock_factory):
        """Test complete business analysis workflow"""
        # Mock clients for each step
        mock_pagespeed_client = AsyncMock()
        mock_openai_client = AsyncMock()

        # Set up return values
        mock_pagespeed_client.analyze_url.return_value = {
            "lighthouseResult": {"categories": {"performance": {"score": 0.7}}}
        }

        mock_openai_client.analyze_website_performance.return_value = {
            "ai_recommendations": [{"issue": "Poor performance", "impact": "high"}]
        }

        mock_openai_client.generate_email_content.return_value = {
            "email_subject": "Website Performance Report",
            "email_body": "Your website needs optimization",
        }

        # Configure factory to return appropriate clients
        def create_client_side_effect(provider):
            if provider == "pagespeed":
                return mock_pagespeed_client
            elif provider == "openai":
                return mock_openai_client

        mock_factory.create_client.side_effect = create_client_side_effect

        # Run complete analysis with a business URL
        result = await facade.complete_business_analysis(
            business_id="test-business-123", business_url="https://testrestaurant.com", include_email_generation=True
        )

        # Verify all components were called
        assert result["business_id"] == "test-business-123"
        assert result["business_data"] is None  # No longer fetches business data
        assert result["website_analysis"]["lighthouseResult"] is not None
        assert len(result["ai_insights"]["ai_recommendations"]) == 1
        assert result["email_content"]["email_subject"] == "Website Performance Report"
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_sendgrid_send_email(self, facade, mock_factory):
        """Test SendGrid send_email through facade"""
        # Mock SendGrid client
        mock_sendgrid_client = AsyncMock()
        mock_sendgrid_client.send_email.return_value = {
            "message_id": "msg-123",
            "status": "accepted",
        }
        mock_factory.create_client.return_value = mock_sendgrid_client

        # Test send email
        result = await facade.send_email(
            to_email="test@example.com",
            from_email="sender@example.com",
            from_name="Test Sender",
            subject="Test Email",
            html_content="<p>Test content</p>",
            text_content="Test content",
            custom_args={"campaign": "test"},
        )

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("sendgrid")

        # Verify client method was called
        mock_sendgrid_client.send_email.assert_called_once_with(
            to_email="test@example.com",
            from_email="sender@example.com",
            from_name="Test Sender",
            subject="Test Email",
            html_content="<p>Test content</p>",
            text_content="Test content",
            reply_to=None,
            template_id=None,
            dynamic_template_data=None,
            custom_args={"campaign": "test"},
            tracking_settings=None,
        )

        # Verify result
        assert result["message_id"] == "msg-123"
        assert result["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_sendgrid_send_bulk_emails(self, facade, mock_factory):
        """Test SendGrid send_bulk_emails through facade"""
        # Mock SendGrid client
        mock_sendgrid_client = AsyncMock()
        mock_sendgrid_client.send_bulk_emails.return_value = {
            "total_emails": 2,
            "sent": 2,
            "failed": 0,
            "results": [
                {"email": "test1@example.com", "status": "sent", "message_id": "msg-1"},
                {"email": "test2@example.com", "status": "sent", "message_id": "msg-2"},
            ],
        }
        mock_factory.create_client.return_value = mock_sendgrid_client

        # Test bulk send
        emails = [
            {
                "to_email": "test1@example.com",
                "subject": "Email 1",
                "html_content": "<p>Content 1</p>",
            },
            {
                "to_email": "test2@example.com",
                "subject": "Email 2",
                "html_content": "<p>Content 2</p>",
            },
        ]

        result = await facade.send_bulk_emails(emails=emails, from_email="sender@example.com", from_name="Test Sender")

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("sendgrid")

        # Verify client method was called
        mock_sendgrid_client.send_bulk_emails.assert_called_once_with(
            emails=emails,
            from_email="sender@example.com",
            from_name="Test Sender",
            template_id=None,
        )

        # Verify result
        assert result["sent"] == 2
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_sendgrid_get_email_stats(self, facade, mock_factory):
        """Test SendGrid get_email_stats through facade"""
        # Mock SendGrid client
        mock_sendgrid_client = AsyncMock()
        mock_sendgrid_client.get_email_stats.return_value = {
            "date": "2024-01-01",
            "stats": [{"metrics": {"delivered": 100, "opens": 50, "clicks": 25}}],
        }
        mock_factory.create_client.return_value = mock_sendgrid_client

        # Test get stats
        result = await facade.get_email_stats(start_date="2024-01-01", end_date="2024-01-31", aggregated_by="day")

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("sendgrid")

        # Verify client method was called
        mock_sendgrid_client.get_email_stats.assert_called_once_with(
            start_date="2024-01-01", end_date="2024-01-31", aggregated_by="day"
        )

        # Verify result
        assert result["stats"][0]["metrics"]["delivered"] == 100

    @pytest.mark.asyncio
    async def test_sendgrid_get_bounces(self, facade, mock_factory):
        """Test SendGrid get_bounces through facade"""
        # Mock SendGrid client
        mock_sendgrid_client = AsyncMock()
        mock_sendgrid_client.get_bounces.return_value = {
            "bounces": [
                {
                    "email": "bounce@example.com",
                    "reason": "550 5.1.1 The email account does not exist",
                }
            ]
        }
        mock_factory.create_client.return_value = mock_sendgrid_client

        # Test get bounces
        result = await facade.get_bounces(start_time=1640995200, limit=100)

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("sendgrid")

        # Verify client method was called
        mock_sendgrid_client.get_bounces.assert_called_once_with(
            start_time=1640995200, end_time=None, limit=100, offset=0
        )

        # Verify result
        assert len(result["bounces"]) == 1
        assert result["bounces"][0]["email"] == "bounce@example.com"

    @pytest.mark.asyncio
    async def test_sendgrid_delete_bounce(self, facade, mock_factory):
        """Test SendGrid delete_bounce through facade"""
        # Mock SendGrid client
        mock_sendgrid_client = AsyncMock()
        mock_sendgrid_client.delete_bounce.return_value = {"status": "deleted"}
        mock_factory.create_client.return_value = mock_sendgrid_client

        # Test delete bounce
        result = await facade.delete_bounce(email="bounce@example.com")

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("sendgrid")

        # Verify client method was called
        mock_sendgrid_client.delete_bounce.assert_called_once_with("bounce@example.com")

        # Verify result
        assert result["status"] == "deleted"

    @pytest.mark.asyncio
    async def test_sendgrid_validate_email_address(self, facade, mock_factory):
        """Test SendGrid validate_email_address through facade"""
        # Mock SendGrid client
        mock_sendgrid_client = AsyncMock()
        mock_sendgrid_client.validate_email_address.return_value = {
            "result": {"email": "test@example.com", "verdict": "Valid", "score": 0.95}
        }
        mock_factory.create_client.return_value = mock_sendgrid_client

        # Test validate email
        result = await facade.validate_email_address(email="test@example.com")

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("sendgrid")

        # Verify client method was called
        mock_sendgrid_client.validate_email_address.assert_called_once_with("test@example.com")

        # Verify result
        assert result["result"]["verdict"] == "Valid"
        assert result["result"]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_sendgrid_get_webhook_stats(self, facade, mock_factory):
        """Test SendGrid get_webhook_stats through facade"""
        # Mock SendGrid client
        mock_sendgrid_client = AsyncMock()
        mock_sendgrid_client.get_webhook_stats.return_value = {
            "enabled": True,
            "url": "https://example.com/webhook",
            "event_types": ["delivered", "opened", "clicked"],
        }
        mock_factory.create_client.return_value = mock_sendgrid_client

        # Test get webhook stats
        result = await facade.get_webhook_stats()

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("sendgrid")

        # Verify client method was called
        mock_sendgrid_client.get_webhook_stats.assert_called_once_with()

        # Verify result
        assert result["enabled"] is True
        assert result["url"] == "https://example.com/webhook"

    @pytest.mark.asyncio
    async def test_sendgrid_error_handling(self, facade, mock_factory):
        """Test SendGrid error handling in facade"""
        # Mock SendGrid client that raises exception
        mock_sendgrid_client = AsyncMock()
        mock_sendgrid_client.send_email.side_effect = Exception("SendGrid API error")
        mock_factory.create_client.return_value = mock_sendgrid_client

        # Test that exception is properly propagated
        with pytest.raises(Exception) as exc_info:
            await facade.send_email(
                to_email="test@example.com",
                from_email="sender@example.com",
                from_name="Test",
                subject="Test",
                html_content="<p>Test</p>",
            )

        assert "SendGrid API error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stripe_create_checkout_session(self, facade, mock_factory):
        """Test Stripe create_checkout_session through facade"""
        # Mock Stripe client
        mock_stripe_client = AsyncMock()
        mock_stripe_client.create_checkout_session.return_value = {
            "id": "cs_test_123",
            "url": "https://checkout.stripe.com/pay/cs_test_123",
            "status": "open",
        }
        mock_factory.create_client.return_value = mock_stripe_client

        # Test create checkout session
        result = await facade.create_checkout_session(
            price_id="price_123",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            quantity=1,
            customer_email="test@example.com",
            metadata={"order_id": "123"},
        )

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("stripe")

        # Verify client method was called
        mock_stripe_client.create_checkout_session.assert_called_once_with(
            price_id="price_123",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            quantity=1,
            customer_email="test@example.com",
            client_reference_id=None,
            metadata={"order_id": "123"},
            mode="payment",
        )

        # Verify result
        assert result["id"] == "cs_test_123"
        assert result["url"] == "https://checkout.stripe.com/pay/cs_test_123"

    @pytest.mark.asyncio
    async def test_stripe_create_payment_intent(self, facade, mock_factory):
        """Test Stripe create_payment_intent through facade"""
        # Mock Stripe client
        mock_stripe_client = AsyncMock()
        mock_stripe_client.create_payment_intent.return_value = {
            "id": "pi_test_123",
            "amount": 1999,
            "currency": "usd",
            "status": "requires_payment_method",
        }
        mock_factory.create_client.return_value = mock_stripe_client

        # Test create payment intent
        result = await facade.create_payment_intent(amount=1999, currency="usd", description="Website report payment")

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("stripe")

        # Verify client method was called
        mock_stripe_client.create_payment_intent.assert_called_once_with(
            amount=1999,
            currency="usd",
            customer_id=None,
            description="Website report payment",
            metadata=None,
            receipt_email=None,
        )

        # Verify result
        assert result["id"] == "pi_test_123"
        assert result["amount"] == 1999

    @pytest.mark.asyncio
    async def test_stripe_get_checkout_session(self, facade, mock_factory):
        """Test Stripe get_checkout_session through facade"""
        # Mock Stripe client
        mock_stripe_client = AsyncMock()
        mock_stripe_client.get_checkout_session.return_value = {
            "id": "cs_test_123",
            "payment_status": "paid",
            "customer_email": "test@example.com",
        }
        mock_factory.create_client.return_value = mock_stripe_client

        # Test get checkout session
        result = await facade.get_checkout_session(session_id="cs_test_123")

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("stripe")

        # Verify client method was called
        mock_stripe_client.get_checkout_session.assert_called_once_with("cs_test_123")

        # Verify result
        assert result["id"] == "cs_test_123"
        assert result["payment_status"] == "paid"

    @pytest.mark.asyncio
    async def test_stripe_create_customer(self, facade, mock_factory):
        """Test Stripe create_customer through facade"""
        # Mock Stripe client
        mock_stripe_client = AsyncMock()
        mock_stripe_client.create_customer.return_value = {
            "id": "cus_test_123",
            "email": "test@example.com",
            "name": "Test Customer",
        }
        mock_factory.create_client.return_value = mock_stripe_client

        # Test create customer
        result = await facade.create_customer(
            email="test@example.com",
            name="Test Customer",
            metadata={"source": "leadfactory"},
        )

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("stripe")

        # Verify client method was called
        mock_stripe_client.create_customer.assert_called_once_with(
            email="test@example.com",
            name="Test Customer",
            description=None,
            metadata={"source": "leadfactory"},
        )

        # Verify result
        assert result["id"] == "cus_test_123"
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_stripe_list_charges(self, facade, mock_factory):
        """Test Stripe list_charges through facade"""
        # Mock Stripe client
        mock_stripe_client = AsyncMock()
        mock_stripe_client.list_charges.return_value = {
            "data": [{"id": "ch_1", "amount": 1999}, {"id": "ch_2", "amount": 2999}],
            "has_more": False,
        }
        mock_factory.create_client.return_value = mock_stripe_client

        # Test list charges
        result = await facade.list_charges(customer_id="cus_test_123", limit=10)

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("stripe")

        # Verify client method was called
        mock_stripe_client.list_charges.assert_called_once_with(
            customer_id="cus_test_123", limit=10, starting_after=None
        )

        # Verify result
        assert len(result["data"]) == 2
        assert result["data"][0]["id"] == "ch_1"

    @pytest.mark.asyncio
    async def test_stripe_create_webhook_endpoint(self, facade, mock_factory):
        """Test Stripe create_webhook_endpoint through facade"""
        # Mock Stripe client
        mock_stripe_client = AsyncMock()
        mock_stripe_client.create_webhook_endpoint.return_value = {
            "id": "we_test_123",
            "url": "https://example.com/webhook",
            "enabled_events": ["checkout.session.completed"],
        }
        mock_factory.create_client.return_value = mock_stripe_client

        # Test create webhook endpoint
        result = await facade.create_webhook_endpoint(
            url="https://example.com/webhook",
            enabled_events=["checkout.session.completed"],
            description="LeadFactory webhook",
        )

        # Verify factory was called correctly
        mock_factory.create_client.assert_called_with("stripe")

        # Verify client method was called
        mock_stripe_client.create_webhook_endpoint.assert_called_once_with(
            url="https://example.com/webhook",
            enabled_events=["checkout.session.completed"],
            description="LeadFactory webhook",
        )

        # Verify result
        assert result["id"] == "we_test_123"
        assert result["url"] == "https://example.com/webhook"

    @pytest.mark.asyncio
    async def test_stripe_error_handling(self, facade, mock_factory):
        """Test Stripe error handling in facade"""
        # Mock Stripe client that raises exception
        mock_stripe_client = AsyncMock()
        mock_stripe_client.create_checkout_session.side_effect = Exception("Stripe API error")
        mock_factory.create_client.return_value = mock_stripe_client

        # Test that exception is properly propagated
        with pytest.raises(Exception) as exc_info:
            await facade.create_checkout_session(
                price_id="price_123",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

        assert "Stripe API error" in str(exc_info.value)

    def test_gateway_status_reporting(self, facade, mock_factory):
        """Test gateway status reporting"""
        # Mock factory responses
        mock_factory.get_client_status.return_value = {
            "registered_providers": ["sendgrid", "pagespeed", "openai"],
            "cached_clients": ["sendgrid"],
            "total_providers": 3,
        }

        mock_factory.health_check.return_value = {
            "overall_status": "healthy",
            "providers": {"sendgrid": {"status": "healthy"}},
        }

        # Mock metrics
        with patch.object(facade.metrics, "get_metrics_summary") as mock_metrics:
            mock_metrics.return_value = {"metrics_enabled": True}

            status = facade.get_gateway_status()

            assert status["status"] == "operational"
            assert "factory" in status
            assert "health" in status
            assert "metrics" in status
            assert status["facade_version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_rate_limit_monitoring(self, facade, mock_factory):
        """Test rate limit monitoring across providers"""
        # Mock clients with different rate limits
        mock_clients = {}
        for provider in ["sendgrid", "pagespeed", "openai"]:
            mock_client = Mock()
            mock_client.get_rate_limit.return_value = {
                "daily_limit": 1000,
                "daily_used": 150,
                "burst_limit": 10,
            }
            mock_clients[provider] = mock_client

        mock_factory.get_provider_names.return_value = ["sendgrid", "pagespeed", "openai"]
        mock_factory.create_client.side_effect = lambda p: mock_clients[p]

        rate_limits = await facade.get_all_rate_limits()

        # Verify rate limits for all providers
        assert len(rate_limits) == 3
        for provider in ["sendgrid", "pagespeed", "openai"]:
            assert provider in rate_limits
            assert rate_limits[provider]["daily_limit"] == 1000
            assert rate_limits[provider]["daily_used"] == 150

    @pytest.mark.asyncio
    async def test_cost_calculation_across_providers(self, facade, mock_factory):
        """Test cost calculation across all providers"""
        mock_factory.get_provider_names.return_value = ["sendgrid", "pagespeed", "openai"]

        # Mock clients
        def create_client_mock(provider):
            mock_client = Mock()
            return mock_client

        mock_factory.create_client.side_effect = create_client_mock

        costs = await facade.calculate_total_costs()

        # Should return costs for all providers
        assert len(costs) == 3
        assert "sendgrid" in costs
        assert "pagespeed" in costs
        assert "openai" in costs

    def test_cache_invalidation_management(self, facade, mock_factory):
        """Test cache invalidation management"""
        # Test cache invalidation
        facade.invalidate_all_caches()

        # Verify factory invalidation was called
        mock_factory.invalidate_cache.assert_called_once()

    def test_error_handling_in_workflows(self, facade, mock_factory):
        """Test error handling in facade workflows"""
        # Mock factory to raise exception
        mock_factory.create_client.side_effect = Exception("Provider unavailable")

        # Test that exceptions are properly handled and logged
        import asyncio

        async def test_error_handling():
            try:
                await facade.analyze_website("https://example.com")
                assert False, "Should have raised exception"
            except Exception as e:
                assert "Provider unavailable" in str(e)

        asyncio.run(test_error_handling())


class TestGlobalInstances:
    def test_global_facade_singleton(self):
        """Test global facade singleton behavior"""
        # Reset global state
        import d0_gateway.facade

        d0_gateway.facade._facade_instance = None

        # Get facade instances
        facade1 = get_gateway_facade()
        facade2 = get_gateway_facade()

        # Should be the same instance
        assert facade1 is facade2

    def test_global_factory_singleton(self):
        """Test global factory singleton behavior"""
        # Reset global state
        import d0_gateway.factory

        d0_gateway.factory._factory_instance = None
        GatewayClientFactory._instance = None
        GatewayClientFactory._initialized = False

        # Get factory instances
        factory1 = get_gateway_factory()
        factory2 = get_gateway_factory()

        # Should be the same instance
        assert factory1 is factory2

    def test_convenience_functions(self):
        """Test convenience functions work correctly"""
        # Reset state
        GatewayClientFactory._instance = None
        GatewayClientFactory._initialized = False

        # Test create_client convenience function
        with patch("d0_gateway.factory.get_gateway_factory") as mock_get_factory:
            mock_factory = Mock()
            mock_get_factory.return_value = mock_factory

            create_client("pagespeed", extra_param="value")

            mock_factory.create_client.assert_called_once_with("pagespeed", extra_param="value")

        # Test register_provider convenience function
        with patch("d0_gateway.factory.get_gateway_factory") as mock_get_factory:
            mock_factory = Mock()
            mock_get_factory.return_value = mock_factory

            class TestClient(BaseAPIClient):
                def _get_base_url(self):
                    return "test"

                def _get_headers(self):
                    return {}

                def get_rate_limit(self):
                    return {}

                def calculate_cost(self, op, **kw):
                    return 0

            register_provider("test", TestClient)

            mock_factory.register_provider.assert_called_once_with("test", TestClient)


class TestThreadSafety:
    @pytest.mark.slow
    def test_factory_thread_safety(self):
        """Test factory thread safety under concurrent access"""
        import threading
        import time

        # Reset singleton
        GatewayClientFactory._instance = None
        GatewayClientFactory._initialized = False

        results = []

        def create_factory():
            factory = GatewayClientFactory()
            results.append(factory)
            # No need for sleep - let threads race naturally

        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=create_factory)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # All results should be the same instance
        first_instance = results[0]
        assert all(instance is first_instance for instance in results)

    def test_client_cache_thread_safety(self):
        """Test client cache thread safety"""
        import threading

        factory = GatewayClientFactory()

        # Mock client creation
        mock_client_class = Mock()
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        with patch.dict(factory._providers, {"test": mock_client_class}), patch.object(
            factory, "_get_provider_config", return_value={}
        ):
            results = []

            def create_client():
                client = factory.create_client("test", use_cache=True)
                results.append(client)

            # Create multiple threads accessing cache
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=create_client)
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join()

            # All should get the same cached instance
            assert all(client is mock_client for client in results)
            # Client should only be created once due to caching
            assert mock_client_class.call_count == 1


class TestGatewayFacadeErrorHandling:
    """Test error handling in Gateway Facade"""

    @pytest.fixture
    def facade(self):
        """Create facade with mocked factory"""
        mock_factory = Mock()
        return GatewayFacade(factory=mock_factory), mock_factory

    @pytest.mark.asyncio
    async def test_get_core_web_vitals_error(self, facade):
        """Test get_core_web_vitals error handling"""
        facade_instance, mock_factory = facade

        # Mock client that raises exception
        mock_client = AsyncMock()
        mock_client.get_core_web_vitals.side_effect = Exception("API error")
        mock_factory.create_client.return_value = mock_client

        # Should raise exception
        with pytest.raises(Exception, match="API error"):
            await facade_instance.get_core_web_vitals("https://example.com")

    @pytest.mark.asyncio
    async def test_analyze_multiple_websites_error(self, facade):
        """Test analyze_multiple_websites error handling"""
        facade_instance, mock_factory = facade

        # Mock client that raises exception
        mock_client = AsyncMock()
        mock_client.batch_analyze_urls.side_effect = Exception("Batch error")
        mock_factory.create_client.return_value = mock_client

        # Should raise exception
        with pytest.raises(Exception, match="Batch error"):
            await facade_instance.analyze_multiple_websites(["https://example.com"])

    @pytest.mark.asyncio
    async def test_generate_website_insights_error(self, facade):
        """Test generate_website_insights error handling"""
        facade_instance, mock_factory = facade

        # Mock client that raises exception
        mock_client = AsyncMock()
        mock_client.analyze_website_performance.side_effect = Exception("AI error")
        mock_factory.create_client.return_value = mock_client

        # Should raise exception
        with pytest.raises(Exception, match="AI error"):
            await facade_instance.generate_website_insights("https://example.com")

    # Removed duplicate test - replaced by correct test below

    @pytest.mark.asyncio
    async def test_send_email_error(self, facade):
        """Test send_email error handling"""
        facade_instance, mock_factory = facade

        # Mock client that raises exception
        mock_client = AsyncMock()
        mock_client.send_email.side_effect = Exception("Send error")
        mock_factory.create_client.return_value = mock_client

        # Should raise exception
        with pytest.raises(Exception, match="Send error"):
            await facade_instance.send_email("test@example.com", "from@example.com", "Test From", "Subject", "Body")

    @pytest.mark.asyncio
    async def test_create_checkout_session_error(self, facade):
        """Test create_checkout_session error handling"""
        facade_instance, mock_factory = facade

        # Mock client that raises exception
        mock_client = AsyncMock()
        mock_client.create_checkout_session.side_effect = Exception("Stripe error")
        mock_factory.create_client.return_value = mock_client

        # Should raise exception
        with pytest.raises(Exception, match="Stripe error"):
            await facade_instance.create_checkout_session("price_123", "https://success.com", "https://cancel.com")

    @pytest.mark.asyncio
    async def test_get_checkout_session_error(self, facade):
        """Test get_checkout_session error handling"""
        facade_instance, mock_factory = facade

        # Mock client that raises exception
        mock_client = AsyncMock()
        mock_client.get_checkout_session.side_effect = Exception("Retrieve error")
        mock_factory.create_client.return_value = mock_client

        # Should raise exception
        with pytest.raises(Exception, match="Retrieve error"):
            await facade_instance.get_checkout_session("cs_123")

    @pytest.mark.asyncio
    async def test_complete_business_analysis_partial_error(self, facade):
        """Test complete_business_analysis with partial errors"""
        facade_instance, mock_factory = facade

        # Mock clients with mixed success/failure
        mock_pagespeed_client = AsyncMock()
        mock_openai_client = AsyncMock()

        # PageSpeed succeeds
        mock_pagespeed_client.analyze_url.return_value = {
            "lighthouseResult": {"categories": {"performance": {"score": 0.8}}}
        }

        # OpenAI fails
        mock_openai_client.analyze_website_performance.side_effect = Exception("AI error")

        def create_client_side_effect(provider):
            if provider == "pagespeed":
                return mock_pagespeed_client
            elif provider == "openai":
                return mock_openai_client

        mock_factory.create_client.side_effect = create_client_side_effect

        # Should handle partial failure gracefully
        result = await facade_instance.complete_business_analysis(
            business_id="test-123", business_url="https://example.com", include_email_generation=True
        )

        # Should have website analysis but errors for AI
        assert result["business_id"] == "test-123"
        assert result["website_analysis"] is not None
        assert result["ai_insights"] is None
        assert len(result["errors"]) > 0

    def test_facade_initialization_with_factory(self):
        """Test facade initialization with provided factory"""
        mock_factory = Mock()
        facade_instance = GatewayFacade(factory=mock_factory)

        assert facade_instance.factory is mock_factory
        assert facade_instance.logger is not None
        assert facade_instance.metrics is not None

    def test_facade_initialization_default_factory(self):
        """Test facade initialization with default factory"""
        with patch("d0_gateway.facade.get_gateway_factory") as mock_get_factory:
            mock_factory = Mock()
            mock_get_factory.return_value = mock_factory

            facade_instance = GatewayFacade()

            assert facade_instance.factory is mock_factory
            mock_get_factory.assert_called_once()


class TestGatewayFacadeModuleFunctions:
    """Test module-level functions"""

    def test_get_gateway_facade_singleton(self):
        """Test get_gateway_facade returns singleton"""
        # Reset any existing facade
        import d0_gateway.facade

        d0_gateway.facade._facade_instance = None

        facade1 = get_gateway_facade()
        facade2 = get_gateway_facade()

        assert facade1 is facade2
        assert isinstance(facade1, GatewayFacade)


class TestGatewayFacadeMissingCoverage:
    """Test missing coverage areas to reach 80%+ coverage"""

    @pytest.fixture
    def mock_factory(self):
        """Create a mock factory for testing"""
        factory = Mock()
        factory.create_client.return_value = Mock()
        return factory

    @pytest.fixture
    def facade(self, mock_factory):
        """Create facade with mock factory"""
        return GatewayFacade(factory=mock_factory)

    @pytest.mark.asyncio
    async def test_get_core_web_vitals_success(self, facade, mock_factory):
        """Test get_core_web_vitals success path"""
        # Mock PageSpeed client
        mock_client = AsyncMock()
        mock_client.get_core_web_vitals.return_value = {"metrics": {"FCP": 1.5, "LCP": 2.1, "CLS": 0.1}}
        mock_factory.create_client.return_value = mock_client

        result = await facade.get_core_web_vitals("https://example.com", "desktop")

        mock_factory.create_client.assert_called_with("pagespeed")
        mock_client.get_core_web_vitals.assert_called_with("https://example.com", "desktop")
        assert result["metrics"]["FCP"] == 1.5

    @pytest.mark.asyncio
    async def test_get_core_web_vitals_error(self, facade, mock_factory):
        """Test get_core_web_vitals error path"""
        mock_client = AsyncMock()
        mock_client.get_core_web_vitals.side_effect = Exception("API error")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="API error"):
            await facade.get_core_web_vitals("https://example.com")

    @pytest.mark.asyncio
    async def test_analyze_multiple_websites_success(self, facade, mock_factory):
        """Test analyze_multiple_websites success path"""
        mock_client = AsyncMock()
        mock_client.batch_analyze_urls.return_value = {"results": [{"url": "https://example.com", "score": 85}]}
        mock_factory.create_client.return_value = mock_client

        result = await facade.analyze_multiple_websites(["https://example.com"], "mobile")

        mock_factory.create_client.assert_called_with("pagespeed")
        mock_client.batch_analyze_urls.assert_called_with(["https://example.com"], "mobile")
        assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_analyze_multiple_websites_error(self, facade, mock_factory):
        """Test analyze_multiple_websites error path"""
        mock_client = AsyncMock()
        mock_client.batch_analyze_urls.side_effect = Exception("Batch error")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Batch error"):
            await facade.analyze_multiple_websites(["https://example.com"])

    @pytest.mark.asyncio
    async def test_generate_website_insights_error(self, facade, mock_factory):
        """Test generate_website_insights error path"""
        mock_client = AsyncMock()
        mock_client.analyze_website_performance.side_effect = Exception("AI insights failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="AI insights failed"):
            await facade.generate_website_insights({"data": "test"})

    @pytest.mark.asyncio
    async def test_generate_personalized_email_success(self, facade, mock_factory):
        """Test generate_personalized_email success path"""
        mock_client = AsyncMock()
        mock_client.generate_email_content.return_value = {"subject": "Test Subject", "body": "Test Body"}
        mock_factory.create_client.return_value = mock_client

        result = await facade.generate_personalized_email("Test Business", [{"issue": "slow loading"}], "John Doe")

        mock_factory.create_client.assert_called_with("openai")
        mock_client.generate_email_content.assert_called_with(
            business_name="Test Business", website_issues=[{"issue": "slow loading"}], recipient_name="John Doe"
        )
        assert result["subject"] == "Test Subject"

    @pytest.mark.asyncio
    async def test_generate_personalized_email_error(self, facade, mock_factory):
        """Test generate_personalized_email error path"""
        mock_client = AsyncMock()
        mock_client.generate_email_content.side_effect = Exception("Email generation failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Email generation failed"):
            await facade.generate_personalized_email("Test", [{"issue": "test"}])

    @pytest.mark.asyncio
    async def test_send_bulk_emails_error(self, facade, mock_factory):
        """Test send_bulk_emails error path"""
        mock_client = AsyncMock()
        mock_client.send_bulk_emails.side_effect = Exception("Bulk send failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Bulk send failed"):
            await facade.send_bulk_emails([{"to": "test@example.com"}], "from@example.com")

    @pytest.mark.asyncio
    async def test_get_email_stats_error(self, facade, mock_factory):
        """Test get_email_stats error path"""
        mock_client = AsyncMock()
        mock_client.get_email_stats.side_effect = Exception("Stats failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Stats failed"):
            await facade.get_email_stats("2024-01-01")

    @pytest.mark.asyncio
    async def test_get_bounces_error(self, facade, mock_factory):
        """Test get_bounces error path"""
        mock_client = AsyncMock()
        mock_client.get_bounces.side_effect = Exception("Bounces failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Bounces failed"):
            await facade.get_bounces()

    @pytest.mark.asyncio
    async def test_delete_bounce_error(self, facade, mock_factory):
        """Test delete_bounce error path"""
        mock_client = AsyncMock()
        mock_client.delete_bounce.side_effect = Exception("Delete failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Delete failed"):
            await facade.delete_bounce("test@example.com")

    @pytest.mark.asyncio
    async def test_validate_email_address_error(self, facade, mock_factory):
        """Test validate_email_address error path"""
        mock_client = AsyncMock()
        mock_client.validate_email_address.side_effect = Exception("Validation failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Validation failed"):
            await facade.validate_email_address("test@example.com")

    @pytest.mark.asyncio
    async def test_get_webhook_stats_error(self, facade, mock_factory):
        """Test get_webhook_stats error path"""
        mock_client = AsyncMock()
        mock_client.get_webhook_stats.side_effect = Exception("Webhook stats failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Webhook stats failed"):
            await facade.get_webhook_stats()

    @pytest.mark.asyncio
    async def test_create_checkout_session_with_line_items_success(self, facade, mock_factory):
        """Test create_checkout_session_with_line_items success path"""
        mock_client = AsyncMock()
        mock_client.create_checkout_session_with_line_items.return_value = {
            "id": "cs_test_123",
            "url": "https://checkout.stripe.com/cs_test_123",
        }
        mock_factory.create_client.return_value = mock_client

        line_items = [{"price": "price_123", "quantity": 1}]
        result = await facade.create_checkout_session_with_line_items(
            line_items=line_items,
            success_url="https://success.com",
            cancel_url="https://cancel.com",
            customer_email="test@example.com",
            mode="subscription",
            expires_at=1640995200,
            payment_method_types=["card"],
            billing_address_collection="required",
            allow_promotion_codes=True,
        )

        mock_factory.create_client.assert_called_with("stripe")
        mock_client.create_checkout_session_with_line_items.assert_called_with(
            line_items=line_items,
            success_url="https://success.com",
            cancel_url="https://cancel.com",
            customer_email="test@example.com",
            client_reference_id=None,
            metadata=None,
            mode="subscription",
            expires_at=1640995200,
            payment_method_types=["card"],
            billing_address_collection="required",
            allow_promotion_codes=True,
        )
        assert result["id"] == "cs_test_123"

    @pytest.mark.asyncio
    async def test_create_checkout_session_with_line_items_error(self, facade, mock_factory):
        """Test create_checkout_session_with_line_items error path"""
        mock_client = AsyncMock()
        mock_client.create_checkout_session_with_line_items.side_effect = Exception("Line items failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Line items failed"):
            await facade.create_checkout_session_with_line_items([], "https://success.com", "https://cancel.com")

    @pytest.mark.asyncio
    async def test_create_payment_intent_error(self, facade, mock_factory):
        """Test create_payment_intent error path"""
        mock_client = AsyncMock()
        mock_client.create_payment_intent.side_effect = Exception("Payment intent failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Payment intent failed"):
            await facade.create_payment_intent(1000)

    @pytest.mark.asyncio
    async def test_get_checkout_session_error(self, facade, mock_factory):
        """Test get_checkout_session error path"""
        mock_client = AsyncMock()
        mock_client.get_checkout_session.side_effect = Exception("Get session failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Get session failed"):
            await facade.get_checkout_session("cs_123")

    @pytest.mark.asyncio
    async def test_get_payment_intent_success(self, facade, mock_factory):
        """Test get_payment_intent success path"""
        mock_client = AsyncMock()
        mock_client.get_payment_intent.return_value = {"id": "pi_123", "status": "succeeded"}
        mock_factory.create_client.return_value = mock_client

        result = await facade.get_payment_intent("pi_123")

        mock_factory.create_client.assert_called_with("stripe")
        mock_client.get_payment_intent.assert_called_with("pi_123")
        assert result["id"] == "pi_123"

    @pytest.mark.asyncio
    async def test_get_payment_intent_error(self, facade, mock_factory):
        """Test get_payment_intent error path"""
        mock_client = AsyncMock()
        mock_client.get_payment_intent.side_effect = Exception("Get payment intent failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Get payment intent failed"):
            await facade.get_payment_intent("pi_123")

    @pytest.mark.asyncio
    async def test_create_customer_error(self, facade, mock_factory):
        """Test create_customer error path"""
        mock_client = AsyncMock()
        mock_client.create_customer.side_effect = Exception("Create customer failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Create customer failed"):
            await facade.create_customer("test@example.com")

    @pytest.mark.asyncio
    async def test_get_customer_success(self, facade, mock_factory):
        """Test get_customer success path"""
        mock_client = AsyncMock()
        mock_client.get_customer.return_value = {"id": "cus_123", "email": "test@example.com"}
        mock_factory.create_client.return_value = mock_client

        result = await facade.get_customer("cus_123")

        mock_factory.create_client.assert_called_with("stripe")
        mock_client.get_customer.assert_called_with("cus_123")
        assert result["id"] == "cus_123"

    @pytest.mark.asyncio
    async def test_get_customer_error(self, facade, mock_factory):
        """Test get_customer error path"""
        mock_client = AsyncMock()
        mock_client.get_customer.side_effect = Exception("Get customer failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Get customer failed"):
            await facade.get_customer("cus_123")

    @pytest.mark.asyncio
    async def test_create_product_success(self, facade, mock_factory):
        """Test create_product success path"""
        mock_client = AsyncMock()
        mock_client.create_product.return_value = {"id": "prod_123", "name": "Test Product"}
        mock_factory.create_client.return_value = mock_client

        result = await facade.create_product(
            name="Test Product", description="Test Description", metadata={"key": "value"}, active=False
        )

        mock_factory.create_client.assert_called_with("stripe")
        mock_client.create_product.assert_called_with(
            name="Test Product", description="Test Description", metadata={"key": "value"}, active=False
        )
        assert result["id"] == "prod_123"

    @pytest.mark.asyncio
    async def test_create_product_error(self, facade, mock_factory):
        """Test create_product error path"""
        mock_client = AsyncMock()
        mock_client.create_product.side_effect = Exception("Create product failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Create product failed"):
            await facade.create_product("Test Product")

    @pytest.mark.asyncio
    async def test_list_charges_error(self, facade, mock_factory):
        """Test list_charges error path"""
        mock_client = AsyncMock()
        mock_client.list_charges.side_effect = Exception("List charges failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="List charges failed"):
            await facade.list_charges()

    @pytest.mark.asyncio
    async def test_create_price_success(self, facade, mock_factory):
        """Test create_price success path"""
        mock_client = AsyncMock()
        mock_client.create_price.return_value = {"id": "price_123", "unit_amount": 1000}
        mock_factory.create_client.return_value = mock_client

        result = await facade.create_price(
            amount=1000,
            currency="eur",
            product_id="prod_123",
            product_data={"name": "Test"},
            recurring={"interval": "month"},
        )

        mock_factory.create_client.assert_called_with("stripe")
        mock_client.create_price.assert_called_with(
            amount=1000,
            currency="eur",
            product_id="prod_123",
            product_data={"name": "Test"},
            recurring={"interval": "month"},
        )
        assert result["id"] == "price_123"

    @pytest.mark.asyncio
    async def test_create_price_error(self, facade, mock_factory):
        """Test create_price error path"""
        mock_client = AsyncMock()
        mock_client.create_price.side_effect = Exception("Create price failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Create price failed"):
            await facade.create_price(1000)

    @pytest.mark.asyncio
    async def test_create_webhook_endpoint_error(self, facade, mock_factory):
        """Test create_webhook_endpoint error path"""
        mock_client = AsyncMock()
        mock_client.create_webhook_endpoint.side_effect = Exception("Webhook endpoint failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Webhook endpoint failed"):
            await facade.create_webhook_endpoint("https://example.com", ["event"])

    @pytest.mark.asyncio
    async def test_construct_webhook_event_success(self, facade, mock_factory):
        """Test construct_webhook_event success path"""
        mock_client = AsyncMock()
        mock_client.construct_webhook_event.return_value = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_123"}},
        }
        mock_factory.create_client.return_value = mock_client

        result = await facade.construct_webhook_event(
            payload='{"test": "data"}', signature="signature", endpoint_secret="secret"
        )

        mock_factory.create_client.assert_called_with("stripe")
        mock_client.construct_webhook_event.assert_called_with(
            payload='{"test": "data"}', signature="signature", endpoint_secret="secret"
        )
        assert result["type"] == "checkout.session.completed"

    @pytest.mark.asyncio
    async def test_construct_webhook_event_error(self, facade, mock_factory):
        """Test construct_webhook_event error path"""
        mock_client = AsyncMock()
        mock_client.construct_webhook_event.side_effect = Exception("Webhook event failed")
        mock_factory.create_client.return_value = mock_client

        with pytest.raises(Exception, match="Webhook event failed"):
            await facade.construct_webhook_event("payload", "signature", "secret")

    @pytest.mark.asyncio
    async def test_complete_business_analysis_no_url(self, facade, mock_factory):
        """Test complete_business_analysis with no URL"""
        result = await facade.complete_business_analysis("test-123")

        assert result["business_id"] == "test-123"
        assert result["business_data"] is None
        assert result["website_analysis"] is None
        assert result["ai_insights"] is None
        assert result["email_content"] is None
        assert "No website URL provided" in result["errors"]

    @pytest.mark.asyncio
    async def test_complete_business_analysis_website_error(self, facade, mock_factory):
        """Test complete_business_analysis with website analysis error"""
        # Mock facade methods to raise exception for website analysis
        with patch.object(facade, "analyze_website", side_effect=Exception("Website analysis failed")):
            result = await facade.complete_business_analysis("test-123", business_url="https://example.com")

            assert result["business_id"] == "test-123"
            assert result["website_analysis"] is None
            assert "Website analysis failed: Website analysis failed" in result["errors"]

    @pytest.mark.asyncio
    async def test_complete_business_analysis_ai_error(self, facade, mock_factory):
        """Test complete_business_analysis with AI insights error"""
        # Mock website analysis success but AI insights failure
        with patch.object(facade, "analyze_website", return_value={"data": "test"}), patch.object(
            facade, "generate_website_insights", side_effect=Exception("AI failed")
        ):
            result = await facade.complete_business_analysis("test-123", business_url="https://example.com")

            assert result["business_id"] == "test-123"
            assert result["website_analysis"] == {"data": "test"}
            assert result["ai_insights"] is None
            assert "AI insights failed: AI failed" in result["errors"]

    @pytest.mark.asyncio
    async def test_complete_business_analysis_email_error(self, facade, mock_factory):
        """Test complete_business_analysis with email generation error"""
        # Mock successful website and AI but email failure
        with patch.object(facade, "analyze_website", return_value={"data": "test"}), patch.object(
            facade, "generate_website_insights", return_value={"ai_recommendations": [{"issue": "test"}]}
        ), patch.object(facade, "generate_personalized_email", side_effect=Exception("Email failed")):
            result = await facade.complete_business_analysis(
                "test-123", business_url="https://example.com", include_email_generation=True
            )

            assert result["business_id"] == "test-123"
            assert result["website_analysis"] == {"data": "test"}
            assert result["ai_insights"] == {"ai_recommendations": [{"issue": "test"}]}
            assert result["email_content"] is None
            assert "Email generation failed: Email failed" in result["errors"]

    def test_get_gateway_status_error(self, facade, mock_factory):
        """Test get_gateway_status error handling"""
        mock_factory.get_client_status.side_effect = Exception("Status error")

        status = facade.get_gateway_status()

        assert status["status"] == "error"
        assert "Status error" in status["error"]

    @pytest.mark.asyncio
    async def test_get_all_rate_limits_with_errors(self, facade, mock_factory):
        """Test get_all_rate_limits with provider errors"""
        mock_factory.get_provider_names.return_value = ["provider1", "provider2"]

        def create_client_side_effect(provider):
            if provider == "provider1":
                raise Exception("Provider 1 error")
            else:
                mock_client = Mock()
                mock_client.get_rate_limit.return_value = {"limit": 100}
                return mock_client

        mock_factory.create_client.side_effect = create_client_side_effect

        rate_limits = await facade.get_all_rate_limits()

        assert "provider1" in rate_limits
        assert "provider2" in rate_limits
        assert "Provider 1 error" in rate_limits["provider1"]["error"]
        assert rate_limits["provider2"]["limit"] == 100

    @pytest.mark.asyncio
    async def test_calculate_total_costs_with_errors(self, facade, mock_factory):
        """Test calculate_total_costs with provider errors"""
        mock_factory.get_provider_names.return_value = ["provider1", "provider2"]

        def create_client_side_effect(provider):
            if provider == "provider1":
                raise Exception("Provider 1 cost error")
            else:
                return Mock()

        mock_factory.create_client.side_effect = create_client_side_effect

        costs = await facade.calculate_total_costs()

        assert "provider1" in costs
        assert "provider2" in costs
        assert costs["provider1"] == 0.00
        assert costs["provider2"] == 0.00
