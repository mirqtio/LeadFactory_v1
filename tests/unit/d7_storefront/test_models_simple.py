"""
Simple Test D7 Storefront Models - Task 055 (No pytest required)

Tests for purchase tracking models with Stripe integration, attribution tracking, and status management.

Acceptance Criteria:
- Purchase tracking model ✓
- Stripe ID fields ✓
- Attribution tracking ✓
- Status management ✓
"""

import sys
from datetime import datetime, timedelta
from decimal import Decimal

# Add project root to path
sys.path.insert(0, "/app")

# Import models to test
from d7_storefront.models import (
    Customer,
    D7Purchase,
    PaymentMethod,
    PaymentSession,
    ProductType,
    PurchaseCreateRequest,
    PurchaseItem,
    PurchaseStatus,
    PurchaseSummary,
    generate_uuid,
)


def test_enum_values():
    """Test enum values are correct"""
    print("Testing enum values...")

    # Test PurchaseStatus
    assert PurchaseStatus.CART == "cart"
    assert PurchaseStatus.CHECKOUT_STARTED == "checkout_started"
    assert PurchaseStatus.PENDING == "pending"
    assert PurchaseStatus.COMPLETED == "completed"
    assert PurchaseStatus.REFUNDED == "refunded"
    assert PurchaseStatus.FAILED == "failed"
    assert PurchaseStatus.CANCELLED == "cancelled"

    # Test PaymentMethod
    assert PaymentMethod.CARD == "card"
    assert PaymentMethod.BANK_TRANSFER == "bank_transfer"
    assert PaymentMethod.PAYPAL == "paypal"
    assert PaymentMethod.APPLE_PAY == "apple_pay"
    assert PaymentMethod.GOOGLE_PAY == "google_pay"

    # Test ProductType
    assert ProductType.AUDIT_REPORT == "audit_report"
    assert ProductType.BULK_REPORTS == "bulk_reports"
    assert ProductType.PREMIUM_REPORT == "premium_report"

    print("✓ Enum values test passed")


def test_purchase_model_creation():
    """Test Purchase model creation"""
    print("Testing Purchase model creation...")

    # Test purchase object creation
    purchase = D7Purchase(
        customer_email="test@example.com",
        amount_cents=2999,  # $29.99
        total_cents=3299,  # $32.99 with tax
        currency="USD",
        status=PurchaseStatus.CART,
    )

    # Verify purchase attributes
    assert purchase.customer_email == "test@example.com"
    assert purchase.amount_cents == 2999
    assert purchase.total_cents == 3299
    assert purchase.currency == "USD"
    assert purchase.status == PurchaseStatus.CART

    print("✓ Purchase model creation test passed")


def test_stripe_id_fields():
    """Test Stripe ID fields - Acceptance Criteria"""
    print("Testing Stripe ID fields...")

    purchase = D7Purchase(
        customer_email="stripe@example.com",
        amount_cents=1999,
        total_cents=1999,
        # Stripe ID fields
        stripe_checkout_session_id="cs_test_123456789",
        stripe_payment_intent_id="pi_test_123456789",
        stripe_customer_id="cus_test_123456789",
        stripe_subscription_id="sub_test_123456789",
    )

    # Verify Stripe ID fields
    assert purchase.stripe_checkout_session_id == "cs_test_123456789"
    assert purchase.stripe_payment_intent_id == "pi_test_123456789"
    assert purchase.stripe_customer_id == "cus_test_123456789"
    assert purchase.stripe_subscription_id == "sub_test_123456789"

    print("✓ Stripe ID fields test passed")


def test_attribution_tracking():
    """Test attribution tracking - Acceptance Criteria"""
    print("Testing attribution tracking...")

    purchase = D7Purchase(
        customer_email="attribution@example.com",
        amount_cents=2999,
        total_cents=2999,
        # Attribution tracking fields
        utm_source="google",
        utm_medium="cpc",
        utm_campaign="q4_audit_promotion",
        utm_term="website audit",
        utm_content="hero_cta",
        referrer_url="https://google.com/search?q=website+audit",
        landing_page="https://example.com/audit",
        session_id="sess_123456789",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        ip_address="192.168.1.1",
        attribution_metadata={"experiment_id": "exp_001", "variant": "control"},
    )

    # Verify attribution tracking
    assert purchase.utm_source == "google"
    assert purchase.utm_medium == "cpc"
    assert purchase.utm_campaign == "q4_audit_promotion"
    assert purchase.utm_term == "website audit"
    assert purchase.utm_content == "hero_cta"
    assert purchase.referrer_url == "https://google.com/search?q=website+audit"
    assert purchase.landing_page == "https://example.com/audit"
    assert purchase.session_id == "sess_123456789"
    assert purchase.user_agent == "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    assert purchase.ip_address == "192.168.1.1"
    assert purchase.attribution_metadata["experiment_id"] == "exp_001"
    assert purchase.attribution_metadata["variant"] == "control"

    print("✓ Attribution tracking test passed")


def test_status_management():
    """Test status management - Acceptance Criteria"""
    print("Testing status management...")

    purchase = D7Purchase(
        customer_email="status@example.com",
        amount_cents=2999,
        total_cents=2999,
        status=PurchaseStatus.CART,
    )

    # Test status transitions
    assert purchase.status == PurchaseStatus.CART

    purchase.status = PurchaseStatus.CHECKOUT_STARTED
    purchase.checkout_started_at = datetime.utcnow()
    assert purchase.status == PurchaseStatus.CHECKOUT_STARTED
    assert purchase.checkout_started_at is not None

    purchase.status = PurchaseStatus.PENDING
    assert purchase.status == PurchaseStatus.PENDING

    purchase.status = PurchaseStatus.COMPLETED
    purchase.payment_completed_at = datetime.utcnow()
    purchase.report_delivered_at = datetime.utcnow()
    assert purchase.status == PurchaseStatus.COMPLETED
    assert purchase.payment_completed_at is not None
    assert purchase.report_delivered_at is not None

    # Test helper methods
    assert purchase.is_completed() is True
    assert purchase.is_paid() is True

    print("✓ Status management test passed")


def test_purchase_amounts():
    """Test purchase amount calculations"""
    print("Testing purchase amounts...")

    purchase = D7Purchase(
        customer_email="amounts@example.com",
        amount_cents=2999,  # $29.99
        total_cents=3299,  # $32.99 with tax
        tax_cents=300,  # $3.00 tax
    )

    # Test amount properties
    assert purchase.amount_usd == Decimal("29.99")
    assert purchase.total_usd == Decimal("32.99")
    assert purchase.tax_cents == 300

    print("✓ Purchase amounts test passed")


def test_purchase_item_model():
    """Test PurchaseItem model"""
    print("Testing PurchaseItem model...")

    item = PurchaseItem(
        purchase_id="test_purchase_123",
        product_type=ProductType.AUDIT_REPORT,
        product_name="Website Audit Report",
        product_description="Comprehensive website performance audit",
        sku="WA-BASIC-001",
        unit_price_cents=2999,
        quantity=1,
        total_price_cents=2999,
        delivered=False,  # Set default value explicitly for test
    )

    # Verify item creation
    assert item.purchase_id == "test_purchase_123"
    assert item.product_type == ProductType.AUDIT_REPORT
    assert item.product_name == "Website Audit Report"
    assert item.sku == "WA-BASIC-001"
    assert item.unit_price_cents == 2999
    assert item.quantity == 1
    assert item.total_price_cents == 2999
    assert item.delivered is False

    # Test amount properties
    assert item.unit_price_usd == Decimal("29.99")
    assert item.total_price_usd == Decimal("29.99")

    print("✓ PurchaseItem model test passed")


def test_customer_model():
    """Test Customer model"""
    print("Testing Customer model...")

    customer = Customer(
        email="customer@example.com",
        name="John Doe",
        phone="+1-555-123-4567",
        company="Example Corp",
        stripe_customer_id="cus_test_123456789",
        total_spent_cents=5998,  # $59.98
        total_purchases=2,
    )

    # Verify customer creation
    assert customer.email == "customer@example.com"
    assert customer.name == "John Doe"
    assert customer.phone == "+1-555-123-4567"
    assert customer.company == "Example Corp"
    assert customer.stripe_customer_id == "cus_test_123456789"
    assert customer.total_spent_cents == 5998
    assert customer.total_purchases == 2

    # Test value metrics
    assert customer.total_spent_usd == Decimal("59.98")
    assert customer.is_repeat_customer() is True

    print("✓ Customer model test passed")


def test_payment_session_model():
    """Test PaymentSession model"""
    print("Testing PaymentSession model...")

    session = PaymentSession(
        purchase_id="test_purchase_123",
        stripe_session_id="cs_test_session_123",
        stripe_session_url="https://checkout.stripe.com/cs_test_session_123",
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        session_expires_at=datetime.utcnow() + timedelta(hours=1),
        payment_methods=["card", "apple_pay"],
    )

    # Verify session creation
    assert session.purchase_id == "test_purchase_123"
    assert session.stripe_session_id == "cs_test_session_123"
    assert session.success_url == "https://example.com/success"
    assert session.cancel_url == "https://example.com/cancel"
    assert session.payment_methods == ["card", "apple_pay"]
    assert session.is_active() is True
    assert session.is_expired() is False

    print("✓ PaymentSession model test passed")


def test_data_classes():
    """Test data classes"""
    print("Testing data classes...")

    # Test UUID generation
    uuid1 = generate_uuid()
    uuid2 = generate_uuid()
    assert uuid1 != uuid2
    assert len(uuid1) == 36
    assert len(uuid2) == 36

    # Test PurchaseCreateRequest
    items = [
        {
            "product_type": "audit_report",
            "product_name": "Website Audit",
            "unit_price_cents": 2999,
            "quantity": 1,
        }
    ]

    attribution = {
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "test_campaign",
    }

    request = PurchaseCreateRequest(customer_email="test@example.com", items=items, attribution=attribution)

    assert request.customer_email == "test@example.com"
    assert len(request.items) == 1
    assert request.attribution["utm_source"] == "google"

    # Test PurchaseSummary
    purchase = D7Purchase(
        customer_email="summary@example.com",
        amount_cents=2999,
        total_cents=3299,
        status=PurchaseStatus.COMPLETED,
        utm_source="facebook",
        utm_campaign="test_campaign",
    )

    # Mock items for summary
    purchase.items = []  # Empty items list for testing

    summary = PurchaseSummary(purchase)
    assert summary.customer_email == "summary@example.com"
    assert summary.status == PurchaseStatus.COMPLETED
    assert summary.amount_usd == Decimal("29.99")
    assert summary.total_usd == Decimal("32.99")
    assert summary.utm_source == "facebook"

    # Test serialization
    summary_dict = summary.to_dict()
    assert summary_dict["customer_email"] == "summary@example.com"
    assert summary_dict["status"] == "completed"
    assert summary_dict["amount_usd"] == 29.99

    print("✓ Data classes test passed")


def run_all_tests():
    """Run all tests"""
    print("Running D7 Storefront Models Tests...")
    print("=" * 50)

    try:
        test_enum_values()
        test_purchase_model_creation()
        test_stripe_id_fields()
        test_attribution_tracking()
        test_status_management()
        test_purchase_amounts()
        test_purchase_item_model()
        test_customer_model()
        test_payment_session_model()
        test_data_classes()

        print("=" * 50)
        print("✅ ALL TESTS PASSED!")
        print("\nAcceptance Criteria Status:")
        print("✓ Purchase tracking model")
        print("✓ Stripe ID fields")
        print("✓ Attribution tracking")
        print("✓ Status management")
        print("\n🎉 Task 055 implementation complete and verified!")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
