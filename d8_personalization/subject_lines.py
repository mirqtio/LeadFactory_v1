"""
D8 Personalization Subject Line Generator - Task 061

Pattern-based subject line generation with token replacement, length limits,
and A/B variant creation for email personalization.

Acceptance Criteria:
- Pattern-based generation ✓
- Token replacement works ✓
- Length limits enforced ✓
- A/B variants created ✓
"""

import hashlib
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import yaml

from .models import EmailContentType, EmailTemplate, PersonalizationStrategy, SubjectLineVariant, VariantStatus


class GenerationStrategy(str, Enum):
    """Strategies for subject line generation"""

    TEMPLATE_BASED = "template_based"
    AB_TESTING = "ab_testing"
    PERFORMANCE_OPTIMIZED = "performance_optimized"
    INDUSTRY_SPECIFIC = "industry_specific"


class ToneStyle(str, Enum):
    """Tone styles for subject lines"""

    PROFESSIONAL = "professional"
    CASUAL = "casual"
    URGENT = "urgent"
    FRIENDLY = "friendly"
    AUTHORITATIVE = "authoritative"


@dataclass
class SubjectLineRequest:
    """Request for subject line generation"""

    business_id: str
    content_type: EmailContentType
    personalization_strategy: PersonalizationStrategy
    business_data: dict[str, Any]
    contact_data: dict[str, Any] | None = None
    assessment_data: dict[str, Any] | None = None
    campaign_context: dict[str, Any] | None = None
    generation_strategy: GenerationStrategy = GenerationStrategy.TEMPLATE_BASED
    max_variants: int = 3
    target_length: int | None = None
    tone_preference: ToneStyle | None = None


@dataclass
class GeneratedSubjectLine:
    """Generated subject line with metadata"""

    text: str
    variant_name: str
    pattern_used: str
    tokens_resolved: dict[str, str]
    tokens_failed: list[str]
    length: int
    tone: ToneStyle
    quality_score: float
    personalization_score: float
    spam_risk_score: float
    generation_method: str


class SubjectLineGenerator:
    """Main subject line generator - Acceptance Criteria"""

    def __init__(self, templates_path: str | None = None):
        """Initialize the subject line generator"""
        self.templates_path = templates_path or self._get_default_templates_path()
        self.templates = self._load_templates()
        self.token_cache = {}  # Cache for resolved tokens

    def _get_default_templates_path(self) -> str:
        """Get default path to templates.yaml"""
        current_dir = os.path.dirname(__file__)
        return os.path.join(current_dir, "templates.yaml")

    def _load_templates(self) -> dict[str, Any]:
        """Load templates from YAML file"""
        try:
            with open(self.templates_path) as file:
                return yaml.safe_load(file)
        except Exception:
            # Fallback to minimal templates if file not found
            return self._get_fallback_templates()

    def _get_fallback_templates(self) -> dict[str, Any]:
        """Fallback templates if YAML file not available"""
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
                    ]
                }
            },
            "token_config": {
                "business_name": {"default": "your business", "max_length": 50},
                "contact_name": {"default": "there", "max_length": 30},
            },
            "generation_rules": {"global_constraints": {"min_length": 10, "max_length": 78}},
        }

    def generate_subject_lines(self, request: SubjectLineRequest) -> list[GeneratedSubjectLine]:
        """Generate subject lines based on request - Acceptance Criteria"""
        if request.generation_strategy == GenerationStrategy.AB_TESTING:
            return self._generate_ab_variants(request)
        if request.generation_strategy == GenerationStrategy.PERFORMANCE_OPTIMIZED:
            return self._generate_performance_optimized(request)
        if request.generation_strategy == GenerationStrategy.INDUSTRY_SPECIFIC:
            return self._generate_industry_specific(request)
        return self._generate_template_based(request)

    def _generate_template_based(self, request: SubjectLineRequest) -> list[GeneratedSubjectLine]:
        """Generate subject lines using template patterns - Acceptance Criteria"""
        content_type_key = request.content_type.value
        templates = self.templates.get("templates", {}).get(content_type_key, {})

        if not templates:
            # Fallback to cold_outreach templates
            templates = self.templates.get("templates", {}).get("cold_outreach", {})

        generated_lines = []
        template_count = 0

        for category, pattern_list in templates.items():
            if template_count >= request.max_variants:
                break

            for template in pattern_list:
                if template_count >= request.max_variants:
                    break

                subject_line = self._generate_from_template(template, request, f"{category}_{template_count}")

                if subject_line and self._passes_quality_checks(subject_line, request):
                    generated_lines.append(subject_line)
                    template_count += 1

        return generated_lines[: request.max_variants]

    def _generate_from_template(
        self, template: dict[str, Any], request: SubjectLineRequest, variant_name: str
    ) -> GeneratedSubjectLine | None:
        """Generate a single subject line from template - Acceptance Criteria"""
        pattern = template.get("pattern", "")
        required_tokens = template.get("tokens", [])
        max_length = template.get("max_length", 78)
        tone = template.get("tone", "professional")

        # Apply target length override if provided
        if request.target_length:
            max_length = min(max_length, request.target_length)

        # Resolve tokens
        tokens_resolved, tokens_failed = self._resolve_tokens(required_tokens, request)

        # Replace tokens in pattern
        subject_text = pattern
        for token, value in tokens_resolved.items():
            subject_text = subject_text.replace(f"{{{token}}}", value)

        # Enforce length limits - Acceptance Criteria
        if len(subject_text) > max_length:
            subject_text = self._truncate_subject_line(subject_text, max_length)

        # Check minimum length
        min_length = self.templates.get("generation_rules", {}).get("global_constraints", {}).get("min_length", 10)

        if len(subject_text) < min_length:
            return None  # Too short to be effective

        # Calculate quality scores
        quality_score = self._calculate_quality_score(subject_text, template, request)
        personalization_score = self._calculate_personalization_score(tokens_resolved, required_tokens)
        spam_risk_score = self._calculate_spam_risk_score(subject_text)

        return GeneratedSubjectLine(
            text=subject_text,
            variant_name=variant_name,
            pattern_used=pattern,
            tokens_resolved=tokens_resolved,
            tokens_failed=tokens_failed,
            length=len(subject_text),
            tone=ToneStyle(tone) if tone in [t.value for t in ToneStyle] else ToneStyle.PROFESSIONAL,
            quality_score=quality_score,
            personalization_score=personalization_score,
            spam_risk_score=spam_risk_score,
            generation_method="template_based",
        )

    def _generate_ab_variants(self, request: SubjectLineRequest) -> list[GeneratedSubjectLine]:
        """Generate A/B testing variants - Acceptance Criteria"""
        variants = []
        ab_config = self.templates.get("ab_testing", {})
        variant_strategies = ab_config.get("variant_strategies", {})

        # Generate length variants
        if "length_variants" in variant_strategies:
            length_variants = variant_strategies["length_variants"]
            for variant_type, config in length_variants.items():
                modified_request = self._modify_request_for_variant(request, "length", config)
                length_variant = self._generate_template_based(modified_request)[0:1]
                if length_variant:
                    length_variant[0].variant_name = f"length_{variant_type}"
                    variants.extend(length_variant)

        # Generate tone variants
        if "tone_variants" in variant_strategies and len(variants) < request.max_variants:
            tone_variants = variant_strategies["tone_variants"]
            for variant_type, config in tone_variants.items():
                if len(variants) >= request.max_variants:
                    break
                modified_request = self._modify_request_for_variant(request, "tone", config)
                tone_variant = self._generate_template_based(modified_request)[0:1]
                if tone_variant:
                    tone_variant[0].variant_name = f"tone_{variant_type}"
                    variants.extend(tone_variant)

        # Generate personalization variants
        if "personalization_variants" in variant_strategies and len(variants) < request.max_variants:
            personalization_variants = variant_strategies["personalization_variants"]
            for variant_type, config in personalization_variants.items():
                if len(variants) >= request.max_variants:
                    break
                modified_request = self._modify_request_for_variant(request, "personalization", config)
                personalization_variant = self._generate_template_based(modified_request)[0:1]
                if personalization_variant:
                    personalization_variant[0].variant_name = f"personalization_{variant_type}"
                    variants.extend(personalization_variant)

        return variants[: request.max_variants]

    def _generate_performance_optimized(self, request: SubjectLineRequest) -> list[GeneratedSubjectLine]:
        """Generate performance-optimized subject lines"""
        high_performers = self.templates.get("high_performing_patterns", {}).get("top_performers", [])
        generated_lines = []

        for i, performer in enumerate(high_performers[: request.max_variants]):
            template = {
                "pattern": performer["pattern"],
                "tokens": self._extract_tokens_from_pattern(performer["pattern"]),
                "max_length": 78,
                "tone": "professional",
                "open_rate": performer.get("open_rate", 0.0),
            }

            subject_line = self._generate_from_template(template, request, f"performance_{i}")

            if subject_line:
                # Boost quality score based on historical performance
                subject_line.quality_score = min(
                    subject_line.quality_score + performer.get("open_rate", 0.0) * 0.3,
                    1.0,
                )
                generated_lines.append(subject_line)

        return generated_lines

    def _generate_industry_specific(self, request: SubjectLineRequest) -> list[GeneratedSubjectLine]:
        """Generate industry-specific subject lines"""
        # Detect industry from business data
        industry = self._detect_industry(request.business_data)
        industry_config = self.templates.get("industry_overrides", {}).get(industry, {})

        # Start with template-based generation
        base_lines = self._generate_template_based(request)

        # Apply industry-specific modifications
        for line in base_lines:
            if industry_config:
                line.text = self._apply_industry_modifications(line.text, industry_config)
                line.generation_method = f"industry_specific_{industry}"

        return base_lines

    def _resolve_tokens(
        self, required_tokens: list[str], request: SubjectLineRequest
    ) -> tuple[dict[str, str], list[str]]:
        """Resolve personalization tokens from request data - Acceptance Criteria"""
        tokens_resolved = {}
        tokens_failed = []
        token_config = self.templates.get("token_config", {})

        for token in required_tokens:
            try:
                value = self._resolve_single_token(token, request, token_config)
                if value:
                    tokens_resolved[token] = value
                else:
                    tokens_failed.append(token)
                    # Use default value
                    default_value = token_config.get(token, {}).get("default", f"{{{token}}}")
                    tokens_resolved[token] = default_value
            except Exception:
                tokens_failed.append(token)
                default_value = token_config.get(token, {}).get("default", f"{{{token}}}")
                tokens_resolved[token] = default_value

        return tokens_resolved, tokens_failed

    def _resolve_single_token(
        self, token: str, request: SubjectLineRequest, token_config: dict[str, Any]
    ) -> str | None:
        """Resolve a single token from request data"""
        config = token_config.get(token, {})
        config.get("source", "")
        max_length = config.get("max_length", 100)
        transformations = config.get("transformations", [])

        # Try to resolve from different data sources
        value = None

        if token == "business_name" and request.business_data:
            value = request.business_data.get("name") or request.business_data.get("business_name")
        elif token == "contact_name" and request.contact_data:
            value = (
                request.contact_data.get("first_name")
                or request.contact_data.get("name")
                or request.contact_data.get("contact_name")
            )
        elif token == "industry" and request.business_data:
            value = (
                request.business_data.get("category")
                or request.business_data.get("industry")
                or request.business_data.get("vertical")
            )
        elif token == "location" and request.business_data:
            location_data = request.business_data.get("location", {})
            if isinstance(location_data, dict):
                value = location_data.get("city") or location_data.get("location") or request.business_data.get("city")
            else:
                value = str(location_data)
        elif token == "speed_score" and request.assessment_data:
            pagespeed_data = request.assessment_data.get("pagespeed", {})
            value = pagespeed_data.get("performance_score")
            if value is not None:
                value = f"{value}/100"
        elif token == "issues_count" and request.assessment_data:
            issues = request.assessment_data.get("issues", {})
            count = issues.get("count") or len(issues.get("list", []))
            if count:
                value = f"{count} issues"

        if not value:
            return None

        # Apply transformations
        value = str(value)
        for transformation in transformations:
            value = self._apply_transformation(value, transformation)

        # Enforce length limits
        if len(value) > max_length:
            value = value[: max_length - 3] + "..."

        return value

    def _apply_transformation(self, value: str, transformation: str) -> str:
        """Apply transformation to token value"""
        if transformation == "title_case":
            return value.title()
        if transformation == "upper_case":
            return value.upper()
        if transformation == "lower_case":
            return value.lower()
        if transformation == "remove_legal_suffixes":
            # Remove LLC, Inc, Corp, etc. (case insensitive)
            legal_suffixes = [" LLC", " Inc", " Corp", " Ltd", " Co"]
            for suffix in legal_suffixes:
                if value.upper().endswith(suffix.upper()):
                    value = value[: -len(suffix)]
                    break
            return value
        if transformation == "normalize_industry":
            # Normalize industry names
            industry_mapping = {
                "restaurants": "restaurant",
                "food": "restaurant",
                "medical": "healthcare",
                "health": "healthcare",
                "retail": "store",
                "shopping": "store",
            }
            return industry_mapping.get(value.lower(), value)
        if transformation == "make_singular":
            if value.endswith("s") and len(value) > 3:
                return value[:-1]
            return value
        if transformation == "remove_state_suffix":
            # Remove state abbreviations from city names
            if ", " in value:
                return value.split(", ")[0]
            return value
        return value

    def _truncate_subject_line(self, text: str, max_length: int) -> str:
        """Truncate subject line while preserving readability - Acceptance Criteria"""
        if len(text) <= max_length:
            return text

        # Try to truncate at word boundary
        if max_length > 10:
            truncated = text[: max_length - 3]
            last_space = truncated.rfind(" ")
            if last_space > len(truncated) * 0.7:  # Don't truncate too aggressively
                return truncated[:last_space] + "..."

        # Fallback: hard truncate
        return text[: max_length - 3] + "..."

    def _calculate_quality_score(
        self, subject_text: str, template: dict[str, Any], request: SubjectLineRequest
    ) -> float:
        """Calculate overall quality score for subject line"""
        score = 0.0

        # Length score (optimal range: 30-50 characters)
        length = len(subject_text)
        if 30 <= length <= 50:
            length_score = 1.0
        elif 20 <= length < 30 or 50 < length <= 60:
            length_score = 0.8
        elif 15 <= length < 20 or 60 < length <= 70:
            length_score = 0.6
        else:
            length_score = 0.3

        score += length_score * 0.3

        # Personalization score
        personalization_score = self._count_personalization_tokens(subject_text) * 0.2
        score += min(personalization_score, 0.3)

        # Readability score (simple heuristic)
        words = subject_text.split()
        avg_word_length = sum(len(word) for word in words) / len(words) if words else 0
        readability_score = max(0, 1.0 - (avg_word_length - 5) * 0.1)
        score += readability_score * 0.2

        # Spam risk (inverse score)
        spam_risk = self._calculate_spam_risk_score(subject_text)
        score += (1.0 - spam_risk) * 0.2

        return min(score, 1.0)

    def _calculate_personalization_score(self, tokens_resolved: dict[str, str], required_tokens: list[str]) -> float:
        """Calculate personalization completeness score"""
        if not required_tokens:
            return 1.0

        successfully_resolved = sum(
            1 for token in required_tokens if token in tokens_resolved and not tokens_resolved[token].startswith("{")
        )

        return successfully_resolved / len(required_tokens)

    def _calculate_spam_risk_score(self, subject_text: str) -> float:
        """Calculate spam risk score (0 = low risk, 1 = high risk)"""
        spam_indicators = 0
        text_upper = subject_text.upper()

        # Check for spam words
        spam_words = (
            self.templates.get("generation_rules", {}).get("global_constraints", {}).get("avoid_spam_words", [])
        )

        for word in spam_words:
            if word in text_upper:
                spam_indicators += 1

        # Check for excessive punctuation
        exclamation_count = subject_text.count("!")
        if exclamation_count > 1:
            spam_indicators += exclamation_count - 1

        # Check for all caps words
        words = subject_text.split()
        caps_words = sum(1 for word in words if word.isupper() and len(word) > 2)
        if caps_words > 2:
            spam_indicators += caps_words - 2

        # Check for excessive numbers/symbols
        number_symbol_ratio = (
            sum(1 for char in subject_text if char.isdigit() or char in "$%@#") / len(subject_text)
            if subject_text
            else 0
        )

        if number_symbol_ratio > 0.2:
            spam_indicators += 2

        # Normalize to 0-1 scale
        return min(spam_indicators * 0.1, 1.0)

    def _count_personalization_tokens(self, text: str) -> int:
        """Count personalization tokens that were successfully resolved"""
        # Count tokens that don't look like unresolved placeholders
        token_pattern = r"\{[^}]+\}"
        unresolved_tokens = len(re.findall(token_pattern, text))

        # Estimate resolved tokens based on capitalized words and common patterns
        words = text.split()
        likely_personalized = sum(
            1
            for word in words
            if word[0].isupper() and len(word) > 3 and word not in ["Quick", "About", "Website", "Your", "Free", "New"]
        )

        return max(0, likely_personalized - unresolved_tokens)

    def _passes_quality_checks(self, subject_line: GeneratedSubjectLine, request: SubjectLineRequest) -> bool:
        """Check if subject line passes quality thresholds"""
        constraints = self.templates.get("generation_rules", {}).get("global_constraints", {})

        # Length constraints
        min_length = constraints.get("min_length", 10)
        max_length = constraints.get("max_length", 78)

        if not (min_length <= subject_line.length <= max_length):
            return False

        # Quality score threshold
        if subject_line.quality_score < 0.3:
            return False

        # Spam risk threshold
        if subject_line.spam_risk_score > 0.7:
            return False

        return True

    def _modify_request_for_variant(
        self, request: SubjectLineRequest, variant_type: str, config: dict[str, Any]
    ) -> SubjectLineRequest:
        """Modify request for A/B variant generation"""
        modified_request = SubjectLineRequest(
            business_id=request.business_id,
            content_type=request.content_type,
            personalization_strategy=request.personalization_strategy,
            business_data=request.business_data,
            contact_data=request.contact_data,
            assessment_data=request.assessment_data,
            campaign_context=request.campaign_context,
            generation_strategy=request.generation_strategy,
            max_variants=1,  # Generate one variant
            target_length=request.target_length,
            tone_preference=request.tone_preference,
        )

        if variant_type == "length":
            modified_request.target_length = config.get("max_length")
        elif variant_type == "tone":
            style = config.get("style")
            if style in [t.value for t in ToneStyle]:
                modified_request.tone_preference = ToneStyle(style)

        return modified_request

    def _extract_tokens_from_pattern(self, pattern: str) -> list[str]:
        """Extract token names from pattern string"""
        token_pattern = r"\{([^}]+)\}"
        return re.findall(token_pattern, pattern)

    def _detect_industry(self, business_data: dict[str, Any]) -> str:
        """Detect industry from business data"""
        category = business_data.get("category", "").lower()
        industry = business_data.get("industry", "").lower()

        # Map to standard industry categories
        if any(term in f"{category} {industry}" for term in ["restaurant", "food", "dining"]):
            return "restaurant"
        if any(term in f"{category} {industry}" for term in ["medical", "health", "doctor", "clinic"]):
            return "medical"
        if any(term in f"{category} {industry}" for term in ["retail", "store", "shop", "clothing"]):
            return "retail"
        if any(term in f"{category} {industry}" for term in ["lawyer", "legal", "attorney", "accountant"]):
            return "professional_services"
        return "general"

    def _apply_industry_modifications(self, text: str, industry_config: dict[str, Any]) -> str:
        """Apply industry-specific modifications to subject line"""
        avoid_terms = industry_config.get("avoid_terms", [])
        prefer_terms = industry_config.get("prefer_terms", [])

        # Simple term replacement (could be enhanced)
        modified_text = text

        for i, avoid_term in enumerate(avoid_terms):
            if avoid_term in modified_text.lower() and i < len(prefer_terms):
                modified_text = modified_text.replace(avoid_term, prefer_terms[i])

        return modified_text


class SubjectLineManager:
    """High-level manager for subject line operations"""

    def __init__(self):
        """Initialize the subject line manager"""
        self.generator = SubjectLineGenerator()

    def create_subject_line_variants(
        self, template: EmailTemplate, request: SubjectLineRequest, session=None
    ) -> list[SubjectLineVariant]:
        """Create subject line variants for database storage"""
        generated_lines = self.generator.generate_subject_lines(request)
        variants = []

        for i, line in enumerate(generated_lines):
            variant = SubjectLineVariant(
                template_id=template.id,
                variant_name=line.variant_name or f"variant_{i + 1}",
                subject_text=line.text,
                personalization_tokens=list(line.tokens_resolved.keys()),
                status=VariantStatus.DRAFT,
                weight=1.0,
                sent_count=0,
                open_count=0,
                click_count=0,
                conversion_count=0,
            )
            variants.append(variant)

            if session:
                session.add(variant)

        return variants

    def get_best_performing_variant(self, template_id: str, session) -> SubjectLineVariant | None:
        """Get the best performing variant for a template"""
        if not session:
            return None

        variants = (
            session.query(SubjectLineVariant)
            .filter(
                SubjectLineVariant.template_id == template_id,
                SubjectLineVariant.status.in_([VariantStatus.ACTIVE, VariantStatus.WINNING]),
                SubjectLineVariant.sent_count > 100,  # Minimum sample size
            )
            .all()
        )

        if not variants:
            return None

        # Calculate performance score (combination of open rate and conversion rate)
        best_variant = None
        best_score = 0

        for variant in variants:
            if variant.sent_count > 0:
                open_rate = variant.open_count / variant.sent_count
                conversion_rate = variant.conversion_count / variant.sent_count
                performance_score = (open_rate * 0.6) + (conversion_rate * 0.4)

                if performance_score > best_score:
                    best_score = performance_score
                    best_variant = variant

        return best_variant


# Utility functions for subject line generation
def validate_subject_line_length(text: str, max_length: int = 78) -> bool:
    """Validate subject line length constraints"""
    return 10 <= len(text) <= max_length


def calculate_subject_line_readability(text: str) -> float:
    """Calculate readability score for subject line"""
    words = text.split()
    if not words:
        return 0.0

    # Simple readability based on word length and complexity
    avg_word_length = sum(len(word) for word in words) / len(words)
    word_count = len(words)

    # Optimal: 3-7 words, average word length 4-6 characters
    word_count_score = 1.0 if 3 <= word_count <= 7 else max(0, 1.0 - abs(word_count - 5) * 0.1)
    word_length_score = 1.0 if 4 <= avg_word_length <= 6 else max(0, 1.0 - abs(avg_word_length - 5) * 0.1)

    return (word_count_score + word_length_score) / 2


def generate_subject_line_hash(text: str) -> str:
    """Generate hash for subject line deduplication"""
    return hashlib.md5(text.lower().encode()).hexdigest()[:16]


# Constants for subject line generation
DEFAULT_MAX_LENGTH = 78  # Gmail truncation limit
DEFAULT_MIN_LENGTH = 10
OPTIMAL_LENGTH_RANGE = (30, 50)
MAX_VARIANTS_PER_TEMPLATE = 5
MIN_SAMPLE_SIZE_FOR_PERFORMANCE = 100
