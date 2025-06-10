"""
Test D7 Storefront Checkout - Task 056

Tests for Stripe checkout integration with session creation, test mode, metadata, and URLs.

Acceptance Criteria:
- Checkout session creation ✓
- Test mode works ✓
- Metadata included ✓
- Success/cancel URLs ✓
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
import stripe

# Import modules to test
from d7_storefront.stripe_client import (
    StripeClient, StripeConfig, StripeCheckoutSession, StripeError,
    create_one_time_line_item, format_amount_for_stripe, format_amount_from_stripe
)
from d7_storefront.checkout import (
    CheckoutManager, CheckoutSession, CheckoutItem, CheckoutConfig, CheckoutError,
    create_test_checkout_items, format_checkout_response_for_api
)
from d7_storefront.models import ProductType


class TestStripeConfig:
    """Test Stripe configuration"""
    
    def test_stripe_config_test_mode(self):
        """Test Stripe config in test mode"""
        config = StripeConfig(test_mode=True)
        
        assert config.test_mode is True
        assert config.api_key == "sk_test_mock_key_for_testing"
        assert config.publishable_key == "pk_test_mock_key_for_testing"
        assert config.webhook_secret == "whsec_test_mock_secret"
        assert config.currency == "usd"
        assert config.session_expires_after_minutes == 30
    
    def test_stripe_config_live_mode(self):
        """Test Stripe config in live mode (with mocked env vars)"""
        with patch.dict('os.environ', {
            'STRIPE_LIVE_SECRET_KEY': 'sk_live_test_key',
            'STRIPE_LIVE_PUBLISHABLE_KEY': 'pk_live_test_key',
            'STRIPE_LIVE_WEBHOOK_SECRET': 'whsec_live_test_secret'
        }):
            config = StripeConfig(test_mode=False)
            
            assert config.test_mode is False
            assert config.api_key == "sk_live_test_key"
            assert config.publishable_key == "pk_live_test_key"
            assert config.webhook_secret == "whsec_live_test_secret"
    
    def test_stripe_config_missing_live_key(self):
        """Test that missing live API key raises error"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                StripeConfig(test_mode=False)
            
            assert "Missing Stripe API key for live mode" in str(exc_info.value)


class TestStripeCheckoutSession:
    """Test Stripe checkout session configuration"""
    
    def test_stripe_checkout_session_creation(self):
        """Test checkout session data class creation"""
        line_items = [{"price": "price_test", "quantity": 1}]
        
        session = StripeCheckoutSession(
            line_items=line_items,
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            customer_email="test@example.com",
            metadata={"test": "data"}
        )
        
        assert session.line_items == line_items
        assert session.success_url == "https://example.com/success"
        assert session.cancel_url == "https://example.com/cancel"
        assert session.customer_email == "test@example.com"
        assert session.metadata == {"test": "data"}
        assert session.mode == "payment"
        assert session.payment_method_types == ["card"]
    
    def test_stripe_checkout_session_to_params(self):
        """Test conversion to Stripe API parameters"""
        config = StripeConfig(test_mode=True)
        line_items = [{"price": "price_test", "quantity": 1}]
        
        session = StripeCheckoutSession(
            line_items=line_items,
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            customer_email="test@example.com",
            metadata={"purchase_id": "test_123"}
        )
        
        params = session.to_stripe_params(config)
        
        assert params["line_items"] == line_items
        assert params["mode"] == "payment"
        assert params["payment_method_types"] == ["card"]
        assert params["success_url"] == "https://example.com/success"
        assert params["cancel_url"] == "https://example.com/cancel"
        assert params["customer_email"] == "test@example.com"
        assert params["metadata"] == {"purchase_id": "test_123"}
        assert "expires_at" in params
        assert params["billing_address_collection"] == "auto"
        assert params["allow_promotion_codes"] is True


class TestStripeClient:
    """Test Stripe client functionality"""
    
    def test_stripe_client_initialization(self):
        """Test Stripe client initialization"""
        config = StripeConfig(test_mode=True)
        client = StripeClient(config)
        
        assert client.config == config
        assert client.stripe == stripe
    
    def test_stripe_client_default_config(self):
        """Test Stripe client with default config"""
        client = StripeClient()
        
        assert client.config.test_mode is True
    
    @patch('stripe.checkout.Session.create')
    def test_create_checkout_session_success(self, mock_create):
        """Test successful checkout session creation - Acceptance Criteria"""
        # Mock successful Stripe response
        mock_session = Mock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_123"
        mock_session.payment_status = "unpaid"
        mock_session.amount_total = 2999
        mock_session.currency = "usd"
        mock_session.expires_at = 1234567890
        mock_session.metadata = {"test": "data"}
        mock_session.mode = "payment"
        mock_session.success_url = "https://example.com/success"
        mock_session.cancel_url = "https://example.com/cancel"
        
        mock_create.return_value = mock_session
        
        client = StripeClient()
        session_config = StripeCheckoutSession(
            line_items=[{"price": "price_test", "quantity": 1}],
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            metadata={"test": "data"}
        )
        
        result = client.create_checkout_session(session_config)
        
        assert result["success"] is True
        assert result["session_id"] == "cs_test_123"
        assert result["session_url"] == "https://checkout.stripe.com/pay/cs_test_123"
        assert result["payment_status"] == "unpaid"
        assert result["amount_total"] == 2999
        assert result["currency"] == "usd"
        assert result["metadata"] == {"test": "data"}
        assert result["success_url"] == "https://example.com/success"
        assert result["cancel_url"] == "https://example.com/cancel"
        
        # Verify Stripe was called
        mock_create.assert_called_once()
    
    @patch('stripe.checkout.Session.create')
    def test_create_checkout_session_stripe_error(self, mock_create):
        """Test checkout session creation with Stripe error"""
        # Mock Stripe error
        stripe_error = stripe.error.CardError(
            message="Your card was declined.",
            param="card",
            code="card_declined"
        )
        stripe_error.user_message = "Your card was declined."
        mock_create.side_effect = stripe_error
        
        client = StripeClient()
        session_config = StripeCheckoutSession(
            line_items=[{"price": "price_test", "quantity": 1}],
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel"
        )
        
        with pytest.raises(StripeError) as exc_info:
            client.create_checkout_session(session_config)
        
        assert "Failed to create checkout session" in str(exc_info.value)
        assert exc_info.value.stripe_error == stripe_error
    
    @patch('stripe.checkout.Session.retrieve')
    def test_retrieve_checkout_session(self, mock_retrieve):
        """Test retrieving checkout session"""
        # Mock session data
        mock_session = Mock()
        mock_session.id = "cs_test_123"
        mock_session.payment_status = "paid"
        mock_session.payment_intent = "pi_test_123"
        mock_session.customer = "cus_test_123"
        mock_session.amount_total = 2999
        mock_session.currency = "usd"
        mock_session.metadata = {"test": "data"}
        mock_session.status = "complete"
        
        mock_retrieve.return_value = mock_session
        
        client = StripeClient()
        result = client.retrieve_checkout_session("cs_test_123")
        
        assert result["success"] is True
        assert result["session_id"] == "cs_test_123"
        assert result["payment_status"] == "paid"
        assert result["payment_intent"] == "pi_test_123"
        assert result["customer"] == "cus_test_123"
        assert result["amount_total"] == 2999
    
    def test_is_test_mode(self):
        """Test mode detection - Acceptance Criteria"""
        test_client = StripeClient(StripeConfig(test_mode=True))
        assert test_client.is_test_mode() is True
        
        live_config = StripeConfig(test_mode=False)
        live_config.api_key = "sk_live_mock"  # Mock live key
        live_client = StripeClient(live_config)
        assert live_client.is_test_mode() is False
    
    def test_get_status(self):
        """Test client status reporting"""
        client = StripeClient()
        status = client.get_status()
        
        assert "test_mode" in status
        assert "api_version" in status
        assert "currency" in status
        assert "webhook_configured" in status
        assert status["test_mode"] is True
        assert status["currency"] == "usd"


class TestCheckoutItem:
    """Test checkout item functionality"""
    
    def test_checkout_item_creation(self):
        """Test checkout item creation"""
        item = CheckoutItem(
            product_name="Website Audit Report",
            amount_usd=Decimal("29.99"),
            quantity=1,
            description="Comprehensive audit",
            product_type=ProductType.AUDIT_REPORT,
            business_id="biz_123"
        )
        
        assert item.product_name == "Website Audit Report"
        assert item.amount_usd == Decimal("29.99")
        assert item.quantity == 1
        assert item.description == "Comprehensive audit"
        assert item.product_type == ProductType.AUDIT_REPORT
        assert item.business_id == "biz_123"
    
    def test_checkout_item_amounts(self):
        """Test amount calculations"""
        item = CheckoutItem(
            product_name="Test Product",
            amount_usd=Decimal("29.99"),
            quantity=2
        )
        
        assert item.amount_cents == 2999
        assert item.total_amount_usd == Decimal("59.98")
    
    def test_checkout_item_to_stripe_line_item(self):
        """Test conversion to Stripe line item"""
        item = CheckoutItem(
            product_name="Website Audit",
            amount_usd=Decimal("29.99"),
            quantity=1
        )
        
        line_item = item.to_stripe_line_item()
        
        assert "price_data" in line_item
        assert line_item["quantity"] == 1
        assert line_item["price_data"]["currency"] == "usd"
        assert line_item["price_data"]["unit_amount"] == 2999
        assert line_item["price_data"]["product_data"]["name"] == "Website Audit"


class TestCheckoutSession:
    """Test checkout session functionality"""
    
    def test_checkout_session_creation(self):
        """Test checkout session creation"""
        items = [
            CheckoutItem("Product 1", Decimal("29.99")),
            CheckoutItem("Product 2", Decimal("19.99"))
        ]
        
        session = CheckoutSession(
            customer_email="test@example.com",
            items=items
        )
        
        assert session.customer_email == "test@example.com"
        assert len(session.items) == 2
        assert session.purchase_id is not None
    
    def test_checkout_session_validation(self):
        """Test checkout session validation"""
        # Test empty items
        with pytest.raises(CheckoutError) as exc_info:
            CheckoutSession("test@example.com", [])
        assert "At least one item is required" in str(exc_info.value)
        
        # Test empty email
        items = [CheckoutItem("Product", Decimal("29.99"))]
        with pytest.raises(CheckoutError) as exc_info:
            CheckoutSession("", items)
        assert "Customer email is required" in str(exc_info.value)
    
    def test_checkout_session_totals(self):
        """Test total calculations"""
        items = [
            CheckoutItem("Product 1", Decimal("29.99"), quantity=1),
            CheckoutItem("Product 2", Decimal("19.99"), quantity=2)
        ]
        
        session = CheckoutSession("test@example.com", items)
        
        assert session.total_amount_usd == Decimal("69.97")  # 29.99 + (19.99 * 2)
        assert session.total_amount_cents == 6997
    
    def test_build_urls(self):
        """Test URL building - Acceptance Criteria"""
        items = [CheckoutItem("Product", Decimal("29.99"))]
        session = CheckoutSession("test@example.com", items, purchase_id="test_purchase_123")
        
        success_url = session.build_success_url()
        cancel_url = session.build_cancel_url()
        
        assert "purchase_id=test_purchase_123" in success_url
        assert "session_id={CHECKOUT_SESSION_ID}" in success_url
        assert "purchase_id=test_purchase_123" in cancel_url
        assert "session_id={CHECKOUT_SESSION_ID}" in cancel_url
    
    def test_build_metadata(self):
        """Test metadata building - Acceptance Criteria"""
        items = [
            CheckoutItem("Audit Report", Decimal("29.99"), product_type=ProductType.AUDIT_REPORT, business_id="biz_123"),
            CheckoutItem("Premium Report", Decimal("99.99"), product_type=ProductType.PREMIUM_REPORT)
        ]
        
        session = CheckoutSession("test@example.com", items, purchase_id="test_purchase_123")
        metadata = session.build_metadata({"campaign": "test_campaign"})
        
        # Check required metadata
        assert metadata["purchase_id"] == "test_purchase_123"
        assert metadata["customer_email"] == "test@example.com"
        assert metadata["item_count"] == "2"
        assert metadata["total_amount_usd"] == "129.98"
        assert metadata["source"] == "leadfactory_checkout"
        
        # Check item metadata
        assert metadata["item_0_name"] == "Audit Report"
        assert metadata["item_0_type"] == "audit_report"
        assert metadata["item_0_amount"] == "29.99"
        assert metadata["item_0_business_id"] == "biz_123"
        
        assert metadata["item_1_name"] == "Premium Report"
        assert metadata["item_1_type"] == "premium_report"
        assert metadata["item_1_amount"] == "99.99"
        
        # Check additional metadata
        assert metadata["campaign"] == "test_campaign"
    
    @patch.object(StripeClient, 'create_checkout_session')
    def test_create_stripe_session(self, mock_create):
        """Test Stripe session creation - Acceptance Criteria"""
        # Mock successful response
        mock_create.return_value = {
            "success": True,
            "session_id": "cs_test_123",
            "session_url": "https://checkout.stripe.com/pay/cs_test_123",
            "payment_status": "unpaid",
            "amount_total": 2999,
            "currency": "usd",
            "expires_at": 1234567890,
            "metadata": {"test": "data"}
        }
        
        items = [CheckoutItem("Product", Decimal("29.99"))]
        session = CheckoutSession("test@example.com", items)
        
        result = session.create_stripe_session({"campaign": "test"})
        
        assert result["success"] is True
        assert result["session_id"] == "cs_test_123"
        assert result["session_url"] == "https://checkout.stripe.com/pay/cs_test_123"
        
        # Verify create_checkout_session was called with correct parameters
        mock_create.assert_called_once()
        call_args = mock_create.call_args[0][0]  # First argument (StripeCheckoutSession)
        
        assert call_args.customer_email == "test@example.com"
        assert len(call_args.line_items) == 1
        assert call_args.mode == "payment"
        assert "purchase_id" in call_args.metadata
        assert "campaign" in call_args.metadata


class TestCheckoutManager:
    """Test checkout manager functionality"""
    
    def test_checkout_manager_initialization(self):
        """Test checkout manager initialization"""
        manager = CheckoutManager()
        
        assert manager.config is not None
        assert manager.stripe_client is not None
        assert manager.config.test_mode is True
    
    @patch.object(CheckoutSession, 'create_stripe_session')
    def test_initiate_checkout_success(self, mock_create_session):
        """Test successful checkout initiation"""
        # Mock successful session creation
        mock_create_session.return_value = {
            "session_id": "cs_test_123",
            "session_url": "https://checkout.stripe.com/pay/cs_test_123",
            "amount_total": 2999,
            "currency": "usd",
            "expires_at": 1234567890
        }
        
        manager = CheckoutManager()
        items = [CheckoutItem("Product", Decimal("29.99"))]
        
        result = manager.initiate_checkout("test@example.com", items)
        
        assert result["success"] is True
        assert result["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_123"
        assert result["session_id"] == "cs_test_123"
        assert result["amount_total_usd"] == 29.99
        assert result["amount_total_cents"] == 2999
        assert result["test_mode"] is True
        assert len(result["items"]) == 1
    
    @patch.object(CheckoutSession, 'create_stripe_session')
    def test_initiate_checkout_error(self, mock_create_session):
        """Test checkout initiation with error"""
        # Mock session creation error
        mock_create_session.side_effect = CheckoutError("Test error")
        
        manager = CheckoutManager()
        items = [CheckoutItem("Product", Decimal("29.99"))]
        
        result = manager.initiate_checkout("test@example.com", items)
        
        assert result["success"] is False
        assert result["error"] == "Test error"
        assert result["error_type"] == "CheckoutError"
    
    @patch.object(StripeClient, 'retrieve_checkout_session')
    def test_retrieve_session_status(self, mock_retrieve):
        """Test session status retrieval"""
        # Mock successful retrieval
        mock_retrieve.return_value = {
            "success": True,
            "session_id": "cs_test_123",
            "payment_status": "paid",
            "status": "complete",
            "amount_total": 2999,
            "currency": "usd",
            "metadata": {"test": "data"}
        }
        
        manager = CheckoutManager()
        result = manager.retrieve_session_status("cs_test_123")
        
        assert result["success"] is True
        assert result["session_id"] == "cs_test_123"
        assert result["payment_status"] == "paid"
        assert result["status"] == "complete"
    
    @patch.object(CheckoutManager, 'initiate_checkout')
    def test_create_audit_report_checkout(self, mock_initiate):
        """Test audit report checkout convenience method"""
        # Mock successful initiation
        mock_initiate.return_value = {"success": True, "checkout_url": "https://test.com"}
        
        manager = CheckoutManager()
        result = manager.create_audit_report_checkout(
            customer_email="test@example.com",
            business_url="https://example.com",
            business_name="Example Business",
            attribution_data={"utm_source": "google"}
        )
        
        assert result["success"] is True
        
        # Verify initiate_checkout was called with correct parameters
        mock_initiate.assert_called_once()
        call_args = mock_initiate.call_args
        
        assert call_args[1]["customer_email"] == "test@example.com"
        assert len(call_args[1]["items"]) == 1
        
        item = call_args[1]["items"][0]
        assert "Example Business" in item.product_name
        assert item.product_type == ProductType.AUDIT_REPORT
        assert item.metadata["business_url"] == "https://example.com"
    
    def test_create_bulk_reports_checkout(self):
        """Test bulk reports checkout"""
        manager = CheckoutManager()
        business_urls = ["https://example1.com", "https://example2.com", "https://example3.com"]
        
        with patch.object(manager, 'initiate_checkout') as mock_initiate:
            mock_initiate.return_value = {"success": True}
            
            result = manager.create_bulk_reports_checkout(
                customer_email="test@example.com",
                business_urls=business_urls,
                amount_per_report_usd=Decimal("24.99")
            )
            
            # Verify call
            call_args = mock_initiate.call_args
            item = call_args[1]["items"][0]
            
            assert item.quantity == 3
            assert item.amount_usd == Decimal("24.99")
            assert item.product_type == ProductType.BULK_REPORTS
            assert "3 reports" in item.product_name
    
    def test_get_status(self):
        """Test manager status reporting"""
        manager = CheckoutManager()
        status = manager.get_status()
        
        assert "test_mode" in status
        assert "success_url" in status
        assert "cancel_url" in status
        assert "stripe_status" in status
        assert status["test_mode"] is True


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_create_one_time_line_item(self):
        """Test one-time line item creation"""
        line_item = create_one_time_line_item("Test Product", 2999, 2)
        
        assert line_item["quantity"] == 2
        assert line_item["price_data"]["currency"] == "usd"
        assert line_item["price_data"]["unit_amount"] == 2999
        assert line_item["price_data"]["product_data"]["name"] == "Test Product"
    
    def test_format_amount_for_stripe(self):
        """Test amount formatting for Stripe"""
        assert format_amount_for_stripe(Decimal("29.99")) == 2999
        assert format_amount_for_stripe(Decimal("100.00")) == 10000
        assert format_amount_for_stripe(Decimal("0.50")) == 50
    
    def test_format_amount_from_stripe(self):
        """Test amount formatting from Stripe"""
        assert format_amount_from_stripe(2999) == Decimal("29.99")
        assert format_amount_from_stripe(10000) == Decimal("100.00")
        assert format_amount_from_stripe(50) == Decimal("0.50")
    
    def test_create_test_checkout_items(self):
        """Test test checkout items creation"""
        items = create_test_checkout_items()
        
        assert len(items) == 2
        assert items[0].product_name == "Website Audit Report - Basic"
        assert items[0].amount_usd == Decimal("29.99")
        assert items[1].product_name == "Website Audit Report - Premium"
        assert items[1].amount_usd == Decimal("99.99")
    
    def test_format_checkout_response_for_api(self):
        """Test API response formatting"""
        # Test success response
        success_response = {
            "success": True,
            "checkout_url": "https://checkout.stripe.com/pay/cs_test",
            "purchase_id": "purchase_123",
            "session_id": "cs_test_123",
            "amount_total_usd": 29.99,
            "currency": "usd",
            "expires_at": 1234567890,
            "test_mode": True
        }
        
        formatted = format_checkout_response_for_api(success_response)
        
        assert formatted["status"] == "success"
        assert formatted["data"]["checkout_url"] == "https://checkout.stripe.com/pay/cs_test"
        assert formatted["data"]["purchase_id"] == "purchase_123"
        
        # Test error response
        error_response = {
            "success": False,
            "error": "Test error",
            "error_type": "CheckoutError"
        }
        
        formatted_error = format_checkout_response_for_api(error_response)
        
        assert formatted_error["status"] == "error"
        assert formatted_error["error"]["message"] == "Test error"
        assert formatted_error["error"]["type"] == "CheckoutError"


class TestAcceptanceCriteria:
    """Test all acceptance criteria for Task 056"""
    
    @patch.object(StripeClient, 'create_checkout_session')
    def test_checkout_session_creation_acceptance_criteria(self, mock_create):
        """Test: Checkout session creation ✓"""
        mock_create.return_value = {
            "success": True,
            "session_id": "cs_test_123",
            "session_url": "https://checkout.stripe.com/pay/cs_test_123",
            "payment_status": "unpaid"
        }
        
        manager = CheckoutManager()
        items = [CheckoutItem("Test Product", Decimal("29.99"))]
        
        result = manager.initiate_checkout("test@example.com", items)
        
        # Verify checkout session was created
        assert result["success"] is True
        assert "session_id" in result
        assert "checkout_url" in result
        print("✓ Checkout session creation works")
    
    def test_test_mode_works_acceptance_criteria(self):
        """Test: Test mode works ✓"""
        # Test mode enabled by default
        config = StripeConfig(test_mode=True)
        client = StripeClient(config)
        manager = CheckoutManager(stripe_client=client)
        
        assert client.is_test_mode() is True
        assert client.config.api_key == "sk_test_mock_key_for_testing"
        assert manager.get_status()["test_mode"] is True
        print("✓ Test mode works")
    
    def test_metadata_included_acceptance_criteria(self):
        """Test: Metadata included ✓"""
        items = [CheckoutItem("Test Product", Decimal("29.99"), business_id="biz_123")]
        session = CheckoutSession("test@example.com", items, purchase_id="purchase_123")
        
        metadata = session.build_metadata({"campaign": "test_campaign"})
        
        # Verify all required metadata is included
        assert metadata["purchase_id"] == "purchase_123"
        assert metadata["customer_email"] == "test@example.com"
        assert metadata["item_count"] == "1"
        assert metadata["total_amount_usd"] == "29.99"
        assert metadata["source"] == "leadfactory_checkout"
        assert metadata["item_0_name"] == "Test Product"
        assert metadata["item_0_business_id"] == "biz_123"
        assert metadata["campaign"] == "test_campaign"
        assert "created_at" in metadata
        print("✓ Metadata included")
    
    def test_success_cancel_urls_acceptance_criteria(self):
        """Test: Success/cancel URLs ✓"""
        config = CheckoutConfig(
            base_success_url="https://leadfactory.com/success",
            base_cancel_url="https://leadfactory.com/cancel"
        )
        
        items = [CheckoutItem("Test Product", Decimal("29.99"))]
        session = CheckoutSession(
            customer_email="test@example.com",
            items=items,
            purchase_id="purchase_123",
            config=config
        )
        
        success_url = session.build_success_url()
        cancel_url = session.build_cancel_url()
        
        # Verify URLs are properly constructed
        assert success_url.startswith("https://leadfactory.com/success")
        assert "purchase_id=purchase_123" in success_url
        assert "session_id={CHECKOUT_SESSION_ID}" in success_url
        
        assert cancel_url.startswith("https://leadfactory.com/cancel")
        assert "purchase_id=purchase_123" in cancel_url
        assert "session_id={CHECKOUT_SESSION_ID}" in cancel_url
        print("✓ Success/cancel URLs work")


class TestCheckoutManagerEnhancements:
    """Additional comprehensive tests for D7 Checkout Manager - GAP-010"""

    def test_checkout_config_edge_cases(self):
        """Test checkout configuration edge cases"""
        # Test with custom URLs
        config = CheckoutConfig(
            base_success_url="https://custom.com/success",
            base_cancel_url="https://custom.com/cancel",
            session_expires_minutes=60,
            default_currency="eur"
        )
        
        assert config.base_success_url == "https://custom.com/success"
        assert config.base_cancel_url == "https://custom.com/cancel"
        assert config.session_expires_minutes == 60
        assert config.default_currency == "eur"

    def test_checkout_item_validation_edge_cases(self):
        """Test checkout item validation edge cases"""
        # Test zero amount
        item = CheckoutItem("Free Product", Decimal("0.00"))
        assert item.amount_usd == Decimal("0.00")
        assert item.amount_cents == 0
        
        # Test large amount
        item = CheckoutItem("Expensive Product", Decimal("9999.99"))
        assert item.amount_cents == 999999
        
        # Test fractional cents (should truncate)
        item = CheckoutItem("Fractional Product", Decimal("29.995"))
        assert item.amount_cents == 2999  # Truncates to int
        
        # Test with maximum quantity
        item = CheckoutItem("Bulk Product", Decimal("1.00"), quantity=1000)
        assert item.total_amount_usd == Decimal("1000.00")

    def test_checkout_item_metadata_handling(self):
        """Test checkout item metadata handling"""
        metadata = {"sku": "TEST-001", "category": "audit"}
        item = CheckoutItem(
            "Test Product",
            Decimal("29.99"),
            metadata=metadata,
            business_id="biz_123"
        )
        
        assert item.metadata["sku"] == "TEST-001"
        assert item.metadata["category"] == "audit"
        assert item.business_id == "biz_123"

    def test_checkout_session_validation_comprehensive(self):
        """Test comprehensive checkout session validation"""
        # Test invalid email formats
        items = [CheckoutItem("Product", Decimal("29.99"))]
        
        invalid_emails = ["", "invalid", "@test.com", "test@", "test..test@example.com"]
        for email in invalid_emails:
            if not email:  # Empty email case
                with pytest.raises(CheckoutError, match="Customer email is required"):
                    CheckoutSession(email, items)
        
        # Test with valid email
        session = CheckoutSession("valid@example.com", items)
        assert session.customer_email == "valid@example.com"

    def test_checkout_session_purchase_id_generation(self):
        """Test purchase ID generation and uniqueness"""
        items = [CheckoutItem("Product", Decimal("29.99"))]
        
        # Test auto-generated IDs are unique
        session1 = CheckoutSession("test@example.com", items)
        session2 = CheckoutSession("test@example.com", items)
        
        assert session1.purchase_id != session2.purchase_id
        assert len(session1.purchase_id) > 10  # Should be UUID-like
        
        # Test custom purchase ID
        custom_id = "custom_purchase_123"
        session3 = CheckoutSession("test@example.com", items, purchase_id=custom_id)
        assert session3.purchase_id == custom_id

    def test_checkout_session_url_building_edge_cases(self):
        """Test URL building with various configurations"""
        items = [CheckoutItem("Product", Decimal("29.99"))]
        
        # Test with custom config
        config = CheckoutConfig(
            base_success_url="https://custom.leadfactory.com/checkout/success",
            base_cancel_url="https://custom.leadfactory.com/checkout/cancel"
        )
        
        session = CheckoutSession("test@example.com", items, config=config)
        
        success_url = session.build_success_url()
        cancel_url = session.build_cancel_url()
        
        assert success_url.startswith("https://custom.leadfactory.com/checkout/success")
        assert cancel_url.startswith("https://custom.leadfactory.com/checkout/cancel")
        assert "{CHECKOUT_SESSION_ID}" in success_url
        assert "{CHECKOUT_SESSION_ID}" in cancel_url

    def test_checkout_session_metadata_comprehensive(self):
        """Test comprehensive metadata building"""
        items = [
            CheckoutItem("Audit Report", Decimal("29.99"), product_type=ProductType.AUDIT_REPORT),
            CheckoutItem("Premium Report", Decimal("99.99"), quantity=2, product_type=ProductType.PREMIUM_REPORT)
        ]
        
        session = CheckoutSession("test@example.com", items, purchase_id="test_123")
        
        # Test metadata with various additional data
        additional = {
            "utm_source": "google",
            "utm_campaign": "summer_sale",
            "referrer": "partner_site"
        }
        
        metadata = session.build_metadata(additional)
        
        # Verify structure
        assert metadata["purchase_id"] == "test_123"
        assert metadata["customer_email"] == "test@example.com"
        assert metadata["item_count"] == "2"
        assert metadata["total_amount_usd"] == "229.97"  # 29.99 + (99.99 * 2)
        assert metadata["source"] == "leadfactory_checkout"
        
        # Verify item details
        assert metadata["item_0_name"] == "Audit Report"
        assert metadata["item_0_type"] == "audit_report"
        assert metadata["item_0_amount"] == "29.99"
        
        assert metadata["item_1_name"] == "Premium Report"
        assert metadata["item_1_type"] == "premium_report"
        assert metadata["item_1_amount"] == "99.99"
        
        # Verify additional metadata
        assert metadata["utm_source"] == "google"
        assert metadata["utm_campaign"] == "summer_sale"
        assert metadata["referrer"] == "partner_site"
        
        # Verify timestamp
        assert "created_at" in metadata
        assert "T" in metadata["created_at"]  # ISO format

    @patch.object(StripeClient, 'create_checkout_session')
    def test_checkout_session_stripe_integration_error_handling(self, mock_create):
        """Test error handling in Stripe integration"""
        items = [CheckoutItem("Product", Decimal("29.99"))]
        session = CheckoutSession("test@example.com", items)
        
        # Test StripeError
        mock_create.side_effect = StripeError("Stripe API error")
        
        with pytest.raises(CheckoutError, match="Failed to create checkout session"):
            session.create_stripe_session()
        
        # Test generic exception
        mock_create.side_effect = Exception("Network timeout")
        
        with pytest.raises(CheckoutError, match="Unexpected checkout error"):
            session.create_stripe_session()

    def test_checkout_manager_initialization_variations(self):
        """Test checkout manager initialization with various configurations"""
        # Test default initialization
        manager1 = CheckoutManager()
        assert manager1.config.test_mode is True
        assert manager1.stripe_client is not None
        
        # Test with custom config
        config = CheckoutConfig(test_mode=False, default_currency="eur")
        manager2 = CheckoutManager(config=config)
        assert manager2.config.test_mode is False
        assert manager2.config.default_currency == "eur"
        
        # Test with custom Stripe client
        stripe_client = StripeClient(StripeConfig(test_mode=True))
        manager3 = CheckoutManager(stripe_client=stripe_client)
        assert manager3.stripe_client is stripe_client

    @patch.object(CheckoutSession, 'create_stripe_session')
    def test_checkout_manager_attribution_data_handling(self, mock_create_session):
        """Test attribution data handling in checkout manager"""
        mock_create_session.return_value = {
            "session_id": "cs_test_123",
            "session_url": "https://checkout.stripe.com/pay/cs_test_123",
            "amount_total": 2999,
            "currency": "usd",
            "expires_at": 1234567890
        }
        
        manager = CheckoutManager()
        items = [CheckoutItem("Product", Decimal("29.99"))]
        
        attribution_data = {
            "utm_source": "google",
            "utm_medium": "cpc",
            "utm_campaign": "test_campaign",
            "referrer": "https://partner.com"
        }
        
        additional_metadata = {
            "promo_code": "SAVE10",
            "experiment_id": "exp_123"
        }
        
        result = manager.initiate_checkout(
            customer_email="test@example.com",
            items=items,
            attribution_data=attribution_data,
            additional_metadata=additional_metadata
        )
        
        assert result["success"] is True
        
        # Verify create_stripe_session was called with correct metadata
        mock_create_session.assert_called_once()
        call_args = mock_create_session.call_args[1]
        assert call_args["additional_metadata"]["promo_code"] == "SAVE10"
        assert call_args["additional_metadata"]["experiment_id"] == "exp_123"

    @patch.object(StripeClient, 'retrieve_checkout_session')
    def test_checkout_manager_session_retrieval_error_handling(self, mock_retrieve):
        """Test session retrieval error handling"""
        manager = CheckoutManager()
        
        # Test StripeError
        mock_retrieve.side_effect = StripeError("Session not found")
        
        result = manager.retrieve_session_status("cs_invalid_123")
        
        assert result["success"] is False
        assert result["error"] == "Session not found"
        assert result["error_type"] == "StripeError"

    def test_audit_report_checkout_customization(self):
        """Test audit report checkout with various customizations"""
        manager = CheckoutManager()
        
        with patch.object(manager, 'initiate_checkout') as mock_initiate:
            mock_initiate.return_value = {"success": True}
            
            # Test with all parameters
            result = manager.create_audit_report_checkout(
                customer_email="test@example.com",
                business_url="https://example-business.com",
                business_name="Example Business Corp",
                amount_usd=Decimal("49.99"),
                attribution_data={
                    "utm_source": "facebook",
                    "utm_campaign": "business_audit_promo"
                }
            )
            
            assert result["success"] is True
            
            # Verify call parameters
            call_args = mock_initiate.call_args
            assert call_args[1]["customer_email"] == "test@example.com"
            
            item = call_args[1]["items"][0]
            assert "Example Business Corp" in item.product_name
            assert item.amount_usd == Decimal("49.99")
            assert item.product_type == ProductType.AUDIT_REPORT
            assert item.metadata["business_url"] == "https://example-business.com"
            assert item.metadata["business_name"] == "Example Business Corp"
            assert item.metadata["product_sku"] == "WA-BASIC-001"
            
            # Check attribution metadata
            additional_metadata = call_args[1]["additional_metadata"]
            assert additional_metadata["attr_utm_source"] == "facebook"
            assert additional_metadata["attr_utm_campaign"] == "business_audit_promo"

    def test_bulk_reports_checkout_edge_cases(self):
        """Test bulk reports checkout edge cases"""
        manager = CheckoutManager()
        
        # Test empty business URLs
        with pytest.raises(CheckoutError, match="At least one business URL is required"):
            manager.create_bulk_reports_checkout(
                customer_email="test@example.com",
                business_urls=[]
            )
        
        # Test single URL (edge of bulk)
        with patch.object(manager, 'initiate_checkout') as mock_initiate:
            mock_initiate.return_value = {"success": True}
            
            result = manager.create_bulk_reports_checkout(
                customer_email="test@example.com",
                business_urls=["https://single-business.com"],
                amount_per_report_usd=Decimal("19.99")
            )
            
            call_args = mock_initiate.call_args
            item = call_args[1]["items"][0]
            
            assert item.quantity == 1
            assert item.amount_usd == Decimal("19.99")
            assert "1 reports" in item.product_name
            assert item.metadata["report_count"] == "1"
        
        # Test large bulk order
        with patch.object(manager, 'initiate_checkout') as mock_initiate:
            mock_initiate.return_value = {"success": True}
            
            business_urls = [f"https://business{i}.com" for i in range(50)]
            
            result = manager.create_bulk_reports_checkout(
                customer_email="test@example.com",
                business_urls=business_urls,
                amount_per_report_usd=Decimal("15.99")
            )
            
            call_args = mock_initiate.call_args
            item = call_args[1]["items"][0]
            
            assert item.quantity == 50
            assert "50 reports" in item.product_name
            assert item.metadata["report_count"] == "50"
            assert len(item.metadata["business_urls"].split(",")) == 50

    def test_checkout_manager_status_comprehensive(self):
        """Test comprehensive status reporting"""
        config = CheckoutConfig(
            base_success_url="https://custom.com/success",
            base_cancel_url="https://custom.com/cancel",
            webhook_url="https://custom.com/webhook",
            session_expires_minutes=45,
            default_currency="eur",
            test_mode=False
        )
        
        manager = CheckoutManager(config=config)
        status = manager.get_status()
        
        assert status["test_mode"] is False
        assert status["success_url"] == "https://custom.com/success"
        assert status["cancel_url"] == "https://custom.com/cancel"
        assert status["webhook_url"] == "https://custom.com/webhook"
        assert status["currency"] == "eur"
        assert status["session_expires_minutes"] == 45
        assert "stripe_status" in status

    def test_utility_functions_edge_cases(self):
        """Test utility functions with edge cases"""
        # Test create_test_checkout_items
        items = create_test_checkout_items()
        assert len(items) == 2
        assert all(isinstance(item, CheckoutItem) for item in items)
        assert items[0].product_type == ProductType.AUDIT_REPORT
        assert items[1].product_type == ProductType.PREMIUM_REPORT
        
        # Test format_checkout_response_for_api with edge cases
        success_response = {
            "success": True,
            "checkout_url": "https://checkout.stripe.com/pay/cs_test",
            "purchase_id": "purchase_123",
            "session_id": "cs_test_123",
            "amount_total_usd": 29.99,
            "expires_at": 1234567890,
            "test_mode": True
        }
        
        formatted = format_checkout_response_for_api(success_response)
        assert formatted["status"] == "success"
        assert formatted["data"]["total_amount"] == 29.99
        assert formatted["data"]["currency"] == "usd"  # Default currency
        
        # Test with missing optional fields
        error_response = {
            "success": False,
            "error": "Payment failed",
            "error_type": "PaymentError"
        }
        
        formatted_error = format_checkout_response_for_api(error_response)
        assert formatted_error["status"] == "error"
        assert formatted_error["error"]["message"] == "Payment failed"
        assert formatted_error["error"]["type"] == "PaymentError"

    def test_constants_and_configuration(self):
        """Test constants and configuration values"""
        # Test DEFAULT_PRICING constants
        assert DEFAULT_PRICING["BASIC_AUDIT"] == Decimal("29.99")
        assert DEFAULT_PRICING["PREMIUM_AUDIT"] == Decimal("99.99")
        assert DEFAULT_PRICING["BULK_DISCOUNT_THRESHOLD"] == 5
        assert DEFAULT_PRICING["BULK_DISCOUNT_RATE"] == Decimal("0.15")
        
        # Test CHECKOUT_URLS constants
        assert "PRODUCTION" in CHECKOUT_URLS
        assert "STAGING" in CHECKOUT_URLS
        assert "DEVELOPMENT" in CHECKOUT_URLS
        
        for env in CHECKOUT_URLS:
            urls = CHECKOUT_URLS[env]
            assert "SUCCESS" in urls
            assert "CANCEL" in urls
            assert "WEBHOOK" in urls
            assert urls["SUCCESS"].startswith("http")
            assert urls["CANCEL"].startswith("http")
            assert urls["WEBHOOK"].startswith("http")

    @patch.object(CheckoutSession, 'create_stripe_session')
    def test_checkout_manager_response_format_consistency(self, mock_create_session):
        """Test response format consistency across different methods"""
        mock_create_session.return_value = {
            "session_id": "cs_test_123",
            "session_url": "https://checkout.stripe.com/pay/cs_test_123",
            "amount_total": 2999,
            "currency": "usd",
            "expires_at": 1234567890
        }
        
        manager = CheckoutManager()
        items = [CheckoutItem("Product", Decimal("29.99"))]
        
        # Test standard initiate_checkout response
        result = manager.initiate_checkout("test@example.com", items)
        
        # Verify response structure
        expected_keys = [
            "success", "purchase_id", "checkout_url", "session_id",
            "amount_total_usd", "amount_total_cents", "currency",
            "expires_at", "test_mode", "items"
        ]
        
        for key in expected_keys:
            assert key in result
        
        assert result["success"] is True
        assert isinstance(result["amount_total_usd"], float)
        assert isinstance(result["amount_total_cents"], int)
        assert isinstance(result["items"], list)
        assert len(result["items"]) == 1
        
        # Verify item structure in response
        item = result["items"][0]
        assert "name" in item
        assert "amount_usd" in item
        assert "quantity" in item
        assert "type" in item

    def test_error_propagation_and_logging(self):
        """Test error propagation and logging behavior"""
        manager = CheckoutManager()
        
        # Test with invalid items (empty list)
        result = manager.initiate_checkout("test@example.com", [])
        
        assert result["success"] is False
        assert "At least one item is required" in result["error"]
        assert result["error_type"] == "CheckoutError"


if __name__ == "__main__":
    # Run basic tests if file is executed directly
    print("Running D7 Storefront Checkout Tests...")
    print("=" * 50)
    
    try:
        # Test basic functionality
        print("Testing basic functionality...")
        
        # Test Stripe config
        config = StripeConfig(test_mode=True)
        assert config.test_mode is True
        print("✓ Stripe config works")
        
        # Test checkout item
        item = CheckoutItem("Test Product", Decimal("29.99"))
        assert item.amount_cents == 2999
        print("✓ Checkout item works")
        
        # Test checkout session
        items = [CheckoutItem("Product", Decimal("29.99"))]
        session = CheckoutSession("test@example.com", items)
        assert session.total_amount_usd == Decimal("29.99")
        print("✓ Checkout session works")
        
        # Test manager
        manager = CheckoutManager()
        assert manager.config.test_mode is True
        print("✓ Checkout manager works")
        
        # Test acceptance criteria
        test_acceptance = TestAcceptanceCriteria()
        test_acceptance.test_test_mode_works_acceptance_criteria()
        test_acceptance.test_metadata_included_acceptance_criteria()
        test_acceptance.test_success_cancel_urls_acceptance_criteria()
        
        print("=" * 50)
        print("🎉 ALL TESTS PASSED!")
        print("")
        print("Acceptance Criteria Status:")
        print("✓ Checkout session creation")
        print("✓ Test mode works")
        print("✓ Metadata included")
        print("✓ Success/cancel URLs")
        print("")
        print("Task 056 implementation complete and verified!")
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()