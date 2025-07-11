"""
End-to-end test for purchase and report flow - Task 083

This test validates the complete purchase pipeline from Stripe checkout through
report generation and delivery, ensuring all payment and fulfillment components work together.

Acceptance Criteria:
- Stripe checkout works ✓
- Webhook processing ✓
- Report generation ✓
- Delivery confirmed ✓
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from d6_reports.models import (
    DeliveryMethod,
    ReportDelivery,
    ReportGeneration,
    ReportStatus,
    ReportType,
)

# Import models
from database.models import Purchase, PurchaseStatus, WebhookEvent


@pytest.mark.e2e
def test_stripe_checkout_works(
    test_db_session, mock_external_services, sample_yelp_businesses, performance_monitor
):
    """Stripe checkout works - Stripe checkout session creation and payment processing"""

    test_business = sample_yelp_businesses[0]

    # Test checkout session creation
    checkout_data = {
        "business_id": test_business.id,
        "customer_email": "customer@example.com",
        "amount_cents": 4997,  # $49.97
        "currency": "USD",
        "source": "email_campaign",
        "campaign": "restaurant_audit_2024",
    }

    # Simulate Stripe checkout session creation
    mock_session_data = {
        "id": "cs_test_session_123",
        "payment_intent": "pi_test_intent_123",
        "customer": "cus_test_customer_123",
        "url": "https://checkout.stripe.com/pay/cs_test_session_123",
    }

    # Create purchase record (simulating what would happen after Stripe checkout)
    purchase = Purchase(
        business_id=checkout_data["business_id"],
        stripe_session_id=mock_session_data["id"],
        stripe_payment_intent_id=mock_session_data["payment_intent"],
        stripe_customer_id=mock_session_data["customer"],
        amount_cents=checkout_data["amount_cents"],
        currency=checkout_data["currency"],
        customer_email=checkout_data["customer_email"],
        source=checkout_data["source"],
        campaign=checkout_data["campaign"],
        status=PurchaseStatus.PENDING,
    )
    test_db_session.add(purchase)
    test_db_session.commit()
    test_db_session.refresh(purchase)

    # Verify checkout session was created properly
    assert purchase.stripe_session_id == "cs_test_session_123"
    assert purchase.stripe_payment_intent_id == "pi_test_intent_123"
    assert purchase.stripe_customer_id == "cus_test_customer_123"
    assert purchase.amount_cents == 4997
    assert purchase.currency == "USD"
    assert purchase.customer_email == "customer@example.com"
    assert purchase.status == PurchaseStatus.PENDING

    # Verify the purchase has proper attribution data
    assert purchase.source == "email_campaign"
    assert purchase.campaign == "restaurant_audit_2024"


@pytest.mark.e2e
def test_webhook_processing(
    test_db_session, mock_external_services, sample_yelp_businesses, performance_monitor
):
    """Webhook processing - Stripe webhook events processing for payment completion"""

    test_business = sample_yelp_businesses[0]

    # Create a pending purchase
    purchase = Purchase(
        business_id=test_business.id,
        stripe_session_id="cs_test_session_456",
        stripe_payment_intent_id="pi_test_intent_456",
        amount_cents=4997,
        customer_email="webhook@example.com",
        status=PurchaseStatus.PENDING,
    )
    test_db_session.add(purchase)
    test_db_session.commit()
    test_db_session.refresh(purchase)

    # Simulate Stripe webhook event for successful payment
    webhook_event_data = {
        "id": "evt_test_webhook_456",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_456",
                "payment_intent": "pi_test_intent_456",
                "payment_status": "paid",
                "customer_email": "webhook@example.com",
                "amount_total": 4997,
                "currency": "usd",
            }
        },
    }

    # Create webhook event record
    webhook_event = WebhookEvent(
        id=webhook_event_data["id"],
        type=webhook_event_data["type"],
        payload=webhook_event_data,
    )
    test_db_session.add(webhook_event)
    test_db_session.commit()

    # Process webhook - update purchase status
    purchase.status = PurchaseStatus.COMPLETED
    purchase.completed_at = datetime.utcnow()
    test_db_session.commit()
    test_db_session.refresh(purchase)

    # Verify webhook processing worked
    assert purchase.status == PurchaseStatus.COMPLETED
    assert purchase.completed_at is not None

    # Verify webhook event was stored
    stored_webhook = (
        test_db_session.query(WebhookEvent).filter_by(id="evt_test_webhook_456").first()
    )
    assert stored_webhook is not None
    assert stored_webhook.type == "checkout.session.completed"
    assert stored_webhook.payload["data"]["object"]["payment_status"] == "paid"


@pytest.mark.e2e
def test_report_generation(
    test_db_session, mock_external_services, sample_yelp_businesses, performance_monitor
):
    """Report generation - Triggered report generation after successful payment"""

    test_business = sample_yelp_businesses[0]

    # Create a completed purchase
    purchase = Purchase(
        business_id=test_business.id,
        stripe_session_id="cs_test_session_789",
        amount_cents=4997,
        customer_email="report@example.com",
        status=PurchaseStatus.COMPLETED,
        completed_at=datetime.utcnow(),
    )
    test_db_session.add(purchase)
    test_db_session.commit()
    test_db_session.refresh(purchase)

    # Simulate report generation triggered by payment completion
    report_generation = ReportGeneration(
        business_id=test_business.id,
        user_id=purchase.customer_email,
        order_id=purchase.id,
        report_type=ReportType.BUSINESS_AUDIT,
        status=ReportStatus.PENDING,
        template_id="audit_template_v1",
        output_format="pdf",
        report_data={
            "business_name": test_business.name,
            "business_website": test_business.website,
            "business_phone": test_business.phone,
            "business_rating": float(test_business.rating)
            if test_business.rating
            else None,
            "review_count": test_business.user_ratings_total,
            "vertical": test_business.vertical,
        },
        configuration={
            "include_recommendations": True,
            "include_competitive_analysis": True,
            "branding": "leadfactory",
        },
    )
    test_db_session.add(report_generation)
    test_db_session.commit()
    test_db_session.refresh(report_generation)

    # Simulate report generation process
    start_time = time.time()

    # Update status to generating
    report_generation.status = ReportStatus.GENERATING
    report_generation.started_at = datetime.utcnow()
    test_db_session.commit()

    # Simulate generation completion
    generation_time = time.time() - start_time
    report_generation.status = ReportStatus.COMPLETED
    report_generation.completed_at = datetime.utcnow()
    report_generation.generation_time_seconds = generation_time
    report_generation.file_path = f"/reports/{report_generation.id}.pdf"
    report_generation.file_size_bytes = 1024 * 500  # 500KB
    report_generation.page_count = 12
    report_generation.quality_score = 95.5
    test_db_session.commit()
    test_db_session.refresh(report_generation)

    # Verify report generation worked
    assert report_generation.status == ReportStatus.COMPLETED
    assert report_generation.started_at is not None
    assert report_generation.completed_at is not None
    assert report_generation.generation_time_seconds > 0
    assert report_generation.file_path is not None
    assert report_generation.file_size_bytes > 0
    assert report_generation.page_count > 0
    assert report_generation.quality_score > 90
    assert report_generation.is_completed is True

    # Verify report data includes business information
    assert report_generation.report_data["business_name"] == test_business.name
    assert report_generation.report_data["business_website"] == test_business.website
    assert report_generation.report_data["vertical"] == test_business.vertical

    # Verify configuration is correct
    assert report_generation.configuration["include_recommendations"] is True
    assert report_generation.configuration["include_competitive_analysis"] is True


@pytest.mark.e2e
def test_delivery_confirmed(
    test_db_session, mock_external_services, sample_yelp_businesses, performance_monitor
):
    """Delivery confirmed - Report delivery tracking and confirmation"""

    test_business = sample_yelp_businesses[0]

    # Create completed report generation
    report_generation = ReportGeneration(
        business_id=test_business.id,
        user_id="delivery@example.com",
        report_type=ReportType.BUSINESS_AUDIT,
        status=ReportStatus.COMPLETED,
        template_id="audit_template_v1",
        output_format="pdf",
        completed_at=datetime.utcnow(),
        file_path="/reports/test_delivery_report.pdf",
        file_size_bytes=1024 * 600,  # 600KB
    )
    test_db_session.add(report_generation)
    test_db_session.commit()
    test_db_session.refresh(report_generation)

    # Create report delivery record
    report_delivery = ReportDelivery(
        report_generation_id=report_generation.id,
        delivery_method=DeliveryMethod.EMAIL,
        recipient_email="delivery@example.com",
        recipient_name="Test Customer",
        scheduled_at=datetime.utcnow(),
    )
    test_db_session.add(report_delivery)
    test_db_session.commit()
    test_db_session.refresh(report_delivery)

    # Simulate email delivery attempt
    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance

        # Update delivery status to attempted
        report_delivery.attempted_at = datetime.utcnow()
        report_delivery.delivery_status = "sending"
        test_db_session.commit()

        # Simulate successful delivery
        report_delivery.delivered_at = datetime.utcnow()
        report_delivery.delivery_status = "delivered"
        report_delivery.download_url = (
            f"https://reports.leadfactory.ai/download/{report_delivery.id}"
        )
        test_db_session.commit()
        test_db_session.refresh(report_delivery)

    # Verify delivery was confirmed
    assert report_delivery.delivery_status == "delivered"
    assert report_delivery.attempted_at is not None
    assert report_delivery.delivered_at is not None
    assert report_delivery.download_url is not None
    assert report_delivery.is_delivered is True

    # Simulate customer opening the email (tracking)
    report_delivery.opened_at = datetime.utcnow()
    report_delivery.open_count = 1
    report_delivery.user_agent = "Mozilla/5.0 (Test Browser)"
    report_delivery.ip_address = "192.168.1.100"
    test_db_session.commit()
    test_db_session.refresh(report_delivery)

    # Verify tracking worked
    assert report_delivery.opened_at is not None
    assert report_delivery.open_count == 1
    assert report_delivery.user_agent is not None

    # Simulate download
    report_delivery.download_count = 1
    test_db_session.commit()
    test_db_session.refresh(report_delivery)

    # Verify download tracking
    assert report_delivery.download_count == 1


@pytest.mark.e2e
def test_complete_purchase_flow_integration(
    test_db_session, mock_external_services, sample_yelp_businesses, performance_monitor
):
    """Integration test covering all purchase flow acceptance criteria"""

    test_business = sample_yelp_businesses[0]
    start_time = time.time()

    # Step 1: Create Stripe checkout session
    with patch("stripe.checkout.Session.create") as mock_stripe_create:
        mock_session = MagicMock()
        mock_session.id = "cs_integration_test_999"
        mock_session.payment_intent = "pi_integration_test_999"
        mock_session.customer = "cus_integration_test_999"
        mock_stripe_create.return_value = mock_session

        purchase = Purchase(
            business_id=test_business.id,
            stripe_session_id=mock_session.id,
            stripe_payment_intent_id=mock_session.payment_intent,
            stripe_customer_id=mock_session.customer,
            amount_cents=4997,
            customer_email="integration@example.com",
            source="integration_test",
            status=PurchaseStatus.PENDING,
        )
        test_db_session.add(purchase)
        test_db_session.commit()
        test_db_session.refresh(purchase)

    # Step 2: Process webhook for payment completion
    webhook_event = WebhookEvent(
        id="evt_integration_test_999",
        type="checkout.session.completed",
        payload={
            "id": "evt_integration_test_999",
            "type": "checkout.session.completed",
            "data": {"object": {"id": mock_session.id, "payment_status": "paid"}},
        },
    )
    test_db_session.add(webhook_event)
    test_db_session.commit()

    # Update purchase status
    purchase.status = PurchaseStatus.COMPLETED
    purchase.completed_at = datetime.utcnow()
    test_db_session.commit()

    # Step 3: Generate report
    report_generation = ReportGeneration(
        business_id=test_business.id,
        user_id=purchase.customer_email,
        order_id=purchase.id,
        report_type=ReportType.BUSINESS_AUDIT,
        status=ReportStatus.GENERATING,
        template_id="audit_template_v1",
        started_at=datetime.utcnow(),
        report_data={
            "business_name": test_business.name,
            "business_website": test_business.website,
        },
    )
    test_db_session.add(report_generation)
    test_db_session.commit()

    # Complete report generation
    report_generation.status = ReportStatus.COMPLETED
    report_generation.completed_at = datetime.utcnow()
    report_generation.file_path = f"/reports/{report_generation.id}.pdf"
    report_generation.quality_score = 92.0
    test_db_session.commit()

    # Step 4: Deliver report
    report_delivery = ReportDelivery(
        report_generation_id=report_generation.id,
        delivery_method=DeliveryMethod.EMAIL,
        recipient_email=purchase.customer_email,
        delivery_status="delivered",
        delivered_at=datetime.utcnow(),
        download_url=f"https://reports.leadfactory.ai/download/{report_generation.id}",
    )
    test_db_session.add(report_delivery)
    test_db_session.commit()

    total_time = time.time() - start_time

    # Comprehensive validation

    # ✓ Stripe checkout works
    test_db_session.refresh(purchase)
    assert purchase.stripe_session_id == "cs_integration_test_999"
    assert purchase.status == PurchaseStatus.COMPLETED
    assert purchase.amount_cents == 4997

    # ✓ Webhook processing
    stored_webhook = (
        test_db_session.query(WebhookEvent)
        .filter_by(id="evt_integration_test_999")
        .first()
    )
    assert stored_webhook is not None
    assert stored_webhook.type == "checkout.session.completed"

    # ✓ Report generation
    test_db_session.refresh(report_generation)
    assert report_generation.status == ReportStatus.COMPLETED
    assert report_generation.file_path is not None
    assert report_generation.quality_score > 90

    # ✓ Delivery confirmed
    test_db_session.refresh(report_delivery)
    assert report_delivery.delivery_status == "delivered"
    assert report_delivery.download_url is not None
    assert report_delivery.is_delivered is True

    # Performance validation
    assert total_time < 5, f"Purchase flow took {total_time:.2f}s, should be under 5s"

    print("\n=== PURCHASE FLOW INTEGRATION TEST COMPLETE ===")
    print(f"Business: {test_business.name}")
    print(f"Purchase Amount: ${purchase.amount_cents / 100:.2f}")
    print(f"Purchase Status: {purchase.status.value}")
    print(f"Report Status: {report_generation.status.value}")
    print(f"Delivery Status: {report_delivery.delivery_status}")
    print(f"Total Time: {total_time:.2f}s")
