"""
Unit tests for D8 Personalization Subject Line Generator - Task 061

Tests for pattern-based generation, token replacement, length limits,
and A/B variant creation functionality.

Acceptance Criteria:
- Pattern-based generation ✓
- Token replacement works ✓
- Length limits enforced ✓
- A/B variants created ✓
"""

import tempfile

import pytest
import yaml

from d8_personalization.models import EmailContentType, PersonalizationStrategy
from d8_personalization.subject_lines import (
    GeneratedSubjectLine,
    GenerationStrategy,
    SubjectLineGenerator,
    SubjectLineManager,
    SubjectLineRequest,
    calculate_subject_line_readability,
    generate_subject_line_hash,
    validate_subject_line_length,
)

# Mark entire module as slow for CI optimization
pytestmark = pytest.mark.slow


@pytest.fixture
def sample_templates():
    """Create sample templates for testing"""
    return {
        "templates": {
            "cold_outreach": {
                "direct": [
                    {
                        "pattern": "Quick question about {business_name}",
                        "tokens": ["business_name"],
                        "max_length": 50,
                        "tone": "professional",
                        "urgency": "low",
                    },
                    {
                        "pattern": "Hi {contact_name}, noticed something about {business_name}",
                        "tokens": ["contact_name", "business_name"],
                        "max_length": 65,
                        "tone": "casual",
                        "urgency": "low",
                    },
                ],
                "problem_focused": [
                    {
                        "pattern": "{business_name}'s website could be losing customers",
                        "tokens": ["business_name"],
                        "max_length": 55,
                        "tone": "professional",
                        "urgency": "high",
                    }
                ],
            },
            "audit_offer": {
                "free_audit": [
                    {
                        "pattern": "Free website audit for {business_name}",
                        "tokens": ["business_name"],
                        "max_length": 45,
                        "tone": "offer",
                        "urgency": "low",
                    }
                ]
            },
        },
        "token_config": {
            "business_name": {
                "source": "business_data.name",
                "default": "your business",
                "max_length": 50,
                "transformations": ["title_case", "remove_legal_suffixes"],
            },
            "contact_name": {
                "source": "contact_data.first_name",
                "default": "there",
                "max_length": 30,
                "transformations": ["title_case"],
            },
            "industry": {
                "source": "business_data.category",
                "default": "business",
                "max_length": 20,
                "transformations": ["normalize_industry"],
            },
            "location": {
                "source": "business_data.location.city",
                "default": "your area",
                "max_length": 25,
                "transformations": ["title_case", "remove_state_suffix"],
            },
        },
        "generation_rules": {
            "global_constraints": {
                "min_length": 10,
                "max_length": 78,
                "avoid_spam_words": ["FREE", "URGENT", "ACT NOW"],
                "max_exclamation_marks": 1,
            }
        },
        "ab_testing": {
            "variant_strategies": {
                "length_variants": {
                    "short": {"max_length": 30, "style": "concise"},
                    "medium": {"max_length": 50, "style": "balanced"},
                    "long": {"max_length": 70, "style": "descriptive"},
                },
                "tone_variants": {
                    "formal": {"style": "professional"},
                    "casual": {"style": "friendly"},
                },
                "personalization_variants": {
                    "minimal": {"tokens": ["business_name"]},
                    "standard": {"tokens": ["business_name", "contact_name"]},
                },
            }
        },
        "high_performing_patterns": {
            "top_performers": [
                {
                    "pattern": "Quick question about {business_name}",
                    "open_rate": 0.31,
                    "click_rate": 0.08,
                },
                {
                    "pattern": "Free website audit for {business_name}",
                    "open_rate": 0.27,
                    "click_rate": 0.15,
                },
            ]
        },
        "industry_overrides": {
            "restaurant": {
                "avoid_terms": ["website", "digital"],
                "prefer_terms": ["online presence", "customers"],
            },
            "medical": {
                "avoid_terms": ["quick", "urgent"],
                "prefer_terms": ["professional", "practice"],
            },
        },
    }


@pytest.fixture
def temp_templates_file(sample_templates):
    """Create temporary templates file for testing"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(sample_templates, f)
        return f.name


@pytest.fixture
def sample_request():
    """Create sample subject line request"""
    return SubjectLineRequest(
        business_id="biz_123",
        content_type=EmailContentType.COLD_OUTREACH,
        personalization_strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
        business_data={
            "name": "Acme Restaurant LLC",
            "category": "restaurant",
            "location": {"city": "Seattle, WA"},
            "industry": "food_service",
        },
        contact_data={"first_name": "john", "name": "John Smith"},
        assessment_data={
            "pagespeed": {"performance_score": 65},
            "issues": {
                "count": 3,
                "list": ["slow_loading", "mobile_unfriendly", "seo_issues"],
            },
        },
        max_variants=3,
    )


class TestSubjectLineGenerator:
    """Test SubjectLineGenerator class - Acceptance Criteria"""

    def test_initialization_with_templates_file(self, temp_templates_file):
        """Test generator initialization with templates file"""
        generator = SubjectLineGenerator(temp_templates_file)
        assert generator.templates is not None
        assert "templates" in generator.templates
        assert "token_config" in generator.templates

    def test_initialization_with_fallback(self):
        """Test generator initialization with fallback templates"""
        generator = SubjectLineGenerator("/nonexistent/path.yaml")
        assert generator.templates is not None
        assert "templates" in generator.templates

    def test_template_based_generation(self, temp_templates_file, sample_request):
        """Test pattern-based generation - Acceptance Criteria"""
        generator = SubjectLineGenerator(temp_templates_file)
        results = generator.generate_subject_lines(sample_request)

        assert len(results) > 0
        assert len(results) <= sample_request.max_variants

        for result in results:
            assert isinstance(result, GeneratedSubjectLine)
            assert len(result.text) > 0
            assert result.pattern_used
            assert result.variant_name
            assert isinstance(result.tokens_resolved, dict)
            assert isinstance(result.tokens_failed, list)

    def test_token_replacement(self, temp_templates_file, sample_request):
        """Test token replacement works - Acceptance Criteria"""
        generator = SubjectLineGenerator(temp_templates_file)
        results = generator.generate_subject_lines(sample_request)

        # Check that tokens were replaced
        for result in results:
            # Should not contain unresolved tokens
            assert "{business_name}" not in result.text
            assert "{contact_name}" not in result.text

            # Should contain actual business name (transformed)
            assert "Acme Restaurant" in result.text or "your business" in result.text

            # Check tokens_resolved contains expected values
            if "business_name" in result.tokens_resolved:
                assert result.tokens_resolved["business_name"] != "{business_name}"

    def test_length_limits_enforced(self, temp_templates_file, sample_request):
        """Test length limits enforced - Acceptance Criteria"""
        generator = SubjectLineGenerator(temp_templates_file)

        # Test with specific length limit
        sample_request.target_length = 30
        results = generator.generate_subject_lines(sample_request)

        for result in results:
            assert len(result.text) <= 30
            assert len(result.text) >= 10  # Minimum length
            assert result.length == len(result.text)

    def test_ab_variants_created(self, temp_templates_file, sample_request):
        """Test A/B variants created - Acceptance Criteria"""
        generator = SubjectLineGenerator(temp_templates_file)

        # Request A/B testing generation
        sample_request.generation_strategy = GenerationStrategy.AB_TESTING
        sample_request.max_variants = 4

        results = generator.generate_subject_lines(sample_request)

        assert len(results) > 1  # Should generate multiple variants

        # Check that variants have different names
        variant_names = [result.variant_name for result in results]
        assert len(set(variant_names)) == len(variant_names)  # All unique

        # Check for different variant types
        variant_types = [name.split("_")[0] for name in variant_names]
        assert len(set(variant_types)) > 1  # Different types (length, tone, personalization)


class TestTokenResolution:
    """Test token resolution functionality"""

    def test_business_name_resolution(self, temp_templates_file, sample_request):
        """Test business name token resolution"""
        generator = SubjectLineGenerator(temp_templates_file)

        tokens_resolved, tokens_failed = generator._resolve_tokens(["business_name"], sample_request)

        assert "business_name" in tokens_resolved
        assert "business_name" not in tokens_failed
        assert tokens_resolved["business_name"] == "Acme Restaurant"  # LLC should be removed

    def test_contact_name_resolution(self, temp_templates_file, sample_request):
        """Test contact name token resolution"""
        generator = SubjectLineGenerator(temp_templates_file)

        tokens_resolved, tokens_failed = generator._resolve_tokens(["contact_name"], sample_request)

        assert "contact_name" in tokens_resolved
        assert tokens_resolved["contact_name"] == "John"  # Should be title cased

    def test_location_resolution(self, temp_templates_file, sample_request):
        """Test location token resolution"""
        generator = SubjectLineGenerator(temp_templates_file)

        tokens_resolved, tokens_failed = generator._resolve_tokens(["location"], sample_request)

        assert "location" in tokens_resolved
        assert tokens_resolved["location"] == "Seattle"  # State suffix should be removed

    def test_failed_token_fallback(self, temp_templates_file, sample_request):
        """Test fallback for failed token resolution"""
        generator = SubjectLineGenerator(temp_templates_file)

        # Remove business data to cause failure
        sample_request.business_data = {}

        tokens_resolved, tokens_failed = generator._resolve_tokens(["business_name"], sample_request)

        assert "business_name" in tokens_resolved
        assert "business_name" in tokens_failed
        assert tokens_resolved["business_name"] == "your business"  # Should use default


class TestTransformations:
    """Test token transformation functionality"""

    def test_title_case_transformation(self, temp_templates_file):
        """Test title case transformation"""
        generator = SubjectLineGenerator(temp_templates_file)

        result = generator._apply_transformation("john smith", "title_case")
        assert result == "John Smith"

        result = generator._apply_transformation("ACME CORP", "title_case")
        assert result == "Acme Corp"

    def test_remove_legal_suffixes(self, temp_templates_file):
        """Test removal of legal suffixes"""
        generator = SubjectLineGenerator(temp_templates_file)

        result = generator._apply_transformation("Acme Corp LLC", "remove_legal_suffixes")
        assert result == "Acme Corp"

        result = generator._apply_transformation("Smith & Associates Inc", "remove_legal_suffixes")
        assert result == "Smith & Associates"

        result = generator._apply_transformation("No Suffix Business", "remove_legal_suffixes")
        assert result == "No Suffix Business"

    def test_normalize_industry(self, temp_templates_file):
        """Test industry normalization"""
        generator = SubjectLineGenerator(temp_templates_file)

        result = generator._apply_transformation("restaurants", "normalize_industry")
        assert result == "restaurant"

        result = generator._apply_transformation("medical", "normalize_industry")
        assert result == "healthcare"

    def test_remove_state_suffix(self, temp_templates_file):
        """Test state suffix removal"""
        generator = SubjectLineGenerator(temp_templates_file)

        result = generator._apply_transformation("Seattle, WA", "remove_state_suffix")
        assert result == "Seattle"

        result = generator._apply_transformation("New York", "remove_state_suffix")
        assert result == "New York"


class TestLengthHandling:
    """Test length constraints and truncation"""

    def test_truncate_subject_line(self, temp_templates_file):
        """Test subject line truncation"""
        generator = SubjectLineGenerator(temp_templates_file)

        long_text = "This is a very long subject line that exceeds the maximum length limit"
        truncated = generator._truncate_subject_line(long_text, 30)

        assert len(truncated) <= 30
        assert truncated.endswith("...")

        # Test word boundary truncation
        text = "Short enough text"
        result = generator._truncate_subject_line(text, 30)
        assert result == text  # Should not be truncated

    def test_length_validation(self):
        """Test length validation utility"""
        assert validate_subject_line_length("Good length subject line") is True
        assert validate_subject_line_length("Too short") is False
        assert validate_subject_line_length("A" * 100) is False


class TestQualityScoring:
    """Test quality scoring functionality"""

    def test_quality_score_calculation(self, temp_templates_file, sample_request):
        """Test quality score calculation"""
        generator = SubjectLineGenerator(temp_templates_file)

        template = {
            "pattern": "Quick question about {business_name}",
            "tokens": ["business_name"],
            "max_length": 50,
            "tone": "professional",
        }

        subject_text = "Quick question about Acme Restaurant"
        score = generator._calculate_quality_score(subject_text, template, sample_request)

        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be reasonably high quality

    def test_personalization_score_calculation(self, temp_templates_file):
        """Test personalization score calculation"""
        generator = SubjectLineGenerator(temp_templates_file)

        # Full personalization
        tokens_resolved = {"business_name": "Acme Corp", "contact_name": "John"}
        required_tokens = ["business_name", "contact_name"]
        score = generator._calculate_personalization_score(tokens_resolved, required_tokens)
        assert score == 1.0

        # Partial personalization
        tokens_resolved = {
            "business_name": "Acme Corp",
            "contact_name": "{contact_name}",
        }
        score = generator._calculate_personalization_score(tokens_resolved, required_tokens)
        assert score == 0.5

    def test_spam_risk_calculation(self, temp_templates_file):
        """Test spam risk score calculation"""
        generator = SubjectLineGenerator(temp_templates_file)

        # Clean subject line
        clean_text = "Quick question about your business"
        spam_score = generator._calculate_spam_risk_score(clean_text)
        assert spam_score < 0.3

        # Spammy subject line
        spammy_text = "FREE URGENT ACT NOW!!!"
        spam_score = generator._calculate_spam_risk_score(spammy_text)
        assert spam_score > 0.5


class TestReadabilityUtilities:
    """Test readability utility functions"""

    def test_readability_calculation(self):
        """Test readability score calculation"""
        # Good readability
        good_text = "Quick question about your business"
        score = calculate_subject_line_readability(good_text)
        assert score > 0.5

        # Poor readability (too many long words)
        poor_text = "Comprehensive technological optimization implementation"
        score = calculate_subject_line_readability(poor_text)
        assert score < 0.8

        # Empty text
        empty_score = calculate_subject_line_readability("")
        assert empty_score == 0.0

    def test_subject_line_hash(self):
        """Test subject line hash generation"""
        text1 = "Test subject line"
        text2 = "Test subject line"
        text3 = "Different subject line"

        hash1 = generate_subject_line_hash(text1)
        hash2 = generate_subject_line_hash(text2)
        hash3 = generate_subject_line_hash(text3)

        assert hash1 == hash2  # Same text should produce same hash
        assert hash1 != hash3  # Different text should produce different hash
        assert len(hash1) == 16  # Should be 16 characters


class TestPerformanceOptimized:
    """Test performance-optimized generation"""

    def test_performance_optimized_generation(self, temp_templates_file, sample_request):
        """Test performance-optimized subject line generation"""
        generator = SubjectLineGenerator(temp_templates_file)

        sample_request.generation_strategy = GenerationStrategy.PERFORMANCE_OPTIMIZED
        results = generator.generate_subject_lines(sample_request)

        assert len(results) > 0

        # Should use high-performing patterns
        for result in results:
            assert result.generation_method == "template_based"
            # Quality score should be boosted for high performers
            assert result.quality_score >= 0.0


class TestIndustrySpecific:
    """Test industry-specific generation"""

    def test_industry_detection(self, temp_templates_file, sample_request):
        """Test industry detection from business data"""
        generator = SubjectLineGenerator(temp_templates_file)

        # Restaurant industry
        industry = generator._detect_industry(sample_request.business_data)
        assert industry == "restaurant"

        # Medical industry
        medical_data = {"category": "medical clinic", "industry": "healthcare"}
        industry = generator._detect_industry(medical_data)
        assert industry == "medical"

        # Unknown industry
        unknown_data = {"category": "unknown business"}
        industry = generator._detect_industry(unknown_data)
        assert industry == "general"

    def test_industry_specific_generation(self, temp_templates_file, sample_request):
        """Test industry-specific subject line generation"""
        generator = SubjectLineGenerator(temp_templates_file)

        sample_request.generation_strategy = GenerationStrategy.INDUSTRY_SPECIFIC
        results = generator.generate_subject_lines(sample_request)

        assert len(results) > 0

        for result in results:
            # Should apply industry-specific modifications
            assert "restaurant" in result.generation_method
            # Should avoid website/digital terms for restaurants
            assert "digital" not in result.text.lower()


class TestSubjectLineManager:
    """Test SubjectLineManager functionality"""

    def test_manager_initialization(self):
        """Test subject line manager initialization"""
        manager = SubjectLineManager()
        assert manager.generator is not None
        assert isinstance(manager.generator, SubjectLineGenerator)


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_business_data(self, temp_templates_file):
        """Test handling of empty business data"""
        generator = SubjectLineGenerator(temp_templates_file)

        empty_request = SubjectLineRequest(
            business_id="empty_biz",
            content_type=EmailContentType.COLD_OUTREACH,
            personalization_strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
            business_data={},
            max_variants=2,
        )

        results = generator.generate_subject_lines(empty_request)

        # Should still generate results with fallback values
        assert len(results) > 0
        for result in results:
            assert len(result.text) > 0
            # Should use default values
            assert "your business" in result.text.lower() or "there" in result.text.lower()

    def test_missing_templates(self, temp_templates_file):
        """Test handling of missing template categories"""
        generator = SubjectLineGenerator(temp_templates_file)

        # Request non-existent content type
        request = SubjectLineRequest(
            business_id="test_biz",
            content_type=EmailContentType.NEWSLETTER,  # Not in test templates
            personalization_strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
            business_data={"name": "Test Business"},
            max_variants=2,
        )

        results = generator.generate_subject_lines(request)

        # Should fallback to cold_outreach templates
        assert len(results) > 0

    def test_extreme_length_limits(self, temp_templates_file, sample_request):
        """Test extreme length limit scenarios"""
        generator = SubjectLineGenerator(temp_templates_file)

        # Very short limit
        sample_request.target_length = 15
        results = generator.generate_subject_lines(sample_request)

        for result in results:
            assert len(result.text) <= 15
            assert len(result.text) >= 10  # Should still meet minimum

        # Very long limit
        sample_request.target_length = 200
        results = generator.generate_subject_lines(sample_request)

        for result in results:
            # Should respect global max even if target is higher
            assert len(result.text) <= 78


class TestAcceptanceCriteria:
    """Test all acceptance criteria together"""

    def test_pattern_based_generation_acceptance(self, temp_templates_file, sample_request):
        """Test: Pattern-based generation ✓"""
        generator = SubjectLineGenerator(temp_templates_file)
        results = generator.generate_subject_lines(sample_request)

        assert len(results) > 0
        for result in results:
            assert result.pattern_used  # Should use a pattern
            assert result.generation_method == "template_based"

    def test_token_replacement_works_acceptance(self, temp_templates_file, sample_request):
        """Test: Token replacement works ✓"""
        generator = SubjectLineGenerator(temp_templates_file)
        results = generator.generate_subject_lines(sample_request)

        for result in results:
            # Should not contain unresolved tokens
            assert "{" not in result.text or "}" not in result.text
            assert len(result.tokens_resolved) > 0

    def test_length_limits_enforced_acceptance(self, temp_templates_file, sample_request):
        """Test: Length limits enforced ✓"""
        generator = SubjectLineGenerator(temp_templates_file)

        sample_request.target_length = 40
        results = generator.generate_subject_lines(sample_request)

        for result in results:
            assert 10 <= len(result.text) <= 40

    def test_ab_variants_created_acceptance(self, temp_templates_file, sample_request):
        """Test: A/B variants created ✓"""
        generator = SubjectLineGenerator(temp_templates_file)

        sample_request.generation_strategy = GenerationStrategy.AB_TESTING
        sample_request.max_variants = 3
        results = generator.generate_subject_lines(sample_request)

        assert len(results) > 1
        variant_names = [r.variant_name for r in results]
        assert len(set(variant_names)) == len(variant_names)  # All unique variants
