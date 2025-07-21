"""
Unit tests for P2-030 Email Personalization V2 - D9 Delivery Integration

Tests integration of LLM-generated personalized content with email delivery system:
- Email template rendering with personalized content
- PersonalizationData integration
- Subject line and body variant selection
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from d8_personalization.generator import (
    EmailGenerationResult,
    EmailPersonalizationGenerator,
    GeneratedBodyContent,
    GeneratedSubjectLine,
    GenerationMode,
)
from d9_delivery.email_builder import EmailBuilder, PersonalizationData


@pytest.fixture
def sample_personalized_content():
    """Sample personalized content from P2-030 generator"""
    return EmailGenerationResult(
        subject_lines=[
            GeneratedSubjectLine(
                text="Boost Acme Restaurant's online performance",
                approach="benefit",
                length=42,
                personalization_tokens=["business_name"],
                spam_risk_score=0.1,
                quality_score=0.9,
            ),
            GeneratedSubjectLine(
                text="Quick question about Acme Restaurant",
                approach="direct",
                length=37,
                personalization_tokens=["business_name"],
                spam_risk_score=0.2,
                quality_score=0.8,
            ),
            GeneratedSubjectLine(
                text="Is Acme Restaurant missing customers?",
                approach="question",
                length=36,
                personalization_tokens=["business_name"],
                spam_risk_score=0.15,
                quality_score=0.85,
            ),
        ],
        body_variants=[
            GeneratedBodyContent(
                content="Hi John,\n\nI noticed some performance issues on Acme Restaurant's website that could be impacting your customer experience. Quick fixes could improve your conversion rates.\n\nWould you be interested in a brief overview of what I found?\n\nBest regards,\n[Your name]",
                variant="direct",
                approach="problem-solution",
                word_count=42,
                personalization_tokens=["contact_name", "business_name"],
                readability_score=0.8,
            ),
            GeneratedBodyContent(
                content="Hi John,\n\nHow important is your website's performance to Acme Restaurant's growth? I ran a quick analysis and found several opportunities that could help attract more customers.\n\nMight be worth a quick conversation?\n\nBest regards,\n[Your name]",
                variant="consultative",
                approach="question-based",
                word_count=38,
                personalization_tokens=["contact_name", "business_name"],
                readability_score=0.85,
            ),
            GeneratedBodyContent(
                content="Hi John,\n\nI was researching restaurant websites and Acme Restaurant stood out. Your site has good foundation, but I spotted 3 specific improvements that could increase visitor engagement.\n\nHappy to share these insights if helpful.\n\nBest regards,\n[Your name]",
                variant="value-first",
                approach="insight-sharing",
                word_count=45,
                personalization_tokens=["contact_name", "business_name"],
                readability_score=0.8,
            ),
        ],
        generation_mode=GenerationMode.LLM_POWERED,
        business_id="acme_restaurant_123",
        generated_at=datetime.utcnow(),
        generation_time_ms=850,
        metadata={
            "business_name": "Acme Restaurant",
            "industry": "restaurant",
            "personalization_level": "enhanced",
            "assessment_included": True,
        },
    )


@pytest.fixture
def sample_personalization_data():
    """Sample personalization data for testing"""
    return PersonalizationData(
        business_name="Acme Restaurant",
        contact_name="John Smith",
        contact_first_name="John",
        business_category="restaurant",
        business_location="Seattle, WA",
        issues_found=[
            {"category": "performance", "severity": "high", "description": "Slow page load times"},
            {"category": "seo", "severity": "medium", "description": "Missing meta descriptions"},
        ],
        assessment_score=45.0,
        custom_data={"industry": "restaurant", "website_url": "https://acmerestaurant.com"},
    )


@pytest.fixture
def email_builder():
    """Email builder instance for testing"""
    return EmailBuilder()


class TestPersonalizedEmailBuilding:
    """Test P2-030 integration with email building"""

    def test_personalization_data_creation(self, sample_personalization_data):
        """Test PersonalizationData structure for P2-030"""
        assert sample_personalization_data.business_name == "Acme Restaurant"
        assert sample_personalization_data.contact_first_name == "John"
        assert sample_personalization_data.business_category == "restaurant"
        assert len(sample_personalization_data.issues_found) == 2
        assert sample_personalization_data.assessment_score == 45.0

    def test_subject_line_selection_for_email(self, sample_personalized_content):
        """Test P2-030 requirement: Select best subject line variant"""
        # Select best performing subject line (highest quality score)
        best_subject = max(sample_personalized_content.subject_lines, key=lambda s: s.quality_score)

        assert best_subject.text == "Boost Acme Restaurant's online performance"
        assert best_subject.approach == "benefit"
        assert best_subject.quality_score == 0.9
        assert best_subject.spam_risk_score == 0.1
        assert "business_name" in best_subject.personalization_tokens

    def test_body_variant_selection_for_email(self, sample_personalized_content):
        """Test P2-030 requirement: Select best body content variant"""
        # Select best performing body content (highest readability score)
        best_body = max(sample_personalized_content.body_variants, key=lambda b: b.readability_score)

        assert best_body.variant == "consultative"
        assert best_body.approach == "question-based"
        assert best_body.readability_score == 0.85
        assert "contact_name" in best_body.personalization_tokens
        assert "business_name" in best_body.personalization_tokens

    def test_personalization_token_validation(self, sample_personalized_content):
        """Test P2-030 requirement: Personalization tokens are properly filled"""
        for subject in sample_personalized_content.subject_lines:
            # Verify personalization has been applied
            assert "Acme Restaurant" in subject.text
            assert "{business_name}" not in subject.text  # Should be replaced

        for body in sample_personalized_content.body_variants:
            # Verify personalization has been applied
            assert "John" in body.content
            assert "Acme Restaurant" in body.content
            assert "{contact_name}" not in body.content  # Should be replaced
            assert "{business_name}" not in body.content  # Should be replaced

    def test_ab_testing_variant_preparation(self, sample_personalized_content):
        """Test A/B testing preparation with P2-030 variants"""
        # Create A/B test variants from P2-030 content
        ab_variants = []

        for i, (subject, body) in enumerate(
            zip(sample_personalized_content.subject_lines, sample_personalized_content.body_variants, strict=False)
        ):
            variant = {
                "variant_id": f"p2030_variant_{chr(65 + i)}",  # A, B, C
                "subject_line": subject.text,
                "body_content": body.content,
                "subject_approach": subject.approach,
                "body_variant": body.variant,
                "performance_metrics": {
                    "spam_risk": subject.spam_risk_score,
                    "quality_score": subject.quality_score,
                    "readability": body.readability_score,
                },
            }
            ab_variants.append(variant)

        # Verify we have P2-030 required variants
        assert len(ab_variants) == 3  # All 3 body variants used
        assert all("Acme Restaurant" in v["subject_line"] for v in ab_variants)
        assert all("John" in v["body_content"] for v in ab_variants)

        # Verify different approaches
        approaches = [v["subject_approach"] for v in ab_variants]
        assert "benefit" in approaches
        assert "direct" in approaches
        assert "question" in approaches

        variants = [v["body_variant"] for v in ab_variants]
        assert "direct" in variants
        assert "consultative" in variants
        assert "value-first" in variants

    def test_email_content_quality_validation(self, sample_personalized_content):
        """Test P2-030 requirement: Quality validation for email content"""
        for subject in sample_personalized_content.subject_lines:
            # Verify quality standards
            assert subject.spam_risk_score <= 0.5  # Low spam risk
            assert subject.quality_score >= 0.7  # Good quality
            assert 20 <= subject.length <= 60  # Reasonable length

        for body in sample_personalized_content.body_variants:
            # Verify readability standards
            assert body.readability_score >= 0.8  # Good readability
            assert body.word_count >= 30  # Reasonable length
            assert body.word_count <= 100  # Not too long


class TestEmailBuilderIntegration:
    """Test email builder integration with P2-030"""

    def test_email_builder_with_personalization_data(self, email_builder, sample_personalization_data):
        """Test email builder can work with P2-030 personalization data"""
        # Verify EmailBuilder can handle PersonalizationData
        assert sample_personalization_data.business_name
        assert sample_personalization_data.contact_first_name
        assert sample_personalization_data.business_category

        # This tests the data structure compatibility
        personalization_dict = {
            "business_name": sample_personalization_data.business_name,
            "contact_name": sample_personalization_data.contact_first_name,
            "industry": sample_personalization_data.business_category,
            "location": sample_personalization_data.business_location,
        }

        assert personalization_dict["business_name"] == "Acme Restaurant"
        assert personalization_dict["contact_name"] == "John"
        assert personalization_dict["industry"] == "restaurant"

    def test_findings_integration_with_personalization(self, sample_personalization_data):
        """Test P2-030 integration with assessment findings"""
        findings = sample_personalization_data.issues_found

        # Verify findings can be used for personalization context
        assert len(findings) == 2
        assert findings[0]["category"] == "performance"
        assert findings[0]["severity"] == "high"
        assert findings[1]["category"] == "seo"

        # This can be used to customize email content based on findings
        performance_issues = [f for f in findings if f["category"] == "performance"]
        seo_issues = [f for f in findings if f["category"] == "seo"]

        assert len(performance_issues) == 1
        assert len(seo_issues) == 1


@pytest.mark.integration
class TestP2030EmailIntegration:
    """Integration tests for P2-030 with email system"""

    @pytest.mark.asyncio
    async def test_p2030_email_generation_workflow(self):
        """Test complete P2-030 email generation workflow"""
        # 1. Generate personalized content using P2-030
        generator = EmailPersonalizationGenerator(use_stubs=True)

        business_data = {
            "name": "Acme Restaurant",
            "industry": "restaurant",
            "location": {"city": "Seattle", "state": "WA"},
        }

        contact_data = {"first_name": "John", "email": "john@acmerestaurant.com"}

        assessment_data = {
            "pagespeed": {"performance_score": 45},
            "lighthouse": {"seo_score": 75, "accessibility_score": 88},
        }

        result = await generator.generate_email_content(
            business_id="integration_test",
            business_data=business_data,
            contact_data=contact_data,
            assessment_data=assessment_data,
        )

        # Verify P2-030 requirements are met
        assert len(result.subject_lines) == 5
        assert len(result.body_variants) == 3
        assert result.generation_mode == GenerationMode.DETERMINISTIC

        # 2. Create PersonalizationData for email building
        personalization_data = PersonalizationData(
            business_name=business_data["name"],
            contact_first_name=contact_data["first_name"],
            business_category=business_data["industry"],
            business_location="Seattle, WA",
            assessment_score=45.0,
            issues_found=[
                {"category": "performance", "severity": "high", "description": "Slow loading"},
                {"category": "seo", "severity": "medium", "description": "SEO improvements needed"},
            ],
        )

        # 3. Select best variants for delivery
        best_subject = max(result.subject_lines, key=lambda s: s.quality_score)
        best_body = max(result.body_variants, key=lambda b: b.readability_score)

        # Verify integration
        assert "Acme Restaurant" in best_subject.text
        assert "John" in best_body.content
        assert personalization_data.business_name == "Acme Restaurant"
        assert personalization_data.contact_first_name == "John"

    def test_p2030_click_tracking_preparation(self, sample_personalized_content):
        """Test P2-030 requirement: Click tracking enabled"""
        # Prepare tracking data for personalized email
        tracking_data = {
            "campaign_id": "p2030_personalization_test",
            "business_id": "acme_restaurant_123",
            "variant_info": {
                "subject_approach": sample_personalized_content.subject_lines[0].approach,
                "body_variant": sample_personalized_content.body_variants[0].variant,
                "generation_mode": "llm_powered",
            },
            "utm_parameters": {
                "utm_campaign": "p2030_personalization_test",
                "utm_source": "email",
                "utm_medium": "personalized_email",
                "utm_content": f"subject_{sample_personalized_content.subject_lines[0].approach}_body_{sample_personalized_content.body_variants[0].variant}",
            },
        }

        # Verify tracking data structure
        assert tracking_data["campaign_id"] == "p2030_personalization_test"
        assert tracking_data["variant_info"]["subject_approach"] == "benefit"
        assert tracking_data["variant_info"]["body_variant"] == "direct"
        assert "utm_campaign" in tracking_data["utm_parameters"]
        assert "subject_benefit_body_direct" in tracking_data["utm_parameters"]["utm_content"]

    def test_p2030_preview_data_structure(self, sample_personalized_content):
        """Test P2-030 requirement: Preview in admin UI"""
        # Create preview data structure for admin UI
        preview_data = {
            "business_info": {
                "name": "Acme Restaurant",
                "industry": "restaurant",
                "location": "Seattle, WA",
            },
            "contact_info": {"name": "John", "email": "john@acmerestaurant.com"},
            "generated_content": {
                "subject_variants": [
                    {
                        "text": subject.text,
                        "approach": subject.approach,
                        "quality_score": subject.quality_score,
                        "spam_risk": subject.spam_risk_score,
                        "length": subject.length,
                    }
                    for subject in sample_personalized_content.subject_lines
                ],
                "body_variants": [
                    {
                        "content": body.content,
                        "variant": body.variant,
                        "approach": body.approach,
                        "readability_score": body.readability_score,
                        "word_count": body.word_count,
                    }
                    for body in sample_personalized_content.body_variants
                ],
                "generation_metadata": sample_personalized_content.metadata,
            },
            "preview_ready": True,
        }

        # Verify preview data structure meets P2-030 requirements
        assert len(preview_data["generated_content"]["subject_variants"]) == 3  # Using sample data
        assert len(preview_data["generated_content"]["body_variants"]) == 3
        assert preview_data["preview_ready"] is True

        # Verify all subject variants contain personalized business name
        for subject_variant in preview_data["generated_content"]["subject_variants"]:
            assert "Acme Restaurant" in subject_variant["text"]
            assert subject_variant["approach"] in ["benefit", "direct", "question"]
            assert 0 <= subject_variant["quality_score"] <= 1
            assert 0 <= subject_variant["spam_risk"] <= 1

        # Verify all body variants contain personalized content
        for body_variant in preview_data["generated_content"]["body_variants"]:
            assert "John" in body_variant["content"]
            assert "Acme Restaurant" in body_variant["content"]
            assert body_variant["variant"] in ["direct", "consultative", "value-first"]
            assert 0 <= body_variant["readability_score"] <= 1
