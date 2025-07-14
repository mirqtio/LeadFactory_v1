"""
Test stub server endpoints
"""
import json

import pytest
from fastapi.testclient import TestClient

from stubs.server import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


# Yelp has been removed from the codebase - these tests are no longer needed
# class TestYelpStubs - removed


class TestGooglePlacesStubs:
    def test_find_place_success(self, client):
        """Test Google Places Find Place returns data"""
        response = client.get(
            "/maps/api/place/findplacefromtext/json",
            params={
                "input": "Example Business, New York",
                "inputtype": "textquery",
                "fields": "place_id,name,formatted_address",
                "key": "test-key",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "OK"
        assert "candidates" in data
        assert len(data["candidates"]) > 0

        candidate = data["candidates"][0]
        assert "place_id" in candidate
        assert candidate["place_id"].startswith("ChIJ_stub_")
        assert "name" in candidate
        assert "formatted_address" in candidate

    def test_place_details_with_hours(self, client):
        """Test Google Places Details returns data with hours"""
        # Test multiple times to get both cases
        has_hours = False
        missing_hours = False

        for i in range(10):
            response = client.get(
                "/maps/api/place/details/json",
                params={"place_id": f"ChIJ_test_{i}", "fields": "name,opening_hours,rating", "key": "test-key"},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "OK"
            assert "result" in data

            result = data["result"]
            assert "place_id" in result
            assert "name" in result
            assert "business_status" in result
            assert "rating" in result

            if "opening_hours" in result:
                has_hours = True
                assert "weekday_text" in result["opening_hours"]
                assert len(result["opening_hours"]["weekday_text"]) == 7
            else:
                missing_hours = True

        # Should have both cases (80% have hours, 20% don't)
        assert has_hours, "Some businesses should have hours"
        assert missing_hours, "Some businesses should have missing hours"


class TestPageSpeedStubs:
    def test_pagespeed_analyze_success(self, client):
        """Test PageSpeed analysis returns data"""
        response = client.get(
            "/pagespeedonline/v5/runPagespeed",
            params={"url": "https://example.com", "strategy": "mobile"},
        )

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "lighthouseResult" in data
        assert "categories" in data["lighthouseResult"]

        # Check scores
        categories = data["lighthouseResult"]["categories"]
        assert "performance" in categories
        assert "seo" in categories
        assert "accessibility" in categories
        assert "best-practices" in categories

        # Scores should be between 0 and 1
        for category in categories.values():
            assert 0 <= category["score"] <= 1

        # Check Core Web Vitals
        audits = data["lighthouseResult"]["audits"]
        assert "largest-contentful-paint" in audits
        assert "max-potential-fid" in audits
        assert "cumulative-layout-shift" in audits


class TestStripeStubs:
    def test_create_checkout_session(self, client):
        """Test Stripe checkout session creation"""
        session_data = {
            "payment_method_types": ["card"],
            "line_items": [{"price": "price_test_123", "quantity": 1}],
            "mode": "payment",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
            "client_reference_id": "biz_123",
            "customer_email": "test@example.com",
            "metadata": {"business_id": "123", "source": "email"},
        }

        response = client.post(
            "/v1/checkout/sessions",
            json=session_data,
            headers={"Authorization": "Bearer sk_test_123"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["id"].startswith("cs_test_stub_")
        assert data["payment_intent"].startswith("pi_test_stub_")
        assert data["status"] == "open"
        assert data["customer_email"] == "test@example.com"
        assert data["metadata"]["business_id"] == "123"


class TestSendGridStubs:
    def test_send_email(self, client):
        """Test SendGrid email sending"""
        mail_data = {
            "personalizations": [{"to": [{"email": "test@example.com"}], "subject": "Test Email"}],
            "from_email": {"email": "sender@example.com", "name": "Sender"},
            "subject": "Test Email",
            "content": [{"type": "text/html", "value": "<p>Test content</p>"}],
        }

        response = client.post("/v3/mail/send", json=mail_data, headers={"Authorization": "Bearer SG.test"})

        assert response.status_code == 202
        assert "X-Message-Id" in response.headers
        assert response.headers["X-Message-Id"].startswith("stub-msg-")


class TestOpenAIStubs:
    def test_chat_completion(self, client):
        """Test OpenAI chat completion"""
        completion_data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Analyze this website"}],
            "temperature": 0.3,
            "max_tokens": 500,
        }

        response = client.post(
            "/v1/chat/completions",
            json=completion_data,
            headers={"Authorization": "Bearer sk-test"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["model"] == "gpt-4o-mini"
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["role"] == "assistant"

        # Check it returns valid JSON recommendations
        content = data["choices"][0]["message"]["content"]
        recommendations = json.loads(content)
        assert isinstance(recommendations, list)
        assert len(recommendations) == 3

        # Check recommendation structure
        for rec in recommendations:
            assert "issue" in rec
            assert "impact" in rec
            assert "effort" in rec
            assert "improvement" in rec


class TestWebhooks:
    def test_stripe_webhook_simulation(self, client):
        """Test Stripe webhook event simulation"""
        response = client.post(
            "/webhooks/stripe",
            params={
                "event_type": "checkout.session.completed",
                "session_id": "cs_test_123",
            },
        )

        assert response.status_code == 200
        event = response.json()

        assert event["type"] == "checkout.session.completed"
        assert event["data"]["object"]["id"] == "cs_test_123"
        assert event["data"]["object"]["amount_total"] == 19900

    def test_sendgrid_webhook_simulation(self, client):
        """Test SendGrid webhook event simulation"""
        events = [
            {"email": "test1@example.com", "event": "delivered"},
            {"email": "test2@example.com", "event": "open"},
            {"email": "test3@example.com", "event": "click"},
        ]

        response = client.post("/webhooks/sendgrid", json=events)

        assert response.status_code == 200
        data = response.json()
        assert data["events_processed"] == 3


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["use_stubs"] is True
