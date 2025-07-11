"""
Tests for D0 Gateway provider implementations
"""
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow

from d0_gateway.providers.openai import OpenAIClient
from d0_gateway.providers.pagespeed import PageSpeedClient
from d0_gateway.providers.sendgrid import SendGridClient
from d0_gateway.providers.stripe import StripeClient
# YelpClient removed - Yelp has been removed from the codebase


# TestYelpClient removed - Yelp has been removed from the codebase


class TestPageSpeedClient:
    @pytest.fixture
    def pagespeed_client(self):
        """Create PageSpeed client for testing"""
        return PageSpeedClient(api_key="test-key")

    def test_pagespeed_client_configuration(self, pagespeed_client):
        """Test PageSpeed client configuration"""
        assert pagespeed_client.provider == "pagespeed"
        assert pagespeed_client._get_base_url() == "https://www.googleapis.com"

        rate_limits = pagespeed_client.get_rate_limit()
        assert rate_limits["daily_limit"] == 25000
        assert rate_limits["burst_limit"] == 50

    def test_pagespeed_cost_calculation(self, pagespeed_client):
        """Test PageSpeed cost calculation"""
        # Free tier operations
        cost = pagespeed_client.calculate_cost("GET:/pagespeedonline/v5/runPagespeed")
        assert cost == Decimal("0.000")

        # Paid tier
        cost = pagespeed_client.calculate_cost("GET:/other")
        assert cost == Decimal("0.004")

    @pytest.mark.asyncio
    async def test_analyze_url(self, pagespeed_client):
        """Test URL analysis"""
        pagespeed_client.make_request = AsyncMock(
            return_value={
                "lighthouseResult": {"categories": {"performance": {"score": 0.85}}}
            }
        )

        result = await pagespeed_client.analyze_url(
            "https://example.com", strategy="mobile"
        )

        pagespeed_client.make_request.assert_called_once()
        args, kwargs = pagespeed_client.make_request.call_args

        assert args[0] == "GET"
        assert args[1] == "/pagespeedonline/v5/runPagespeed"
        assert kwargs["params"]["url"] == "https://example.com"
        assert kwargs["params"]["strategy"] == "mobile"

    def test_extract_opportunities(self, pagespeed_client):
        """Test opportunity extraction from PageSpeed results"""
        pagespeed_result = {
            "lighthouseResult": {
                "audits": {
                    "unused-css-rules": {
                        "score": 0.5,
                        "title": "Remove unused CSS",
                        "description": "Remove dead rules from stylesheets",
                        "details": {"overallSavingsMs": 1500},
                    },
                    "efficient-animated-content": {
                        "score": 0.8,
                        "title": "Use video formats",
                        "description": "Use video for animated content",
                        "details": {"overallSavingsMs": 500},
                    },
                }
            }
        }

        opportunities = pagespeed_client.extract_opportunities(pagespeed_result)

        assert len(opportunities) == 2
        # Should be sorted by savings (highest first)
        assert opportunities[0]["savings_ms"] == 1500
        assert opportunities[0]["impact"] == "high"
        assert opportunities[1]["savings_ms"] == 500
        assert opportunities[1]["impact"] == "medium"


class TestOpenAIClient:
    @pytest.fixture
    def openai_client(self):
        """Create OpenAI client for testing"""
        return OpenAIClient(api_key="test-key")

    def test_openai_client_configuration(self, openai_client):
        """Test OpenAI client configuration"""
        assert openai_client.provider == "openai"
        assert openai_client._get_base_url() == "https://api.openai.com"

        headers = openai_client._get_headers()
        assert "Authorization" in headers
        assert "Bearer" in headers["Authorization"]
        assert headers["Authorization"] in ["Bearer test-key", "Bearer stub-openai-key"]

    def test_openai_cost_calculation(self, openai_client):
        """Test OpenAI cost calculation"""
        cost = openai_client.calculate_cost("POST:/v1/chat/completions")
        # Should be positive cost for AI operations
        assert cost > Decimal("0.000")
        assert cost < Decimal("0.01")  # Should be reasonable

    @pytest.mark.asyncio
    async def test_chat_completion(self, openai_client):
        """Test chat completion"""
        openai_client.make_request = AsyncMock(
            return_value={
                "choices": [{"message": {"content": "Test response"}}],
                "model": "gpt-4o-mini",
            }
        )

        messages = [{"role": "user", "content": "Hello"}]
        result = await openai_client.chat_completion(messages)

        openai_client.make_request.assert_called_once()
        args, kwargs = openai_client.make_request.call_args

        assert args[0] == "POST"
        assert args[1] == "/v1/chat/completions"
        assert kwargs["json"]["messages"] == messages
        assert kwargs["json"]["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_analyze_website_performance(self, openai_client):
        """Test website performance analysis"""
        # Mock AI response
        openai_client.chat_completion = AsyncMock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": '[{"issue": "Slow loading", "impact": "high", "effort": "medium", "improvement": "Optimize images"}]'
                        }
                    }
                ],
                "model": "gpt-4o-mini",
                "usage": {"total_tokens": 500},
            }
        )

        pagespeed_data = {
            "id": "https://example.com",
            "lighthouseResult": {
                "categories": {"performance": {"score": 0.6}, "seo": {"score": 0.8}}
            },
        }

        result = await openai_client.analyze_website_performance(pagespeed_data)

        assert result["url"] == "https://example.com"
        assert "ai_recommendations" in result
        assert "performance_summary" in result
        assert result["performance_summary"]["performance_score"] == 0.6


class TestSendGridClient:
    @pytest.fixture
    def sendgrid_client(self):
        """Create SendGrid client for testing"""
        return SendGridClient(api_key="test-key")

    def test_sendgrid_client_configuration(self, sendgrid_client):
        """Test SendGrid client configuration"""
        assert sendgrid_client.provider == "sendgrid"
        assert sendgrid_client._get_base_url() == "https://api.sendgrid.com"

        rate_limits = sendgrid_client.get_rate_limit()
        assert rate_limits["daily_limit"] == 100000

    def test_sendgrid_cost_calculation(self, sendgrid_client):
        """Test SendGrid cost calculation"""
        cost = sendgrid_client.calculate_cost("POST:/v3/mail/send")
        assert cost == Decimal("0.0006")

    @pytest.mark.asyncio
    async def test_send_email(self, sendgrid_client):
        """Test email sending"""
        sendgrid_client.make_request = AsyncMock(return_value={"message": "success"})

        result = await sendgrid_client.send_email(
            to_email="test@example.com",
            subject="Test Email",
            html_content="<p>Test</p>",
            from_email="sender@example.com",
        )

        sendgrid_client.make_request.assert_called_once()
        args, kwargs = sendgrid_client.make_request.call_args

        assert args[0] == "POST"
        assert args[1] == "/v3/mail/send"

        payload = kwargs["json"]
        assert payload["personalizations"][0]["to"][0]["email"] == "test@example.com"
        assert payload["personalizations"][0]["subject"] == "Test Email"
        assert payload["from"]["email"] == "sender@example.com"

    def test_format_email_for_lead_outreach(self, sendgrid_client):
        """Test email formatting for lead outreach"""
        website_issues = [
            {"issue": "Slow loading", "improvement": "Optimize images"},
            {"issue": "Poor SEO", "improvement": "Add meta tags"},
        ]

        email_data = sendgrid_client.format_email_for_lead_outreach(
            business_name="Test Business",
            recipient_email="owner@testbusiness.com",
            website_issues=website_issues,
        )

        assert email_data["to_email"] == "owner@testbusiness.com"
        assert "Test Business" in email_data["subject"]
        assert "Test Business" in email_data["html_content"]
        assert "Slow loading" in email_data["html_content"]
        assert email_data["custom_args"]["business_name"] == "Test Business"
        assert email_data["custom_args"]["issues_count"] == "2"


class TestStripeClient:
    @pytest.fixture
    def stripe_client(self):
        """Create Stripe client for testing"""
        return StripeClient(api_key="test-key")

    def test_stripe_client_configuration(self, stripe_client):
        """Test Stripe client configuration"""
        assert stripe_client.provider == "stripe"
        assert stripe_client._get_base_url() == "https://api.stripe.com"

        headers = stripe_client._get_headers()
        assert "application/x-www-form-urlencoded" in headers["Content-Type"]

    def test_stripe_cost_calculation(self, stripe_client):
        """Test Stripe cost calculation"""
        # API calls are free
        cost = stripe_client.calculate_cost("POST:/v1/charges")
        assert cost == Decimal("0.000")

    @pytest.mark.asyncio
    async def test_create_checkout_session(self, stripe_client):
        """Test checkout session creation"""
        stripe_client.make_request = AsyncMock(
            return_value={
                "id": "cs_test_123",
                "url": "https://checkout.stripe.com/pay/cs_test_123",
            }
        )

        result = await stripe_client.create_checkout_session(
            price_id="price_123",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            customer_email="test@example.com",
        )

        stripe_client.make_request.assert_called_once()
        args, kwargs = stripe_client.make_request.call_args

        assert args[0] == "POST"
        assert args[1] == "/v1/checkout/sessions"

        data = kwargs["data"]
        assert data["line_items[0][price]"] == "price_123"
        assert data["success_url"] == "https://example.com/success"
        assert data["customer_email"] == "test@example.com"

    def test_format_checkout_session_for_report(self, stripe_client):
        """Test checkout session formatting for report purchase"""
        session_data = stripe_client.format_checkout_session_for_report(
            business_name="Test Business",
            business_id="biz_123",
            customer_email="owner@test.com",
            report_url="https://example.com/report",
        )

        assert session_data["customer_email"] == "owner@test.com"
        assert session_data["client_reference_id"] == "biz_123"
        assert session_data["metadata"]["business_name"] == "Test Business"
        assert session_data["metadata"]["product_type"] == "website_report"
        assert "https://example.com/report" in session_data["success_url"]
