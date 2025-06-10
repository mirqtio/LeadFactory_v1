"""
Stripe API client implementation for payment processing
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..base import BaseAPIClient


class StripeClient(BaseAPIClient):
    """Stripe API client for payment processing"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(provider="stripe", api_key=api_key)

    def _get_base_url(self) -> str:
        """Get Stripe API base URL"""
        return "https://api.stripe.com"

    def _get_headers(self) -> Dict[str, str]:
        """Get Stripe API headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def get_rate_limit(self) -> Dict[str, int]:
        """Get Stripe rate limit configuration"""
        return {
            "daily_limit": 50000,  # Very high for payment processing
            "daily_used": 0,
            "burst_limit": 25,
            "window_seconds": 1,
        }

    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        """
        Calculate cost for Stripe operations

        Stripe fees:
        - 2.9% + 30¢ per successful charge
        - API calls are free
        """
        if operation.startswith("POST:/v1/charges"):
            # Payment processing fee would be calculated on the charge amount
            # For API cost tracking, we consider the API call free
            return Decimal("0.000")
        else:
            # All other API operations are free
            return Decimal("0.000")

    async def create_checkout_session(
        self,
        price_id: str,
        success_url: str,
        cancel_url: str,
        quantity: int = 1,
        customer_email: Optional[str] = None,
        client_reference_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        mode: str = "payment",
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout session with a single price ID

        Args:
            price_id: Stripe price ID
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect after cancelled payment
            quantity: Quantity of items
            customer_email: Pre-fill customer email
            client_reference_id: Reference ID for tracking
            metadata: Additional metadata
            mode: Payment mode (payment, subscription, setup)

        Returns:
            Dict containing checkout session data
        """
        # Stripe expects form-encoded data
        payload = {
            "payment_method_types[]": "card",
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": str(quantity),
            "mode": mode,
            "success_url": success_url,
            "cancel_url": cancel_url,
        }

        if customer_email:
            payload["customer_email"] = customer_email

        if client_reference_id:
            payload["client_reference_id"] = client_reference_id

        if metadata:
            for key, value in metadata.items():
                payload[f"metadata[{key}]"] = value

        return await self.make_request("POST", "/v1/checkout/sessions", data=payload)

    async def create_checkout_session_with_line_items(
        self,
        line_items: List[Dict[str, Any]],
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str] = None,
        client_reference_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        mode: str = "payment",
        expires_at: Optional[int] = None,
        payment_method_types: Optional[List[str]] = None,
        billing_address_collection: Optional[str] = None,
        allow_promotion_codes: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout session with line items (supports dynamic pricing)

        Args:
            line_items: List of line items with price_data or price
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect after cancelled payment
            customer_email: Pre-fill customer email
            client_reference_id: Reference ID for tracking
            metadata: Additional metadata
            mode: Payment mode (payment, subscription, setup)
            expires_at: Unix timestamp when session expires
            payment_method_types: List of payment methods to accept
            billing_address_collection: How to collect billing address
            allow_promotion_codes: Whether to allow promo codes

        Returns:
            Dict containing checkout session data
        """
        # Stripe expects form-encoded data
        payload = {"mode": mode, "success_url": success_url, "cancel_url": cancel_url}

        # Add payment method types
        if payment_method_types:
            for i, method in enumerate(payment_method_types):
                payload[f"payment_method_types[{i}]"] = method
        else:
            payload["payment_method_types[]"] = "card"

        # Add line items
        for i, item in enumerate(line_items):
            if "price" in item:
                # Using existing price ID
                payload[f"line_items[{i}][price]"] = item["price"]
                payload[f"line_items[{i}][quantity]"] = str(item.get("quantity", 1))
            elif "price_data" in item:
                # Using inline pricing
                price_data = item["price_data"]
                payload[f"line_items[{i}][price_data][currency]"] = price_data.get(
                    "currency", "usd"
                )
                payload[f"line_items[{i}][price_data][unit_amount]"] = str(
                    price_data["unit_amount"]
                )

                if "product_data" in price_data:
                    product_data = price_data["product_data"]
                    payload[
                        f"line_items[{i}][price_data][product_data][name]"
                    ] = product_data["name"]
                    if "description" in product_data:
                        payload[
                            f"line_items[{i}][price_data][product_data][description]"
                        ] = product_data["description"]
                    if "metadata" in product_data:
                        for key, value in product_data["metadata"].items():
                            payload[
                                f"line_items[{i}][price_data][product_data][metadata][{key}]"
                            ] = value

                payload[f"line_items[{i}][quantity]"] = str(item.get("quantity", 1))

        if customer_email:
            payload["customer_email"] = customer_email

        if client_reference_id:
            payload["client_reference_id"] = client_reference_id

        if metadata:
            for key, value in metadata.items():
                payload[f"metadata[{key}]"] = value

        if expires_at:
            payload["expires_at"] = str(expires_at)

        if billing_address_collection:
            payload["billing_address_collection"] = billing_address_collection

        if allow_promotion_codes is not None:
            payload["allow_promotion_codes"] = (
                "true" if allow_promotion_codes else "false"
            )

        return await self.make_request("POST", "/v1/checkout/sessions", data=payload)

    async def create_payment_intent(
        self,
        amount: int,
        currency: str = "usd",
        customer_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        receipt_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a payment intent

        Args:
            amount: Amount in cents
            currency: Currency code
            customer_id: Stripe customer ID
            description: Payment description
            metadata: Additional metadata
            receipt_email: Email for receipt

        Returns:
            Dict containing payment intent data
        """
        payload = {
            "amount": str(amount),
            "currency": currency,
            "automatic_payment_methods[enabled]": "true",
        }

        if customer_id:
            payload["customer"] = customer_id
        if description:
            payload["description"] = description
        if receipt_email:
            payload["receipt_email"] = receipt_email
        if metadata:
            for key, value in metadata.items():
                payload[f"metadata[{key}]"] = value

        return await self.make_request("POST", "/v1/payment_intents", data=payload)

    async def get_checkout_session(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieve a checkout session

        Args:
            session_id: Checkout session ID

        Returns:
            Dict containing session data
        """
        return await self.make_request("GET", f"/v1/checkout/sessions/{session_id}")

    async def get_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        """
        Retrieve a payment intent

        Args:
            payment_intent_id: Payment intent ID

        Returns:
            Dict containing payment intent data
        """
        return await self.make_request(
            "GET", f"/v1/payment_intents/{payment_intent_id}"
        )

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a customer

        Args:
            email: Customer email
            name: Customer name
            description: Customer description
            metadata: Additional metadata

        Returns:
            Dict containing customer data
        """
        payload = {"email": email}

        if name:
            payload["name"] = name
        if description:
            payload["description"] = description
        if metadata:
            for key, value in metadata.items():
                payload[f"metadata[{key}]"] = value

        return await self.make_request("POST", "/v1/customers", data=payload)

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Retrieve a customer

        Args:
            customer_id: Stripe customer ID

        Returns:
            Dict containing customer data
        """
        return await self.make_request("GET", f"/v1/customers/{customer_id}")

    async def create_product(
        self,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        active: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a product

        Args:
            name: Product name
            description: Product description
            metadata: Additional metadata
            active: Whether product is active

        Returns:
            Dict containing product data
        """
        payload = {"name": name, "active": "true" if active else "false"}

        if description:
            payload["description"] = description
        if metadata:
            for key, value in metadata.items():
                payload[f"metadata[{key}]"] = value

        return await self.make_request("POST", "/v1/products", data=payload)

    async def list_charges(
        self,
        customer_id: Optional[str] = None,
        limit: int = 10,
        starting_after: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List charges

        Args:
            customer_id: Filter by customer ID
            limit: Number of charges to return
            starting_after: Pagination cursor

        Returns:
            Dict containing list of charges
        """
        params = {"limit": str(limit)}

        if customer_id:
            params["customer"] = customer_id
        if starting_after:
            params["starting_after"] = starting_after

        return await self.make_request("GET", "/v1/charges", params=params)

    async def create_price(
        self,
        amount: int,
        currency: str = "usd",
        product_id: Optional[str] = None,
        product_data: Optional[Dict[str, str]] = None,
        recurring: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a price

        Args:
            amount: Price amount in cents
            currency: Currency code
            product_id: Existing product ID
            product_data: New product data
            recurring: Recurring billing configuration

        Returns:
            Dict containing price data
        """
        payload = {"unit_amount": str(amount), "currency": currency}

        if product_id:
            payload["product"] = product_id
        elif product_data:
            for key, value in product_data.items():
                payload[f"product_data[{key}]"] = value

        if recurring:
            for key, value in recurring.items():
                payload[f"recurring[{key}]"] = str(value)

        return await self.make_request("POST", "/v1/prices", data=payload)

    async def create_webhook_endpoint(
        self, url: str, enabled_events: List[str], description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a webhook endpoint

        Args:
            url: Webhook URL
            enabled_events: List of events to listen for
            description: Webhook description

        Returns:
            Dict containing webhook endpoint data
        """
        payload = {"url": url}

        for i, event in enumerate(enabled_events):
            payload[f"enabled_events[{i}]"] = event

        if description:
            payload["description"] = description

        return await self.make_request("POST", "/v1/webhook_endpoints", data=payload)

    async def construct_webhook_event(
        self, payload: str, signature: str, endpoint_secret: str
    ) -> Dict[str, Any]:
        """
        Verify and construct webhook event (simplified version)

        In production, this would use Stripe's webhook verification
        For now, we'll parse the payload directly

        Args:
            payload: Raw webhook payload
            signature: Webhook signature
            endpoint_secret: Webhook endpoint secret

        Returns:
            Dict containing webhook event data
        """
        # In production, use stripe.Webhook.construct_event()
        # For now, return a basic structure
        import json

        try:
            event_data = json.loads(payload)
            return event_data
        except json.JSONDecodeError:
            raise ValueError("Invalid webhook payload")

    def format_checkout_session_for_report(
        self, business_name: str, business_id: str, customer_email: str, report_url: str
    ) -> Dict[str, Any]:
        """
        Format checkout session data for website report purchase

        Args:
            business_name: Business name for the report
            business_id: Internal business ID
            customer_email: Customer email address
            report_url: URL to the report

        Returns:
            Formatted checkout session data
        """
        success_url = f"{report_url}?session_id={{CHECKOUT_SESSION_ID}}&success=true"
        cancel_url = f"{report_url}?cancelled=true"

        return {
            "price_id": "price_website_report",  # Would be configured in Stripe
            "success_url": success_url,
            "cancel_url": cancel_url,
            "customer_email": customer_email,
            "client_reference_id": business_id,
            "metadata": {
                "business_name": business_name,
                "business_id": business_id,
                "product_type": "website_report",
                "source": "leadfactory",
            },
        }
