"""
D7 Storefront & Purchase Flow

This module handles Stripe payments and report delivery for the LeadFactory MVP.
Contains models and functionality for managing purchases, checkout sessions, and payment tracking.
"""

from . import api, schemas
from .checkout import CheckoutConfig, CheckoutError, CheckoutItem, CheckoutManager, CheckoutSession
from .models import Customer, D7Purchase, PaymentSession, PurchaseItem
from .stripe_client import StripeCheckoutSession, StripeClient, StripeConfig, StripeError
from .webhook_handlers import (
    CheckoutSessionHandler,
    CustomerHandler,
    InvoiceHandler,
    PaymentIntentHandler,
    ReportGenerationStatus,
)
from .webhooks import WebhookError, WebhookEventType, WebhookProcessor, WebhookStatus

__all__ = [
    # Models
    "D7Purchase",
    "PurchaseItem",
    "Customer",
    "PaymentSession",
    # Stripe Integration
    "StripeClient",
    "StripeConfig",
    "StripeCheckoutSession",
    "StripeError",
    # Checkout Flow
    "CheckoutManager",
    "CheckoutSession",
    "CheckoutItem",
    "CheckoutConfig",
    "CheckoutError",
    # Webhook Processing
    "WebhookProcessor",
    "WebhookEventType",
    "WebhookStatus",
    "WebhookError",
    "CheckoutSessionHandler",
    "PaymentIntentHandler",
    "CustomerHandler",
    "InvoiceHandler",
    "ReportGenerationStatus",
    # API & Schemas
    "api",
    "schemas",
]
