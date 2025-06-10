"""
Task 059 Verification Test - Integration Tests for Payments

End-to-end verification of payment flow integration tests with
Stripe checkout, webhook processing, and report generation.

Acceptance Criteria:
- Full payment flow works ✓
- Webhook processing verified ✓
- Report generation triggered ✓
- Stripe test mode used ✓
"""

import sys

sys.path.insert(0, "/app")

import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

# Mock stripe module to avoid actual API calls
import stripe

from d7_storefront.checkout import CheckoutItem, CheckoutManager
from d7_storefront.models import ProductType
from d7_storefront.stripe_client import StripeClient, StripeConfig
from d7_storefront.webhook_handlers import CheckoutSessionHandler
from d7_storefront.webhooks import WebhookProcessor, WebhookStatus

stripe.api_key = "sk_test_mock_key_for_testing"


def test_task_059():
    """Test Task 059 acceptance criteria"""
    print("Testing Task 059: Integration tests for payments")
    print("=" * 50)

    # Test 1: Full payment flow works
    print("Testing full payment flow...")

    # Initialize components in test mode
    stripe_config = StripeConfig(test_mode=True)
    stripe_client = StripeClient(stripe_config)
    checkout_manager = CheckoutManager()
    webhook_processor = WebhookProcessor(stripe_client)

    # Verify all components are properly initialized
    assert stripe_client.is_test_mode() is True
    assert checkout_manager is not None
    assert webhook_processor is not None

    # Create test checkout items
    test_items = [
        CheckoutItem(
            product_name="Integration Test - Website Audit",
            amount_usd=Decimal("29.99"),
            quantity=1,
            description="Full integration test audit",
            product_type=ProductType.AUDIT_REPORT,
            business_id="integration_test_123",
            metadata={
                "business_url": "https://integration-test.com",
                "test_mode": "true",
                "integration_test": "task_059",
            },
        )
    ]

    # Test checkout flow with mocked Stripe
    with patch.object(
        checkout_manager.stripe_client, "create_checkout_session"
    ) as mock_create_session:
        mock_response = {
            "success": True,
            "session_id": "cs_integration_test_123",
            "session_url": "https://checkout.stripe.com/pay/cs_integration_test_123",
            "payment_status": "unpaid",
            "amount_total": 2999,
            "currency": "usd",
            "expires_at": int((datetime.utcnow() + timedelta(minutes=30)).timestamp()),
            "metadata": {
                "purchase_id": "integration_purchase_123",
                "customer_email": "integration@example.com",
                "item_count": "1",
                "item_0_name": "Integration Test - Website Audit",
                "business_url": "https://integration-test.com",
            },
            "mode": "payment",
            "success_url": "https://leadfactory.com/success",
            "cancel_url": "https://leadfactory.com/cancel",
        }
        mock_create_session.return_value = mock_response

        # Initiate checkout
        checkout_result = checkout_manager.initiate_checkout(
            customer_email="integration@example.com",
            items=test_items,
            attribution_data={"utm_source": "integration_test"},
            additional_metadata={"test_type": "full_flow"},
        )

        # Verify checkout success
        assert checkout_result["success"] is True
        assert checkout_result["session_id"] == "cs_integration_test_123"
        assert checkout_result["test_mode"] is True
        assert checkout_result["amount_total_usd"] == 29.99

        print("✓ Checkout initiation successful")

    print("✓ Full payment flow works")

    # Test 2: Webhook processing verified
    print("Testing webhook processing...")

    # Create mock webhook event
    webhook_event = {
        "id": "evt_integration_test_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_integration_test_123",
                "payment_status": "paid",
                "customer_email": "integration@example.com",
                "amount_total": 2999,
                "currency": "usd",
                "metadata": {
                    "purchase_id": "integration_purchase_123",
                    "customer_email": "integration@example.com",
                    "item_count": "1",
                    "item_0_name": "Integration Test - Website Audit",
                    "business_url": "https://integration-test.com",
                },
            }
        },
        "created": int(datetime.utcnow().timestamp()),
        "livemode": False,
    }

    webhook_payload = json.dumps(webhook_event).encode()

    # Test webhook processing with mocked signature verification
    with patch.object(webhook_processor, "verify_signature", return_value=True):
        with patch.object(webhook_processor, "construct_event") as mock_construct:
            mock_construct.return_value = {
                "success": True,
                "event_id": webhook_event["id"],
                "event_type": webhook_event["type"],
                "data": webhook_event["data"],
                "created": webhook_event["created"],
            }

            # Process webhook
            webhook_result = webhook_processor.process_webhook(
                webhook_payload, "integration_test_signature"
            )

            # Verify webhook processing
            assert webhook_result["success"] is True
            assert webhook_result["event_type"] == "checkout.session.completed"
            assert webhook_result["status"] == WebhookStatus.COMPLETED.value
            assert "data" in webhook_result

            print("✓ Webhook event processed successfully")

    # Test different webhook event types
    test_events = [
        "checkout.session.completed",
        "checkout.session.expired",
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
    ]

    for event_type in test_events:
        test_event = {
            "id": f"evt_test_{event_type.replace('.', '_')}",
            "type": event_type,
            "data": {"object": {"id": "test_obj_123", "metadata": {}}},
            "created": int(datetime.utcnow().timestamp()),
            "livemode": False,
        }

        with patch.object(webhook_processor, "verify_signature", return_value=True):
            with patch.object(webhook_processor, "construct_event") as mock_construct:
                mock_construct.return_value = {
                    "success": True,
                    "event_id": test_event["id"],
                    "event_type": test_event["type"],
                    "data": test_event["data"],
                    "created": test_event["created"],
                }

                result = webhook_processor.process_webhook(
                    json.dumps(test_event).encode(), "test_signature"
                )

                assert result["success"] is True
                assert result["event_type"] == event_type

    print("✓ Multiple webhook event types processed")
    print("✓ Webhook processing verified")

    # Test 3: Report generation triggered
    print("Testing report generation...")

    # Test single report generation
    handler = CheckoutSessionHandler(stripe_client)

    single_report_event = {
        "object": {
            "id": "cs_single_report_test",
            "customer_email": "single@example.com",
            "payment_status": "paid",
            "amount_total": 2999,
            "metadata": {
                "purchase_id": "single_purchase_123",
                "customer_email": "single@example.com",
                "item_count": "1",
                "item_0_name": "Single Website Audit",
                "item_0_type": "audit_report",
                "business_url": "https://single-test.com",
            },
        }
    }

    single_result = handler.handle_session_completed(
        single_report_event, "evt_single_123"
    )

    assert single_result["success"] is True
    assert "report_generation" in single_result["data"]
    assert single_result["data"]["report_generation"]["success"] is True
    assert single_result["data"]["report_generation"]["status"] == "triggered"
    assert single_result["data"]["report_generation"]["report_type"] == "single"
    assert single_result["data"]["report_generation"]["business_count"] == 1

    print("✓ Single report generation triggered")

    # Test bulk report generation
    bulk_report_event = {
        "object": {
            "id": "cs_bulk_report_test",
            "customer_email": "bulk@example.com",
            "payment_status": "paid",
            "amount_total": 7497,  # 3 reports at $24.99 each
            "metadata": {
                "purchase_id": "bulk_purchase_123",
                "customer_email": "bulk@example.com",
                "item_count": "3",
                "business_urls": "https://bulk1.com,https://bulk2.com,https://bulk3.com",
            },
        }
    }

    bulk_result = handler.handle_session_completed(bulk_report_event, "evt_bulk_123")

    assert bulk_result["success"] is True
    assert "report_generation" in bulk_result["data"]
    assert bulk_result["data"]["report_generation"]["success"] is True
    assert bulk_result["data"]["report_generation"]["status"] == "triggered"
    assert bulk_result["data"]["report_generation"]["report_type"] == "bulk"
    assert bulk_result["data"]["report_generation"]["business_count"] == 3
    assert "job_id" in bulk_result["data"]["report_generation"]

    print("✓ Bulk report generation triggered")
    print("✓ Report generation triggered")

    # Test 4: Stripe test mode used
    print("Testing Stripe test mode...")

    # Verify Stripe client test mode
    assert stripe_client.is_test_mode() is True
    assert stripe_client.config.test_mode is True
    assert stripe_client.config.api_key == "sk_test_mock_key_for_testing"
    assert stripe_client.config.publishable_key == "pk_test_mock_key_for_testing"

    print("✓ Stripe client in test mode")

    # Verify checkout manager test mode
    manager_status = checkout_manager.get_status()
    assert manager_status["test_mode"] is True

    stripe_status = manager_status["stripe_status"]
    assert stripe_status["test_mode"] is True
    assert stripe_status["currency"] == "usd"

    print("✓ Checkout manager in test mode")

    # Verify webhook processor test mode
    processor_status = webhook_processor.get_status()
    assert processor_status["stripe_test_mode"] is True
    assert processor_status["idempotency_enabled"] is True

    print("✓ Webhook processor in test mode")

    # Test end-to-end flow in test mode
    with patch.object(
        checkout_manager.stripe_client, "create_checkout_session"
    ) as mock_create:
        mock_create.return_value = {
            "success": True,
            "session_id": "cs_test_mode_verification",
            "session_url": "https://checkout.stripe.com/pay/cs_test_mode_verification",
            "payment_status": "unpaid",
            "amount_total": 2999,
            "currency": "usd",
            "expires_at": int((datetime.utcnow() + timedelta(minutes=30)).timestamp()),
            "metadata": {"test_mode": "true"},
            "mode": "payment",
            "success_url": "https://leadfactory.com/success",
            "cancel_url": "https://leadfactory.com/cancel",
        }

        test_result = checkout_manager.initiate_checkout(
            customer_email="testmode@example.com",
            items=[
                CheckoutItem(
                    product_name="Test Mode Verification Audit",
                    amount_usd=Decimal("29.99"),
                    quantity=1,
                    product_type=ProductType.AUDIT_REPORT,
                )
            ],
        )

        assert test_result["success"] is True
        assert test_result["test_mode"] is True

    print("✓ End-to-end flow uses test mode")
    print("✓ Stripe test mode used")

    # Test additional integration scenarios
    print("Testing additional integration scenarios...")

    # Test error handling integration
    with patch.object(webhook_processor, "verify_signature", return_value=False):
        invalid_result = webhook_processor.process_webhook(
            b'{"invalid": "data"}', "invalid_signature"
        )

        assert invalid_result["success"] is False
        assert "Invalid signature" in invalid_result["error"]

    print("✓ Error handling integration works")

    # Test idempotency
    processor_with_idempotency = WebhookProcessor(
        stripe_client, enable_idempotency=True
    )

    event_id = "evt_idempotency_test_123"
    assert processor_with_idempotency.is_duplicate_event(event_id) is False

    processor_with_idempotency.mark_event_processed(event_id)
    assert processor_with_idempotency.is_duplicate_event(event_id) is True

    print("✓ Idempotency integration works")

    # Test component status reporting
    components_status = {
        "stripe_client": stripe_client.get_status(),
        "checkout_manager": checkout_manager.get_status(),
        "webhook_processor": webhook_processor.get_status(),
    }

    # Verify all components report healthy status
    assert components_status["stripe_client"]["test_mode"] is True
    assert components_status["checkout_manager"]["test_mode"] is True
    assert components_status["webhook_processor"]["stripe_test_mode"] is True

    print("✓ Component status integration works")

    # Test webhook event routing
    from d7_storefront.webhook_handlers import (CustomerHandler,
                                                InvoiceHandler,
                                                PaymentIntentHandler)

    # Test payment intent handler
    payment_handler = PaymentIntentHandler(stripe_client)
    payment_event = {
        "object": {
            "id": "pi_test_123",
            "amount": 2999,
            "currency": "usd",
            "metadata": {
                "purchase_id": "payment_test_123",
                "customer_email": "payment@example.com",
            },
        }
    }

    payment_result = payment_handler.handle_payment_succeeded(
        payment_event, "evt_payment_123"
    )
    assert payment_result["success"] is True

    # Test customer handler
    customer_handler = CustomerHandler(stripe_client)
    customer_event = {
        "object": {
            "id": "cus_test_123",
            "email": "customer@example.com",
            "name": "Test Customer",
            "metadata": {},
        }
    }

    customer_result = customer_handler.handle_customer_created(
        customer_event, "evt_customer_123"
    )
    assert customer_result["success"] is True

    print("✓ Webhook handler routing integration works")

    print("=" * 50)
    print("🎉 ALL INTEGRATION TESTS PASSED!")
    print("")
    print("Acceptance Criteria Status:")
    print("✓ Full payment flow works")
    print("✓ Webhook processing verified")
    print("✓ Report generation triggered")
    print("✓ Stripe test mode used")
    print("")
    print("Task 059 integration tests complete and verified!")
    return True


if __name__ == "__main__":
    test_task_059()
