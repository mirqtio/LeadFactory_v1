"""
Unit tests for D8 Personalization Models - Task 060

Tests for email content model, subject line variants, personalization tokens,
and spam score tracking functionality.

Acceptance Criteria:
- Email content model ✓
- Subject line variants ✓
- Personalization tokens ✓
- Spam score tracking ✓
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d8_personalization.models import (
    ContentStrategy,
    ContentVariant,
    EmailContent,
    EmailContentType,
    EmailGenerationLog,
    EmailTemplate,
    PersonalizationStrategy,
    PersonalizationToken,
    PersonalizationVariable,
    SpamCategory,
    SpamScoreTracking,
    SubjectLineVariant,
    VariantStatus,
    calculate_personalization_score,
    determine_risk_level,
    generate_content_hash,
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
def sample_email_template(db_session):
    """Create sample email template"""
    template = EmailTemplate(
        name="Cold Outreach Template v1",
        description="Initial contact template for website audit offers",
        content_type=EmailContentType.COLD_OUTREACH,
        strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
        subject_template="Improve {business_name}'s website performance in {location}",
        body_template="Hi {contact_name}, I noticed some opportunities to improve {business_name}'s website...",
        text_template="Hi {contact_name}, I noticed opportunities for {business_name}...",
        required_tokens=["business_name", "contact_name"],
        optional_tokens=["location", "industry"],
        variable_config={"max_subject_length": 200},
        usage_count=150,
        success_rate=0.23,
        avg_spam_score=25.5,
        is_active=True,
        created_by="system",
    )
    db_session.add(template)
    db_session.commit()
    return template


@pytest.fixture
def sample_personalization_token(db_session):
    """Create sample personalization token"""
    token = PersonalizationToken(
        token_name="business_name",
        token_type="business_info",
        description="Name of the business from sourced data",
        data_source="business_data",
        field_path="$.name",
        default_value="your business",
        transformation_rules={"case": "title", "max_length": 100},
        usage_count=500,
        success_rate=0.95,
        max_length=100,
        min_length=2,
        is_active=True,
    )
    db_session.add(token)
    db_session.commit()
    return token


class TestEmailTemplate:
    """Test EmailTemplate model - Acceptance Criteria"""

    def test_create_email_template(self, db_session):
        """Test creating an email template"""
        template = EmailTemplate(
            name="Test Template",
            content_type=EmailContentType.AUDIT_OFFER,
            strategy=PersonalizationStrategy.INDUSTRY_VERTICAL,
            subject_template="Test subject for {business_name}",
            body_template="Test body content with {business_name} personalization",
            required_tokens=["business_name"],
            optional_tokens=["industry"],
            is_active=True,
        )

        db_session.add(template)
        db_session.commit()

        assert template.id is not None
        assert template.name == "Test Template"
        assert template.content_type == EmailContentType.AUDIT_OFFER
        assert template.strategy == PersonalizationStrategy.INDUSTRY_VERTICAL
        assert template.usage_count == 0
        assert template.is_active is True
        assert template.created_at is not None

    def test_template_relationships(self, sample_email_template, db_session):
        """Test template relationships work correctly"""
        # Add subject line variant
        variant = SubjectLineVariant(
            template_id=sample_email_template.id,
            variant_name="Variant A",
            subject_text="Test subject line",
            status=VariantStatus.ACTIVE,
        )
        db_session.add(variant)
        db_session.commit()

        # Test relationship
        db_session.refresh(sample_email_template)
        assert len(sample_email_template.subject_variants) == 1
        assert sample_email_template.subject_variants[0].variant_name == "Variant A"


class TestSubjectLineVariant:
    """Test SubjectLineVariant model - Acceptance Criteria"""

    def test_create_subject_variant(self, sample_email_template, db_session):
        """Test creating subject line variants"""
        variant = SubjectLineVariant(
            template_id=sample_email_template.id,
            variant_name="High Converting Subject",
            subject_text="Boost your website performance in 24 hours",
            personalization_tokens=["business_name", "location"],
            status=VariantStatus.ACTIVE,
            weight=1.5,
            target_audience="restaurants",
            sent_count=100,
            open_count=25,
            click_count=8,
            conversion_count=3,
        )

        db_session.add(variant)
        db_session.commit()

        assert variant.id is not None
        assert variant.variant_name == "High Converting Subject"
        assert variant.status == VariantStatus.ACTIVE
        assert variant.weight == 1.5
        assert variant.sent_count == 100
        assert variant.open_count == 25

    def test_performance_calculations(self, sample_email_template, db_session):
        """Test performance metric calculations"""
        variant = SubjectLineVariant(
            template_id=sample_email_template.id,
            variant_name="Performance Test",
            subject_text="Test subject",
            sent_count=1000,
            open_count=250,
            click_count=50,
            conversion_count=10,
            spam_reports=5,
        )

        # Calculate rates
        variant.open_rate = (
            variant.open_count / variant.sent_count if variant.sent_count > 0 else 0
        )
        variant.click_rate = (
            variant.click_count / variant.open_count if variant.open_count > 0 else 0
        )
        variant.conversion_rate = (
            variant.conversion_count / variant.sent_count
            if variant.sent_count > 0
            else 0
        )
        variant.spam_rate = (
            variant.spam_reports / variant.sent_count if variant.sent_count > 0 else 0
        )

        db_session.add(variant)
        db_session.commit()

        assert variant.open_rate == 0.25  # 25%
        assert variant.click_rate == 0.20  # 20% of opens
        assert variant.conversion_rate == 0.01  # 1%
        assert variant.spam_rate == 0.005  # 0.5%


class TestPersonalizationToken:
    """Test PersonalizationToken model - Acceptance Criteria"""

    def test_create_personalization_token(self, db_session):
        """Test creating personalization tokens"""
        token = PersonalizationToken(
            token_name="contact_name",
            token_type="contact_info",
            description="Primary contact name for the business",
            data_source="business_profile",
            field_path="$.contact.name",
            default_value="there",
            transformation_rules={"case": "proper", "fallback": "friend"},
            max_length=50,
            min_length=1,
            required_format=r"^[A-Za-z\s]+$",
            is_active=True,
        )

        db_session.add(token)
        db_session.commit()

        assert token.id is not None
        assert token.token_name == "contact_name"
        assert token.token_type == "contact_info"
        assert token.data_source == "business_profile"
        assert token.default_value == "there"
        assert token.max_length == 50
        assert token.is_active is True

    def test_token_uniqueness(self, db_session):
        """Test token name uniqueness constraint"""
        token1 = PersonalizationToken(
            token_name="unique_token",
            token_type="test",
            data_source="test",
            field_path="$.test",
        )
        db_session.add(token1)
        db_session.commit()

        # Try to create duplicate
        token2 = PersonalizationToken(
            token_name="unique_token",
            token_type="test2",
            data_source="test2",
            field_path="$.test2",
        )
        db_session.add(token2)

        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()


class TestPersonalizationVariable:
    """Test PersonalizationVariable model"""

    def test_create_personalization_variable(
        self, sample_personalization_token, db_session
    ):
        """Test creating personalization variables"""
        variable = PersonalizationVariable(
            token_id=sample_personalization_token.id,
            business_id="biz_123",
            campaign_id="campaign_456",
            context_hash="abcd1234",
            generated_value="Acme Restaurant",
            backup_value="your restaurant",
            confidence_score=0.92,
            source_data={"yelp_name": "Acme Restaurant", "verified": True},
            generation_method="direct_mapping",
            character_count=15,
            word_count=2,
            sentiment_score=0.7,
            readability_score=0.8,
            times_used=5,
            last_used_at=datetime.utcnow(),
        )

        db_session.add(variable)
        db_session.commit()

        assert variable.id is not None
        assert variable.business_id == "biz_123"
        assert variable.generated_value == "Acme Restaurant"
        assert variable.confidence_score == 0.92
        assert variable.character_count == 15
        assert variable.word_count == 2


class TestEmailContent:
    """Test EmailContent model - Acceptance Criteria"""

    def test_create_email_content(self, sample_email_template, db_session):
        """Test creating email content"""
        content = EmailContent(
            template_id=sample_email_template.id,
            business_id="biz_789",
            campaign_id="campaign_101",
            generation_id="gen_202",
            subject_line="Improve Acme Restaurant's website performance in Seattle",
            html_content="<html><body>Hi John, I noticed some opportunities...</body></html>",
            text_content="Hi John, I noticed some opportunities...",
            preview_text="Website improvement opportunities for Acme Restaurant",
            personalization_data={
                "business_name": "Acme Restaurant",
                "contact_name": "John",
                "location": "Seattle",
            },
            personalization_strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
            content_strategy=ContentStrategy.PROBLEM_AGITATION,
            content_length=500,
            word_count=75,
            readability_score=0.8,
            sentiment_score=0.6,
            call_to_action_count=2,
            times_sent=10,
            delivery_rate=0.98,
            open_rate=0.25,
            click_rate=0.08,
            conversion_rate=0.02,
            is_approved=True,
            approved_by="manager@example.com",
        )

        db_session.add(content)
        db_session.commit()

        assert content.id is not None
        assert content.business_id == "biz_789"
        assert (
            content.subject_line
            == "Improve Acme Restaurant's website performance in Seattle"
        )
        assert (
            content.personalization_strategy
            == PersonalizationStrategy.BUSINESS_SPECIFIC
        )
        assert content.is_approved is True
        assert content.open_rate == 0.25


class TestSpamScoreTracking:
    """Test SpamScoreTracking model - Acceptance Criteria"""

    def test_create_spam_score_tracking(self, sample_email_template, db_session):
        """Test creating spam score tracking"""
        # First create email content
        content = EmailContent(
            template_id=sample_email_template.id,
            business_id="biz_spam_test",
            subject_line="Test spam analysis",
            html_content="<html><body>Test content</body></html>",
            personalization_strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
            content_strategy=ContentStrategy.DIRECT_OFFER,
        )
        db_session.add(content)
        db_session.commit()

        # Create spam score tracking
        spam_score = SpamScoreTracking(
            email_content_id=content.id,
            overall_score=35.7,
            category_scores={
                "subject_line": 25.0,
                "content_body": 40.0,
                "call_to_action": 30.0,
                "formatting": 45.0,
            },
            spam_indicators=["excessive_exclamation_marks", "urgent_language_detected"],
            subject_line_score=25.0,
            content_body_score=40.0,
            call_to_action_score=30.0,
            formatting_score=45.0,
            personalization_score=20.0,
            flagged_words=["urgent", "limited time", "act now"],
            excessive_caps=False,
            too_many_exclamations=True,
            suspicious_links=0,
            image_text_ratio=0.3,
            analyzer_version="v2.1.0",
            analysis_method="rule_based_with_ml",
            confidence_score=0.87,
            improvement_suggestions=[
                "Reduce exclamation marks",
                "Use less urgent language",
                "Improve text-to-image ratio",
            ],
            risk_level="medium",
        )

        db_session.add(spam_score)
        db_session.commit()

        assert spam_score.id is not None
        assert spam_score.overall_score == 35.7
        assert spam_score.risk_level == "medium"
        assert spam_score.too_many_exclamations is True
        assert spam_score.suspicious_links == 0
        assert len(spam_score.flagged_words) == 3
        assert len(spam_score.improvement_suggestions) == 3

    def test_spam_score_constraints(self, sample_email_template, db_session):
        """Test spam score validation constraints"""
        content = EmailContent(
            template_id=sample_email_template.id,
            business_id="biz_constraint_test",
            subject_line="Test constraints",
            html_content="<html><body>Test</body></html>",
            personalization_strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
            content_strategy=ContentStrategy.DIRECT_OFFER,
        )
        db_session.add(content)
        db_session.commit()

        # Test valid score
        valid_spam_score = SpamScoreTracking(
            email_content_id=content.id,
            overall_score=75.5,
            analyzer_version="v1.0",
            analysis_method="test",
        )
        db_session.add(valid_spam_score)
        db_session.commit()

        assert valid_spam_score.overall_score == 75.5


class TestContentVariant:
    """Test ContentVariant model"""

    def test_create_content_variant(self, sample_email_template, db_session):
        """Test creating content variants"""
        variant = ContentVariant(
            template_id=sample_email_template.id,
            variant_name="Problem-Solution Variant",
            content_strategy=ContentStrategy.PROBLEM_AGITATION,
            status=VariantStatus.ACTIVE,
            opening_hook="Are you losing customers because of your slow website?",
            main_content="Website speed directly impacts your bottom line...",
            call_to_action="Get your free website audit today",
            closing_content="Best regards, The Website Team",
            weight=1.2,
            target_segment="restaurants",
            min_sample_size=50,
            sent_count=200,
            engagement_score=0.75,
            conversion_rate=0.03,
        )

        db_session.add(variant)
        db_session.commit()

        assert variant.id is not None
        assert variant.variant_name == "Problem-Solution Variant"
        assert variant.content_strategy == ContentStrategy.PROBLEM_AGITATION
        assert variant.status == VariantStatus.ACTIVE
        assert variant.conversion_rate == 0.03


class TestEmailGenerationLog:
    """Test EmailGenerationLog model"""

    def test_create_generation_log(self, sample_email_template, db_session):
        """Test creating email generation log"""
        log = EmailGenerationLog(
            template_id=sample_email_template.id,
            business_id="biz_log_test",
            campaign_id="campaign_log_test",
            generation_request_id="req_123456789",
            input_data={
                "business_name": "Test Business",
                "contact_name": "Jane Doe",
                "industry": "restaurant",
            },
            personalization_strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
            content_strategy=ContentStrategy.EDUCATIONAL_VALUE,
            tokens_requested=["business_name", "contact_name", "industry"],
            tokens_resolved=["business_name", "contact_name"],
            tokens_failed=["industry"],
            llm_model_used="gpt-4o-mini",
            llm_tokens_consumed=150,
            llm_cost_usd=Decimal("0.0025"),
            llm_response_time_ms=850,
            generation_successful=True,
            personalization_completeness=0.67,
            content_quality_score=0.82,
            generation_time_ms=1200,
            generated_by="api_user_123",
        )

        db_session.add(log)
        db_session.commit()

        assert log.id is not None
        assert log.generation_request_id == "req_123456789"
        assert log.generation_successful is True
        assert log.llm_model_used == "gpt-4o-mini"
        assert log.llm_cost_usd == Decimal("0.0025")
        assert log.personalization_completeness == 0.67


class TestUtilityFunctions:
    """Test utility functions"""

    def test_calculate_personalization_score(self):
        """Test personalization score calculation"""
        assert calculate_personalization_score(5, 5) == 1.0
        assert calculate_personalization_score(3, 5) == 0.6
        assert calculate_personalization_score(0, 5) == 0.0
        assert calculate_personalization_score(0, 0) == 1.0

    def test_determine_risk_level(self):
        """Test risk level determination"""
        assert determine_risk_level(15.0) == "low"
        assert determine_risk_level(35.0) == "medium"
        assert determine_risk_level(65.0) == "high"
        assert determine_risk_level(85.0) == "critical"

    def test_generate_content_hash(self):
        """Test content hash generation"""
        hash1 = generate_content_hash("Subject 1", "Body content 1")
        hash2 = generate_content_hash("Subject 1", "Body content 1")
        hash3 = generate_content_hash("Subject 2", "Body content 1")

        assert hash1 == hash2  # Same content should generate same hash
        assert hash1 != hash3  # Different content should generate different hash
        assert len(hash1) == 16  # Should be 16 characters long


class TestEnumValues:
    """Test enum values and constraints"""

    def test_email_content_type_enum(self):
        """Test EmailContentType enum values"""
        assert EmailContentType.COLD_OUTREACH == "cold_outreach"
        assert EmailContentType.AUDIT_OFFER == "audit_offer"
        assert EmailContentType.FOLLOW_UP == "follow_up"

    def test_personalization_strategy_enum(self):
        """Test PersonalizationStrategy enum values"""
        assert PersonalizationStrategy.BUSINESS_SPECIFIC == "business_specific"
        assert PersonalizationStrategy.INDUSTRY_VERTICAL == "industry_vertical"
        assert PersonalizationStrategy.GEOGRAPHIC == "geographic"

    def test_variant_status_enum(self):
        """Test VariantStatus enum values"""
        assert VariantStatus.DRAFT == "draft"
        assert VariantStatus.ACTIVE == "active"
        assert VariantStatus.WINNING == "winning"
        assert VariantStatus.LOSING == "losing"


class TestModelIntegration:
    """Test integration between different models"""

    def test_complete_personalization_workflow(self, db_session):
        """Test complete workflow from template to generated content"""
        # 1. Create template
        template = EmailTemplate(
            name="Integration Test Template",
            content_type=EmailContentType.COLD_OUTREACH,
            strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
            subject_template="Hi {business_name}",
            body_template="Your business {business_name} could benefit...",
            required_tokens=["business_name"],
            is_active=True,
        )
        db_session.add(template)
        db_session.commit()

        # 2. Create personalization token
        token = PersonalizationToken(
            token_name="business_name",
            token_type="business_info",
            data_source="yelp",
            field_path="$.name",
            default_value="your business",
            is_active=True,
        )
        db_session.add(token)
        db_session.commit()

        # 3. Create personalization variable
        variable = PersonalizationVariable(
            token_id=token.id,
            business_id="biz_integration",
            generated_value="Integration Test Cafe",
            confidence_score=0.95,
        )
        db_session.add(variable)
        db_session.commit()

        # 4. Create email content
        content = EmailContent(
            template_id=template.id,
            business_id="biz_integration",
            subject_line="Hi Integration Test Cafe",
            html_content="Your business Integration Test Cafe could benefit...",
            personalization_data={"business_name": "Integration Test Cafe"},
            personalization_strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
            content_strategy=ContentStrategy.DIRECT_OFFER,
            is_approved=True,
        )
        db_session.add(content)
        db_session.commit()

        # 5. Create spam score
        spam_score = SpamScoreTracking(
            email_content_id=content.id,
            overall_score=20.0,
            risk_level="low",
            analyzer_version="v1.0",
            analysis_method="integration_test",
        )
        db_session.add(spam_score)
        db_session.commit()

        # 6. Create generation log
        log = EmailGenerationLog(
            template_id=template.id,
            business_id="biz_integration",
            generation_request_id="integration_test_123",
            tokens_requested=["business_name"],
            tokens_resolved=["business_name"],
            tokens_failed=[],
            generation_successful=True,
            email_content_id=content.id,
            personalization_completeness=1.0,
            generated_by="integration_test",
        )
        db_session.add(log)
        db_session.commit()

        # Verify all relationships work
        db_session.refresh(template)
        db_session.refresh(content)
        db_session.refresh(token)

        assert len(template.generation_logs) == 1
        assert len(content.spam_scores) == 1
        assert len(token.variables) == 1
        assert content.spam_scores[0].overall_score == 20.0
        assert log.email_content_id == content.id
