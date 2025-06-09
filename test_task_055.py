"""
Task 055 Verification Test - D7 Storefront Models

Tests for purchase tracking models with Stripe integration, attribution tracking, and status management.
"""

import sys
sys.path.insert(0, '/app')

from d7_storefront.models import (
    Purchase, PurchaseItem, Customer, PaymentSession,
    PurchaseStatus, PaymentMethod, ProductType,
    generate_uuid
)
from decimal import Decimal

def test_task_055():
    """Test Task 055 acceptance criteria"""
    print("Testing Task 055: Create purchase models")
    print("=" * 50)
    
    # Test 1: Purchase tracking model
    print("Testing purchase tracking model...")
    purchase = Purchase(
        customer_email="test@example.com",
        amount_cents=2999,
        total_cents=2999,
        status=PurchaseStatus.CART
    )
    assert purchase.customer_email == "test@example.com"
    assert purchase.amount_cents == 2999
    assert purchase.status == PurchaseStatus.CART
    print("✓ Purchase tracking model works")
    
    # Test 2: Stripe ID fields
    print("Testing Stripe ID fields...")
    purchase.stripe_checkout_session_id = "cs_test_123"
    purchase.stripe_payment_intent_id = "pi_test_123"
    purchase.stripe_customer_id = "cus_test_123"
    assert purchase.stripe_checkout_session_id == "cs_test_123"
    assert purchase.stripe_payment_intent_id == "pi_test_123"
    assert purchase.stripe_customer_id == "cus_test_123"
    print("✓ Stripe ID fields work")
    
    # Test 3: Attribution tracking
    print("Testing attribution tracking...")
    purchase.utm_source = "google"
    purchase.utm_medium = "cpc"
    purchase.utm_campaign = "test_campaign"
    purchase.referrer_url = "https://google.com"
    purchase.attribution_metadata = {"test": "data"}
    assert purchase.utm_source == "google"
    assert purchase.utm_medium == "cpc"
    assert purchase.utm_campaign == "test_campaign"
    assert purchase.referrer_url == "https://google.com"
    assert purchase.attribution_metadata["test"] == "data"
    print("✓ Attribution tracking works")
    
    # Test 4: Status management
    print("Testing status management...")
    purchase.status = PurchaseStatus.COMPLETED
    assert purchase.status == PurchaseStatus.COMPLETED
    assert purchase.is_completed() == True
    assert purchase.is_paid() == True
    print("✓ Status management works")
    
    # Test additional models
    print("Testing other models...")
    
    # PurchaseItem
    item = PurchaseItem(
        purchase_id="test_123",
        product_type=ProductType.AUDIT_REPORT,
        product_name="Test Report",
        unit_price_cents=2999,
        quantity=1,
        total_price_cents=2999
    )
    assert item.unit_price_usd == Decimal("29.99")
    print("✓ PurchaseItem model works")
    
    # Customer
    customer = Customer(
        email="customer@test.com",
        stripe_customer_id="cus_test"
    )
    assert customer.email == "customer@test.com"
    print("✓ Customer model works")
    
    # PaymentSession
    from datetime import datetime, timedelta
    session = PaymentSession(
        purchase_id="test_123",
        stripe_session_id="cs_test",
        success_url="https://success.com",
        cancel_url="https://cancel.com",
        session_expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    assert session.is_active() == True
    print("✓ PaymentSession model works")
    
    print("=" * 50)
    print("🎉 ALL TESTS PASSED!")
    print("")
    print("Acceptance Criteria Status:")
    print("✓ Purchase tracking model")
    print("✓ Stripe ID fields")
    print("✓ Attribution tracking")
    print("✓ Status management")
    print("")
    print("Task 055 implementation complete and verified!")
    return True

if __name__ == "__main__":
    test_task_055()