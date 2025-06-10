"""
D7 Storefront Checkout - Task 056

Checkout flow management with Stripe integration for the LeadFactory MVP.

Acceptance Criteria:
- Checkout session creation ✓
- Test mode works ✓
- Metadata included ✓
- Success/cancel URLs ✓
"""

import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .models import (PaymentSession, ProductType, Purchase, PurchaseItem,
                     PurchaseStatus)
from .stripe_client import (PAYMENT_METHOD_TYPES, SESSION_MODES,
                            StripeCheckoutSession, StripeClient, StripeConfig,
                            StripeError, create_one_time_line_item,
                            format_amount_for_stripe)

logger = logging.getLogger(__name__)


class CheckoutError(Exception):
    """Custom exception for checkout-related errors"""

    pass


class CheckoutConfig:
    """Configuration for checkout flow"""

    def __init__(
        self,
        base_success_url: str = "https://leadfactory.com/success",
        base_cancel_url: str = "https://leadfactory.com/cancel",
        webhook_url: str = "https://leadfactory.com/webhooks/stripe",
        session_expires_minutes: int = 30,
        default_currency: str = "usd",
        test_mode: bool = True,
    ):
        self.base_success_url = base_success_url
        self.base_cancel_url = base_cancel_url
        self.webhook_url = webhook_url
        self.session_expires_minutes = session_expires_minutes
        self.default_currency = default_currency
        self.test_mode = test_mode


class CheckoutItem:
    """Item for checkout session"""

    def __init__(
        self,
        product_name: str,
        amount_usd: Decimal,
        quantity: int = 1,
        description: Optional[str] = None,
        product_type: ProductType = ProductType.AUDIT_REPORT,
        business_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.product_name = product_name
        self.amount_usd = amount_usd
        self.quantity = quantity
        self.description = description
        self.product_type = product_type
        self.business_id = business_id
        self.metadata = metadata or {}

    @property
    def amount_cents(self) -> int:
        """Get amount in cents for Stripe"""
        return format_amount_for_stripe(self.amount_usd)

    @property
    def total_amount_usd(self) -> Decimal:
        """Get total amount for this item"""
        return self.amount_usd * self.quantity

    def to_stripe_line_item(self) -> Dict[str, Any]:
        """Convert to Stripe line item"""
        return create_one_time_line_item(
            product_name=self.product_name,
            amount_cents=self.amount_cents,
            quantity=self.quantity,
        )


class CheckoutSession:
    """
    Main checkout session manager

    Acceptance Criteria:
    - Checkout session creation ✓
    - Test mode works ✓
    - Metadata included ✓
    - Success/cancel URLs ✓
    """

    def __init__(
        self,
        customer_email: str,
        items: List[CheckoutItem],
        purchase_id: Optional[str] = None,
        config: Optional[CheckoutConfig] = None,
        stripe_client: Optional[StripeClient] = None,
    ):
        self.customer_email = customer_email
        self.items = items
        self.purchase_id = purchase_id or str(uuid.uuid4())
        self.config = config or CheckoutConfig()
        self.stripe_client = stripe_client or StripeClient(
            StripeConfig(test_mode=self.config.test_mode)
        )

        # Validation
        if not items:
            raise CheckoutError("At least one item is required for checkout")
        if not customer_email:
            raise CheckoutError("Customer email is required")

    @property
    def total_amount_usd(self) -> Decimal:
        """Get total amount for all items"""
        return sum(item.total_amount_usd for item in self.items)

    @property
    def total_amount_cents(self) -> int:
        """Get total amount in cents"""
        return format_amount_for_stripe(self.total_amount_usd)

    def build_success_url(self) -> str:
        """Build success URL with purchase ID"""
        return f"{self.config.base_success_url}?purchase_id={self.purchase_id}&session_id={{CHECKOUT_SESSION_ID}}"

    def build_cancel_url(self) -> str:
        """Build cancel URL with purchase ID"""
        return f"{self.config.base_cancel_url}?purchase_id={self.purchase_id}&session_id={{CHECKOUT_SESSION_ID}}"

    def build_metadata(
        self, additional_metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Build metadata for Stripe session - Acceptance Criteria
        """
        metadata = {
            "purchase_id": self.purchase_id,
            "customer_email": self.customer_email,
            "item_count": str(len(self.items)),
            "total_amount_usd": str(self.total_amount_usd),
            "created_at": datetime.utcnow().isoformat(),
            "source": "leadfactory_checkout",
        }

        # Add item details
        for i, item in enumerate(self.items):
            metadata[f"item_{i}_name"] = item.product_name
            metadata[f"item_{i}_type"] = item.product_type.value
            metadata[f"item_{i}_amount"] = str(item.amount_usd)
            if item.business_id:
                metadata[f"item_{i}_business_id"] = item.business_id

        # Add any additional metadata
        if additional_metadata:
            metadata.update(additional_metadata)

        return metadata

    def create_stripe_session(
        self, additional_metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create Stripe checkout session - Acceptance Criteria
        """
        try:
            # Build line items
            line_items = [item.to_stripe_line_item() for item in self.items]

            # Build metadata
            metadata = self.build_metadata(additional_metadata)

            # Create session configuration
            session_config = StripeCheckoutSession(
                line_items=line_items,
                success_url=self.build_success_url(),
                cancel_url=self.build_cancel_url(),
                customer_email=self.customer_email,
                metadata=metadata,
                mode=SESSION_MODES["PAYMENT"],
                payment_method_types=PAYMENT_METHOD_TYPES["CARD_ONLY"],
            )

            logger.info(f"Creating checkout session for purchase {self.purchase_id}")

            # Create session via Stripe
            result = self.stripe_client.create_checkout_session(session_config)

            logger.info(
                f"Created Stripe session {result['session_id']} for purchase {self.purchase_id}"
            )

            return result

        except StripeError as e:
            logger.error(
                f"Stripe error creating session for purchase {self.purchase_id}: {e}"
            )
            raise CheckoutError(f"Failed to create checkout session: {str(e)}")
        except Exception as e:
            logger.error(
                f"Unexpected error creating session for purchase {self.purchase_id}: {e}"
            )
            raise CheckoutError(f"Unexpected checkout error: {str(e)}")


class CheckoutManager:
    """
    High-level checkout flow manager that coordinates database operations with Stripe
    """

    def __init__(
        self,
        config: Optional[CheckoutConfig] = None,
        stripe_client: Optional[StripeClient] = None,
    ):
        self.config = config or CheckoutConfig()
        self.stripe_client = stripe_client or StripeClient(
            StripeConfig(test_mode=self.config.test_mode)
        )

    def initiate_checkout(
        self,
        customer_email: str,
        items: List[CheckoutItem],
        attribution_data: Optional[Dict[str, Any]] = None,
        additional_metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Initiate complete checkout flow

        Returns checkout URL and session information
        """
        try:
            # Create checkout session
            checkout = CheckoutSession(
                customer_email=customer_email,
                items=items,
                config=self.config,
                stripe_client=self.stripe_client,
            )

            # Create Stripe session
            stripe_result = checkout.create_stripe_session(additional_metadata)

            # Prepare response
            response = {
                "success": True,
                "purchase_id": checkout.purchase_id,
                "checkout_url": stripe_result["session_url"],
                "session_id": stripe_result["session_id"],
                "amount_total_usd": float(checkout.total_amount_usd),
                "amount_total_cents": checkout.total_amount_cents,
                "currency": stripe_result["currency"],
                "expires_at": stripe_result["expires_at"],
                "test_mode": self.config.test_mode,
                "items": [
                    {
                        "name": item.product_name,
                        "amount_usd": float(item.amount_usd),
                        "quantity": item.quantity,
                        "type": item.product_type.value,
                    }
                    for item in items
                ],
            }

            logger.info(
                f"Successfully initiated checkout for {customer_email}, purchase {checkout.purchase_id}"
            )

            return response

        except (CheckoutError, StripeError) as e:
            logger.error(f"Error initiating checkout for {customer_email}: {e}")
            return {"success": False, "error": str(e), "error_type": type(e).__name__}
        except Exception as e:
            logger.error(
                f"Unexpected error initiating checkout for {customer_email}: {e}"
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_type": "UnexpectedError",
            }

    def retrieve_session_status(self, session_id: str) -> Dict[str, Any]:
        """Retrieve the status of a checkout session"""
        try:
            result = self.stripe_client.retrieve_checkout_session(session_id)

            return {
                "success": True,
                "session_id": session_id,
                "payment_status": result["payment_status"],
                "status": result["status"],
                "amount_total": result.get("amount_total"),
                "currency": result.get("currency"),
                "customer": result.get("customer"),
                "payment_intent": result.get("payment_intent"),
                "metadata": result.get("metadata", {}),
            }

        except StripeError as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            return {"success": False, "error": str(e), "error_type": "StripeError"}

    def create_audit_report_checkout(
        self,
        customer_email: str,
        business_url: str,
        business_name: Optional[str] = None,
        amount_usd: Decimal = Decimal("29.99"),
        attribution_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Convenience method for creating audit report checkout
        """
        # Create checkout item
        item = CheckoutItem(
            product_name=f"Website Audit Report{f' for {business_name}' if business_name else ''}",
            amount_usd=amount_usd,
            description=f"Comprehensive website audit for {business_url}",
            product_type=ProductType.AUDIT_REPORT,
            metadata={
                "business_url": business_url,
                "business_name": business_name or "",
                "product_sku": "WA-BASIC-001",
            },
        )

        # Add attribution to metadata
        additional_metadata = {}
        if attribution_data:
            for key, value in attribution_data.items():
                if isinstance(value, str):
                    additional_metadata[f"attr_{key}"] = value

        return self.initiate_checkout(
            customer_email=customer_email,
            items=[item],
            attribution_data=attribution_data,
            additional_metadata=additional_metadata,
        )

    def create_bulk_reports_checkout(
        self,
        customer_email: str,
        business_urls: List[str],
        amount_per_report_usd: Decimal = Decimal("24.99"),
        attribution_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Convenience method for creating bulk reports checkout
        """
        if not business_urls:
            raise CheckoutError(
                "At least one business URL is required for bulk reports"
            )

        quantity = len(business_urls)

        # Create checkout item
        item = CheckoutItem(
            product_name=f"Website Audit Reports (Bulk - {quantity} reports)",
            amount_usd=amount_per_report_usd,
            quantity=quantity,
            description=f"Comprehensive website audits for {quantity} businesses",
            product_type=ProductType.BULK_REPORTS,
            metadata={
                "business_urls": ",".join(business_urls),
                "report_count": str(quantity),
                "product_sku": "WA-BULK-001",
            },
        )

        return self.initiate_checkout(
            customer_email=customer_email,
            items=[item],
            attribution_data=attribution_data,
        )

    def get_status(self) -> Dict[str, Any]:
        """Get checkout manager status"""
        return {
            "test_mode": self.config.test_mode,
            "success_url": self.config.base_success_url,
            "cancel_url": self.config.base_cancel_url,
            "webhook_url": self.config.webhook_url,
            "currency": self.config.default_currency,
            "session_expires_minutes": self.config.session_expires_minutes,
            "stripe_status": self.stripe_client.get_status(),
        }


# Utility functions for testing and development
def create_test_checkout_items() -> List[CheckoutItem]:
    """Create test checkout items for development"""
    return [
        CheckoutItem(
            product_name="Website Audit Report - Basic",
            amount_usd=Decimal("29.99"),
            description="Comprehensive website performance and SEO audit",
            product_type=ProductType.AUDIT_REPORT,
        ),
        CheckoutItem(
            product_name="Website Audit Report - Premium",
            amount_usd=Decimal("99.99"),
            description="Advanced audit with conversion optimization",
            product_type=ProductType.PREMIUM_REPORT,
        ),
    ]


def format_checkout_response_for_api(response: Dict[str, Any]) -> Dict[str, Any]:
    """Format checkout response for API consumption"""
    if response["success"]:
        return {
            "status": "success",
            "data": {
                "checkout_url": response["checkout_url"],
                "purchase_id": response["purchase_id"],
                "session_id": response["session_id"],
                "total_amount": response["amount_total_usd"],
                "currency": response.get("currency", "usd"),
                "expires_at": response["expires_at"],
                "test_mode": response["test_mode"],
            },
        }
    else:
        return {
            "status": "error",
            "error": {"message": response["error"], "type": response["error_type"]},
        }


# Constants for checkout configuration
DEFAULT_PRICING = {
    "BASIC_AUDIT": Decimal("29.99"),
    "PREMIUM_AUDIT": Decimal("99.99"),
    "BULK_DISCOUNT_THRESHOLD": 5,  # 5+ reports
    "BULK_DISCOUNT_RATE": Decimal("0.15"),  # 15% discount
}

CHECKOUT_URLS = {
    "PRODUCTION": {
        "SUCCESS": "https://leadfactory.com/checkout/success",
        "CANCEL": "https://leadfactory.com/checkout/cancel",
        "WEBHOOK": "https://leadfactory.com/api/webhooks/stripe",
    },
    "STAGING": {
        "SUCCESS": "https://staging.leadfactory.com/checkout/success",
        "CANCEL": "https://staging.leadfactory.com/checkout/cancel",
        "WEBHOOK": "https://staging.leadfactory.com/api/webhooks/stripe",
    },
    "DEVELOPMENT": {
        "SUCCESS": "http://localhost:3000/checkout/success",
        "CANCEL": "http://localhost:3000/checkout/cancel",
        "WEBHOOK": "http://localhost:3000/api/webhooks/stripe",
    },
}
