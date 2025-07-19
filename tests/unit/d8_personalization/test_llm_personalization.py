"""
Unit tests for P2-030 LLM Personalization - Email Personalization V2

Tests the LLM-powered email content generation with:
- 5 subject line variants
- 3 body copy variants
- Deterministic test mode
- LLM integration with Humanloop
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
    GenerationOptions,
    PersonalizationLevel,
    generate_body_variants,
    generate_full_email_content,
    generate_subject_lines,
)


@pytest.fixture
def sample_business_data():
    """Sample business data for testing"""
    return {
        "name": "Acme Restaurant",
        "business_name": "Acme Restaurant",
        "industry": "restaurant",
        "category": "restaurant",
        "location": {"city": "Seattle", "state": "WA"},
        "city": "Seattle",
    }


@pytest.fixture
def sample_contact_data():
    """Sample contact data for testing"""
    return {
        "first_name": "John",
        "name": "John Smith",
        "contact_name": "John",
        "email": "john@acmerestaurant.com",
    }


@pytest.fixture
def sample_assessment_data():
    """Sample assessment data for testing"""
    return {
        "pagespeed": {"performance_score": 45},
        "lighthouse": {
            "performance_score": 65,
            "accessibility_score": 88,
            "seo_score": 75,
            "best_practices_score": 92,
        },
    }


@pytest.fixture
def generator_stub():
    """Generator with USE_STUBS=True for deterministic testing"""
    return EmailPersonalizationGenerator(use_stubs=True)


@pytest.fixture
def generator_llm():
    """Generator with USE_STUBS=False for LLM testing"""
    return EmailPersonalizationGenerator(use_stubs=False)


class TestEmailPersonalizationGenerator:
    """Test P2-030 Email Personalization V2 Generator"""

    def test_generator_initialization_stub_mode(self, generator_stub):
        """Test generator initialization in stub mode"""
        assert generator_stub.use_stubs is True
        assert generator_stub.humanloop_client is not None
        assert len(generator_stub._deterministic_subjects) == 5
        assert len(generator_stub._deterministic_bodies) == 3

    def test_generator_initialization_llm_mode(self, generator_llm):
        """Test generator initialization in LLM mode"""
        assert generator_llm.use_stubs is False
        assert generator_llm.humanloop_client is not None

    @pytest.mark.asyncio
    async def test_generate_email_content_deterministic(
        self, generator_stub, sample_business_data, sample_contact_data, sample_assessment_data
    ):
        """Test P2-030 requirement: Generate email content in deterministic mode"""
        result = await generator_stub.generate_email_content(
            business_id="test_biz_123",
            business_data=sample_business_data,
            contact_data=sample_contact_data,
            assessment_data=sample_assessment_data,
        )

        # P2-030 Acceptance Criteria: 5 subject line variants
        assert len(result.subject_lines) == 5
        assert all(isinstance(subject, GeneratedSubjectLine) for subject in result.subject_lines)

        # P2-030 Acceptance Criteria: 3 body copy variants
        assert len(result.body_variants) == 3
        assert all(isinstance(body, GeneratedBodyContent) for body in result.body_variants)

        # Verify result metadata
        assert result.generation_mode == GenerationMode.DETERMINISTIC
        assert result.business_id == "test_biz_123"
        assert isinstance(result.generated_at, datetime)
        assert result.generation_time_ms >= 0

    @pytest.mark.asyncio
    async def test_subject_line_generation_variants(self, generator_stub, sample_business_data):
        """Test P2-030 requirement: 5 subject line variants with different approaches"""
        result = await generator_stub.generate_email_content(
            business_id="test_biz_456", business_data=sample_business_data
        )

        subject_lines = result.subject_lines
        assert len(subject_lines) == 5

        # Verify different approaches are used
        approaches = [subject.approach for subject in subject_lines]
        expected_approaches = ["direct", "question", "benefit", "curiosity", "urgency"]
        assert set(approaches) == set(expected_approaches)

        # Verify personalization tokens are extracted
        for subject in subject_lines:
            assert isinstance(subject.text, str)
            assert len(subject.text) > 0
            assert subject.length == len(subject.text)
            assert 0 <= subject.spam_risk_score <= 1
            assert 0 <= subject.quality_score <= 1

    @pytest.mark.asyncio
    async def test_body_content_generation_variants(self, generator_stub, sample_business_data, sample_contact_data):
        """Test P2-030 requirement: 3 body copy variants with different strategies"""
        result = await generator_stub.generate_email_content(
            business_id="test_biz_789", business_data=sample_business_data, contact_data=sample_contact_data
        )

        body_variants = result.body_variants
        assert len(body_variants) == 3

        # Verify different variants are used
        variants = [body.variant for body in body_variants]
        expected_variants = ["direct", "consultative", "value-first"]
        assert set(variants) == set(expected_variants)

        # Verify content quality
        for body in body_variants:
            assert isinstance(body.content, str)
            assert len(body.content) > 0
            assert body.word_count > 0
            assert 0 <= body.readability_score <= 1

    @pytest.mark.asyncio
    async def test_personalization_token_replacement(self, generator_stub, sample_business_data, sample_contact_data):
        """Test personalization token replacement in content"""
        result = await generator_stub.generate_email_content(
            business_id="test_personalization", business_data=sample_business_data, contact_data=sample_contact_data
        )

        # Check subject lines for proper personalization
        for subject in result.subject_lines:
            assert "Acme Restaurant" in subject.text
            assert "{business_name}" not in subject.text  # Should be replaced

        # Check body content for proper personalization
        for body in result.body_variants:
            assert "Acme Restaurant" in body.content
            assert "John" in body.content
            assert "{business_name}" not in body.content  # Should be replaced
            assert "{contact_name}" not in body.content  # Should be replaced

    @pytest.mark.asyncio
    async def test_generation_options_customization(self, generator_stub, sample_business_data):
        """Test custom generation options"""
        custom_options = GenerationOptions(
            mode=GenerationMode.DETERMINISTIC,
            personalization_level=PersonalizationLevel.COMPREHENSIVE,
            subject_line_count=3,  # Custom count
            body_variant_count=2,  # Custom count
            max_subject_length=50,
            temperature=0.5,
        )

        result = await generator_stub.generate_email_content(
            business_id="test_custom", business_data=sample_business_data, options=custom_options
        )

        # Should still get P2-030 defaults (5 subjects, 3 bodies)
        assert len(result.subject_lines) == 5
        assert len(result.body_variants) == 3

    @pytest.mark.asyncio
    async def test_assessment_context_integration(self, generator_stub, sample_business_data, sample_assessment_data):
        """Test integration with assessment data for personalization"""
        result = await generator_stub.generate_email_content(
            business_id="test_assessment",
            business_data=sample_business_data,
            assessment_data=sample_assessment_data,
        )

        # Verify assessment context is included in metadata
        assert result.metadata["assessment_included"] is True
        assert "Acme Restaurant" in result.metadata["business_name"]
        assert "restaurant" in result.metadata["industry"]

    @pytest.mark.asyncio
    async def test_spam_risk_calculation(self, generator_stub, sample_business_data):
        """Test spam risk scoring for generated content"""
        result = await generator_stub.generate_email_content(
            business_id="test_spam", business_data=sample_business_data
        )

        for subject in result.subject_lines:
            # Deterministic content should have low spam risk
            assert subject.spam_risk_score <= 0.5
            assert isinstance(subject.spam_risk_score, float)

    @pytest.mark.asyncio
    async def test_quality_score_calculation(self, generator_stub, sample_business_data):
        """Test quality scoring for generated content"""
        result = await generator_stub.generate_email_content(
            business_id="test_quality", business_data=sample_business_data
        )

        for subject in result.subject_lines:
            # Deterministic content should have good quality
            assert subject.quality_score >= 0.5
            assert isinstance(subject.quality_score, float)

        for body in result.body_variants:
            assert body.readability_score >= 0.5
            assert isinstance(body.readability_score, float)


class TestLLMIntegration:
    """Test LLM integration with Humanloop"""

    @pytest.mark.asyncio
    async def test_llm_subject_generation_success(self, generator_llm, sample_business_data):
        """Test successful LLM subject line generation"""
        mock_response = {
            "output": """{
                "subject_lines": [
                    {"text": "Boost {business_name}'s online performance today", "approach": "benefit"},
                    {"text": "Quick question about {business_name}", "approach": "direct"},
                    {"text": "Is {business_name} missing customers?", "approach": "question"},
                    {"text": "3 ways to improve {business_name} visibility", "approach": "benefit"},
                    {"text": "Urgent: {business_name} website issues found", "approach": "urgency"}
                ]
            }"""
        }

        with patch.object(generator_llm.humanloop_client, "completion", new_callable=AsyncMock) as mock_completion:
            mock_completion.return_value = mock_response

            result = await generator_llm.generate_email_content(
                business_id="test_llm_subject", business_data=sample_business_data
            )

            # Verify LLM was called
            mock_completion.assert_called_once()
            call_args = mock_completion.call_args
            assert call_args[1]["prompt_slug"] == "email_subject_generation_v2"

            # Verify P2-030 requirements met
            assert len(result.subject_lines) == 5
            assert result.generation_mode == GenerationMode.LLM_POWERED

    @pytest.mark.asyncio
    async def test_llm_body_generation_success(self, generator_llm, sample_business_data, sample_contact_data):
        """Test successful LLM body content generation"""
        mock_response = {
            "output": """{
                "body_variants": [
                    {"content": "Hi {contact_name}, I noticed some opportunities for {business_name}...", "variant": "direct", "approach": "problem-solution"},
                    {"content": "Hello {contact_name}, How important is online visibility to {business_name}?", "variant": "consultative", "approach": "question-based"},
                    {"content": "Hi {contact_name}, {business_name} has great potential. Here are 3 insights...", "variant": "value-first", "approach": "insight-sharing"}
                ]
            }"""
        }

        with patch.object(generator_llm.humanloop_client, "completion", new_callable=AsyncMock) as mock_completion:
            mock_completion.return_value = mock_response

            result = await generator_llm.generate_email_content(
                business_id="test_llm_body", business_data=sample_business_data, contact_data=sample_contact_data
            )

            # Verify P2-030 requirements met
            assert len(result.body_variants) == 3
            assert result.generation_mode == GenerationMode.LLM_POWERED

    @pytest.mark.asyncio
    async def test_llm_fallback_to_deterministic(self, generator_llm, sample_business_data):
        """Test fallback to deterministic mode when LLM fails"""
        with patch.object(generator_llm.humanloop_client, "completion", new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = Exception("LLM service unavailable")

            result = await generator_llm.generate_email_content(
                business_id="test_fallback", business_data=sample_business_data
            )

            # Should fallback to deterministic mode
            assert len(result.subject_lines) == 5
            assert len(result.body_variants) == 3
            # Note: generation_mode might still be LLM_POWERED if fallback is internal


class TestConvenienceFunctions:
    """Test P2-030 convenience functions for backward compatibility"""

    @pytest.mark.asyncio
    async def test_generate_subject_lines_function(self, sample_business_data):
        """Test convenience function for subject line generation"""
        with patch("d8_personalization.generator.EmailPersonalizationGenerator") as mock_generator:
            mock_instance = Mock()
            mock_result = Mock()
            mock_result.subject_lines = [Mock() for _ in range(5)]
            mock_instance.generate_email_content = AsyncMock(return_value=mock_result)
            mock_generator.return_value = mock_instance

            result = await generate_subject_lines("test_biz", sample_business_data)

            assert len(result) == 5
            mock_instance.generate_email_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_body_variants_function(self, sample_business_data):
        """Test convenience function for body variant generation"""
        with patch("d8_personalization.generator.EmailPersonalizationGenerator") as mock_generator:
            mock_instance = Mock()
            mock_result = Mock()
            mock_result.body_variants = [Mock() for _ in range(3)]
            mock_instance.generate_email_content = AsyncMock(return_value=mock_result)
            mock_generator.return_value = mock_instance

            result = await generate_body_variants("test_biz", sample_business_data)

            assert len(result) == 3
            mock_instance.generate_email_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_full_email_content_function(self, sample_business_data):
        """Test convenience function for full email content generation"""
        with patch("d8_personalization.generator.EmailPersonalizationGenerator") as mock_generator:
            mock_instance = Mock()
            mock_result = Mock(spec=EmailGenerationResult)
            mock_instance.generate_email_content = AsyncMock(return_value=mock_result)
            mock_generator.return_value = mock_instance

            result = await generate_full_email_content("test_biz", sample_business_data)

            assert result == mock_result
            mock_instance.generate_email_content.assert_called_once()


class TestUtilityMethods:
    """Test utility methods for content processing"""

    def test_personalize_text(self, generator_stub, sample_business_data, sample_contact_data):
        """Test text personalization utility"""
        template = "Hi {contact_name}, improve {business_name} in {location}"

        result = generator_stub._personalize_text(template, sample_business_data, sample_contact_data)

        assert "John" in result
        assert "Acme Restaurant" in result
        assert "Seattle" in result or "Seattle, WA" in result
        assert "{contact_name}" not in result
        assert "{business_name}" not in result

    def test_extract_tokens(self, generator_stub):
        """Test token extraction from templates"""
        template = "Hi {contact_name}, improve {business_name} performance"

        tokens = generator_stub._extract_tokens(template)

        assert "contact_name" in tokens
        assert "business_name" in tokens
        assert len(tokens) == 2

    def test_calculate_spam_risk(self, generator_stub):
        """Test spam risk calculation"""
        # Low risk text
        low_risk = generator_stub._calculate_spam_risk("Professional website audit for your business")
        assert low_risk <= 0.2

        # High risk text
        high_risk = generator_stub._calculate_spam_risk("FREE URGENT OFFER! ACT NOW! LIMITED TIME!")
        assert high_risk >= 0.6

    def test_calculate_quality_score(self, generator_stub):
        """Test quality score calculation"""
        # Good quality subject
        good_quality = generator_stub._calculate_quality_score("Improve your website performance today")
        assert good_quality >= 0.5

        # Poor quality subject
        poor_quality = generator_stub._calculate_quality_score("a")
        assert poor_quality <= 0.3

    def test_format_assessment_context(self, generator_stub, sample_assessment_data):
        """Test assessment context formatting"""
        context = generator_stub._format_assessment_context(sample_assessment_data)

        assert "Performance Score: 45" in context
        assert "65" in context  # Lighthouse performance score

    def test_format_issues_summary(self, generator_stub, sample_assessment_data):
        """Test issues summary formatting"""
        summary = generator_stub._format_issues_summary(sample_assessment_data)

        assert "slow page loading" in summary  # Low performance score
        assert "SEO optimization" in summary  # Low SEO score


@pytest.mark.integration
class TestP2030AcceptanceCriteria:
    """Integration tests for P2-030 acceptance criteria"""

    @pytest.mark.asyncio
    async def test_p2030_complete_workflow(self, sample_business_data, sample_contact_data, sample_assessment_data):
        """Test complete P2-030 workflow meets all acceptance criteria"""
        generator = EmailPersonalizationGenerator(use_stubs=True)

        result = await generator.generate_email_content(
            business_id="p2030_acceptance_test",
            business_data=sample_business_data,
            contact_data=sample_contact_data,
            assessment_data=sample_assessment_data,
        )

        # ✅ P2-030 Acceptance Criteria: 5 subject line variants
        assert len(result.subject_lines) == 5
        assert all(isinstance(s, GeneratedSubjectLine) for s in result.subject_lines)

        # ✅ P2-030 Acceptance Criteria: 3 body copy variants
        assert len(result.body_variants) == 3
        assert all(isinstance(b, GeneratedBodyContent) for b in result.body_variants)

        # ✅ P2-030 Acceptance Criteria: Deterministic test mode
        assert result.generation_mode == GenerationMode.DETERMINISTIC

        # ✅ P2-030 Acceptance Criteria: Placeholders filled
        for subject in result.subject_lines:
            assert "{business_name}" not in subject.text
            assert "Acme Restaurant" in subject.text

        for body in result.body_variants:
            assert "{business_name}" not in body.content
            assert "{contact_name}" not in body.content
            assert "Acme Restaurant" in body.content
            assert "John" in body.content

        # ✅ Additional Requirements: Performance check
        assert result.generation_time_ms < 5000  # Should be fast in test mode

        # ✅ Additional Requirements: Quality validation
        for subject in result.subject_lines:
            assert subject.spam_risk_score <= 0.5  # Low spam risk
            assert subject.quality_score >= 0.5  # Good quality

    @pytest.mark.asyncio
    async def test_p2030_preview_ready_content(self, sample_business_data):
        """Test content is ready for admin UI preview"""
        generator = EmailPersonalizationGenerator(use_stubs=True)

        result = await generator.generate_email_content(business_id="preview_test", business_data=sample_business_data)

        # Content should be properly formatted for preview
        for subject in result.subject_lines:
            assert len(subject.text.strip()) > 0
            assert subject.approach in ["direct", "question", "benefit", "curiosity", "urgency"]

        for body in result.body_variants:
            assert len(body.content.strip()) > 0
            assert body.variant in ["direct", "consultative", "value-first"]
            assert body.word_count > 10  # Reasonable length for preview
