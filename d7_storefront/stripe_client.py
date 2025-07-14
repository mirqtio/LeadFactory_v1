"""
D7 Storefront Stripe Client - Task 056

Stripe integration for handling checkout sessions and payment processing.
Refactored to use Gateway facade instead of direct Stripe SDK usage.

Acceptance Criteria:
- Checkout session creation ✓
- Test mode works ✓
- Metadata included ✓
- Success/cancel URLs ✓
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

import stripe

from d0_gateway.facade import get_gateway_facade

# Configure logging
logger = logging.getLogger(__name__)


class StripeConfig:
    """Configuration for Stripe integration"""

    def __init__(self, test_mode: bool = True):
        self.test_mode = test_mode

        # Set API keys based on mode
        if test_mode:
            self.api_key = os.getenv("STRIPE_TEST_SECRET_KEY", "sk_test_mock_key_for_testing")
            self.publishable_key = os.getenv("STRIPE_TEST_PUBLISHABLE_KEY", "pk_test_mock_key_for_testing")
            self.webhook_secret = os.getenv("STRIPE_TEST_WEBHOOK_SECRET", "whsec_test_mock_secret")
        else:
            self.api_key = os.getenv("STRIPE_LIVE_SECRET_KEY")
            self.publishable_key = os.getenv("STRIPE_LIVE_PUBLISHABLE_KEY")
            self.webhook_secret = os.getenv("STRIPE_LIVE_WEBHOOK_SECRET")

            # Validate required keys for live mode
            if not self.api_key:
                raise ValueError(
                    "Missing Stripe API key for live mode. Set STRIPE_LIVE_SECRET_KEY environment variable."
                )
            if not self.publishable_key:
                raise ValueError(
                    "Missing Stripe publishable key for live mode. Set STRIPE_LIVE_PUBLISHABLE_KEY environment variable."
                )
            if not self.webhook_secret:
                raise ValueError(
                    "Missing Stripe webhook secret for live mode. Set STRIPE_LIVE_WEBHOOK_SECRET environment variable."
                )

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
        payment_method_types: Optional[List[str]] = None,
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
            "expires_at": int(
                (datetime.utcnow() + timedelta(minutes=config.session_expires_after_minutes)).timestamp()
            ),
            "billing_address_collection": config.billing_address_collection,
            "allow_promotion_codes": config.allow_promotion_codes,
            "metadata": self.metadata,
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

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        error_type: Optional[str] = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.error_type = error_type


class StripeClient:
    """
    Stripe client for handling checkout sessions and payment processing
    Uses Gateway facade instead of direct Stripe SDK calls

    Acceptance Criteria:
    - Checkout session creation ✓
    - Test mode works ✓
    - Metadata included ✓
    - Success/cancel URLs ✓
    """

    def __init__(self, config: Optional[StripeConfig] = None):
        self.config = config or StripeConfig(test_mode=True)
        self.gateway = get_gateway_facade()
        self._executor = ThreadPoolExecutor(max_workers=1)

        # For compatibility with tests that expect direct Stripe SDK access
        self.stripe = stripe

        logger.info(f"Initialized Stripe client in {'test' if self.config.test_mode else 'live'} mode")

    def _run_async(self, coro):
        """Helper to run async gateway methods from sync context"""
        try:
            # Check if we're already in an event loop
            asyncio.get_running_loop()
            # If we are, we need to run the coroutine in a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        except RuntimeError:
            # No event loop running, create one
            return asyncio.run(coro)

    def create_checkout_session(self, session_config: StripeCheckoutSession) -> Dict[str, Any]:
        """
        Create a Stripe checkout session

        Acceptance Criteria: Checkout session creation ✓
        """
        try:
            # Convert to Stripe parameters
            params = session_config.to_stripe_params(self.config)

            logger.info("Creating checkout session with line items")

            # Create session via Gateway API
            result = self._run_async(
                self.gateway.create_checkout_session_with_line_items(
                    line_items=params["line_items"],
                    success_url=params["success_url"],
                    cancel_url=params["cancel_url"],
                    customer_email=params.get("customer_email"),
                    metadata=params.get("metadata"),
                    mode=params["mode"],
                    expires_at=params.get("expires_at"),
                    payment_method_types=params.get("payment_method_types"),
                    billing_address_collection=params.get("billing_address_collection"),
                    allow_promotion_codes=params.get("allow_promotion_codes"),
                )
            )

            logger.info(f"Created checkout session: {result.get('id')}")

            # Return formatted response
            return {
                "success": True,
                "session_id": result.get("id"),
                "session_url": result.get("url"),
                "payment_status": result.get("payment_status"),
                "amount_total": result.get("amount_total"),
                "currency": result.get("currency"),
                "expires_at": result.get("expires_at"),
                "metadata": result.get("metadata"),
                "mode": result.get("mode"),
                "success_url": params["success_url"],
                "cancel_url": params["cancel_url"],
            }

        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            raise StripeError(f"Failed to create checkout session: {str(e)}")

    def retrieve_checkout_session(self, session_id: str) -> Dict[str, Any]:
        """Retrieve a checkout session by ID"""
        try:
            result = self._run_async(self.gateway.get_checkout_session(session_id))

            return {
                "success": True,
                "session_id": result.get("id"),
                "payment_status": result.get("payment_status"),
                "payment_intent": result.get("payment_intent"),
                "customer": result.get("customer"),
                "amount_total": result.get("amount_total"),
                "currency": result.get("currency"),
                "metadata": result.get("metadata"),
                "status": result.get("status"),
            }

        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            raise StripeError(f"Failed to retrieve session: {str(e)}")

    def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe customer"""
        try:
            result = self._run_async(self.gateway.create_customer(email=email, name=name, metadata=metadata))

            return {
                "success": True,
                "customer_id": result.get("id"),
                "email": result.get("email"),
                "name": result.get("name"),
                "created": result.get("created"),
            }

        except Exception as e:
            logger.error(f"Error creating customer: {e}")
            raise StripeError(f"Failed to create customer: {str(e)}")

    def create_product(
        self,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe product"""
        try:
            result = self._run_async(self.gateway.create_product(name=name, description=description, metadata=metadata))

            return {
                "success": True,
                "product_id": result.get("id"),
                "name": result.get("name"),
                "description": result.get("description"),
                "active": result.get("active"),
            }

        except Exception as e:
            logger.error(f"Error creating product: {e}")
            raise StripeError(f"Failed to create product: {str(e)}")

    def create_price(
        self,
        product_id: str,
        amount_cents: int,
        currency: str = "usd",
        recurring: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe price"""
        try:
            result = self._run_async(
                self.gateway.create_price(
                    amount=amount_cents,
                    currency=currency,
                    product_id=product_id,
                    recurring=recurring,
                )
            )

            return {
                "success": True,
                "price_id": result.get("id"),
                "product_id": result.get("product"),
                "unit_amount": result.get("unit_amount"),
                "currency": result.get("currency"),
                "type": result.get("type"),
            }

        except Exception as e:
            logger.error(f"Error creating price: {e}")
            raise StripeError(f"Failed to create price: {str(e)}")

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Stripe webhook signature"""
        try:
            self._run_async(
                self.gateway.construct_webhook_event(
                    payload=payload.decode("utf-8"),
                    signature=signature,
                    webhook_secret=self.config.webhook_secret,
                )
            )
            return True
        except Exception as e:
            logger.warning(f"Invalid webhook signature: {e}")
            return False

    def construct_webhook_event(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """Construct and validate webhook event"""
        try:
            result = self._run_async(
                self.gateway.construct_webhook_event(
                    payload=payload.decode("utf-8"),
                    signature=signature,
                    webhook_secret=self.config.webhook_secret,
                )
            )

            return {
                "success": True,
                "event_id": result.get("id"),
                "event_type": result.get("type"),
                "data": result.get("data"),
                "created": result.get("created"),
                "livemode": result.get("livemode"),
            }

        except Exception as e:
            logger.error(f"Error constructing webhook event: {e}")
            raise StripeError(f"Failed to construct event: {str(e)}")

    def get_test_clock(self) -> Optional[str]:
        """Get test clock ID for test mode (for testing time-based features)"""
        if not self.config.test_mode:
            return None

        # Test clock functionality not available via Gateway yet
        logger.warning("Test clock functionality not available via Gateway")
        return None

    def is_test_mode(self) -> bool:
        """Check if client is in test mode"""
        return self.config.test_mode

    def get_api_version(self) -> str:
        """Get Stripe API version"""
        return "2023-10-16"  # Default API version used by Gateway

    def get_status(self) -> Dict[str, Any]:
        """Get client status for monitoring"""
        return {
            "test_mode": self.config.test_mode,
            "api_version": self.get_api_version(),
            "currency": self.config.currency,
            "webhook_configured": bool(self.config.webhook_secret),
            "session_expires_minutes": self.config.session_expires_after_minutes,
            "gateway_enabled": True,
        }


# Utility functions for common operations
def create_line_item(price_id: str, quantity: int = 1) -> Dict[str, Any]:
    """Create a line item for checkout session"""
    return {"price": price_id, "quantity": quantity}


def create_one_time_line_item(
    product_name: str, amount_cents: int, quantity: int = 1, currency: str = "usd"
) -> Dict[str, Any]:
    """Create a one-time payment line item"""
    return {
        "price_data": {
            "currency": currency,
            "product_data": {"name": product_name},
            "unit_amount": amount_cents,
        },
        "quantity": quantity,
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
    "MOBILE_OPTIMIZED": ["card", "cashapp", "link"],
}

SESSION_MODES = {
    "PAYMENT": "payment",  # One-time payment
    "SUBSCRIPTION": "subscription",  # Recurring subscription
    "SETUP": "setup",  # Setup for future payments
}

BILLING_ADDRESS_COLLECTION = {"AUTO": "auto", "REQUIRED": "required"}
