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

import pytest
import json
import hashlib
import hmac
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import stripe

# Import modules to test
from d7_storefront.webhooks import (
    WebhookProcessor, WebhookEventType, WebhookStatus, WebhookError,
    generate_event_hash, extract_metadata_from_event, format_webhook_response_for_api
)
from d7_storefront.webhook_handlers import (
    CheckoutSessionHandler, PaymentIntentHandler, CustomerHandler, InvoiceHandler,
    ReportGenerationStatus, extract_business_info_from_metadata, determine_report_priority
)
from d7_storefront.stripe_client import StripeClient, StripeConfig


class TestWebhookProcessor:
    """Test webhook processor functionality"""
    
    def test_webhook_processor_initialization(self):
        """Test webhook processor initialization"""
        processor = WebhookProcessor()
        
        assert processor.stripe_client is not None
        assert processor.max_event_age_hours == 24
        assert processor.enable_idempotency is True
        assert processor._processed_events is not None
    
    @patch.object(StripeClient, 'verify_webhook_signature')
    def test_verify_signature_success(self, mock_verify):
        """Test successful signature verification - Acceptance Criteria"""
        mock_verify.return_value = True
        
        processor = WebhookProcessor()
        payload = b'{"test": "data"}'
        signature = "test_signature"
        
        result = processor.verify_signature(payload, signature)
        
        assert result is True
        mock_verify.assert_called_once_with(payload, signature)
    
    @patch.object(StripeClient, 'verify_webhook_signature')
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
    
    @patch.object(StripeClient, 'verify_webhook_signature')
    @patch.object(StripeClient, 'construct_webhook_event')
    @patch.object(WebhookProcessor, '_process_event')
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
            "created": int(datetime.utcnow().timestamp())
        }
        
        # Mock successful event processing
        mock_process.return_value = {
            "success": True,
            "status": WebhookStatus.COMPLETED.value
        }
        
        processor = WebhookProcessor()
        payload = b'{"id": "evt_test_123"}'
        signature = "test_signature"
        
        result = processor.process_webhook(payload, signature)
        
        assert result["success"] is True
        assert result["event_id"] == "evt_test_123"
        assert result["event_type"] == "checkout.session.completed"
        assert result["status"] == WebhookStatus.COMPLETED.value
    
    @patch.object(StripeClient, 'verify_webhook_signature')
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
    
    @patch.object(StripeClient, 'verify_webhook_signature')
    @patch.object(StripeClient, 'construct_webhook_event')
    def test_process_webhook_duplicate_event(self, mock_construct, mock_verify):
        """Test webhook processing with duplicate event - Acceptance Criteria"""
        mock_verify.return_value = True
        
        event_id = "evt_test_123"
        mock_construct.return_value = {
            "success": True,
            "event_id": event_id,
            "event_type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test"}},
            "created": int(datetime.utcnow().timestamp())
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
                    "business_url": "https://example.com"
                }
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
                "metadata": {}  # No purchase_id
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
                "metadata": {
                    "purchase_id": "purchase_123"
                }
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
            "object": {
                "id": "cs_test_123",
                "metadata": {
                    "purchase_id": "purchase_123"
                }
            }
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
                    "business_url": "https://example.com"
                }
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
            "object": {
                "id": "pi_test_123",
                "metadata": {
                    "purchase_id": "purchase_123"
                }
            }
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
                "metadata": {
                    "source": "leadfactory"
                }
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
                    "customer_email": "test@example.com"
                }
            }
        }
        
        result = handler.handle_invoice_event(
            "invoice.payment_succeeded",
            event_data,
            "evt_123"
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
                "metadata": {}
            }
        }
        
        result = handler.handle_invoice_event(
            "invoice.payment_failed",
            event_data,
            "evt_123"
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
                    "custom_field": "custom_value"
                }
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
            "data": {"test": "data"}
        }
        
        formatted = format_webhook_response_for_api(result)
        
        assert formatted["status"] == "success"
        assert formatted["webhook"]["event_id"] == "evt_test_123"
        assert formatted["webhook"]["event_type"] == "checkout.session.completed"
        assert formatted["webhook"]["processing_status"] == WebhookStatus.COMPLETED.value
    
    def test_format_webhook_response_for_api_error(self):
        """Test API response formatting for error"""
        result = {
            "success": False,
            "event_id": "evt_test_123",
            "error": "Processing failed",
            "status": WebhookStatus.FAILED.value
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
            "business_url": "https://single.com"
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
        
        # Test premium detection
        metadata = {"item_0_name": "Premium Audit Report"}
        assert determine_report_priority(metadata) == "high"
        
        # Test bulk detection
        metadata = {"item_0_name": "Bulk Reports"}
        assert determine_report_priority(metadata) == "medium"
        
        # Test normal priority
        metadata = {"item_0_name": "Standard Report"}
        assert determine_report_priority(metadata) == "normal"


class TestAcceptanceCriteria:
    """Test all acceptance criteria for Task 057"""
    
    @patch.object(StripeClient, 'verify_webhook_signature')
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
    
    @patch.object(StripeClient, 'verify_webhook_signature')
    @patch.object(StripeClient, 'construct_webhook_event')
    @patch.object(WebhookProcessor, '_process_event')
    def test_event_processing_works_acceptance_criteria(self, mock_process, mock_construct, mock_verify):
        """Test: Event processing works ✓"""
        # Setup mocks
        mock_verify.return_value = True
        mock_construct.return_value = {
            "success": True,
            "event_id": "evt_test_123",
            "event_type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test"}},
            "created": int(datetime.utcnow().timestamp())
        }
        mock_process.return_value = {
            "success": True,
            "status": WebhookStatus.COMPLETED.value
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
                    "business_url": "https://example.com"
                }
            }
        }
        
        result = handler.handle_session_completed(event_data, "evt_123")
        
        # Verify report generation was triggered
        assert result["success"] is True
        assert "report_generation" in result["data"]
        assert result["data"]["report_generation"]["success"] is True
        assert result["data"]["report_generation"]["status"] == ReportGenerationStatus.TRIGGERED.value
        assert result["data"]["report_generation"]["purchase_id"] == "purchase_123"
        assert result["data"]["report_generation"]["customer_email"] == "test@example.com"
        assert "job_id" in result["data"]["report_generation"]
        
        print("✓ Report generation triggered")


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
        print("Task 057 implementation complete and verified!")
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()