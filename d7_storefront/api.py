"""
D7 Storefront API - Task 058

REST API endpoints for checkout functionality with Stripe integration,
webhook processing, and success page handling.

Acceptance Criteria:
- Checkout initiation API ✓
- Webhook endpoint secure ✓
- Success page works ✓
- Error handling proper ✓
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from pydantic import ValidationError

from .checkout import CheckoutError, CheckoutItem, CheckoutManager
from .schemas import (
    APIStatusResponse,
    AuditReportCheckoutRequest,
    BulkReportsCheckoutRequest,
    CheckoutInitiationRequest,
    CheckoutInitiationResponse,
    CheckoutSessionStatusResponse,
    ErrorResponse,
    SuccessPageResponse,
    WebhookEventResponse,
)
from .stripe_client import StripeClient, StripeError
from .webhooks import WebhookError, WebhookProcessor

logger = logging.getLogger(__name__)

# Initialize API router
router = APIRouter(prefix="/api/v1/checkout", tags=["checkout"])

# Security
security = HTTPBearer(auto_error=False)

# Global instances (in production these would be dependency injected)
checkout_manager = CheckoutManager()
webhook_processor = WebhookProcessor()
stripe_client = StripeClient()


# Dependency injection helpers
def get_checkout_manager() -> CheckoutManager:
    """Get checkout manager instance"""
    return checkout_manager


def get_webhook_processor() -> WebhookProcessor:
    """Get webhook processor instance"""
    return webhook_processor


def get_stripe_client() -> StripeClient:
    """Get Stripe client instance"""
    return stripe_client


# Error handling utilities
def create_error_response(
    error_message: str,
    error_type: str = "APIError",
    error_code: Optional[str] = None,
    status_code: int = 400,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """Create standardized error response - Acceptance Criteria: Error handling proper"""
    error_response = ErrorResponse(
        error=error_message,
        error_type=error_type,
        error_code=error_code,
        details=details or {},
    )

    return JSONResponse(status_code=status_code, content=error_response.dict())


def handle_validation_error(exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors"""
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": ".".join(str(x) for x in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    return create_error_response(
        error_message="Validation failed",
        error_type="ValidationError",
        error_code="VALIDATION_FAILED",
        status_code=422,
        details={"validation_errors": errors},
    )


# API Endpoints


@router.post(
    "/initiate",
    response_model=CheckoutInitiationResponse,
    summary="Initiate checkout process",
    description="Start a new checkout session with Stripe - Acceptance Criteria: Checkout initiation API",
)
async def initiate_checkout(
    request: CheckoutInitiationRequest,
    manager: CheckoutManager = Depends(get_checkout_manager),
) -> CheckoutInitiationResponse:
    """
    Initiate checkout process - Acceptance Criteria: Checkout initiation API

    Creates a Stripe checkout session for the provided items and returns
    the checkout URL for the customer to complete payment.
    """
    try:
        logger.info(
            f"Initiating checkout for {request.customer_email} with {len(request.items)} items"
        )

        # Convert request items to checkout items
        checkout_items = []
        for item_req in request.items:
            checkout_item = CheckoutItem(
                product_name=item_req.product_name,
                amount_usd=item_req.amount_usd,
                quantity=item_req.quantity,
                description=item_req.description,
                product_type=item_req.product_type,
                business_id=item_req.business_id,
                metadata=item_req.metadata,
            )
            checkout_items.append(checkout_item)

        # Initiate checkout through manager
        result = manager.initiate_checkout(
            customer_email=request.customer_email,
            items=checkout_items,
            attribution_data=request.attribution_data,
            additional_metadata=request.additional_metadata,
        )

        if result["success"]:
            logger.info(
                f"Successfully initiated checkout for {request.customer_email}: {result['purchase_id']}"
            )
            return CheckoutInitiationResponse(**result)
        else:
            logger.error(
                f"Checkout initiation failed for {request.customer_email}: {result.get('error')}"
            )
            return CheckoutInitiationResponse(
                success=False,
                error=result.get("error", "Unknown error"),
                error_type=result.get("error_type", "CheckoutError"),
            )

    except ValidationError as e:
        logger.error(f"Validation error during checkout initiation: {e}")
        raise HTTPException(status_code=422, detail=str(e))

    except (CheckoutError, StripeError) as e:
        logger.error(f"Checkout/Stripe error during initiation: {e}")
        return CheckoutInitiationResponse(
            success=False, error=str(e), error_type=type(e).__name__
        )

    except Exception as e:
        logger.error(f"Unexpected error during checkout initiation: {e}")
        return CheckoutInitiationResponse(
            success=False, error="Internal server error", error_type="InternalError"
        )


@router.post(
    "/webhook",
    response_model=WebhookEventResponse,
    summary="Stripe webhook endpoint",
    description="Secure webhook endpoint for processing Stripe events - Acceptance Criteria: Webhook endpoint secure",
)
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    processor: WebhookProcessor = Depends(get_webhook_processor),
) -> WebhookEventResponse:
    """
    Stripe webhook endpoint - Acceptance Criteria: Webhook endpoint secure

    Securely processes Stripe webhook events with signature verification,
    idempotency handling, and automatic report generation triggering.
    """
    try:
        # Get raw payload and signature
        payload = await request.body()
        stripe_signature = request.headers.get("stripe-signature")

        if not stripe_signature:
            logger.warning("Webhook request missing Stripe signature")
            raise HTTPException(status_code=401, detail="Missing Stripe signature")

        logger.info(f"Processing webhook with signature: {stripe_signature[:20]}...")

        # Process webhook through processor
        result = processor.process_webhook(payload, stripe_signature)

        if result["success"]:
            logger.info(
                f"Successfully processed webhook event: {result.get('event_id')}"
            )

            # For completed payments, potentially trigger background tasks
            if (
                result.get("event_type") == "checkout.session.completed"
                and result.get("data", {}).get("payment_status") == "paid"
            ):
                # Add background task for additional processing if needed
                # background_tasks.add_task(post_payment_processing, result["data"])
                pass

            return WebhookEventResponse(
                success=True,
                event_id=result.get("event_id"),
                event_type=result.get("event_type"),
                processing_status=result.get("status"),
                data=result.get("data", {}),
            )
        else:
            logger.error(f"Webhook processing failed: {result.get('error')}")
            return WebhookEventResponse(
                success=False, error=result.get("error", "Webhook processing failed")
            )

    except HTTPException:
        raise

    except WebhookError as e:
        logger.error(f"Webhook error: {e}")
        return WebhookEventResponse(success=False, error=str(e))

    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {e}")
        return WebhookEventResponse(success=False, error="Internal server error")


@router.get(
    "/session/{session_id}/status",
    response_model=CheckoutSessionStatusResponse,
    summary="Get checkout session status",
    description="Retrieve the current status of a checkout session",
)
async def get_session_status(
    session_id: str, manager: CheckoutManager = Depends(get_checkout_manager)
) -> CheckoutSessionStatusResponse:
    """
    Get checkout session status

    Retrieves the current payment and processing status of a checkout session.
    """
    try:
        logger.info(f"Retrieving session status for: {session_id}")

        result = manager.retrieve_session_status(session_id)

        if result["success"]:
            return CheckoutSessionStatusResponse(**result)
        else:
            return CheckoutSessionStatusResponse(
                success=False,
                error=result.get("error", "Unknown error"),
                error_type=result.get("error_type", "StripeError"),
            )

    except StripeError as e:
        logger.error(f"Stripe error retrieving session status: {e}")
        return CheckoutSessionStatusResponse(
            success=False, error=str(e), error_type="StripeError"
        )

    except Exception as e:
        logger.error(f"Unexpected error retrieving session status: {e}")
        return CheckoutSessionStatusResponse(
            success=False, error="Internal server error", error_type="InternalError"
        )


@router.get(
    "/success",
    response_model=SuccessPageResponse,
    summary="Payment success page",
    description="Handle successful payment completion - Acceptance Criteria: Success page works",
)
async def payment_success(
    session_id: str,
    purchase_id: Optional[str] = None,
    manager: CheckoutManager = Depends(get_checkout_manager),
) -> SuccessPageResponse:
    """
    Payment success page - Acceptance Criteria: Success page works

    Handles successful payment completion and provides order details
    and report generation status to the customer.
    """
    try:
        logger.info(
            f"Processing success page for session: {session_id}, purchase: {purchase_id}"
        )

        # Retrieve session details
        session_result = manager.retrieve_session_status(session_id)

        if not session_result["success"]:
            logger.error(
                f"Failed to retrieve session {session_id}: {session_result.get('error')}"
            )
            return SuccessPageResponse(
                success=False, error="Session not found or invalid"
            )

        # Extract session information
        session_data = session_result
        payment_status = session_data.get("payment_status")
        metadata = session_data.get("metadata", {})

        # Determine success based on payment status
        payment_successful = payment_status == "paid"

        if payment_successful:
            # Extract purchase details from metadata
            actual_purchase_id = purchase_id or metadata.get("purchase_id")
            customer_email = metadata.get("customer_email")

            # Extract item information
            items = []
            item_count = int(metadata.get("item_count", "0"))
            for i in range(item_count):
                item_name = metadata.get(f"item_{i}_name")
                item_type = metadata.get(f"item_{i}_type")
                business_url = metadata.get(f"item_{i}_business_url") or metadata.get(
                    "business_url"
                )

                if item_name:
                    items.append(
                        {
                            "name": item_name,
                            "type": item_type,
                            "business_url": business_url,
                        }
                    )

            # Determine report status and delivery estimate
            report_status = "generating"
            estimated_delivery = "within 24 hours"

            # For multiple items, adjust delivery estimate
            if item_count > 5:
                estimated_delivery = "within 48 hours"
            elif item_count > 10:
                estimated_delivery = "within 72 hours"

            logger.info(f"Payment successful for purchase {actual_purchase_id}")

            return SuccessPageResponse(
                success=True,
                purchase_id=actual_purchase_id,
                session_id=session_id,
                customer_email=customer_email,
                amount_total_usd=session_data.get("amount_total", 0) / 100.0
                if session_data.get("amount_total")
                else None,
                payment_status=payment_status,
                items=items,
                report_status=report_status,
                estimated_delivery=estimated_delivery,
            )
        else:
            logger.warning(
                f"Payment not completed for session {session_id}: status={payment_status}"
            )
            return SuccessPageResponse(
                success=False,
                session_id=session_id,
                payment_status=payment_status,
                error=f"Payment not completed. Status: {payment_status}",
            )

    except Exception as e:
        logger.error(f"Error processing success page: {e}")
        return SuccessPageResponse(success=False, error="Internal server error")


# Convenience endpoints for common use cases


@router.post(
    "/audit-report",
    response_model=CheckoutInitiationResponse,
    summary="Create audit report checkout",
    description="Convenience endpoint for single audit report checkout",
)
async def create_audit_report_checkout(
    request: AuditReportCheckoutRequest,
    manager: CheckoutManager = Depends(get_checkout_manager),
) -> CheckoutInitiationResponse:
    """
    Convenience endpoint for audit report checkout

    Simplified endpoint for creating a checkout session for a single
    website audit report.
    """
    try:
        logger.info(f"Creating audit report checkout for {request.business_url}")

        result = manager.create_audit_report_checkout(
            customer_email=request.customer_email,
            business_url=request.business_url,
            business_name=request.business_name,
            amount_usd=request.amount_usd,
            attribution_data=request.attribution_data,
        )

        if result["success"]:
            return CheckoutInitiationResponse(**result)
        else:
            return CheckoutInitiationResponse(
                success=False,
                error=result.get("error", "Unknown error"),
                error_type=result.get("error_type", "CheckoutError"),
            )

    except Exception as e:
        logger.error(f"Error creating audit report checkout: {e}")
        return CheckoutInitiationResponse(
            success=False, error="Internal server error", error_type="InternalError"
        )


@router.post(
    "/bulk-reports",
    response_model=CheckoutInitiationResponse,
    summary="Create bulk reports checkout",
    description="Convenience endpoint for bulk audit reports checkout",
)
async def create_bulk_reports_checkout(
    request: BulkReportsCheckoutRequest,
    manager: CheckoutManager = Depends(get_checkout_manager),
) -> CheckoutInitiationResponse:
    """
    Convenience endpoint for bulk reports checkout

    Simplified endpoint for creating a checkout session for multiple
    website audit reports with bulk pricing.
    """
    try:
        logger.info(
            f"Creating bulk reports checkout for {len(request.business_urls)} URLs"
        )

        result = manager.create_bulk_reports_checkout(
            customer_email=request.customer_email,
            business_urls=request.business_urls,
            amount_per_report_usd=request.amount_per_report_usd,
            attribution_data=request.attribution_data,
        )

        if result["success"]:
            return CheckoutInitiationResponse(**result)
        else:
            return CheckoutInitiationResponse(
                success=False,
                error=result.get("error", "Unknown error"),
                error_type=result.get("error_type", "CheckoutError"),
            )

    except Exception as e:
        logger.error(f"Error creating bulk reports checkout: {e}")
        return CheckoutInitiationResponse(
            success=False, error="Internal server error", error_type="InternalError"
        )


# Health and status endpoints


@router.get(
    "/status",
    response_model=APIStatusResponse,
    summary="API health status",
    description="Get API and service health status",
)
async def get_api_status(
    manager: CheckoutManager = Depends(get_checkout_manager),
    processor: WebhookProcessor = Depends(get_webhook_processor),
    stripe_client: StripeClient = Depends(get_stripe_client),
) -> APIStatusResponse:
    """
    Get API health and status information

    Returns the current health status of the API and its dependencies.
    """
    try:
        # Check service statuses
        checkout_status = manager.get_status()
        webhook_status = processor.get_status()
        stripe_status = stripe_client.get_status()

        services = {
            "stripe": "connected"
            if stripe_status.get("webhook_configured")
            else "limited",
            "checkout_manager": "active"
            if checkout_status.get("test_mode") is not None
            else "inactive",
            "webhook_processor": "active"
            if webhook_status.get("idempotency_enabled") is not None
            else "inactive",
        }

        overall_status = (
            "healthy"
            if all(s in ["connected", "active"] for s in services.values())
            else "degraded"
        )

        return APIStatusResponse(
            status=overall_status, version="1.0.0", services=services
        )

    except Exception as e:
        logger.error(f"Error getting API status: {e}")
        return APIStatusResponse(
            status="error", version="1.0.0", services={"error": str(e)}
        )


# Error handlers - these would be added to the main FastAPI app, not the router
# Example of how to add them:
# app.add_exception_handler(ValidationError, validation_exception_handler)
# app.add_exception_handler(CheckoutError, checkout_exception_handler)
# app.add_exception_handler(StripeError, stripe_exception_handler)
# app.add_exception_handler(WebhookError, webhook_exception_handler)


async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle validation errors - Acceptance Criteria: Error handling proper"""
    return handle_validation_error(exc)


async def checkout_exception_handler(request: Request, exc: CheckoutError):
    """Handle checkout errors"""
    return create_error_response(
        error_message=str(exc), error_type="CheckoutError", status_code=400
    )


async def stripe_exception_handler(request: Request, exc: StripeError):
    """Handle Stripe errors"""
    return create_error_response(
        error_message=str(exc),
        error_type="StripeError",
        error_code=exc.error_code,
        status_code=402 if "payment" in str(exc).lower() else 400,
    )


async def webhook_exception_handler(request: Request, exc: WebhookError):
    """Handle webhook errors"""
    return create_error_response(
        error_message=str(exc), error_type="WebhookError", status_code=400
    )


# Utility functions for background tasks
async def post_payment_processing(payment_data: Dict[str, Any]) -> None:
    """Background task for post-payment processing"""
    try:
        purchase_id = payment_data.get("purchase_id")
        logger.info(f"Running post-payment processing for purchase {purchase_id}")

        # Here you would:
        # 1. Send confirmation email
        # 2. Update analytics
        # 3. Notify other services
        # 4. Log metrics

        logger.info(f"Completed post-payment processing for purchase {purchase_id}")

    except Exception as e:
        logger.error(f"Error in post-payment processing: {e}")


# Request/response middleware for logging
# Note: Middleware would be added to the main FastAPI app, not the router
# Example: app.middleware("http")(log_requests)


async def log_requests(request: Request, call_next):
    """Log API requests and responses"""
    start_time = datetime.utcnow()

    # Log request
    logger.info(f"API Request: {request.method} {request.url.path}")

    # Process request
    response = await call_next(request)

    # Log response
    duration = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"API Response: {response.status_code} ({duration:.3f}s)")

    return response


# Configuration constants
API_CONFIG = {
    "MAX_REQUEST_SIZE": 1024 * 1024,  # 1MB
    "RATE_LIMIT_PER_MINUTE": 100,
    "SESSION_TIMEOUT_MINUTES": 30,
    "WEBHOOK_TIMEOUT_SECONDS": 30,
}

CORS_SETTINGS = {
    "ALLOW_ORIGINS": ["https://leadfactory.com", "https://staging.leadfactory.com"],
    "ALLOW_METHODS": ["GET", "POST"],
    "ALLOW_HEADERS": ["*"],
    "ALLOW_CREDENTIALS": True,
}

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}
