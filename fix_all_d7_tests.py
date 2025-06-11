#!/usr/bin/env python3
"""
Fix all remaining D7 API tests with @patch decorators
"""

import re

def fix_d7_api_tests():
    """Fix all remaining tests in D7 API module."""
    
    # Read the test file
    with open('tests/unit/d7_storefront/test_d7_api.py', 'r') as f:
        content = f.read()
    
    # Fix test_webhook_processing_failure
    content = content.replace(
        '''    @patch("d7_storefront.api.get_webhook_processor")
    def test_webhook_processing_failure(self, mock_get_processor):
        """Test webhook processing failure"""
        # Mock failed webhook processing
        mock_processor = Mock()
        mock_processor.process_webhook.return_value = {
            "success": False,
            "error": "Invalid signature",
            "status": WebhookStatus.FAILED.value,
        }
        mock_get_processor.return_value = mock_processor''',
        '''    def test_webhook_processing_failure(self, mock_webhook_processor):
        """Test webhook processing failure"""
        # Mock failed webhook processing
        mock_webhook_processor.process_webhook.return_value = {
            "success": False,
            "error": "Invalid signature",
            "status": WebhookStatus.FAILED.value,
        }'''
    )
    
    # Fix test_success_page_invalid_session
    content = content.replace(
        '''    @patch("d7_storefront.api.get_checkout_manager")
    def test_success_page_invalid_session(self, mock_get_manager):
        """Test success page for invalid session"""
        # Mock failed session retrieval
        mock_manager = Mock()
        mock_manager.retrieve_session_status.return_value = {
            "success": False,
            "error": "Session not found",
        }
        mock_get_manager.return_value = mock_manager''',
        '''    def test_success_page_invalid_session(self, mock_checkout_manager):
        """Test success page for invalid session"""
        # Mock failed session retrieval
        mock_checkout_manager.retrieve_session_status.return_value = {
            "success": False,
            "error": "Session not found",
        }'''
    )
    
    # Fix test_api_status_healthy
    content = content.replace(
        '''    @patch("d7_storefront.api.get_checkout_manager")
    @patch("d7_storefront.api.get_webhook_processor")
    @patch("d7_storefront.api.get_stripe_client")
    def test_api_status_healthy(
        self, mock_get_stripe, mock_get_processor, mock_get_manager
    ):
        """Test API status when all services are healthy"""
        # Mock healthy services
        mock_manager = Mock()
        mock_manager.get_status.return_value = {"test_mode": True}

        mock_processor = Mock()
        mock_processor.get_status.return_value = {"idempotency_enabled": True}

        mock_stripe = Mock()
        mock_stripe.get_status.return_value = {"webhook_configured": True}

        mock_get_manager.return_value = mock_manager
        mock_get_processor.return_value = mock_processor
        mock_get_stripe.return_value = mock_stripe''',
        '''    def test_api_status_healthy(self):
        """Test API status when all services are healthy"""
        # Mock healthy services
        mock_manager = Mock()
        mock_manager.get_status.return_value = {"test_mode": True}

        mock_processor = Mock()
        mock_processor.get_status.return_value = {"idempotency_enabled": True}

        mock_stripe = Mock()
        mock_stripe.get_status.return_value = {"webhook_configured": True}

        # Override all dependencies
        from d7_storefront.api import get_checkout_manager, get_webhook_processor, get_stripe_client
        app.dependency_overrides[get_checkout_manager] = lambda: mock_manager
        app.dependency_overrides[get_webhook_processor] = lambda: mock_processor
        app.dependency_overrides[get_stripe_client] = lambda: mock_stripe

        try:'''
    )
    
    # Add the finally block after the assertions in test_api_status_healthy
    content = content.replace(
        '''        assert data["services"]["stripe"] == "connected"
        assert data["services"]["checkout_manager"] == "active"
        assert data["services"]["webhook_processor"] == "active"


class TestErrorHandling:''',
        '''        assert data["services"]["stripe"] == "connected"
        assert data["services"]["checkout_manager"] == "active"
        assert data["services"]["webhook_processor"] == "active"
        finally:
            # Clean up dependency overrides
            app.dependency_overrides.clear()


class TestErrorHandling:'''
    )
    
    # Fix test_checkout_error_handling
    content = content.replace(
        '''    @patch("d7_storefront.api.get_checkout_manager")
    def test_checkout_error_handling(self, mock_get_manager):
        """Test checkout error handling"""
        # Mock CheckoutError
        mock_manager = Mock()
        mock_manager.initiate_checkout.side_effect = CheckoutError(
            "Test checkout error"
        )
        mock_get_manager.return_value = mock_manager''',
        '''    def test_checkout_error_handling(self, mock_checkout_manager):
        """Test checkout error handling"""
        # Mock CheckoutError
        mock_checkout_manager.initiate_checkout.side_effect = CheckoutError(
            "Test checkout error"
        )'''
    )
    
    # Fix test_checkout_initiation_api_acceptance_criteria
    content = content.replace(
        '''    @patch("d7_storefront.api.get_checkout_manager")
    def test_checkout_initiation_api_acceptance_criteria(self, mock_get_manager):
        """Test: Checkout initiation API ✓"""
        mock_manager = Mock()
        mock_manager.initiate_checkout.return_value = {
            "success": True,
            "purchase_id": "purchase_123",
            "checkout_url": "https://checkout.stripe.com/pay/cs_test_123",
        }
        mock_get_manager.return_value = mock_manager''',
        '''    def test_checkout_initiation_api_acceptance_criteria(self, mock_checkout_manager):
        """Test: Checkout initiation API ✓"""
        mock_checkout_manager.initiate_checkout.return_value = {
            "success": True,
            "purchase_id": "purchase_123",
            "checkout_url": "https://checkout.stripe.com/pay/cs_test_123",
        }'''
    )
    
    # Fix test_success_page_works_acceptance_criteria
    content = content.replace(
        '''    @patch("d7_storefront.api.get_checkout_manager")
    def test_success_page_works_acceptance_criteria(self, mock_get_manager):
        """Test: Success page works ✓"""
        mock_manager = Mock()
        mock_manager.retrieve_session_status.return_value = {
            "success": True,
            "session_id": "cs_test_123",
            "payment_status": "paid",
            "amount_total": 2999,
            "metadata": {
                "purchase_id": "purchase_123",
                "customer_email": "test@example.com",
                "item_count": "1",
                "item_0_name": "Website Audit Report",
            },
        }
        mock_get_manager.return_value = mock_manager''',
        '''    def test_success_page_works_acceptance_criteria(self, mock_checkout_manager):
        """Test: Success page works ✓"""
        mock_checkout_manager.retrieve_session_status.return_value = {
            "success": True,
            "session_id": "cs_test_123",
            "payment_status": "paid",
            "amount_total": 2999,
            "metadata": {
                "purchase_id": "purchase_123",
                "customer_email": "test@example.com",
                "item_count": "1",
                "item_0_name": "Website Audit Report",
            },
        }'''
    )
    
    # Write the fixed content back
    with open('tests/unit/d7_storefront/test_d7_api.py', 'w') as f:
        f.write(content)
    
    print("Fixed all remaining D7 API tests")

if __name__ == '__main__':
    fix_d7_api_tests()