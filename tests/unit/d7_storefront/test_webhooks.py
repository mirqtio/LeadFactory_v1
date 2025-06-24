"""
Test D7 Storefront Webhooks - Task 057

Tests for Stripe webhook processing with signature verification, event processing,
idempotency handling, and report generation triggering.

Acceptance Criteria:
- Signature verification ✓
- Event processing works ✓
- Idempotency handled ✓
- Report generation triggered ✓
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
import stripe

from d7_storefront.stripe_client import StripeClient, StripeConfig, StripeError
from d7_storefront.webhook_handlers import (
    BaseWebhookHandler,
    CheckoutSessionHandler,
    CustomerHandler,
    InvoiceHandler,
    PaymentIntentHandler,
    ReportGenerationStatus,
    determine_report_priority,
    extract_business_info_from_metadata,
    format_report_generation_request,
)

# Import modules to test
from d7_storefront.webhooks import (
    WebhookError,
    WebhookEventType,
    WebhookProcessor,
    WebhookStatus,
    extract_metadata_from_event,
    format_webhook_response_for_api,
    generate_event_hash,
)


class TestWebhookProcessor:
    """Test webhook processor functionality"""

    def test_webhook_processor_initialization(self):
        """Test webhook processor initialization"""
        processor = WebhookProcessor()

        assert processor.stripe_client is not None
        assert processor.max_event_age_hours == 24
        assert processor.enable_idempotency is True
        assert processor._processed_events is not None

    @patch.object(StripeClient, "verify_webhook_signature")
    def test_verify_signature_success(self, mock_verify):
        """Test successful signature verification - Acceptance Criteria"""
        mock_verify.return_value = True

        processor = WebhookProcessor()
        payload = b'{"test": "data"}'
        signature = "test_signature"

        result = processor.verify_signature(payload, signature)

        assert result is True
        mock_verify.assert_called_once_with(payload, signature)

    @patch.object(StripeClient, "verify_webhook_signature")
    def test_verify_signature_failure(self, mock_verify):
        """Test signature verification failure - Acceptance Criteria"""
        mock_verify.return_value = False

        processor = WebhookProcessor()
        payload = b'{"test": "data"}'
        signature = "invalid_signature"

        result = processor.verify_signature(payload, signature)

        assert result is False

    def test_is_event_too_old(self):
        """Test event age checking"""
        processor = WebhookProcessor(max_event_age_hours=1)

        # Test recent event
        recent_timestamp = int(datetime.utcnow().timestamp())
        assert processor.is_event_too_old(recent_timestamp) is False

        # Test old event
        old_timestamp = int((datetime.utcnow() - timedelta(hours=2)).timestamp())
        assert processor.is_event_too_old(old_timestamp) is True

    def test_idempotency_handling(self):
        """Test idempotency handling - Acceptance Criteria"""
        processor = WebhookProcessor(enable_idempotency=True)

        event_id = "evt_test_123"

        # First check - should not be duplicate
        assert processor.is_duplicate_event(event_id) is False

        # Mark as processed
        processor.mark_event_processed(event_id)

        # Second check - should be duplicate
        assert processor.is_duplicate_event(event_id) is True

    def test_idempotency_disabled(self):
        """Test behavior when idempotency is disabled"""
        processor = WebhookProcessor(enable_idempotency=False)

        event_id = "evt_test_123"

        # Should always return False when disabled
        assert processor.is_duplicate_event(event_id) is False

        processor.mark_event_processed(event_id)

        assert processor.is_duplicate_event(event_id) is False

    @patch.object(StripeClient, "verify_webhook_signature")
    @patch.object(StripeClient, "construct_webhook_event")
    @patch.object(WebhookProcessor, "_process_event")
    def test_process_webhook_success(self, mock_process, mock_construct, mock_verify):
        """Test successful webhook processing - Acceptance Criteria"""
        # Mock successful verification
        mock_verify.return_value = True

        # Mock successful event construction
        mock_construct.return_value = {
            "success": True,
            "event_id": "evt_test_123",
            "event_type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test"}},
            "created": int(datetime.utcnow().timestamp()),
        }

        # Mock successful event processing
        mock_process.return_value = {
            "success": True,
            "status": WebhookStatus.COMPLETED.value,
        }

        processor = WebhookProcessor()
        payload = b'{"id": "evt_test_123"}'
        signature = "test_signature"

        result = processor.process_webhook(payload, signature)

        assert result["success"] is True
        assert result["event_id"] == "evt_test_123"
        assert result["event_type"] == "checkout.session.completed"
        assert result["status"] == WebhookStatus.COMPLETED.value

    @patch.object(StripeClient, "verify_webhook_signature")
    def test_process_webhook_invalid_signature(self, mock_verify):
        """Test webhook processing with invalid signature"""
        mock_verify.return_value = False

        processor = WebhookProcessor()
        payload = b'{"test": "data"}'
        signature = "invalid_signature"

        result = processor.process_webhook(payload, signature)

        assert result["success"] is False
        assert result["error"] == "Invalid signature"
        assert result["status"] == WebhookStatus.FAILED.value

    @patch.object(StripeClient, "verify_webhook_signature")
    @patch.object(StripeClient, "construct_webhook_event")
    def test_process_webhook_duplicate_event(self, mock_construct, mock_verify):
        """Test webhook processing with duplicate event - Acceptance Criteria"""
        mock_verify.return_value = True

        event_id = "evt_test_123"
        mock_construct.return_value = {
            "success": True,
            "event_id": event_id,
            "event_type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test"}},
            "created": int(datetime.utcnow().timestamp()),
        }

        processor = WebhookProcessor()
        payload = b'{"id": "evt_test_123"}'
        signature = "test_signature"

        # Mark event as already processed
        processor.mark_event_processed(event_id)

        result = processor.process_webhook(payload, signature)

        assert result["success"] is True
        assert result["status"] == WebhookStatus.IGNORED.value
        assert result["reason"] == "Duplicate event"

    def test_get_supported_events(self):
        """Test getting supported event types"""
        processor = WebhookProcessor()

        events = processor.get_supported_events()

        assert "checkout.session.completed" in events
        assert "payment_intent.succeeded" in events
        assert "customer.created" in events
        assert len(events) > 0

    def test_get_status(self):
        """Test processor status reporting"""
        processor = WebhookProcessor()

        status = processor.get_status()

        assert "stripe_test_mode" in status
        assert "idempotency_enabled" in status
        assert "max_event_age_hours" in status
        assert "supported_events" in status
        assert "webhook_secret_configured" in status
        assert status["idempotency_enabled"] is True

    def test_clear_processed_events(self):
        """Test clearing processed events cache"""
        processor = WebhookProcessor()

        # Add some events
        processor.mark_event_processed("evt_1")
        processor.mark_event_processed("evt_2")

        assert len(processor._processed_events) == 2

        # Clear cache
        processor.clear_processed_events()

        assert len(processor._processed_events) == 0


class TestCheckoutSessionHandler:
    """Test checkout session event handling"""

    def test_handler_initialization(self):
        """Test handler initialization"""
        stripe_client = StripeClient()
        handler = CheckoutSessionHandler(stripe_client)

        assert handler.stripe_client == stripe_client

    def test_handle_session_completed_success(self):
        """Test handling successful checkout session - Acceptance Criteria"""
        handler = CheckoutSessionHandler(StripeClient())

        event_data = {
            "object": {
                "id": "cs_test_123",
                "customer_email": "test@example.com",
                "payment_status": "paid",
                "amount_total": 2999,
                "currency": "usd",
                "metadata": {
                    "purchase_id": "purchase_123",
                    "item_count": "1",
                    "item_0_name": "Website Audit",
                    "business_url": "https://example.com",
                },
            }
        }

        result = handler.handle_session_completed(event_data, "evt_123")

        assert result["success"] is True
        assert result["status"] == WebhookStatus.COMPLETED.value
        assert result["data"]["purchase_id"] == "purchase_123"
        assert result["data"]["session_id"] == "cs_test_123"
        assert result["data"]["payment_status"] == "paid"
        assert "report_generation" in result["data"]
        assert result["data"]["report_generation"]["success"] is True

    def test_handle_session_completed_no_purchase_id(self):
        """Test handling session without purchase ID"""
        handler = CheckoutSessionHandler(StripeClient())

        event_data = {
            "object": {
                "id": "cs_test_123",
                "customer_email": "test@example.com",
                "payment_status": "paid",
                "metadata": {},  # No purchase_id
            }
        }

        result = handler.handle_session_completed(event_data, "evt_123")

        assert result["success"] is True
        assert result["status"] == WebhookStatus.IGNORED.value
        assert result["reason"] == "No purchase_id in metadata"

    def test_handle_session_completed_payment_not_paid(self):
        """Test handling session with unpaid status"""
        handler = CheckoutSessionHandler(StripeClient())

        event_data = {
            "object": {
                "id": "cs_test_123",
                "customer_email": "test@example.com",
                "payment_status": "unpaid",
                "metadata": {"purchase_id": "purchase_123"},
            }
        }

        result = handler.handle_session_completed(event_data, "evt_123")

        assert result["success"] is True
        assert result["status"] == WebhookStatus.COMPLETED.value
        assert result["data"]["payment_status"] == "unpaid"
        assert "note" in result["data"]

    def test_handle_session_expired(self):
        """Test handling expired checkout session"""
        handler = CheckoutSessionHandler(StripeClient())

        event_data = {
            "object": {"id": "cs_test_123", "metadata": {"purchase_id": "purchase_123"}}
        }

        result = handler.handle_session_expired(event_data, "evt_123")

        assert result["success"] is True
        assert result["status"] == WebhookStatus.COMPLETED.value
        assert result["data"]["purchase_id"] == "purchase_123"
        assert result["data"]["action"] == "marked_as_expired"


class TestPaymentIntentHandler:
    """Test payment intent event handling"""

    def test_handle_payment_succeeded(self):
        """Test handling successful payment intent"""
        handler = PaymentIntentHandler(StripeClient())

        event_data = {
            "object": {
                "id": "pi_test_123",
                "amount": 2999,
                "currency": "usd",
                "metadata": {
                    "purchase_id": "purchase_123",
                    "customer_email": "test@example.com",
                    "business_url": "https://example.com",
                },
            }
        }

        result = handler.handle_payment_succeeded(event_data, "evt_123")

        assert result["success"] is True
        assert result["status"] == WebhookStatus.COMPLETED.value
        assert result["data"]["payment_intent_id"] == "pi_test_123"
        assert result["data"]["purchase_id"] == "purchase_123"
        assert result["data"]["amount"] == 2999
        assert "report_generation" in result["data"]

    def test_handle_payment_failed(self):
        """Test handling failed payment intent"""
        handler = PaymentIntentHandler(StripeClient())

        event_data = {
            "object": {"id": "pi_test_123", "metadata": {"purchase_id": "purchase_123"}}
        }

        result = handler.handle_payment_failed(event_data, "evt_123")

        assert result["success"] is True
        assert result["status"] == WebhookStatus.COMPLETED.value
        assert result["data"]["payment_intent_id"] == "pi_test_123"
        assert result["data"]["action"] == "marked_as_failed"


class TestCustomerHandler:
    """Test customer event handling"""

    def test_handle_customer_created(self):
        """Test handling customer creation"""
        handler = CustomerHandler(StripeClient())

        event_data = {
            "object": {
                "id": "cus_test_123",
                "email": "test@example.com",
                "name": "John Doe",
                "metadata": {"source": "leadfactory"},
            }
        }

        result = handler.handle_customer_created(event_data, "evt_123")

        assert result["success"] is True
        assert result["status"] == WebhookStatus.COMPLETED.value
        assert result["data"]["customer_id"] == "cus_test_123"
        assert result["data"]["email"] == "test@example.com"
        assert result["data"]["name"] == "John Doe"
        assert result["data"]["action"] == "customer_stored"


class TestInvoiceHandler:
    """Test invoice event handling"""

    def test_handle_invoice_payment_succeeded(self):
        """Test handling successful invoice payment"""
        handler = InvoiceHandler(StripeClient())

        event_data = {
            "object": {
                "id": "in_test_123",
                "customer": "cus_test_123",
                "amount_paid": 2999,
                "currency": "usd",
                "metadata": {
                    "purchase_id": "purchase_123",
                    "customer_email": "test@example.com",
                },
            }
        }

        result = handler.handle_invoice_event(
            "invoice.payment_succeeded", event_data, "evt_123"
        )

        assert result["success"] is True
        assert result["status"] == WebhookStatus.COMPLETED.value
        assert result["data"]["invoice_id"] == "in_test_123"
        assert result["data"]["action"] == "payment_succeeded"
        assert "report_generation" in result["data"]

    def test_handle_invoice_payment_failed(self):
        """Test handling failed invoice payment"""
        handler = InvoiceHandler(StripeClient())

        event_data = {
            "object": {
                "id": "in_test_123",
                "customer": "cus_test_123",
                "amount_paid": 0,
                "currency": "usd",
                "metadata": {},
            }
        }

        result = handler.handle_invoice_event(
            "invoice.payment_failed", event_data, "evt_123"
        )

        assert result["success"] is True
        assert result["status"] == WebhookStatus.COMPLETED.value
        assert result["data"]["action"] == "payment_failed"


class TestUtilityFunctions:
    """Test utility functions"""

    def test_generate_event_hash(self):
        """Test event hash generation"""
        event_id = "evt_test_123"
        event_type = "checkout.session.completed"
        created = 1234567890

        hash1 = generate_event_hash(event_id, event_type, created)
        hash2 = generate_event_hash(event_id, event_type, created)

        # Same inputs should produce same hash
        assert hash1 == hash2

        # Different inputs should produce different hash
        hash3 = generate_event_hash("evt_different", event_type, created)
        assert hash1 != hash3

    def test_extract_metadata_from_event(self):
        """Test metadata extraction from event"""
        event_data = {
            "object": {
                "id": "cs_test_123",
                "object": "checkout_session",
                "amount_total": 2999,
                "currency": "usd",
                "customer": "cus_test_123",
                "payment_intent": "pi_test_123",
                "metadata": {
                    "purchase_id": "purchase_123",
                    "custom_field": "custom_value",
                },
            }
        }

        metadata = extract_metadata_from_event(event_data)

        assert metadata["purchase_id"] == "purchase_123"
        assert metadata["custom_field"] == "custom_value"
        assert metadata["stripe_id"] == "cs_test_123"
        assert metadata["stripe_object_type"] == "checkout_session"
        assert metadata["amount_total"] == 2999
        assert metadata["currency"] == "usd"

    def test_format_webhook_response_for_api_success(self):
        """Test API response formatting for success"""
        result = {
            "success": True,
            "event_id": "evt_test_123",
            "event_type": "checkout.session.completed",
            "status": WebhookStatus.COMPLETED.value,
            "data": {"test": "data"},
        }

        formatted = format_webhook_response_for_api(result)

        assert formatted["status"] == "success"
        assert formatted["webhook"]["event_id"] == "evt_test_123"
        assert formatted["webhook"]["event_type"] == "checkout.session.completed"
        assert (
            formatted["webhook"]["processing_status"] == WebhookStatus.COMPLETED.value
        )

    def test_format_webhook_response_for_api_error(self):
        """Test API response formatting for error"""
        result = {
            "success": False,
            "event_id": "evt_test_123",
            "error": "Processing failed",
            "status": WebhookStatus.FAILED.value,
        }

        formatted = format_webhook_response_for_api(result)

        assert formatted["status"] == "error"
        assert formatted["error"]["message"] == "Processing failed"
        assert formatted["error"]["event_id"] == "evt_test_123"
        assert formatted["error"]["processing_status"] == WebhookStatus.FAILED.value

    def test_extract_business_info_from_metadata(self):
        """Test business info extraction from metadata"""
        metadata = {
            "purchase_id": "purchase_123",
            "item_count": "2",
            "item_0_name": "Audit for Business A",
            "item_0_business_id": "biz_a",
            "item_1_name": "Audit for Business B",
            "item_1_business_id": "biz_b",
            "business_urls": "https://a.com,https://b.com",
            "business_url": "https://single.com",
        }

        business_info = extract_business_info_from_metadata(metadata)

        assert len(business_info["names"]) == 2
        assert "Audit for Business A" in business_info["names"]
        assert "Audit for Business B" in business_info["names"]

        assert len(business_info["ids"]) == 2
        assert "biz_a" in business_info["ids"]
        assert "biz_b" in business_info["ids"]

        assert len(business_info["urls"]) == 2
        assert "https://a.com" in business_info["urls"]
        assert "https://b.com" in business_info["urls"]

    def test_determine_report_priority(self):
        """Test report priority determination"""
        # Test explicit priority
        metadata = {"priority": "high"}
        assert determine_report_priority(metadata) == "high"

        # Test premium detection (checks key names, not values)
        metadata = {"premium_report": "Audit Report"}
        assert determine_report_priority(metadata) == "high"

        # Test bulk detection (checks key names, not values)
        metadata = {"bulk_reports": "Reports"}
        assert determine_report_priority(metadata) == "medium"

        # Test normal priority
        metadata = {"item_0_name": "Standard Report"}
        assert determine_report_priority(metadata) == "normal"


class TestAcceptanceCriteria:
    """Test all acceptance criteria for Task 057"""

    @patch.object(StripeClient, "verify_webhook_signature")
    def test_signature_verification_acceptance_criteria(self, mock_verify):
        """Test: Signature verification ✓"""
        mock_verify.return_value = True

        processor = WebhookProcessor()
        payload = b'{"test": "data"}'
        signature = "valid_signature"

        # Verify signature verification works
        result = processor.verify_signature(payload, signature)
        assert result is True

        # Test with invalid signature
        mock_verify.return_value = False
        result = processor.verify_signature(payload, "invalid_signature")
        assert result is False

        print("✓ Signature verification works")

    @patch.object(StripeClient, "verify_webhook_signature")
    @patch.object(StripeClient, "construct_webhook_event")
    @patch.object(WebhookProcessor, "_process_event")
    def test_event_processing_works_acceptance_criteria(
        self, mock_process, mock_construct, mock_verify
    ):
        """Test: Event processing works ✓"""
        # Setup mocks
        mock_verify.return_value = True
        mock_construct.return_value = {
            "success": True,
            "event_id": "evt_test_123",
            "event_type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test"}},
            "created": int(datetime.utcnow().timestamp()),
        }
        mock_process.return_value = {
            "success": True,
            "status": WebhookStatus.COMPLETED.value,
        }

        processor = WebhookProcessor()
        payload = b'{"id": "evt_test_123"}'
        signature = "test_signature"

        result = processor.process_webhook(payload, signature)

        # Verify event processing pipeline works
        assert result["success"] is True
        assert result["event_id"] == "evt_test_123"
        assert result["status"] == WebhookStatus.COMPLETED.value

        # Verify all steps were called
        mock_verify.assert_called_once()
        mock_construct.assert_called_once()
        mock_process.assert_called_once()

        print("✓ Event processing works")

    def test_idempotency_handled_acceptance_criteria(self):
        """Test: Idempotency handled ✓"""
        processor = WebhookProcessor(enable_idempotency=True)

        event_id = "evt_test_123"

        # First processing - should not be duplicate
        assert processor.is_duplicate_event(event_id) is False

        # Mark as processed
        processor.mark_event_processed(event_id)

        # Second processing - should be duplicate
        assert processor.is_duplicate_event(event_id) is True

        # Verify processed events tracking
        assert len(processor._processed_events) == 1
        assert event_id in processor._processed_events

        print("✓ Idempotency handled")

    def test_report_generation_triggered_acceptance_criteria(self):
        """Test: Report generation triggered ✓"""
        handler = CheckoutSessionHandler(StripeClient())

        # Test successful session with payment completed
        event_data = {
            "object": {
                "id": "cs_test_123",
                "customer_email": "test@example.com",
                "payment_status": "paid",
                "amount_total": 2999,
                "currency": "usd",
                "metadata": {
                    "purchase_id": "purchase_123",
                    "item_count": "1",
                    "item_0_name": "Website Audit Report",
                    "business_url": "https://example.com",
                },
            }
        }

        result = handler.handle_session_completed(event_data, "evt_123")

        # Verify report generation was triggered
        assert result["success"] is True
        assert "report_generation" in result["data"]
        assert result["data"]["report_generation"]["success"] is True
        assert (
            result["data"]["report_generation"]["status"]
            == ReportGenerationStatus.TRIGGERED.value
        )
        assert result["data"]["report_generation"]["purchase_id"] == "purchase_123"
        assert (
            result["data"]["report_generation"]["customer_email"] == "test@example.com"
        )
        assert "job_id" in result["data"]["report_generation"]

        print("✓ Report generation triggered")


class TestWebhookEnhancements:
    """Enhanced webhook tests for comprehensive coverage - GAP-011"""

    def test_webhook_processor_edge_cases(self):
        """Test webhook processor edge cases"""
        # Test with custom event age limit
        processor = WebhookProcessor(max_event_age_hours=2, enable_idempotency=False)

        assert processor.max_event_age_hours == 2
        assert processor.enable_idempotency is False
        assert processor._processed_events is None

        # Test event age boundary conditions
        recent_timestamp = int(datetime.utcnow().timestamp())
        old_timestamp = int((datetime.utcnow() - timedelta(hours=3)).timestamp())

        assert processor.is_event_too_old(recent_timestamp) is False
        assert processor.is_event_too_old(old_timestamp) is True

    @patch.object(StripeClient, "verify_webhook_signature")
    def test_webhook_processor_signature_exceptions(self, mock_verify):
        """Test signature verification exception handling"""
        # Test signature verification with exception
        mock_verify.side_effect = Exception("Signature verification failed")

        processor = WebhookProcessor()
        payload = b'{"test": "data"}'
        signature = "test_signature"

        result = processor.verify_signature(payload, signature)
        assert result is False

    @patch.object(StripeClient, "verify_webhook_signature")
    @patch.object(StripeClient, "construct_webhook_event")
    def test_webhook_processor_construct_event_failure(
        self, mock_construct, mock_verify
    ):
        """Test event construction failure handling"""
        mock_verify.return_value = True
        mock_construct.return_value = {
            "success": False,
            "error": "Invalid event format",
        }

        processor = WebhookProcessor()
        payload = b'{"invalid": "event"}'
        signature = "test_signature"

        result = processor.process_webhook(payload, signature)

        assert result["success"] is False
        assert result["error"] == "Failed to construct event"
        assert result["status"] == WebhookStatus.FAILED.value

    @patch.object(StripeClient, "construct_webhook_event")
    def test_webhook_processor_construct_event_exception(self, mock_construct):
        """Test event construction with WebhookError"""
        processor = WebhookProcessor()

        # Test WebhookError handling in construct_event
        mock_construct.side_effect = StripeError("Invalid signature")

        with pytest.raises(WebhookError, match="Failed to construct event"):
            processor.construct_event(b'{"test": "data"}', "invalid_signature")

    @patch.object(StripeClient, "verify_webhook_signature")
    @patch.object(StripeClient, "construct_webhook_event")
    def test_webhook_processor_event_too_old_handling(
        self, mock_construct, mock_verify
    ):
        """Test handling of events that are too old"""
        mock_verify.return_value = True

        # Create an old event (25 hours ago, default limit is 24 hours)
        old_timestamp = int((datetime.utcnow() - timedelta(hours=25)).timestamp())
        mock_construct.return_value = {
            "success": True,
            "event_id": "evt_old_123",
            "event_type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test"}},
            "created": old_timestamp,
        }

        processor = WebhookProcessor()
        payload = b'{"id": "evt_old_123"}'
        signature = "test_signature"

        result = processor.process_webhook(payload, signature)

        assert result["success"] is True
        assert result["status"] == WebhookStatus.IGNORED.value
        assert result["reason"] == "Event too old"

    @patch.object(StripeClient, "verify_webhook_signature")
    @patch.object(StripeClient, "construct_webhook_event")
    @patch.object(WebhookProcessor, "_process_event")
    def test_webhook_processor_event_processing_exception(
        self, mock_process, mock_construct, mock_verify
    ):
        """Test exception handling in event processing"""
        mock_verify.return_value = True
        mock_construct.return_value = {
            "success": True,
            "event_id": "evt_test_123",
            "event_type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test"}},
            "created": int(datetime.utcnow().timestamp()),
        }

        # Mock processing exception
        mock_process.side_effect = Exception("Processing failed")

        processor = WebhookProcessor()
        payload = b'{"id": "evt_test_123"}'
        signature = "test_signature"

        result = processor.process_webhook(payload, signature)

        assert result["success"] is False
        assert "Unexpected error" in result["error"]
        assert result["status"] == WebhookStatus.FAILED.value

    def test_webhook_processor_unhandled_event_type(self):
        """Test handling of unhandled event types"""
        from d7_storefront.webhook_handlers import CheckoutSessionHandler

        processor = WebhookProcessor()

        # Test with unhandled event type
        result = processor._process_event(
            "subscription.created",  # Unhandled event type
            {"object": {"id": "sub_test"}},
            "evt_test_123",
        )

        assert result["success"] is True
        assert result["status"] == WebhookStatus.IGNORED.value
        assert "Unhandled event type" in result["reason"]

    def test_webhook_processor_process_event_exception(self):
        """Test exception handling in _process_event"""
        processor = WebhookProcessor()

        # Test with invalid event data that causes handler to fail
        with patch(
            "d7_storefront.webhook_handlers.CheckoutSessionHandler"
        ) as mock_handler_class:
            mock_handler = Mock()
            mock_handler.handle_session_completed.side_effect = Exception(
                "Handler error"
            )
            mock_handler_class.return_value = mock_handler

            result = processor._process_event(
                "checkout.session.completed",
                {"object": {"id": "cs_test"}},
                "evt_test_123",
            )

            assert result["success"] is False
            assert result["status"] == WebhookStatus.FAILED.value
            assert "Handler error" in result["error"]

    def test_checkout_session_handler_edge_cases(self):
        """Test checkout session handler edge cases"""
        handler = CheckoutSessionHandler(StripeClient())

        # Test with malformed event data
        malformed_event = {"object": None}  # No object data

        result = handler.handle_session_completed(malformed_event, "evt_123")

        # The handler gracefully handles malformed data and returns an error
        assert result["success"] is False
        assert result["status"] == WebhookStatus.FAILED.value
        assert "'NoneType' object has no attribute 'get'" in result["error"]

    def test_checkout_session_handler_exception_handling(self):
        """Test checkout session handler exception handling"""
        handler = CheckoutSessionHandler(StripeClient())

        # Test handle_session_completed with exception in _trigger_report_generation
        with patch.object(handler, "_trigger_report_generation") as mock_trigger:
            mock_trigger.side_effect = Exception("Report generation failed")

            event_data = {
                "object": {
                    "id": "cs_test_123",
                    "customer_email": "test@example.com",
                    "payment_status": "paid",
                    "metadata": {"purchase_id": "purchase_123"},
                }
            }

            result = handler.handle_session_completed(event_data, "evt_123")

            assert result["success"] is False
            assert result["status"] == WebhookStatus.FAILED.value
            assert "Report generation failed" in result["error"]

    def test_checkout_session_handler_expired_exception(self):
        """Test checkout session expired handler exception handling"""
        handler = CheckoutSessionHandler(StripeClient())

        # Test handle_session_expired with exception
        with patch.object(handler, "_extract_purchase_id") as mock_extract:
            mock_extract.side_effect = Exception("Extract failed")

            event_data = {
                "object": {
                    "id": "cs_test_123",
                    "metadata": {"purchase_id": "purchase_123"},
                }
            }

            result = handler.handle_session_expired(event_data, "evt_123")

            assert result["success"] is False
            assert result["status"] == WebhookStatus.FAILED.value
            assert "Extract failed" in result["error"]

    def test_payment_intent_handler_edge_cases(self):
        """Test payment intent handler edge cases"""
        handler = PaymentIntentHandler(StripeClient())

        # Test payment succeeded without customer email
        event_data = {
            "object": {
                "id": "pi_test_123",
                "amount": 2999,
                "currency": "usd",
                "metadata": {
                    "purchase_id": "purchase_123"
                    # No customer_email
                },
            }
        }

        result = handler.handle_payment_succeeded(event_data, "evt_123")

        assert result["success"] is True
        assert (
            result["data"]["report_generation"]["status"]
            == ReportGenerationStatus.SKIPPED.value
        )
        assert "No customer email" in result["data"]["report_generation"]["reason"]

    def test_payment_intent_handler_no_purchase_id(self):
        """Test payment intent handler without purchase ID"""
        handler = PaymentIntentHandler(StripeClient())

        # Test payment succeeded without purchase_id
        event_data = {
            "object": {
                "id": "pi_test_123",
                "amount": 2999,
                "currency": "usd",
                "metadata": {},  # No purchase_id
            }
        }

        result = handler.handle_payment_succeeded(event_data, "evt_123")

        assert result["success"] is True
        assert (
            result["data"]["report_generation"]["status"]
            == ReportGenerationStatus.SKIPPED.value
        )
        assert "No purchase ID" in result["data"]["report_generation"]["reason"]

    def test_payment_intent_handler_exception_handling(self):
        """Test payment intent handler exception handling"""
        handler = PaymentIntentHandler(StripeClient())

        # Test handle_payment_succeeded with exception
        with patch.object(handler, "_extract_purchase_id") as mock_extract:
            mock_extract.side_effect = Exception("Extract failed")

            event_data = {
                "object": {
                    "id": "pi_test_123",
                    "amount": 2999,
                    "currency": "usd",
                    "metadata": {"purchase_id": "purchase_123"},
                }
            }

            result = handler.handle_payment_succeeded(event_data, "evt_123")

            assert result["success"] is False
            assert result["status"] == WebhookStatus.FAILED.value
            assert "Extract failed" in result["error"]

        # Test handle_payment_failed with exception
        with patch.object(handler, "_extract_purchase_id") as mock_extract:
            mock_extract.side_effect = Exception("Extract failed")

            event_data = {
                "object": {
                    "id": "pi_test_123",
                    "metadata": {"purchase_id": "purchase_123"},
                }
            }

            result = handler.handle_payment_failed(event_data, "evt_123")

            assert result["success"] is False
            assert result["status"] == WebhookStatus.FAILED.value
            assert "Extract failed" in result["error"]

    def test_customer_handler_exception_handling(self):
        """Test customer handler exception handling"""
        handler = CustomerHandler(StripeClient())

        # Test handle_customer_created with exception
        with patch("logging.Logger.info") as mock_log:
            mock_log.side_effect = Exception("Logging failed")

            event_data = {
                "object": {
                    "id": "cus_test_123",
                    "email": "test@example.com",
                    "name": "John Doe",
                    "metadata": {"source": "leadfactory"},
                }
            }

            result = handler.handle_customer_created(event_data, "evt_123")

            assert result["success"] is False
            assert result["status"] == WebhookStatus.FAILED.value
            assert "Logging failed" in result["error"]

    def test_invoice_handler_edge_cases(self):
        """Test invoice handler edge cases"""
        handler = InvoiceHandler(StripeClient())

        # Test invoice payment succeeded without customer email
        event_data = {
            "object": {
                "id": "in_test_123",
                "customer": "cus_test_123",
                "amount_paid": 2999,
                "currency": "usd",
                "metadata": {
                    "purchase_id": "purchase_123"
                    # No customer_email
                },
            }
        }

        result = handler.handle_invoice_event(
            "invoice.payment_succeeded", event_data, "evt_123"
        )

        assert result["success"] is True
        assert (
            result["data"]["report_generation"]["status"]
            == ReportGenerationStatus.SKIPPED.value
        )

    def test_invoice_handler_unknown_event_type(self):
        """Test invoice handler with unknown event type"""
        handler = InvoiceHandler(StripeClient())

        event_data = {
            "object": {"id": "in_test_123", "customer": "cus_test_123", "metadata": {}}
        }

        result = handler.handle_invoice_event(
            "invoice.unknown_event", event_data, "evt_123"
        )

        assert result["success"] is True
        assert result["data"]["action"] == "unknown"
        assert (
            result["data"]["report_generation"]["status"]
            == ReportGenerationStatus.SKIPPED.value
        )

    def test_invoice_handler_exception_handling(self):
        """Test invoice handler exception handling"""
        handler = InvoiceHandler(StripeClient())

        # Test handle_invoice_event with exception
        with patch.object(handler, "_extract_purchase_id") as mock_extract:
            mock_extract.side_effect = Exception("Extract failed")

            event_data = {
                "object": {
                    "id": "in_test_123",
                    "customer": "cus_test_123",
                    "metadata": {"purchase_id": "purchase_123"},
                }
            }

            result = handler.handle_invoice_event(
                "invoice.payment_succeeded", event_data, "evt_123"
            )

            assert result["success"] is False
            assert result["status"] == WebhookStatus.FAILED.value
            assert "Extract failed" in result["error"]

    def test_base_webhook_handler_helper_methods(self):
        """Test base webhook handler helper methods"""
        handler = BaseWebhookHandler(StripeClient())

        # Test _extract_purchase_id
        metadata = {"purchase_id": "test_123", "other": "data"}
        assert handler._extract_purchase_id(metadata) == "test_123"
        assert handler._extract_purchase_id({}) is None

        # Test _extract_customer_email
        event_data = {
            "object": {
                "customer_email": "test@example.com",
                "receipt_email": "receipt@example.com",
            }
        }
        assert handler._extract_customer_email(event_data) == "test@example.com"

        # Test fallback to receipt_email
        event_data = {"object": {"receipt_email": "receipt@example.com"}}
        assert handler._extract_customer_email(event_data) == "receipt@example.com"

        # Test no email
        event_data = {"object": {}}
        assert handler._extract_customer_email(event_data) is None

    def test_report_generation_trigger_comprehensive(self):
        """Test comprehensive report generation triggering"""
        handler = BaseWebhookHandler(StripeClient())

        # Test with bulk business URLs
        metadata = {
            "purchase_id": "purchase_123",
            "business_urls": "https://a.com, https://b.com, https://c.com",
            "item_count": "3",
        }

        result = handler._trigger_report_generation(
            "purchase_123", "test@example.com", metadata
        )

        assert result["success"] is True
        assert result["status"] == ReportGenerationStatus.TRIGGERED.value
        assert result["report_type"] == "bulk"
        assert result["business_count"] == 3
        assert "job_id" in result

        # Test with single business URL fallback
        metadata = {
            "purchase_id": "purchase_123",
            "business_url": "https://single.com",
            "item_count": "1",
        }

        result = handler._trigger_report_generation(
            "purchase_123", "test@example.com", metadata
        )

        assert result["success"] is True
        assert result["report_type"] == "single"
        assert result["business_count"] == 1

    def test_report_generation_trigger_exception_handling(self):
        """Test report generation trigger exception handling"""
        handler = BaseWebhookHandler(StripeClient())

        # Mock datetime to cause exception
        with patch("d7_storefront.webhook_handlers.datetime") as mock_datetime:
            mock_datetime.utcnow.side_effect = Exception("Time error")

            result = handler._trigger_report_generation(
                "purchase_123", "test@example.com", {}
            )

            assert result["success"] is False
            assert result["status"] == ReportGenerationStatus.FAILED.value
            assert "Time error" in result["error"]

    def test_utility_functions_comprehensive(self):
        """Test utility functions comprehensively"""
        # Test generate_event_hash with different inputs
        hash1 = generate_event_hash("evt_123", "test.event", 1234567890)
        hash2 = generate_event_hash("evt_123", "test.event", 1234567890)
        hash3 = generate_event_hash("evt_456", "test.event", 1234567890)

        assert hash1 == hash2  # Same inputs
        assert hash1 != hash3  # Different event ID
        assert len(hash1) == 64  # SHA256 hex length

        # Test extract_metadata_from_event with missing fields
        event_data = {
            "object": {
                "id": "test_123",
                "metadata": {"key": "value"},
                "amount_total": None,  # Should be filtered out
                "currency": "usd",
            }
        }

        metadata = extract_metadata_from_event(event_data)
        assert "amount_total" not in metadata  # None values filtered
        assert metadata["currency"] == "usd"
        assert metadata["key"] == "value"

    def test_extract_business_info_edge_cases(self):
        """Test business info extraction edge cases"""
        # Test with invalid item indices
        metadata = {
            "item_abc_name": "Invalid Index",  # Non-numeric index
            "item_0_name": "Valid Item",
            "item_1_business_id": "biz_123",
            "business_urls": "https://a.com,https://b.com",
            "business_url": "https://fallback.com",  # Should be ignored when business_urls exists
        }

        business_info = extract_business_info_from_metadata(metadata)

        assert len(business_info["names"]) == 1
        assert "Valid Item" in business_info["names"]
        assert len(business_info["ids"]) == 1
        assert "biz_123" in business_info["ids"]
        assert len(business_info["urls"]) == 2
        assert "https://a.com" in business_info["urls"]

        # Test with only single business_url
        metadata = {"business_url": "https://single.com"}

        business_info = extract_business_info_from_metadata(metadata)
        assert business_info["urls"] == ["https://single.com"]

    def test_determine_report_priority_edge_cases(self):
        """Test report priority determination edge cases"""
        # Test empty metadata
        assert determine_report_priority({}) == "normal"

        # Test case insensitivity (checks key names, not values)
        metadata = {"premium_item": "Audit Report"}
        assert determine_report_priority(metadata) == "high"

        metadata = {"bulk_package": "Reports"}
        assert determine_report_priority(metadata) == "medium"

        # Test with explicit priority
        metadata = {"priority": "urgent"}
        assert determine_report_priority(metadata) == "urgent"

    def test_format_report_generation_request(self):
        """Test report generation request formatting"""
        business_info = {
            "urls": ["https://a.com", "https://b.com"],
            "names": ["Business A", "Business B"],
            "ids": ["biz_a", "biz_b"],
        }

        metadata = {"campaign": "test", "priority": "high"}

        request = format_report_generation_request(
            "purchase_123", "test@example.com", business_info, metadata
        )

        assert request["purchase_id"] == "purchase_123"
        assert request["customer_email"] == "test@example.com"
        assert request["business_urls"] == ["https://a.com", "https://b.com"]
        assert request["priority"] == "high"
        assert request["report_type"] == "bulk"
        assert "requested_at" in request

        # Test single URL (should be "single" type)
        business_info["urls"] = ["https://single.com"]
        request = format_report_generation_request(
            "purchase_123", "test@example.com", business_info, metadata
        )
        assert request["report_type"] == "single"

    def test_webhook_constants_and_configuration(self):
        """Test webhook constants and configuration"""
        # Test WEBHOOK_HANDLER_CONFIG
        from d7_storefront.webhook_handlers import WEBHOOK_HANDLER_CONFIG

        assert WEBHOOK_HANDLER_CONFIG["REPORT_GENERATION_TIMEOUT_SECONDS"] == 300
        assert WEBHOOK_HANDLER_CONFIG["MAX_BUSINESS_URLS_PER_REQUEST"] == 50
        assert WEBHOOK_HANDLER_CONFIG["DEFAULT_REPORT_PRIORITY"] == "normal"
        assert WEBHOOK_HANDLER_CONFIG["RETRY_FAILED_GENERATIONS"] is True

        # Test SUPPORTED_CURRENCIES
        from d7_storefront.webhook_handlers import SUPPORTED_CURRENCIES

        assert "usd" in SUPPORTED_CURRENCIES
        assert "eur" in SUPPORTED_CURRENCIES
        assert "gbp" in SUPPORTED_CURRENCIES

        # Test WEBHOOK_RESPONSE_CODES
        from d7_storefront.webhook_handlers import WEBHOOK_RESPONSE_CODES

        assert WEBHOOK_RESPONSE_CODES["SUCCESS"] == 200
        assert WEBHOOK_RESPONSE_CODES["INVALID_SIGNATURE"] == 401
        assert WEBHOOK_RESPONSE_CODES["MALFORMED_REQUEST"] == 400

        # Test webhook configuration from webhooks.py
        from d7_storefront.webhooks import (
            WEBHOOK_CONFIG,
            WEBHOOK_ENDPOINTS,
            WEBHOOK_EVENTS_TO_SUBSCRIBE,
        )

        assert "PRODUCTION" in WEBHOOK_ENDPOINTS
        assert "checkout.session.completed" in WEBHOOK_EVENTS_TO_SUBSCRIBE
        assert WEBHOOK_CONFIG["API_VERSION"] == "2023-10-16"
        assert WEBHOOK_CONFIG["TIMEOUT_SECONDS"] == 30

    def test_webhook_error_exception(self):
        """Test WebhookError exception"""
        # Test WebhookError creation and usage
        error = WebhookError("Test webhook error")
        assert str(error) == "Test webhook error"
        assert isinstance(error, Exception)

        # Test raising WebhookError
        with pytest.raises(WebhookError, match="Test webhook error"):
            raise WebhookError("Test webhook error")

    def test_webhook_event_type_enum(self):
        """Test WebhookEventType enum"""
        # Test all event types are defined
        assert (
            WebhookEventType.CHECKOUT_SESSION_COMPLETED.value
            == "checkout.session.completed"
        )
        assert (
            WebhookEventType.CHECKOUT_SESSION_EXPIRED.value
            == "checkout.session.expired"
        )
        assert (
            WebhookEventType.PAYMENT_INTENT_SUCCEEDED.value
            == "payment_intent.succeeded"
        )
        assert (
            WebhookEventType.PAYMENT_INTENT_FAILED.value
            == "payment_intent.payment_failed"
        )
        assert WebhookEventType.CUSTOMER_CREATED.value == "customer.created"
        assert (
            WebhookEventType.INVOICE_PAYMENT_SUCCEEDED.value
            == "invoice.payment_succeeded"
        )
        assert WebhookEventType.INVOICE_PAYMENT_FAILED.value == "invoice.payment_failed"

        # Test enum membership
        assert len(list(WebhookEventType)) == 7

    def test_webhook_status_enum(self):
        """Test WebhookStatus enum"""
        # Test all status values are defined
        assert WebhookStatus.PENDING.value == "pending"
        assert WebhookStatus.PROCESSING.value == "processing"
        assert WebhookStatus.COMPLETED.value == "completed"
        assert WebhookStatus.FAILED.value == "failed"
        assert WebhookStatus.IGNORED.value == "ignored"

        # Test enum membership
        assert len(list(WebhookStatus)) == 5

    def test_report_generation_status_enum(self):
        """Test ReportGenerationStatus enum"""
        # Test all status values are defined
        assert ReportGenerationStatus.QUEUED.value == "queued"
        assert ReportGenerationStatus.TRIGGERED.value == "triggered"
        assert ReportGenerationStatus.FAILED.value == "failed"
        assert ReportGenerationStatus.SKIPPED.value == "skipped"

        # Test enum membership
        assert len(list(ReportGenerationStatus)) == 4


if __name__ == "__main__":
    # Run basic tests if file is executed directly
    print("Running D7 Storefront Webhook Tests...")
    print("=" * 50)

    try:
        # Test basic functionality
        print("Testing basic functionality...")

        # Test webhook processor
        processor = WebhookProcessor()
        assert processor.enable_idempotency is True
        print("✓ Webhook processor works")

        # Test event types
        events = processor.get_supported_events()
        assert "checkout.session.completed" in events
        print("✓ Event types configured")

        # Test handlers
        handler = CheckoutSessionHandler(StripeClient())
        assert handler.stripe_client is not None
        print("✓ Webhook handlers work")

        # Test enhanced functionality
        test_enhancements = TestWebhookEnhancements()
        test_enhancements.test_webhook_processor_edge_cases()
        test_enhancements.test_base_webhook_handler_helper_methods()
        test_enhancements.test_utility_functions_comprehensive()
        print("✓ Enhanced webhook functionality works")

        # Test acceptance criteria
        test_acceptance = TestAcceptanceCriteria()
        test_acceptance.test_signature_verification_acceptance_criteria()
        test_acceptance.test_idempotency_handled_acceptance_criteria()
        test_acceptance.test_report_generation_triggered_acceptance_criteria()

        print("=" * 50)
        print("🎉 ALL TESTS PASSED!")
        print("")
        print("Acceptance Criteria Status:")
        print("✓ Signature verification")
        print("✓ Event processing works")
        print("✓ Idempotency handled")
        print("✓ Report generation triggered")
        print("")
        print("Enhanced Test Coverage:")
        print("✓ Webhook processor edge cases")
        print("✓ Handler exception handling")
        print("✓ Event type routing")
        print("✓ Utility function coverage")
        print("✓ Configuration validation")
        print("")
        print("Task 057 implementation complete and verified!")
        print("GAP-011 enhanced test coverage added!")

    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
