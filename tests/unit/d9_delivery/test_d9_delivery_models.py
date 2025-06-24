"""
Unit tests for D9 delivery models

Tests email delivery tracking, bounce management, suppression lists,
and event tracking models for compliance and monitoring.

Acceptance Criteria Tests:
- Email send tracking ✓
- Bounce tracking model ✓ 
- Suppression list ✓
- Event timestamps ✓
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from d9_delivery.models import (
    BounceTracking,
    BounceType,
    DeliveryEvent,
    DeliveryStatus,
    EmailDelivery,
    EventType,
    SuppressionList,
    SuppressionReason,
)
from database.base import Base


@pytest.fixture
def db_session():
    """Create test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()


@pytest.fixture
def sample_email_delivery(db_session):
    """Create sample email delivery for testing"""
    delivery = EmailDelivery(
        to_email="test@example.com",
        to_name="Test User",
        from_email="noreply@leadfactory.com",
        from_name="LeadFactory",
        subject="Test Email",
        html_content="<p>Test HTML content</p>",
        text_content="Test text content",
        business_id="biz_123",
        campaign_id="camp_456",
        categories=["test", "email"],
        custom_args={"test_flag": True},
    )
    db_session.add(delivery)
    db_session.commit()
    return delivery


class TestEmailDelivery:
    """Test EmailDelivery model functionality"""

    def test_email_delivery_creation(self, db_session):
        """Test basic email delivery model creation - Email send tracking"""

        # Create email delivery
        delivery = EmailDelivery(
            to_email="recipient@example.com",
            to_name="John Doe",
            from_email="sender@leadfactory.com",
            from_name="LeadFactory Team",
            subject="Welcome to LeadFactory",
            html_content="<p>Welcome email content</p>",
            text_content="Welcome email content",
            business_id="business_123",
            campaign_id="campaign_456",
        )

        # Test required fields
        assert delivery.to_email == "recipient@example.com"
        assert delivery.to_name == "John Doe"
        assert delivery.from_email == "sender@leadfactory.com"
        assert delivery.subject == "Welcome to LeadFactory"
        assert delivery.status == DeliveryStatus.PENDING.value

        # Test default values
        assert delivery.retry_count == 0
        assert delivery.max_retries == 3
        assert delivery.estimated_cost == 0.0

        # Test unique delivery_id generation
        assert delivery.delivery_id is not None
        assert len(delivery.delivery_id) > 0

        # Save to database
        db_session.add(delivery)
        db_session.commit()

        # Verify creation timestamp
        assert delivery.created_at is not None
        # Note: SQLite doesn't preserve timezone info, but PostgreSQL will

        # Test retrieval
        retrieved = (
            db_session.query(EmailDelivery)
            .filter_by(to_email="recipient@example.com")
            .first()
        )
        assert retrieved is not None
        assert retrieved.delivery_id == delivery.delivery_id

        print("✓ Email delivery creation works")

    def test_email_delivery_status_tracking(self, db_session):
        """Test email delivery status tracking functionality"""

        # Create delivery
        delivery = EmailDelivery(
            to_email="status@example.com",
            from_email="test@leadfactory.com",
            subject="Status Test",
            html_content="<p>Test</p>",
        )
        db_session.add(delivery)
        db_session.commit()

        # Test status progression
        assert delivery.status == DeliveryStatus.PENDING.value

        # Update to processing
        delivery.status = DeliveryStatus.PROCESSING.value
        db_session.commit()

        # Update to delivered with timestamp
        delivery.status = DeliveryStatus.DELIVERED.value
        delivery.sent_at = datetime.now(timezone.utc)
        delivery.delivered_at = datetime.now(timezone.utc)
        db_session.commit()

        # Verify timestamps are set
        assert delivery.sent_at is not None
        assert delivery.delivered_at is not None
        assert delivery.status == DeliveryStatus.DELIVERED.value

        print("✓ Email delivery status tracking works")

    def test_email_delivery_sendgrid_integration(self, db_session):
        """Test SendGrid integration fields"""

        delivery = EmailDelivery(
            to_email="sendgrid@example.com",
            from_email="test@leadfactory.com",
            subject="SendGrid Test",
            sendgrid_message_id="msg_12345",
            sendgrid_batch_id="batch_67890",
            categories=["marketing", "leadfactory"],
            custom_args={
                "business_id": "biz_123",
                "campaign_type": "cold_outreach",
                "user_id": "user_456",
            },
        )
        db_session.add(delivery)
        db_session.commit()

        # Test SendGrid fields
        assert delivery.sendgrid_message_id == "msg_12345"
        assert delivery.sendgrid_batch_id == "batch_67890"
        assert "marketing" in delivery.categories
        assert "leadfactory" in delivery.categories
        assert delivery.custom_args["business_id"] == "biz_123"

        # Test unique delivery_id
        delivery2 = EmailDelivery(
            to_email="sendgrid2@example.com",
            from_email="test@leadfactory.com",
            subject="SendGrid Test 2",
        )
        db_session.add(delivery2)
        db_session.commit()

        assert delivery.delivery_id != delivery2.delivery_id

        print("✓ SendGrid integration fields work")

    def test_email_delivery_to_dict(self, sample_email_delivery):
        """Test email delivery dictionary conversion"""

        delivery_dict = sample_email_delivery.to_dict()

        # Test required fields in dict
        assert "id" in delivery_dict
        assert "delivery_id" in delivery_dict
        assert "to_email" in delivery_dict
        assert "from_email" in delivery_dict
        assert "subject" in delivery_dict
        assert "status" in delivery_dict
        assert "created_at" in delivery_dict

        # Test values
        assert delivery_dict["to_email"] == "test@example.com"
        assert delivery_dict["business_id"] == "biz_123"
        assert delivery_dict["campaign_id"] == "camp_456"

        print("✓ Email delivery to_dict conversion works")


class TestBounceTracking:
    """Test BounceTracking model functionality"""

    def test_bounce_tracking_creation(self, sample_email_delivery, db_session):
        """Test bounce tracking model creation - Bounce tracking model"""

        # Create bounce tracking
        bounce = BounceTracking(
            email_delivery_id=sample_email_delivery.id,
            bounce_type=BounceType.HARD.value,
            bounce_reason="550 5.1.1 User unknown",
            bounce_classification="Invalid",
            email="test@example.com",
            sendgrid_event_id="event_12345",
            sendgrid_bounce_data={
                "event": "bounce",
                "sg_event_id": "event_12345",
                "sg_message_id": "msg_12345",
                "reason": "550 5.1.1 User unknown",
                "status": "5.1.1",
            },
        )

        # Test required fields
        assert bounce.email_delivery_id == sample_email_delivery.id
        assert bounce.bounce_type == BounceType.HARD.value
        assert bounce.bounce_reason == "550 5.1.1 User unknown"
        assert bounce.email == "test@example.com"

        # Save to database
        db_session.add(bounce)
        db_session.commit()

        # Test timestamps
        assert bounce.bounced_at is not None
        assert bounce.created_at is not None

        # Test relationship
        assert bounce.email_delivery == sample_email_delivery
        assert sample_email_delivery.bounce_tracking == bounce

        print("✓ Bounce tracking creation works")

    def test_bounce_types_and_classifications(self, sample_email_delivery, db_session):
        """Test different bounce types and classifications"""

        bounce_scenarios = [
            {
                "type": BounceType.SOFT.value,
                "reason": "Mailbox temporarily full",
                "classification": "MailboxFull",
            },
            {
                "type": BounceType.HARD.value,
                "reason": "No such user",
                "classification": "Invalid",
            },
            {
                "type": BounceType.SPAM.value,
                "reason": "Message rejected as spam",
                "classification": "SpamContent",
            },
            {
                "type": BounceType.BLOCK.value,
                "reason": "IP address blocked",
                "classification": "Reputation",
            },
        ]

        for i, scenario in enumerate(bounce_scenarios):
            # Create new delivery for each bounce
            delivery = EmailDelivery(
                to_email=f"bounce{i}@example.com",
                from_email="test@leadfactory.com",
                subject=f"Bounce Test {i}",
            )
            db_session.add(delivery)
            db_session.flush()  # Get ID without committing

            bounce = BounceTracking(
                email_delivery_id=delivery.id,
                bounce_type=scenario["type"],
                bounce_reason=scenario["reason"],
                bounce_classification=scenario["classification"],
                email=delivery.to_email,
            )
            db_session.add(bounce)

        db_session.commit()

        # Verify all bounces created
        bounces = db_session.query(BounceTracking).all()
        assert len(bounces) >= 4

        # Test bounce types exist
        bounce_types = [b.bounce_type for b in bounces]
        assert BounceType.SOFT.value in bounce_types
        assert BounceType.HARD.value in bounce_types
        assert BounceType.SPAM.value in bounce_types
        assert BounceType.BLOCK.value in bounce_types

        print("✓ Bounce types and classifications work")


class TestSuppressionList:
    """Test SuppressionList model functionality"""

    def test_suppression_list_creation(self, db_session):
        """Test suppression list model creation - Suppression list"""

        # Create suppression entry
        suppression = SuppressionList(
            email="suppressed@example.com",
            reason=SuppressionReason.UNSUBSCRIBE.value,
            source="user_request",
            suppression_data={
                "unsubscribe_source": "email_link",
                "campaign_id": "camp_123",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            created_by="system",
        )

        # Test required fields
        assert suppression.email == "suppressed@example.com"
        assert suppression.reason == SuppressionReason.UNSUBSCRIBE.value
        assert suppression.is_active is True

        # Save to database
        db_session.add(suppression)
        db_session.commit()

        # Test timestamps
        assert suppression.suppressed_at is not None
        assert suppression.created_at is not None

        # Test suppression data
        assert suppression.suppression_data["unsubscribe_source"] == "email_link"

        # Test uniqueness constraint
        duplicate = SuppressionList(
            email="suppressed@example.com", reason=SuppressionReason.BOUNCE.value
        )
        db_session.add(duplicate)

        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()

        print("✓ Suppression list creation works")

    def test_suppression_reasons(self, db_session):
        """Test different suppression reasons"""

        suppression_scenarios = [
            SuppressionReason.UNSUBSCRIBE.value,
            SuppressionReason.BOUNCE.value,
            SuppressionReason.SPAM_REPORT.value,
            SuppressionReason.INVALID_EMAIL.value,
            SuppressionReason.GLOBAL_SUPPRESSION.value,
        ]

        for i, reason in enumerate(suppression_scenarios):
            suppression = SuppressionList(
                email=f"suppress{i}@example.com",
                reason=reason,
                source="automated_system",
            )
            db_session.add(suppression)

        db_session.commit()

        # Verify all suppressions created
        suppressions = db_session.query(SuppressionList).all()
        assert len(suppressions) >= 5

        # Test all reasons exist
        reasons = [s.reason for s in suppressions]
        for scenario_reason in suppression_scenarios:
            assert scenario_reason in reasons

        print("✓ Suppression reasons work")

    def test_is_suppressed_method(self, db_session):
        """Test the is_suppressed method"""

        # Active suppression
        active_suppression = SuppressionList(
            email="active@example.com",
            reason=SuppressionReason.UNSUBSCRIBE.value,
            is_active=True,
        )
        db_session.add(active_suppression)

        # Inactive suppression
        inactive_suppression = SuppressionList(
            email="inactive@example.com",
            reason=SuppressionReason.UNSUBSCRIBE.value,
            is_active=False,
        )
        db_session.add(inactive_suppression)

        # Expired suppression
        expired_suppression = SuppressionList(
            email="expired@example.com",
            reason=SuppressionReason.BOUNCE.value,
            is_active=True,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db_session.add(expired_suppression)

        # Future expiry suppression
        future_suppression = SuppressionList(
            email="future@example.com",
            reason=SuppressionReason.BOUNCE.value,
            is_active=True,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(future_suppression)

        db_session.commit()

        # Test suppression status
        assert active_suppression.is_suppressed() is True
        assert inactive_suppression.is_suppressed() is False
        assert expired_suppression.is_suppressed() is False
        assert future_suppression.is_suppressed() is True

        print("✓ is_suppressed method works")


class TestDeliveryEvent:
    """Test DeliveryEvent model functionality"""

    def test_delivery_event_creation(self, sample_email_delivery, db_session):
        """Test delivery event model creation - Event timestamps"""

        # Create delivery event
        event = DeliveryEvent(
            email_delivery_id=sample_email_delivery.id,
            event_type=EventType.DELIVERED.value,
            event_data={
                "event": "delivered",
                "sg_event_id": "event_12345",
                "sg_message_id": "msg_12345",
                "timestamp": 1234567890,
            },
            sendgrid_event_id="event_12345",
            sendgrid_message_id="msg_12345",
            event_timestamp=datetime.now(timezone.utc),
            user_agent="Mozilla/5.0 (compatible; test)",
            ip_address="192.168.1.1",
        )

        # Test required fields
        assert event.email_delivery_id == sample_email_delivery.id
        assert event.event_type == EventType.DELIVERED.value
        assert event.sendgrid_event_id == "event_12345"

        # Save to database
        db_session.add(event)
        db_session.commit()

        # Test timestamps
        assert event.event_timestamp is not None
        assert event.processed_at is not None
        assert event.is_processed is True

        # Test relationship
        assert event.email_delivery == sample_email_delivery
        assert event in sample_email_delivery.delivery_events

        print("✓ Delivery event creation works")

    def test_event_types(self, sample_email_delivery, db_session):
        """Test different event types"""

        event_scenarios = [
            {
                "type": EventType.SENT.value,
                "data": {"event": "sent", "timestamp": 1234567890},
            },
            {
                "type": EventType.DELIVERED.value,
                "data": {"event": "delivered", "timestamp": 1234567891},
            },
            {
                "type": EventType.OPENED.value,
                "data": {"event": "open", "timestamp": 1234567892},
            },
            {
                "type": EventType.CLICKED.value,
                "data": {
                    "event": "click",
                    "url": "https://example.com",
                    "timestamp": 1234567893,
                },
                "url": "https://example.com",
            },
            {
                "type": EventType.BOUNCED.value,
                "data": {
                    "event": "bounce",
                    "reason": "User unknown",
                    "timestamp": 1234567894,
                },
            },
        ]

        for i, scenario in enumerate(event_scenarios):
            event = DeliveryEvent(
                email_delivery_id=sample_email_delivery.id,
                event_type=scenario["type"],
                event_data=scenario["data"],
                event_timestamp=datetime.now(timezone.utc) + timedelta(seconds=i),
                url=scenario.get("url"),
            )
            db_session.add(event)

        db_session.commit()

        # Verify all events created
        events = db_session.query(DeliveryEvent).all()
        assert len(events) >= 5

        # Test event types exist
        event_types = [e.event_type for e in events]
        assert EventType.SENT.value in event_types
        assert EventType.DELIVERED.value in event_types
        assert EventType.OPENED.value in event_types
        assert EventType.CLICKED.value in event_types
        assert EventType.BOUNCED.value in event_types

        # Test URL tracking for click events
        click_events = [e for e in events if e.event_type == EventType.CLICKED.value]
        assert len(click_events) > 0
        assert click_events[0].url == "https://example.com"

        print("✓ Event types work")

    def test_event_uniqueness_constraint(self, sample_email_delivery, db_session):
        """Test unique constraint on delivery events"""

        event_time = datetime.now(timezone.utc)

        # Create first event
        event1 = DeliveryEvent(
            email_delivery_id=sample_email_delivery.id,
            event_type=EventType.OPENED.value,
            event_timestamp=event_time,
            event_data={"event": "open"},
        )
        db_session.add(event1)
        db_session.commit()

        # Try to create duplicate event (same delivery, type, timestamp)
        event2 = DeliveryEvent(
            email_delivery_id=sample_email_delivery.id,
            event_type=EventType.OPENED.value,
            event_timestamp=event_time,
            event_data={"event": "open", "duplicate": True},
        )
        db_session.add(event2)

        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()

        print("✓ Event uniqueness constraint works")


class TestModelIntegration:
    """Test integration between delivery models"""

    def test_complete_delivery_lifecycle(self, db_session):
        """Test complete email delivery lifecycle with all models"""

        # 1. Create email delivery
        delivery = EmailDelivery(
            to_email="lifecycle@example.com",
            from_email="test@leadfactory.com",
            subject="Lifecycle Test",
            html_content="<p>Test content</p>",
            business_id="biz_lifecycle",
            categories=["test", "lifecycle"],
        )
        db_session.add(delivery)
        db_session.flush()

        # 2. Add sent event
        sent_event = DeliveryEvent(
            email_delivery_id=delivery.id,
            event_type=EventType.SENT.value,
            event_timestamp=datetime.now(timezone.utc),
            event_data={"event": "sent"},
        )
        db_session.add(sent_event)

        # 3. Add delivered event
        delivered_event = DeliveryEvent(
            email_delivery_id=delivery.id,
            event_type=EventType.DELIVERED.value,
            event_timestamp=datetime.now(timezone.utc) + timedelta(seconds=30),
            event_data={"event": "delivered"},
        )
        db_session.add(delivered_event)

        # 4. Update delivery status
        delivery.status = DeliveryStatus.DELIVERED.value
        delivery.delivered_at = datetime.now(timezone.utc)

        # 5. Add open event
        open_event = DeliveryEvent(
            email_delivery_id=delivery.id,
            event_type=EventType.OPENED.value,
            event_timestamp=datetime.now(timezone.utc) + timedelta(minutes=5),
            event_data={"event": "open"},
        )
        db_session.add(open_event)

        db_session.commit()

        # Verify complete lifecycle
        retrieved_delivery = (
            db_session.query(EmailDelivery)
            .filter_by(to_email="lifecycle@example.com")
            .first()
        )

        assert retrieved_delivery is not None
        assert retrieved_delivery.status == DeliveryStatus.DELIVERED.value
        assert len(retrieved_delivery.delivery_events) == 3

        # Check event types
        event_types = [e.event_type for e in retrieved_delivery.delivery_events]
        assert EventType.SENT.value in event_types
        assert EventType.DELIVERED.value in event_types
        assert EventType.OPENED.value in event_types

        print("✓ Complete delivery lifecycle works")

    def test_bounce_and_suppression_workflow(self, db_session):
        """Test bounce leading to suppression workflow"""

        # 1. Create email delivery
        delivery = EmailDelivery(
            to_email="bounce@example.com",
            from_email="test@leadfactory.com",
            subject="Bounce Test",
        )
        db_session.add(delivery)
        db_session.flush()

        # 2. Create bounce tracking
        bounce = BounceTracking(
            email_delivery_id=delivery.id,
            bounce_type=BounceType.HARD.value,
            bounce_reason="User unknown",
            email="bounce@example.com",
            sendgrid_event_id="bounce_123",
        )
        db_session.add(bounce)

        # 3. Create bounce event
        bounce_event = DeliveryEvent(
            email_delivery_id=delivery.id,
            event_type=EventType.BOUNCED.value,
            event_timestamp=datetime.now(timezone.utc),
            event_data={"event": "bounce", "reason": "User unknown", "type": "hard"},
        )
        db_session.add(bounce_event)

        # 4. Add to suppression list
        suppression = SuppressionList(
            email="bounce@example.com",
            reason=SuppressionReason.BOUNCE.value,
            source="hard_bounce",
            suppression_data={
                "bounce_event_id": "bounce_123",
                "delivery_id": delivery.delivery_id,
            },
        )
        db_session.add(suppression)

        # 5. Update delivery status
        delivery.status = DeliveryStatus.BOUNCED.value

        db_session.commit()

        # Verify workflow
        retrieved_delivery = (
            db_session.query(EmailDelivery)
            .filter_by(to_email="bounce@example.com")
            .first()
        )

        assert retrieved_delivery.status == DeliveryStatus.BOUNCED.value
        assert retrieved_delivery.bounce_tracking is not None
        assert retrieved_delivery.bounce_tracking.bounce_type == BounceType.HARD.value

        # Check suppression exists
        suppressed = (
            db_session.query(SuppressionList)
            .filter_by(email="bounce@example.com")
            .first()
        )

        assert suppressed is not None
        assert suppressed.is_suppressed() is True
        assert suppressed.reason == SuppressionReason.BOUNCE.value

        print("✓ Bounce and suppression workflow works")


def test_model_integration():
    """Test all email delivery models work together"""

    # Test database setup
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Create sample data across all models
        delivery = EmailDelivery(
            to_email="integration@example.com",
            from_email="test@leadfactory.com",
            subject="Integration Test",
            categories=["integration", "test"],
        )
        session.add(delivery)
        session.flush()

        # Add events
        events = [
            DeliveryEvent(
                email_delivery_id=delivery.id,
                event_type=EventType.SENT.value,
                event_timestamp=datetime.now(timezone.utc),
            ),
            DeliveryEvent(
                email_delivery_id=delivery.id,
                event_type=EventType.DELIVERED.value,
                event_timestamp=datetime.now(timezone.utc) + timedelta(seconds=30),
            ),
        ]

        for event in events:
            session.add(event)

        session.commit()

        # Verify relationships work
        assert len(delivery.delivery_events) == 2
        assert delivery.delivery_events[0].email_delivery == delivery

        print("✓ Model integration test passed")
        return True

    finally:
        session.close()


if __name__ == "__main__":
    test_model_integration()
    print("All email delivery model tests completed!")
