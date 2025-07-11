"""
D7 Storefront Schemas - Task 058

Pydantic schemas for checkout API endpoints with validation,
serialization, and API documentation support.

Acceptance Criteria:
- Checkout initiation API ✓
- Webhook endpoint secure ✓
- Success page works ✓
- Error handling proper ✓
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, validator

from .models import ProductType


class CheckoutItemRequest(BaseModel):
    """Schema for checkout item in API request"""

    product_name: str = Field(
        ..., min_length=1, max_length=200, description="Name of the product"
    )
    amount_usd: Decimal = Field(..., gt=0, le=10000, description="Price in USD")
    quantity: int = Field(default=1, ge=1, le=100, description="Quantity of items")
    description: Optional[str] = Field(
        None, max_length=500, description="Product description"
    )
    product_type: ProductType = Field(
        default=ProductType.AUDIT_REPORT, description="Type of product"
    )
    business_id: Optional[str] = Field(
        None, max_length=100, description="Associated business ID"
    )
    metadata: Optional[Dict[str, str]] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @validator("amount_usd")
    def validate_amount(cls, v):
        """Validate amount has maximum 2 decimal places"""
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount cannot have more than 2 decimal places")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "product_name": "Website Audit Report",
                "amount_usd": 29.99,
                "quantity": 1,
                "description": "Comprehensive website audit",
                "product_type": "audit_report",
                "business_id": "biz_123",
                "metadata": {"business_url": "https://example.com"},
            }
        }


class CheckoutInitiationRequest(BaseModel):
    """Schema for checkout initiation API request - Acceptance Criteria"""

    customer_email: EmailStr = Field(..., description="Customer email address")
    items: List[CheckoutItemRequest] = Field(
        ..., min_items=1, max_items=50, description="Items to purchase"
    )
    attribution_data: Optional[Dict[str, str]] = Field(
        default_factory=dict, description="Marketing attribution data"
    )
    additional_metadata: Optional[Dict[str, str]] = Field(
        default_factory=dict, description="Additional metadata"
    )
    success_url: Optional[str] = Field(None, description="Custom success URL")
    cancel_url: Optional[str] = Field(None, description="Custom cancel URL")

    @validator("items")
    def validate_items_not_empty(cls, v):
        """Ensure at least one item is provided"""
        if not v:
            raise ValueError("At least one item is required")
        return v

    @validator("attribution_data", "additional_metadata")
    def validate_metadata_keys(cls, v):
        """Validate metadata keys and values"""
        if v:
            for key, value in v.items():
                if len(key) > 100:
                    raise ValueError(f'Metadata key "{key}" too long (max 100 chars)')
                if len(str(value)) > 500:
                    raise ValueError(
                        f'Metadata value for "{key}" too long (max 500 chars)'
                    )
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "customer_email": "customer@example.com",
                "items": [
                    {
                        "product_name": "Website Audit Report",
                        "amount_usd": 29.99,
                        "quantity": 1,
                        "description": "Comprehensive website audit",
                        "product_type": "audit_report",
                        "metadata": {"business_url": "https://example.com"},
                    }
                ],
                "attribution_data": {
                    "utm_source": "google",
                    "utm_medium": "cpc",
                    "utm_campaign": "website_audit",
                },
            }
        }


class CheckoutInitiationResponse(BaseModel):
    """Schema for checkout initiation API response"""

    success: bool = Field(..., description="Whether the operation was successful")
    purchase_id: Optional[str] = Field(None, description="Generated purchase ID")
    checkout_url: Optional[str] = Field(None, description="Stripe checkout URL")
    session_id: Optional[str] = Field(None, description="Stripe session ID")
    amount_total_usd: Optional[float] = Field(None, description="Total amount in USD")
    amount_total_cents: Optional[int] = Field(None, description="Total amount in cents")
    currency: Optional[str] = Field(None, description="Currency code")
    expires_at: Optional[int] = Field(None, description="Session expiration timestamp")
    test_mode: Optional[bool] = Field(None, description="Whether in test mode")
    items: Optional[List[Dict[str, Any]]] = Field(None, description="Item summary")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_type: Optional[str] = Field(None, description="Error type if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "purchase_id": "purchase_123456",
                "checkout_url": "https://checkout.stripe.com/pay/cs_test_123",
                "session_id": "cs_test_123456",
                "amount_total_usd": 29.99,
                "amount_total_cents": 2999,
                "currency": "usd",
                "expires_at": 1640995200,
                "test_mode": True,
                "items": [
                    {
                        "name": "Website Audit Report",
                        "amount_usd": 29.99,
                        "quantity": 1,
                        "type": "audit_report",
                    }
                ],
            }
        }


class WebhookEventRequest(BaseModel):
    """Schema for webhook event processing - Acceptance Criteria"""

    event_type: str = Field(..., description="Stripe webhook event type")
    event_id: str = Field(..., description="Stripe event ID")
    data: Dict[str, Any] = Field(..., description="Event data payload")
    created: int = Field(..., description="Event creation timestamp")
    livemode: bool = Field(..., description="Whether event is from live mode")

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "checkout.session.completed",
                "event_id": "evt_1234567890",
                "data": {
                    "object": {
                        "id": "cs_test_123",
                        "payment_status": "paid",
                        "customer_email": "customer@example.com",
                    }
                },
                "created": 1640995200,
                "livemode": False,
            }
        }


class WebhookEventResponse(BaseModel):
    """Schema for webhook event processing response"""

    success: bool = Field(..., description="Whether webhook processing was successful")
    event_id: Optional[str] = Field(None, description="Processed event ID")
    event_type: Optional[str] = Field(None, description="Event type that was processed")
    processing_status: Optional[str] = Field(None, description="Processing status")
    data: Optional[Dict[str, Any]] = Field(None, description="Processing result data")
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "event_id": "evt_1234567890",
                "event_type": "checkout.session.completed",
                "processing_status": "completed",
                "data": {
                    "purchase_id": "purchase_123456",
                    "session_id": "cs_test_123",
                    "report_generation": {
                        "status": "triggered",
                        "job_id": "report_job_123",
                    },
                },
            }
        }


class CheckoutSessionStatusRequest(BaseModel):
    """Schema for checkout session status request"""

    session_id: str = Field(..., min_length=1, description="Stripe checkout session ID")

    class Config:
        json_schema_extra = {"example": {"session_id": "cs_test_1234567890"}}


class CheckoutSessionStatusResponse(BaseModel):
    """Schema for checkout session status response"""

    success: bool = Field(..., description="Whether the operation was successful")
    session_id: Optional[str] = Field(None, description="Checkout session ID")
    payment_status: Optional[str] = Field(None, description="Payment status")
    status: Optional[str] = Field(None, description="Session status")
    amount_total: Optional[int] = Field(None, description="Total amount in cents")
    currency: Optional[str] = Field(None, description="Currency code")
    customer: Optional[str] = Field(None, description="Stripe customer ID")
    payment_intent: Optional[str] = Field(None, description="Payment intent ID")
    metadata: Optional[Dict[str, str]] = Field(None, description="Session metadata")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_type: Optional[str] = Field(None, description="Error type if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_id": "cs_test_123",
                "payment_status": "paid",
                "status": "complete",
                "amount_total": 2999,
                "currency": "usd",
                "customer": "cus_test_123",
                "payment_intent": "pi_test_123",
                "metadata": {"purchase_id": "purchase_123456"},
            }
        }


class SuccessPageRequest(BaseModel):
    """Schema for success page request - Acceptance Criteria"""

    session_id: str = Field(..., description="Stripe checkout session ID")
    purchase_id: Optional[str] = Field(None, description="Purchase ID from metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "cs_test_1234567890",
                "purchase_id": "purchase_123456",
            }
        }


class SuccessPageResponse(BaseModel):
    """Schema for success page response"""

    success: bool = Field(..., description="Whether payment was successful")
    purchase_id: Optional[str] = Field(None, description="Purchase ID")
    session_id: Optional[str] = Field(None, description="Session ID")
    customer_email: Optional[str] = Field(None, description="Customer email")
    amount_total_usd: Optional[float] = Field(None, description="Total amount paid")
    payment_status: Optional[str] = Field(None, description="Payment status")
    items: Optional[List[Dict[str, Any]]] = Field(None, description="Purchased items")
    report_status: Optional[str] = Field(None, description="Report generation status")
    estimated_delivery: Optional[str] = Field(
        None, description="Estimated delivery time"
    )
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "purchase_id": "purchase_123456",
                "session_id": "cs_test_123",
                "customer_email": "customer@example.com",
                "amount_total_usd": 29.99,
                "payment_status": "paid",
                "items": [
                    {
                        "name": "Website Audit Report",
                        "type": "audit_report",
                        "business_url": "https://example.com",
                    }
                ],
                "report_status": "generating",
                "estimated_delivery": "within 24 hours",
            }
        }


class ErrorResponse(BaseModel):
    """Schema for API error responses - Acceptance Criteria"""

    success: bool = Field(default=False, description="Always false for error responses")
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Error type/category")
    error_code: Optional[str] = Field(None, description="Specific error code")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "Invalid email address format",
                "error_type": "ValidationError",
                "error_code": "INVALID_EMAIL",
                "details": {
                    "field": "customer_email",
                    "provided_value": "invalid-email",
                },
                "timestamp": "2023-12-01T12:00:00Z",
            }
        }


class AuditReportCheckoutRequest(BaseModel):
    """Schema for audit report checkout convenience endpoint"""

    customer_email: EmailStr = Field(..., description="Customer email address")
    business_url: str = Field(..., description="Business website URL to audit")
    business_name: Optional[str] = Field(
        None, max_length=200, description="Business name"
    )
    amount_usd: Optional[Decimal] = Field(
        default=Decimal("29.99"), description="Custom amount"
    )
    attribution_data: Optional[Dict[str, str]] = Field(
        default_factory=dict, description="Attribution data"
    )

    @validator("business_url")
    def validate_business_url(cls, v):
        """Validate business URL format"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Business URL must start with http:// or https://")
        if len(v) > 500:
            raise ValueError("Business URL too long (max 500 chars)")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "customer_email": "customer@example.com",
                "business_url": "https://example.com",
                "business_name": "Example Business",
                "amount_usd": 29.99,
                "attribution_data": {
                    "utm_source": "google",
                    "utm_campaign": "audit_reports",
                },
            }
        }


class BulkReportsCheckoutRequest(BaseModel):
    """Schema for bulk reports checkout convenience endpoint"""

    customer_email: EmailStr = Field(..., description="Customer email address")
    business_urls: List[str] = Field(
        ..., min_items=2, max_items=50, description="List of business URLs"
    )
    amount_per_report_usd: Optional[Decimal] = Field(
        default=Decimal("24.99"), description="Price per report"
    )
    attribution_data: Optional[Dict[str, str]] = Field(
        default_factory=dict, description="Attribution data"
    )

    @validator("business_urls")
    def validate_business_urls(cls, v):
        """Validate business URLs"""
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f'URL "{url}" must start with http:// or https://')
            if len(url) > 500:
                raise ValueError(f'URL "{url}" too long (max 500 chars)')

        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Duplicate URLs are not allowed")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "customer_email": "customer@example.com",
                "business_urls": [
                    "https://example1.com",
                    "https://example2.com",
                    "https://example3.com",
                ],
                "amount_per_report_usd": 24.99,
                "attribution_data": {
                    "utm_source": "google",
                    "utm_campaign": "bulk_audits",
                },
            }
        }


# Utility schemas for common patterns
class APIStatusResponse(BaseModel):
    """Schema for API status/health check response"""

    status: str = Field(..., description="API status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Current timestamp"
    )
    services: Dict[str, str] = Field(..., description="Service status")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2023-12-01T12:00:00Z",
                "services": {
                    "stripe": "connected",
                    "database": "connected",
                    "webhook_processor": "active",
                },
            }
        }


# Schema validation helpers
def validate_stripe_session_id(session_id: str) -> bool:
    """Validate Stripe session ID format"""
    return session_id.startswith(("cs_test_", "cs_live_")) and len(session_id) > 10


def validate_purchase_id_format(purchase_id: str) -> bool:
    """Validate purchase ID format"""
    return len(purchase_id) >= 10 and purchase_id.isalnum()


# Constants for schema validation
MAX_ITEMS_PER_CHECKOUT = 50
MAX_METADATA_KEY_LENGTH = 100
MAX_METADATA_VALUE_LENGTH = 500
MAX_BUSINESS_URL_LENGTH = 500
MIN_AMOUNT_USD = Decimal("0.50")  # Stripe minimum
MAX_AMOUNT_USD = Decimal("10000.00")  # Reasonable maximum

SUPPORTED_CURRENCIES = ["usd", "eur", "gbp", "cad", "aud"]
SUPPORTED_PRODUCT_TYPES = [ptype.value for ptype in ProductType]
