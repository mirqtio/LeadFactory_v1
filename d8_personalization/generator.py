"""
D8 Personalization Generator - P2-030 Email Personalization V2

LLM-powered email content generation with 5 subject line variants and 3 body copy variants.
Implements deterministic test mode and integrates with existing email personalization infrastructure.

Integration Points:
- Subject line generation via LLM (5 variants)
- Body copy generation via LLM (3 variants)
- Deterministic test mode using USE_STUBS flag
- Template system integration
- A/B testing capabilities
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from core.logging import get_logger
from d0_gateway.providers.humanloop import HumanloopClient

logger = get_logger("d8_generator", domain="d8_personalization")


class GenerationMode(str, Enum):
    """Generation modes for email content"""

    LLM_POWERED = "llm_powered"  # P2-030 LLM generation
    DETERMINISTIC = "deterministic"  # Test mode with fixed responses
    TEMPLATE_BASED = "template_based"  # Legacy pattern-based


class PersonalizationLevel(str, Enum):
    """Levels of personalization for email content"""

    BASIC = "basic"  # Name and business only
    ENHANCED = "enhanced"  # Include assessment data
    COMPREHENSIVE = "comprehensive"  # Full context and insights


@dataclass
class GenerationOptions:
    """Options for email content generation"""

    mode: GenerationMode = GenerationMode.LLM_POWERED
    personalization_level: PersonalizationLevel = PersonalizationLevel.ENHANCED
    subject_line_count: int = 5  # P2-030 requirement
    body_variant_count: int = 3  # P2-030 requirement
    include_assessment_context: bool = True
    deterministic_seed: str | None = None  # For testing
    max_subject_length: int = 60
    max_body_words: int = 150
    temperature: float = 0.7


@dataclass
class GeneratedSubjectLine:
    """Generated subject line with metadata"""

    text: str
    approach: str  # direct, question, benefit, curiosity, urgency
    length: int
    personalization_tokens: list[str] = field(default_factory=list)
    spam_risk_score: float = 0.0
    quality_score: float = 0.0


@dataclass
class GeneratedBodyContent:
    """Generated email body with metadata"""

    content: str
    variant: str  # direct, consultative, value-first
    approach: str
    word_count: int
    personalization_tokens: list[str] = field(default_factory=list)
    readability_score: float = 0.0


@dataclass
class EmailGenerationResult:
    """Complete email generation result"""

    subject_lines: list[GeneratedSubjectLine]
    body_variants: list[GeneratedBodyContent]
    generation_mode: GenerationMode
    business_id: str
    generated_at: datetime
    total_cost: Decimal = Decimal("0.00")
    generation_time_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class EmailPersonalizationGenerator:
    """
    P2-030 Email Personalization V2 Generator

    LLM-powered email content generation with deterministic test mode support.
    Generates 5 subject line variants and 3 body copy variants as specified.
    """

    def __init__(self, use_stubs: bool = None, humanloop_client: HumanloopClient | None = None):
        """
        Initialize the email personalization generator

        Args:
            use_stubs: Override for deterministic mode (defaults to USE_STUBS env var)
            humanloop_client: Optional Humanloop client (creates default if None)
        """
        self.use_stubs = use_stubs if use_stubs is not None else os.getenv("USE_STUBS", "false").lower() == "true"
        self.humanloop_client = humanloop_client or HumanloopClient()

        # Deterministic responses for testing
        self._deterministic_subjects = [
            {"text": "Quick question about {business_name}", "approach": "direct", "length": 35},
            {"text": "Is {business_name} missing out on customers?", "approach": "question", "length": 45},
            {"text": "3 ways to boost {business_name} performance", "approach": "benefit", "length": 42},
            {"text": "Something caught my eye about {business_name}", "approach": "curiosity", "length": 47},
            {"text": "{business_name} website needs attention", "approach": "urgency", "length": 38},
        ]

        self._deterministic_bodies = [
            {
                "variant": "direct",
                "content": "Hi {contact_name},\n\nI noticed some performance issues on {business_name}'s website that could be impacting your customer experience. Quick fixes could improve your conversion rates.\n\nWould you be interested in a brief overview of what I found?\n\nBest regards,\n[Your name]",
                "approach": "problem-solution",
                "word_count": 42,
            },
            {
                "variant": "consultative",
                "content": "Hi {contact_name},\n\nHow important is your website's performance to {business_name}'s growth? I ran a quick analysis and found several opportunities that could help attract more customers.\n\nMight be worth a quick conversation?\n\nBest regards,\n[Your name]",
                "approach": "question-based",
                "word_count": 38,
            },
            {
                "variant": "value-first",
                "content": "Hi {contact_name},\n\nI was researching {industry} websites and {business_name} stood out. Your site has good foundation, but I spotted 3 specific improvements that could increase visitor engagement.\n\nHappy to share these insights if helpful.\n\nBest regards,\n[Your name]",
                "approach": "insight-sharing",
                "word_count": 45,
            },
        ]

    async def generate_email_content(
        self,
        business_id: str,
        business_data: dict[str, Any],
        contact_data: dict[str, Any] | None = None,
        assessment_data: dict[str, Any] | None = None,
        options: GenerationOptions | None = None,
    ) -> EmailGenerationResult:
        """
        Generate personalized email content (P2-030 main functionality)

        Args:
            business_id: Unique business identifier
            business_data: Business information (name, industry, location, etc.)
            contact_data: Contact information (name, email, etc.)
            assessment_data: Website assessment results
            options: Generation options and preferences

        Returns:
            EmailGenerationResult with subject lines and body variants
        """
        if options is None:
            options = GenerationOptions()

        start_time = datetime.now()

        # Determine generation mode
        if self.use_stubs or options.mode == GenerationMode.DETERMINISTIC:
            generation_mode = GenerationMode.DETERMINISTIC
        else:
            generation_mode = options.mode

        logger.info(f"Generating email content for {business_id} using {generation_mode} mode")

        try:
            # Generate subject lines (5 variants as required)
            subject_lines = await self._generate_subject_lines(
                business_data, contact_data, assessment_data, options, generation_mode
            )

            # Generate body content (3 variants as required)
            body_variants = await self._generate_body_content(
                business_data, contact_data, assessment_data, options, generation_mode
            )

            # Calculate generation time
            generation_time = (datetime.now() - start_time).total_seconds() * 1000

            result = EmailGenerationResult(
                subject_lines=subject_lines,
                body_variants=body_variants,
                generation_mode=generation_mode,
                business_id=business_id,
                generated_at=start_time,
                generation_time_ms=int(generation_time),
                metadata={
                    "business_name": business_data.get("name", ""),
                    "industry": business_data.get("industry", ""),
                    "personalization_level": options.personalization_level.value,
                    "assessment_included": assessment_data is not None,
                },
            )

            logger.info(
                f"Email content generated for {business_id}: {len(subject_lines)} subjects, {len(body_variants)} bodies"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to generate email content for {business_id}: {e}", exc_info=True)
            raise

    async def _generate_subject_lines(
        self,
        business_data: dict[str, Any],
        contact_data: dict[str, Any] | None,
        assessment_data: dict[str, Any] | None,
        options: GenerationOptions,
        mode: GenerationMode,
    ) -> list[GeneratedSubjectLine]:
        """Generate 5 subject line variants"""

        if mode == GenerationMode.DETERMINISTIC:
            return self._generate_deterministic_subjects(business_data)

        # Prepare context for LLM
        context = self._prepare_generation_context(business_data, contact_data, assessment_data, options)

        try:
            # Call Humanloop for subject line generation
            response = await self.humanloop_client.completion(
                prompt_slug="email_subject_generation_v2",
                inputs=context,
                environment="production" if not self.use_stubs else "testing",
            )

            # Parse LLM response
            llm_output = response.get("output", "")
            subject_data = self._parse_llm_json_response(llm_output)

            if "subject_lines" not in subject_data:
                raise ValueError("LLM response missing subject_lines field")

            subject_lines = []
            for item in subject_data["subject_lines"][:5]:  # Ensure max 5
                subject_line = GeneratedSubjectLine(
                    text=self._personalize_text(item["text"], business_data, contact_data),
                    approach=item.get("approach", "unknown"),
                    length=len(item["text"]),
                    personalization_tokens=self._extract_tokens(item["text"]),
                    spam_risk_score=self._calculate_spam_risk(item["text"]),
                    quality_score=self._calculate_quality_score(item["text"]),
                )
                subject_lines.append(subject_line)

            return subject_lines

        except Exception as e:
            logger.warning(f"LLM subject generation failed, falling back to deterministic: {e}")
            return self._generate_deterministic_subjects(business_data)

    async def _generate_body_content(
        self,
        business_data: dict[str, Any],
        contact_data: dict[str, Any] | None,
        assessment_data: dict[str, Any] | None,
        options: GenerationOptions,
        mode: GenerationMode,
    ) -> list[GeneratedBodyContent]:
        """Generate 3 body content variants"""

        if mode == GenerationMode.DETERMINISTIC:
            return self._generate_deterministic_bodies(business_data, contact_data)

        # Prepare context for LLM
        context = self._prepare_generation_context(business_data, contact_data, assessment_data, options)

        try:
            # Call Humanloop for body generation
            response = await self.humanloop_client.completion(
                prompt_slug="email_body_generation_v2",
                inputs=context,
                environment="production" if not self.use_stubs else "testing",
            )

            # Parse LLM response
            llm_output = response.get("output", "")
            body_data = self._parse_llm_json_response(llm_output)

            if "body_variants" not in body_data:
                raise ValueError("LLM response missing body_variants field")

            body_variants = []
            for item in body_data["body_variants"][:3]:  # Ensure max 3
                content = self._personalize_text(item["content"], business_data, contact_data)
                body_content = GeneratedBodyContent(
                    content=content,
                    variant=item.get("variant", "unknown"),
                    approach=item.get("approach", "unknown"),
                    word_count=len(content.split()),
                    personalization_tokens=self._extract_tokens(item["content"]),
                    readability_score=self._calculate_readability(content),
                )
                body_variants.append(body_content)

            return body_variants

        except Exception as e:
            logger.warning(f"LLM body generation failed, falling back to deterministic: {e}")
            return self._generate_deterministic_bodies(business_data, contact_data)

    def _generate_deterministic_subjects(self, business_data: dict[str, Any]) -> list[GeneratedSubjectLine]:
        """Generate deterministic subject lines for testing"""
        subjects = []
        for item in self._deterministic_subjects:
            text = self._personalize_text(item["text"], business_data, {})
            subject = GeneratedSubjectLine(
                text=text,
                approach=item["approach"],
                length=len(text),
                personalization_tokens=self._extract_tokens(item["text"]),
                spam_risk_score=0.1,  # Low risk for test data
                quality_score=0.8,  # Good quality for test data
            )
            subjects.append(subject)
        return subjects

    def _generate_deterministic_bodies(
        self, business_data: dict[str, Any], contact_data: dict[str, Any] | None
    ) -> list[GeneratedBodyContent]:
        """Generate deterministic body content for testing"""
        bodies = []
        for item in self._deterministic_bodies:
            content = self._personalize_text(item["content"], business_data, contact_data or {})
            body = GeneratedBodyContent(
                content=content,
                variant=item["variant"],
                approach=item["approach"],
                word_count=len(content.split()),
                personalization_tokens=self._extract_tokens(item["content"]),
                readability_score=0.8,  # Good readability for test data
            )
            bodies.append(body)
        return bodies

    def _prepare_generation_context(
        self,
        business_data: dict[str, Any],
        contact_data: dict[str, Any] | None,
        assessment_data: dict[str, Any] | None,
        options: GenerationOptions,
    ) -> dict[str, Any]:
        """Prepare context dictionary for LLM prompts"""

        # Basic business context
        context = {
            "business_name": business_data.get("name", business_data.get("business_name", "the business")),
            "industry": business_data.get("industry", business_data.get("category", "business")),
            "location": self._format_location(business_data),
            "contact_name": self._get_contact_name(contact_data),
        }

        # Assessment context
        if assessment_data and options.include_assessment_context:
            context.update(
                {
                    "assessment_context": self._format_assessment_context(assessment_data),
                    "issues_summary": self._format_issues_summary(assessment_data),
                    "findings_detail": self._format_findings_detail(assessment_data),
                }
            )
        else:
            context.update(
                {
                    "assessment_context": "",
                    "issues_summary": "performance optimization opportunities",
                    "findings_detail": "website performance and user experience improvements",
                }
            )

        return context

    def _format_location(self, business_data: dict[str, Any]) -> str:
        """Format business location from data"""
        location_data = business_data.get("location", {})
        if isinstance(location_data, dict):
            city = location_data.get("city", "")
            state = location_data.get("state", "")
            if city and state:
                return f"{city}, {state}"
            if city:
                return city
        elif isinstance(location_data, str):
            return location_data
        return business_data.get("city", "")

    def _get_contact_name(self, contact_data: dict[str, Any] | None) -> str:
        """Extract contact name from data"""
        if not contact_data:
            return "there"
        return contact_data.get("first_name") or contact_data.get("name") or contact_data.get("contact_name") or "there"

    def _format_assessment_context(self, assessment_data: dict[str, Any]) -> str:
        """Format assessment data for prompt context"""
        context_parts = []

        if "pagespeed" in assessment_data:
            ps_data = assessment_data["pagespeed"]
            score = ps_data.get("performance_score")
            if score is not None:
                context_parts.append(f"Performance Score: {score}/100")

        if "lighthouse" in assessment_data:
            lh_data = assessment_data["lighthouse"]
            for metric, value in lh_data.items():
                if isinstance(value, (int, float)) and metric.endswith("_score"):
                    context_parts.append(f"{metric.replace('_', ' ').title()}: {value}")

        return "\n".join(context_parts) if context_parts else ""

    def _format_issues_summary(self, assessment_data: dict[str, Any]) -> str:
        """Format issues summary for prompts"""
        issues = []

        # Performance issues
        if "pagespeed" in assessment_data:
            ps_data = assessment_data["pagespeed"]
            score = ps_data.get("performance_score")
            if score and score < 70:
                issues.append("slow page loading")

        # SEO issues
        if "lighthouse" in assessment_data:
            lh_data = assessment_data["lighthouse"]
            seo_score = lh_data.get("seo_score")
            if seo_score and seo_score < 90:
                issues.append("SEO optimization")

        # Accessibility issues
        if "lighthouse" in assessment_data:
            lh_data = assessment_data["lighthouse"]
            a11y_score = lh_data.get("accessibility_score")
            if a11y_score and a11y_score < 90:
                issues.append("accessibility improvements")

        return ", ".join(issues) if issues else "performance optimization opportunities"

    def _format_findings_detail(self, assessment_data: dict[str, Any]) -> str:
        """Format detailed findings for body content"""
        findings = []

        if "pagespeed" in assessment_data:
            ps_data = assessment_data["pagespeed"]
            score = ps_data.get("performance_score")
            if score:
                findings.append(f"Website loads with {score}/100 performance score")

        if "lighthouse" in assessment_data:
            lh_data = assessment_data["lighthouse"]
            for metric, score in lh_data.items():
                if isinstance(score, (int, float)) and metric.endswith("_score") and score < 90:
                    metric_name = metric.replace("_score", "").replace("_", " ").title()
                    findings.append(f"{metric_name}: {score}/100")

        return ". ".join(findings) if findings else "Several optimization opportunities identified"

    def _personalize_text(self, text: str, business_data: dict[str, Any], contact_data: dict[str, Any]) -> str:
        """Replace personalization tokens in text"""
        personalized = text

        # Business name
        business_name = business_data.get("name", business_data.get("business_name", "your business"))
        personalized = personalized.replace("{business_name}", business_name)

        # Contact name
        contact_name = self._get_contact_name(contact_data)
        personalized = personalized.replace("{contact_name}", contact_name)

        # Industry
        industry = business_data.get("industry", business_data.get("category", "business"))
        personalized = personalized.replace("{industry}", industry)

        # Location
        location = self._format_location(business_data)
        personalized = personalized.replace("{location}", location)

        return personalized

    def _extract_tokens(self, text: str) -> list[str]:
        """Extract personalization tokens from text"""
        import re

        token_pattern = r"\{([^}]+)\}"
        return re.findall(token_pattern, text)

    def _parse_llm_json_response(self, response_text: str) -> dict[str, Any]:
        """Parse JSON response from LLM, handling potential formatting issues"""
        try:
            # Try direct JSON parse first
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re

            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            # Fallback to empty structure
            logger.warning(f"Failed to parse LLM JSON response: {response_text[:200]}...")
            return {}

    def _calculate_spam_risk(self, text: str) -> float:
        """Calculate spam risk score (0-1, lower is better)"""
        spam_indicators = 0
        text_upper = text.upper()

        # Check for spam words
        spam_words = ["FREE", "URGENT", "LIMITED TIME", "ACT NOW", "CLICK HERE", "GUARANTEED"]
        for word in spam_words:
            if word in text_upper:
                spam_indicators += 1

        # Check for excessive punctuation
        if text.count("!") > 1:
            spam_indicators += 1

        # Check for all caps words
        words = text.split()
        caps_count = sum(1 for word in words if word.isupper() and len(word) > 2)
        if caps_count > 2:
            spam_indicators += 1

        return min(spam_indicators * 0.2, 1.0)

    def _calculate_quality_score(self, text: str) -> float:
        """Calculate subject line quality score (0-1, higher is better)"""
        score = 0.0

        # Length score (30-60 characters optimal)
        length = len(text)
        if 30 <= length <= 60:
            score += 0.4
        elif 20 <= length <= 70:
            score += 0.2

        # Personalization bonus
        if "{" in text or any(word.istitle() for word in text.split()):
            score += 0.3

        # Readability score
        words = text.split()
        if 3 <= len(words) <= 8:
            score += 0.3

        return min(score, 1.0)

    def _calculate_readability(self, text: str) -> float:
        """Calculate email body readability score (0-1, higher is better)"""
        words = text.split()
        sentences = text.count(".") + text.count("!") + text.count("?")

        if not words or not sentences:
            return 0.0

        # Simple readability metrics
        avg_words_per_sentence = len(words) / sentences
        avg_word_length = sum(len(word) for word in words) / len(words)

        # Optimal: 15-20 words/sentence, 4-6 chars/word
        sentence_score = 1.0 if 10 <= avg_words_per_sentence <= 25 else 0.5
        word_score = 1.0 if 3 <= avg_word_length <= 7 else 0.5

        return (sentence_score + word_score) / 2


# Convenience functions for backward compatibility and easy testing
async def generate_subject_lines(
    business_id: str, business_data: dict[str, Any], **kwargs
) -> list[GeneratedSubjectLine]:
    """Generate 5 subject line variants"""
    generator = EmailPersonalizationGenerator()
    result = await generator.generate_email_content(business_id, business_data, **kwargs)
    return result.subject_lines


async def generate_body_variants(
    business_id: str, business_data: dict[str, Any], **kwargs
) -> list[GeneratedBodyContent]:
    """Generate 3 body content variants"""
    generator = EmailPersonalizationGenerator()
    result = await generator.generate_email_content(business_id, business_data, **kwargs)
    return result.body_variants


async def generate_full_email_content(
    business_id: str, business_data: dict[str, Any], **kwargs
) -> EmailGenerationResult:
    """Generate complete email content (subjects + bodies)"""
    generator = EmailPersonalizationGenerator()
    return await generator.generate_email_content(business_id, business_data, **kwargs)
