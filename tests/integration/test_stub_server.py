"""
Test stub server endpoints
"""
import pytest
from fastapi.testclient import TestClient
import json

from stubs.server import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


class TestYelpStubs:
    def test_yelp_search_success(self, client):
        """Test Yelp search returns businesses"""
        response = client.get(
            "/v3/businesses/search",
            params={
                "location": "New York, NY",
                "categories": "restaurant",
                "limit": 10,
                "offset": 0
            },
            headers={"Authorization": "Bearer test-key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "businesses" in data
        assert "total" in data
        assert len(data["businesses"]) == 10

        # Check business structure
        business = data["businesses"][0]
        assert "id" in business
        assert business["id"].startswith("stub-yelp-")
        assert "name" in business
        assert "rating" in business
        assert 3.0 <= business["rating"] <= 5.0
        assert "location" in business
        assert "phone" in business

    def test_yelp_search_pagination(self, client):
        """Test Yelp search pagination"""
        # First page
        response1 = client.get(
            "/v3/businesses/search",
            params={"location": "NYC", "limit": 50, "offset": 0}
        )
        assert response1.status_code == 200
        data1 = response1.json()

        # Second page
        response2 = client.get(
            "/v3/businesses/search",
            params={"location": "NYC", "limit": 50, "offset": 50}
        )
        assert response2.status_code == 200
        data2 = response2.json()

        # Should have different businesses
        ids1 = {b["id"] for b in data1["businesses"]}
        ids2 = {b["id"] for b in data2["businesses"]}
        assert len(ids1.intersection(ids2)) == 0


class TestPageSpeedStubs:
    def test_pagespeed_analyze_success(self, client):
        """Test PageSpeed analysis returns data"""
        response = client.get(
            "/pagespeedonline/v5/runPagespeed",
            params={
                "url": "https://example.com",
                "strategy": "mobile"
            }
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
            "line_items": [{
                "price": "price_test_123",
                "quantity": 1
            }],
            "mode": "payment",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
            "client_reference_id": "biz_123",
            "customer_email": "test@example.com",
            "metadata": {
                "business_id": "123",
                "source": "email"
            }
        }

        response = client.post(
            "/v1/checkout/sessions",
            json=session_data,
            headers={"Authorization": "Bearer sk_test_123"}
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
            "personalizations": [{
                "to": [{"email": "test@example.com"}],
                "subject": "Test Email"
            }],
            "from_email": {"email": "sender@example.com", "name": "Sender"},
            "subject": "Test Email",
            "content": [{
                "type": "text/html",
                "value": "<p>Test content</p>"
            }]
        }

        response = client.post(
            "/v3/mail/send",
            json=mail_data,
            headers={"Authorization": "Bearer SG.test"}
        )

        assert response.status_code == 202
        assert "X-Message-Id" in response.headers
        assert response.headers["X-Message-Id"].startswith("stub-msg-")


class TestOpenAIStubs:
    def test_chat_completion(self, client):
        """Test OpenAI chat completion"""
        completion_data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": "Analyze this website"}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }

        response = client.post(
            "/v1/chat/completions",
            json=completion_data,
            headers={"Authorization": "Bearer sk-test"}
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
                "session_id": "cs_test_123"
            }
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
            {"email": "test3@example.com", "event": "click"}
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
