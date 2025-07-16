"""
LLM Heuristic Assessor - P1-040

GPT-4 powered content analysis for comprehensive website usability and conversion heuristics.
Analyzes websites for UVP clarity, contact info completeness, CTA effectiveness, and other
key conversion factors.

PRP P1-040 Requirements:
- UVP Clarity Score (0-100)
- Contact Info Completeness (0-100) 
- CTA Clarity Score (0-100)
- Social Proof Presence (0-100)
- Readability Score (0-100)
- Mobile Viewport Detection (boolean)
- Intrusive Popup Detection (boolean)
- Cost: ~$0.03 per audit
- Timeout handling
- Structured output with insights and recommendations
"""
import json
from typing import Any, Dict

from core.config import settings
from core.logging import get_logger
from d0_gateway.factory import create_client
from d0_gateway.providers.humanloop import HumanloopClient
from d3_assessment.assessors.base import AssessmentResult, BaseAssessor
from d3_assessment.exceptions import AssessmentError, AssessmentTimeoutError
from d3_assessment.models import AssessmentType

logger = get_logger(__name__, domain="d3")


class LLMHeuristicAssessor(BaseAssessor):
    """
    LLM-powered heuristic assessment for website usability and conversion optimization

    Uses GPT-4 via Humanloop to analyze websites for:
    - Value proposition clarity
    - Contact information completeness
    - Call-to-action effectiveness
    - Social proof presence
    - Content readability
    - Mobile viewport optimization
    - Intrusive popup detection
    """

    def __init__(self):
        super().__init__()
        self.timeout = 30  # 30 second timeout for LLM analysis
        self._client = None

    @property
    def assessment_type(self) -> AssessmentType:
        return AssessmentType.AI_INSIGHTS

    def _get_client(self) -> HumanloopClient:
        """Get or create Humanloop client"""
        if not self._client:
            self._client = create_client("humanloop")
        return self._client

    async def assess(self, url: str, business_data: Dict[str, Any]) -> AssessmentResult:
        """
        Perform LLM heuristic assessment of website

        Args:
            url: Website URL to assess
            business_data: Business information and website content data

        Returns:
            AssessmentResult with heuristic scores and detailed analysis
        """
        try:
            # Check if LLM audit is enabled
            if not settings.get("ENABLE_LLM_AUDIT", False) and not settings.use_stubs:
                return AssessmentResult(
                    assessment_type=self.assessment_type,
                    status="skipped",
                    error_message="LLM audit disabled via feature flag",
                )

            # Extract website content from business data or previous assessments
            website_content = self._extract_website_content(business_data)
            performance_data = self._extract_performance_data(business_data)

            # Check if we have meaningful content
            has_content = (
                website_content.get("title", "")
                or website_content.get("meta_description", "")
                or website_content.get("paragraphs", [])
                or website_content.get("headings", [])
            )

            if not has_content:
                return AssessmentResult(
                    assessment_type=self.assessment_type,
                    status="failed",
                    error_message="No website content available for heuristic analysis",
                )

            # Get Humanloop client
            client = self._get_client()

            # Prepare inputs for the heuristic audit prompt
            inputs = {
                "website_url": url,
                "business_type": business_data.get("business_type", "Unknown"),
                "industry": business_data.get("industry", "General"),
                "website_content": json.dumps(website_content, indent=2),
                "performance_data": json.dumps(performance_data, indent=2),
            }

            # Call Humanloop with heuristic audit prompt
            response = await client.completion(
                prompt_slug="website_heuristic_audit_v1",
                inputs=inputs,
                metadata={"business_id": business_data.get("id"), "assessment_type": "heuristic_audit", "url": url},
            )

            if not response or "output" not in response:
                raise AssessmentError("Invalid response from LLM heuristic audit")

            # Parse the JSON response
            content = response["output"]
            try:
                heuristic_data = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from the response
                heuristic_data = self._extract_json_from_text(content)

            # Validate and extract heuristic scores
            heuristic_scores = heuristic_data.get("heuristic_scores", {})
            detailed_analysis = heuristic_data.get("detailed_analysis", {})
            priority_recommendations = heuristic_data.get("priority_recommendations", [])
            overall_assessment = heuristic_data.get("overall_assessment", {})

            # Validate required scores are present and within range
            validated_scores = self._validate_heuristic_scores(heuristic_scores)

            # Calculate cost from actual token usage
            usage = response.get("usage", {})
            cost = self._calculate_actual_cost(usage)

            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    "heuristic_scores": validated_scores,
                    "detailed_analysis": detailed_analysis,
                    "priority_recommendations": priority_recommendations[:5],  # Limit to top 5
                    "overall_assessment": overall_assessment,
                    "llm_metadata": {
                        "model_used": response.get("model", "gpt-4o-mini"),
                        "prompt_slug": "website_heuristic_audit_v1",
                        "total_tokens": usage.get("total_tokens", 0),
                        "completion_id": response.get("id"),
                    },
                },
                metrics={
                    "uvp_clarity_score": validated_scores.get("uvp_clarity_score", 0),
                    "contact_info_completeness": validated_scores.get("contact_info_completeness", 0),
                    "cta_clarity_score": validated_scores.get("cta_clarity_score", 0),
                    "social_proof_presence": validated_scores.get("social_proof_presence", 0),
                    "readability_score": validated_scores.get("readability_score", 0),
                    "mobile_viewport_detection": validated_scores.get("mobile_viewport_detection", False),
                    "intrusive_popup_detection": validated_scores.get("intrusive_popup_detection", False),
                    "conversion_readiness": overall_assessment.get("conversion_readiness", "unknown"),
                    "recommendations_count": len(priority_recommendations),
                    "total_tokens": usage.get("total_tokens", 0),
                    "api_cost_usd": cost,
                },
                cost=cost,
            )

        except AssessmentTimeoutError:
            raise
        except Exception as e:
            logger.error(f"LLM heuristic assessment failed for {url}: {e}")

            # Return minimal result with error for graceful degradation
            return AssessmentResult(
                assessment_type=self.assessment_type,
                status="completed",
                data={
                    "heuristic_scores": self._get_default_scores(),
                    "detailed_analysis": {},
                    "priority_recommendations": [
                        {
                            "category": "System",
                            "issue": "LLM heuristic analysis unavailable",
                            "recommendation": "Manual review recommended",
                            "impact": "low",
                            "effort": "low",
                        }
                    ],
                    "overall_assessment": {
                        "conversion_readiness": "unknown",
                        "user_experience_quality": "requires_analysis",
                        "key_strengths": [],
                        "critical_issues": ["Analysis failed"],
                        "next_steps": ["Retry analysis or perform manual review"],
                    },
                    "error": str(e),
                },
                error_message=f"LLM heuristic audit error: {str(e)}",
                cost=0.0,
            )

    def _extract_website_content(self, business_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract website content from business data or assessments"""
        content = {}

        # Try to get content from BeautifulSoup assessment
        assessments = business_data.get("assessments", {})
        bsoup_data = assessments.get("bsoup_json", {})

        if isinstance(bsoup_data, dict):
            # Safely extract lists and handle potential None values
            headings = bsoup_data.get("headings", [])
            paragraphs = bsoup_data.get("paragraphs", [])
            links = bsoup_data.get("links", [])
            forms = bsoup_data.get("forms", [])
            images = bsoup_data.get("images", [])
            scripts = bsoup_data.get("scripts", [])
            styles = bsoup_data.get("styles", [])

            # Ensure they're lists before slicing
            if not isinstance(headings, list):
                headings = []
            if not isinstance(paragraphs, list):
                paragraphs = []
            if not isinstance(links, list):
                links = []
            if not isinstance(forms, list):
                forms = []
            if not isinstance(images, list):
                images = []
            if not isinstance(scripts, list):
                scripts = []
            if not isinstance(styles, list):
                styles = []

            content.update(
                {
                    "title": bsoup_data.get("title", ""),
                    "meta_description": bsoup_data.get("meta_description", ""),
                    "headings": headings,
                    "paragraphs": paragraphs[:10],  # Limit to first 10 paragraphs
                    "links": links[:20],  # Limit to first 20 links
                    "forms": forms,
                    "images": len(images),
                    "scripts": len(scripts),
                    "styles": len(styles),
                }
            )

        # Add any direct content from business data
        if "website_content" in business_data:
            website_content = business_data["website_content"]
            if isinstance(website_content, dict):
                content.update(website_content)

        return content

    def _extract_performance_data(self, business_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract performance data from assessments"""
        performance = {}

        assessments = business_data.get("assessments", {})

        # PageSpeed data
        pagespeed_data = assessments.get("pagespeed_data", {})
        if isinstance(pagespeed_data, dict):
            performance.update(
                {
                    "performance_score": pagespeed_data.get("performance_score", 0),
                    "accessibility_score": pagespeed_data.get("accessibility_score", 0),
                    "best_practices_score": pagespeed_data.get("best_practices_score", 0),
                    "seo_score": pagespeed_data.get("seo_score", 0),
                    "largest_contentful_paint": pagespeed_data.get("largest_contentful_paint", 0),
                    "first_input_delay": pagespeed_data.get("first_input_delay", 0),
                    "cumulative_layout_shift": pagespeed_data.get("cumulative_layout_shift", 0),
                }
            )

        # Add any other performance metrics from business data
        for key in ["performance_score", "accessibility_score", "seo_score"]:
            if key in business_data:
                performance[key] = business_data[key]

        return performance

    def _validate_heuristic_scores(self, scores: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clamp heuristic scores to expected ranges"""
        validated = {}

        # Numeric scores (0-100)
        numeric_scores = [
            "uvp_clarity_score",
            "contact_info_completeness",
            "cta_clarity_score",
            "social_proof_presence",
            "readability_score",
        ]

        for score_name in numeric_scores:
            score_value = scores.get(score_name, 0)
            try:
                score_int = int(float(score_value))
                validated[score_name] = max(0, min(100, score_int))
            except (ValueError, TypeError):
                validated[score_name] = 0

        # Boolean scores
        validated["mobile_viewport_detection"] = bool(scores.get("mobile_viewport_detection", False))
        validated["intrusive_popup_detection"] = bool(scores.get("intrusive_popup_detection", False))

        return validated

    def _get_default_scores(self) -> Dict[str, Any]:
        """Get default scores when analysis fails"""
        return {
            "uvp_clarity_score": 0,
            "contact_info_completeness": 0,
            "cta_clarity_score": 0,
            "social_proof_presence": 0,
            "readability_score": 0,
            "mobile_viewport_detection": False,
            "intrusive_popup_detection": False,
        }

    def _extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """Try to extract JSON from text response"""
        import re

        # Look for JSON-like structure
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except Exception:
                pass

        # Return fallback structure if extraction fails
        return {
            "heuristic_scores": self._get_default_scores(),
            "detailed_analysis": {},
            "priority_recommendations": [
                {
                    "category": "Analysis",
                    "issue": "Failed to parse LLM response",
                    "recommendation": "Retry analysis or review manually",
                    "impact": "low",
                    "effort": "low",
                }
            ],
            "overall_assessment": {
                "conversion_readiness": "unknown",
                "user_experience_quality": "requires_analysis",
                "key_strengths": [],
                "critical_issues": ["Response parsing failed"],
                "next_steps": ["Retry with different parameters"],
            },
        }

    def _calculate_actual_cost(self, usage: Dict[str, Any]) -> float:
        """Calculate actual cost based on token usage"""
        # GPT-4o-mini pricing (as of 2024)
        input_tokens = usage.get("prompt_tokens", 800)  # Default estimate
        output_tokens = usage.get("completion_tokens", 500)  # Default estimate

        # $0.15 per 1M input tokens, $0.60 per 1M output tokens
        input_cost = (input_tokens / 1_000_000) * 0.15
        output_cost = (output_tokens / 1_000_000) * 0.60

        total_cost = input_cost + output_cost

        # Ensure we're within expected range (~$0.03 per audit)
        return min(total_cost, 0.10)  # Cap at $0.10 for safety

    def calculate_cost(self) -> float:
        """Calculate estimated cost for LLM heuristic assessment"""
        return 0.03  # Estimated $0.03 per audit as per PRP requirements

    def is_available(self) -> bool:
        """Check if LLM heuristic assessor is available"""
        # Available if we have Humanloop configured or using stubs
        return (bool(settings.humanloop_api_key) or settings.use_stubs) and settings.get("ENABLE_LLM_AUDIT", False)

    def get_timeout(self) -> int:
        """Get timeout in seconds for LLM assessment"""
        return self.timeout
