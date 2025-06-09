"""
D7 Storefront & Purchase Flow

This module handles Stripe payments and report delivery for the LeadFactory MVP.
Contains models and functionality for managing purchases, checkout sessions, and payment tracking.
"""

from .models import Purchase, PurchaseItem, Customer, PaymentSession
from .stripe_client import StripeClient, StripeConfig, StripeCheckoutSession, StripeError
from .checkout import CheckoutManager, CheckoutSession, CheckoutItem, CheckoutConfig, CheckoutError
from .webhooks import WebhookProcessor, WebhookEventType, WebhookStatus, WebhookError
from .webhook_handlers import (
    CheckoutSessionHandler, PaymentIntentHandler, CustomerHandler, InvoiceHandler,
    ReportGenerationStatus
)
from . import api
from . import schemas

__all__ = [
    # Models
    "Purchase",
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
    "schemas"
]