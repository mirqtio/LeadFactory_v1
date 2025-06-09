"""
D7 Storefront Stripe Client - Task 056

Stripe integration for handling checkout sessions and payment processing.

Acceptance Criteria:
- Checkout session creation ✓
- Test mode works ✓
- Metadata included ✓
- Success/cancel URLs ✓
"""

import os
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
import stripe
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)


class StripeConfig:
    """Configuration for Stripe integration"""
    
    def __init__(self, test_mode: bool = True):
        self.test_mode = test_mode
        
        # Get API keys from environment
        if test_mode:
            self.api_key = os.getenv("STRIPE_TEST_SECRET_KEY", "sk_test_mock_key_for_testing")
            self.publishable_key = os.getenv("STRIPE_TEST_PUBLISHABLE_KEY", "pk_test_mock_key_for_testing")
            self.webhook_secret = os.getenv("STRIPE_TEST_WEBHOOK_SECRET", "whsec_test_mock_secret")
        else:
            self.api_key = os.getenv("STRIPE_LIVE_SECRET_KEY")
            self.publishable_key = os.getenv("STRIPE_LIVE_PUBLISHABLE_KEY") 
            self.webhook_secret = os.getenv("STRIPE_LIVE_WEBHOOK_SECRET")
        
        # Validate required keys
        if not self.api_key:
            raise ValueError(f"Missing Stripe API key for {'test' if test_mode else 'live'} mode")
        
        # Configure Stripe
        stripe.api_key = self.api_key
        
        # Default configuration
        self.currency = "usd"
        self.session_expires_after_minutes = 30
        self.automatic_tax = False
        self.billing_address_collection = "auto"
        self.allow_promotion_codes = True


class StripeCheckoutSession:
    """Data class for Stripe checkout session configuration"""
    
    def __init__(
        self,
        line_items: List[Dict[str, Any]],
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        mode: str = "payment",
        payment_method_types: Optional[List[str]] = None
    ):
        self.line_items = line_items
        self.success_url = success_url
        self.cancel_url = cancel_url
        self.customer_email = customer_email
        self.metadata = metadata or {}
        self.mode = mode
        self.payment_method_types = payment_method_types or ["card"]
    
    def to_stripe_params(self, config: StripeConfig) -> Dict[str, Any]:
        """Convert to Stripe API parameters"""
        params = {
            "line_items": self.line_items,
            "mode": self.mode,
            "payment_method_types": self.payment_method_types,
            "success_url": self.success_url,
            "cancel_url": self.cancel_url,
            "expires_at": int((datetime.utcnow() + timedelta(minutes=config.session_expires_after_minutes)).timestamp()),
            "billing_address_collection": config.billing_address_collection,
            "allow_promotion_codes": config.allow_promotion_codes,
            "metadata": self.metadata
        }
        
        # Add customer email if provided
        if self.customer_email:
            params["customer_email"] = self.customer_email
        
        # Add automatic tax if configured
        if config.automatic_tax:
            params["automatic_tax"] = {"enabled": True}
        
        return params


class StripeError(Exception):
    """Custom exception for Stripe-related errors"""
    
    def __init__(self, message: str, stripe_error: Optional[stripe.error.StripeError] = None):
        super().__init__(message)
        self.stripe_error = stripe_error
        self.error_code = stripe_error.code if stripe_error else None
        self.error_type = stripe_error.type if stripe_error else None


class StripeClient:
    """
    Stripe client for handling checkout sessions and payment processing
    
    Acceptance Criteria:
    - Checkout session creation ✓
    - Test mode works ✓
    - Metadata included ✓
    - Success/cancel URLs ✓
    """
    
    def __init__(self, config: Optional[StripeConfig] = None):
        self.config = config or StripeConfig(test_mode=True)
        self.stripe = stripe
        
        logger.info(f"Initialized Stripe client in {'test' if self.config.test_mode else 'live'} mode")
    
    def create_checkout_session(self, session_config: StripeCheckoutSession) -> Dict[str, Any]:
        """
        Create a Stripe checkout session
        
        Acceptance Criteria: Checkout session creation ✓
        """
        try:
            # Convert to Stripe parameters
            params = session_config.to_stripe_params(self.config)
            
            logger.info(f"Creating checkout session with params: {params}")
            
            # Create session via Stripe API
            session = stripe.checkout.Session.create(**params)
            
            logger.info(f"Created checkout session: {session.id}")
            
            # Return formatted response
            return {
                "success": True,
                "session_id": session.id,
                "session_url": session.url,
                "payment_status": session.payment_status,
                "amount_total": session.amount_total,
                "currency": session.currency,
                "expires_at": session.expires_at,
                "metadata": session.metadata,
                "mode": session.mode,
                "success_url": session.success_url,
                "cancel_url": session.cancel_url
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise StripeError(f"Failed to create checkout session: {e.user_message}", e)
        except Exception as e:
            logger.error(f"Unexpected error creating checkout session: {e}")
            raise StripeError(f"Unexpected error: {str(e)}")
    
    def retrieve_checkout_session(self, session_id: str) -> Dict[str, Any]:
        """Retrieve a checkout session by ID"""
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            
            return {
                "success": True,
                "session_id": session.id,
                "payment_status": session.payment_status,
                "payment_intent": session.payment_intent,
                "customer": session.customer,
                "amount_total": session.amount_total,
                "currency": session.currency,
                "metadata": session.metadata,
                "status": session.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving session {session_id}: {e}")
            raise StripeError(f"Failed to retrieve session: {e.user_message}", e)
    
    def create_customer(self, email: str, name: Optional[str] = None, metadata: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Create a Stripe customer"""
        try:
            params = {
                "email": email,
                "metadata": metadata or {}
            }
            
            if name:
                params["name"] = name
            
            customer = stripe.Customer.create(**params)
            
            return {
                "success": True,
                "customer_id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "created": customer.created
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer: {e}")
            raise StripeError(f"Failed to create customer: {e.user_message}", e)
    
    def create_product(self, name: str, description: Optional[str] = None, metadata: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Create a Stripe product"""
        try:
            params = {
                "name": name,
                "metadata": metadata or {}
            }
            
            if description:
                params["description"] = description
            
            product = stripe.Product.create(**params)
            
            return {
                "success": True,
                "product_id": product.id,
                "name": product.name,
                "description": product.description,
                "active": product.active
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating product: {e}")
            raise StripeError(f"Failed to create product: {e.user_message}", e)
    
    def create_price(self, product_id: str, amount_cents: int, currency: str = "usd", recurring: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Create a Stripe price"""
        try:
            params = {
                "product": product_id,
                "unit_amount": amount_cents,
                "currency": currency
            }
            
            if recurring:
                params["recurring"] = recurring
            
            price = stripe.Price.create(**params)
            
            return {
                "success": True,
                "price_id": price.id,
                "product_id": price.product,
                "unit_amount": price.unit_amount,
                "currency": price.currency,
                "type": price.type
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating price: {e}")
            raise StripeError(f"Failed to create price: {e.user_message}", e)
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Stripe webhook signature"""
        try:
            stripe.Webhook.construct_event(
                payload, signature, self.config.webhook_secret
            )
            return True
        except stripe.error.SignatureVerificationError:
            logger.warning("Invalid webhook signature")
            return False
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    def construct_webhook_event(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """Construct and validate webhook event"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.config.webhook_secret
            )
            
            return {
                "success": True,
                "event_id": event.id,
                "event_type": event.type,
                "data": event.data,
                "created": event.created,
                "livemode": event.livemode
            }
            
        except stripe.error.SignatureVerificationError as e:
            logger.warning(f"Invalid webhook signature: {e}")
            raise StripeError("Invalid webhook signature", e)
        except Exception as e:
            logger.error(f"Error constructing webhook event: {e}")
            raise StripeError(f"Failed to construct event: {str(e)}")
    
    def get_test_clock(self) -> Optional[str]:
        """Get test clock ID for test mode (for testing time-based features)"""
        if not self.config.test_mode:
            return None
        
        try:
            clocks = stripe.test_helpers.TestClock.list(limit=1)
            if clocks.data:
                return clocks.data[0].id
            return None
        except Exception as e:
            logger.warning(f"Could not retrieve test clock: {e}")
            return None
    
    def is_test_mode(self) -> bool:
        """Check if client is in test mode"""
        return self.config.test_mode
    
    def get_api_version(self) -> str:
        """Get Stripe API version"""
        return stripe.api_version
    
    def get_status(self) -> Dict[str, Any]:
        """Get client status for monitoring"""
        return {
            "test_mode": self.config.test_mode,
            "api_version": stripe.api_version,
            "currency": self.config.currency,
            "webhook_configured": bool(self.config.webhook_secret),
            "session_expires_minutes": self.config.session_expires_after_minutes
        }


# Utility functions for common operations
def create_line_item(price_id: str, quantity: int = 1) -> Dict[str, Any]:
    """Create a line item for checkout session"""
    return {
        "price": price_id,
        "quantity": quantity
    }


def create_one_time_line_item(product_name: str, amount_cents: int, quantity: int = 1, currency: str = "usd") -> Dict[str, Any]:
    """Create a one-time payment line item"""
    return {
        "price_data": {
            "currency": currency,
            "product_data": {
                "name": product_name
            },
            "unit_amount": amount_cents
        },
        "quantity": quantity
    }


def format_amount_for_stripe(amount_usd: Decimal) -> int:
    """Convert USD amount to cents for Stripe"""
    return int(amount_usd * 100)


def format_amount_from_stripe(amount_cents: int) -> Decimal:
    """Convert cents from Stripe to USD amount"""
    return Decimal(amount_cents) / 100


# Constants for common Stripe configurations
PAYMENT_METHOD_TYPES = {
    "CARD_ONLY": ["card"],
    "CARD_AND_BANK": ["card", "us_bank_account"],
    "ALL_METHODS": ["card", "us_bank_account", "cashapp"],
    "MOBILE_OPTIMIZED": ["card", "cashapp", "link"]
}

SESSION_MODES = {
    "PAYMENT": "payment",      # One-time payment
    "SUBSCRIPTION": "subscription",  # Recurring subscription
    "SETUP": "setup"          # Setup for future payments
}

BILLING_ADDRESS_COLLECTION = {
    "AUTO": "auto",
    "REQUIRED": "required"
}