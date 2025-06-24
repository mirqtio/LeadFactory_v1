"""
Test database models and relationships
"""
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d3_assessment.models import AssessmentResult
from d3_assessment.types import AssessmentType
from d11_orchestration.models import Experiment, ExperimentStatus, ExperimentVariant
from database.base import Base
from database.models import (
    Batch,
    BatchStatus,
    Business,
    Email,
    EmailClick,
    EmailStatus,
    GatewayUsage,
    GeoType,
    Purchase,
    PurchaseStatus,
    ScoringResult,
    Target,
)


@pytest.fixture
def test_session():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


class TestBusinessModel:
    def test_create_business(self, test_session):
        """Test creating a business entity"""
        business = Business(
            yelp_id="test-yelp-123",
            name="Test Restaurant",
            url="https://test.com",
            phone="+1234567890",
            email="test@restaurant.com",
            city="New York",
            state="NY",
            vertical="restaurant",
            rating=Decimal("4.5"),
        )

        test_session.add(business)
        test_session.commit()

        # Query back
        saved = test_session.query(Business).filter_by(yelp_id="test-yelp-123").first()
        assert saved is not None
        assert saved.name == "Test Restaurant"
        assert saved.rating == Decimal("4.5")
        assert saved.id is not None  # UUID generated

    def test_business_relationships(self, test_session):
        """Test business relationships with other models"""
        # Create business
        business = Business(
            yelp_id="test-yelp-456", name="Test Business", vertical="medical"
        )
        test_session.add(business)
        test_session.commit()

        # Add assessment
        assessment = AssessmentResult(
            business_id=business.id,
            assessment_type=AssessmentType.PAGESPEED,
            url="https://test-business.com",
            domain="test-business.com",
            performance_score=75,
            seo_score=85,
        )
        test_session.add(assessment)

        # Add scoring
        score = ScoringResult(
            business_id=business.id,
            score_pct=82,
            tier="A",
            confidence=Decimal("0.95"),
            scoring_version=1,
            passed_gate=True,
        )
        test_session.add(score)
        test_session.commit()

        # Test relationships
        assert len(business.assessments) == 1
        assert business.assessments[0].performance_score == 75
        assert len(business.scores) == 1
        assert business.scores[0].tier == "A"


class TestTargetingModels:
    def test_create_target(self, test_session):
        """Test creating geo x vertical targets"""
        target = Target(
            geo_type=GeoType.CITY,
            geo_value="New York",
            vertical="restaurant",
            estimated_businesses=5000,
            priority_score=Decimal("0.8"),
        )

        test_session.add(target)
        test_session.commit()

        assert target.id is not None
        assert target.is_active is True

    def test_batch_creation(self, test_session):
        """Test batch creation with target"""
        # Create target
        target = Target(geo_type=GeoType.ZIP, geo_value="10001", vertical="medical")
        test_session.add(target)
        test_session.commit()

        # Create batch
        batch = Batch(
            target_id=target.id,
            batch_date=datetime.now().date(),
            planned_size=100,
            status=BatchStatus.PENDING,
        )
        test_session.add(batch)
        test_session.commit()

        assert batch.target.geo_value == "10001"
        assert len(target.batches) == 1


class TestEmailModels:
    def test_email_lifecycle(self, test_session):
        """Test email status progression"""
        # Create business
        business = Business(yelp_id="test-789", name="Test Biz")
        test_session.add(business)
        test_session.commit()

        # Create email
        email = Email(
            business_id=business.id,
            subject="Your Website Audit",
            preview_text="We found issues...",
            html_body="<html>...</html>",
            status=EmailStatus.PENDING,
        )
        test_session.add(email)
        test_session.commit()

        # Update status
        email.status = EmailStatus.SENT
        email.sent_at = datetime.utcnow()
        test_session.commit()

        # Add click
        click = EmailClick(
            email_id=email.id,
            url="https://leadfactory.com/report/123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0...",
        )
        test_session.add(click)
        test_session.commit()

        assert len(email.clicks) == 1
        assert email.clicks[0].url == "https://leadfactory.com/report/123"


class TestPurchaseModel:
    def test_purchase_flow(self, test_session):
        """Test purchase creation and status"""
        # Create business
        business = Business(yelp_id="test-purchase", name="Purchase Test")
        test_session.add(business)
        test_session.commit()

        # Create purchase
        purchase = Purchase(
            business_id=business.id,
            stripe_session_id="cs_test_123",
            amount_cents=19900,
            customer_email="customer@test.com",
            source="email",
            campaign="launch",
            status=PurchaseStatus.PENDING,
        )
        test_session.add(purchase)
        test_session.commit()

        # Complete purchase
        purchase.status = PurchaseStatus.COMPLETED
        purchase.completed_at = datetime.utcnow()
        purchase.stripe_payment_intent_id = "pi_test_456"
        test_session.commit()

        assert purchase.amount_cents == 19900
        assert purchase.currency == "USD"
        assert purchase.status == PurchaseStatus.COMPLETED


class TestGatewayModels:
    def test_gateway_usage_tracking(self, test_session):
        """Test API usage tracking"""
        usage = GatewayUsage(
            provider="yelp",
            endpoint="business_search",
            cost_usd=Decimal("0.001"),
            cache_hit=False,
            response_time_ms=250,
            status_code=200,
        )

        test_session.add(usage)
        test_session.commit()

        assert usage.id is not None
        assert usage.cost_usd == Decimal("0.001")


class TestExperimentModels:
    def test_experiment_creation(self, test_session):
        """Test A/B experiment setup"""
        experiment = Experiment(
            name="email_subject_test",
            description="Test urgency vs question subject lines",
            created_by="test_user",
            primary_metric="conversion_rate",
        )

        test_session.add(experiment)
        test_session.flush()  # Get the experiment ID

        # Create variants
        control_variant = ExperimentVariant(
            experiment_id=experiment.experiment_id,
            variant_key="control",
            name="control",
            description="Control variant",
            weight=50.0,
            is_control=True,
        )

        urgency_variant = ExperimentVariant(
            experiment_id=experiment.experiment_id,
            variant_key="urgency",
            name="urgency",
            description="Urgency variant",
            weight=25.0,
        )

        question_variant = ExperimentVariant(
            experiment_id=experiment.experiment_id,
            variant_key="question",
            name="question",
            description="Question variant",
            weight=25.0,
        )

        test_session.add_all([control_variant, urgency_variant, question_variant])
        test_session.commit()

        assert experiment.status == ExperimentStatus.DRAFT
        assert len(experiment.variants) == 3
        assert experiment.variants[0].weight == 50.0
