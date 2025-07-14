"""
OpenAI API client implementation for LLM-powered insights
DEPRECATED: Use HumanloopClient instead for all LLM operations
"""
import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..base import BaseAPIClient


class OpenAIClient(BaseAPIClient):
    """OpenAI API client for GPT-4o-mini"""

    def __init__(self, api_key: Optional[str] = None):
        from core.config import get_settings
        settings = get_settings()
        
        # Check if OpenAI is enabled
        if not settings.enable_openai:
            raise RuntimeError("OpenAI client initialized but ENABLE_OPENAI=false")
            
        super().__init__(provider="openai", api_key=api_key)

    def _get_base_url(self) -> str:
        """Get OpenAI API base URL"""
        return "https://api.openai.com"

    def _get_headers(self) -> Dict[str, str]:
        """Get OpenAI API headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def get_rate_limit(self) -> Dict[str, int]:
        """Get OpenAI rate limit configuration"""
        return {
            "daily_limit": 10000,
            "daily_used": 0,  # Would be fetched from Redis in real implementation
            "burst_limit": 20,
            "window_seconds": 1,
        }

    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        """
        Calculate cost for OpenAI API operations

        GPT-4o-mini pricing (as of 2024):
        - Input: $0.15 per 1M tokens
        - Output: $0.60 per 1M tokens

        Estimated 1000 tokens per analysis = ~$0.0008
        """
        if operation.startswith("POST:/v1/chat/completions"):
            # Estimate based on typical website analysis
            estimated_input_tokens = 800  # Prompt + context
            estimated_output_tokens = 300  # Response

            input_cost = (
                Decimal(estimated_input_tokens) / Decimal("1000000")
            ) * Decimal("0.15")
            output_cost = (
                Decimal(estimated_output_tokens) / Decimal("1000000")
            ) * Decimal("0.60")

            return input_cost + output_cost
        else:
            # Other operations
            return Decimal("0.001")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a chat completion

        Args:
            messages: List of message objects
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Response format specification

        Returns:
            Dict containing the completion response
        """
        payload = {"model": model, "messages": messages, "temperature": temperature}

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if response_format:
            payload["response_format"] = response_format

        return await self.make_request("POST", "/v1/chat/completions", json=payload)

    async def analyze_website_performance(
        self,
        pagespeed_data: Dict[str, Any],
        business_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate AI insights from PageSpeed data

        Args:
            pagespeed_data: PageSpeed Insights results
            business_context: Additional business context

        Returns:
            Dict containing AI-generated insights and recommendations
        """
        # Extract key metrics from PageSpeed data
        lighthouse_result = pagespeed_data.get("lighthouseResult", {})
        categories = lighthouse_result.get("categories", {})
        audits = lighthouse_result.get("audits", {})

        # Build context for AI analysis
        context = {
            "performance_score": categories.get("performance", {}).get("score", 0),
            "seo_score": categories.get("seo", {}).get("score", 0),
            "accessibility_score": categories.get("accessibility", {}).get("score", 0),
            "best_practices_score": categories.get("best-practices", {}).get(
                "score", 0
            ),
            "url": pagespeed_data.get("id", "unknown"),
        }

        # Add Core Web Vitals
        if "largest-contentful-paint" in audits:
            context["lcp_score"] = audits["largest-contentful-paint"].get("score", 0)
            context["lcp_value"] = audits["largest-contentful-paint"].get(
                "displayValue", ""
            )

        if "cumulative-layout-shift" in audits:
            context["cls_score"] = audits["cumulative-layout-shift"].get("score", 0)
            context["cls_value"] = audits["cumulative-layout-shift"].get(
                "displayValue", ""
            )

        # Create prompt for AI analysis
        system_prompt = """You are a website performance expert. Analyze the provided PageSpeed Insights data and generate exactly 3 actionable recommendations in JSON format.

Each recommendation should have:
- issue: Brief description of the problem
- impact: Business impact (high/medium/low)
- effort: Implementation effort (high/medium/low)
- improvement: Specific action to take

Return only valid JSON array with exactly 3 recommendations."""

        user_prompt = f"""Website Performance Data:
URL: {context['url']}
Performance Score: {context['performance_score']:.2f}
SEO Score: {context['seo_score']:.2f}
Accessibility Score: {context['accessibility_score']:.2f}
Best Practices Score: {context['best_practices_score']:.2f}

{f"LCP: {context.get('lcp_value', 'N/A')} (Score: {context.get('lcp_score', 0):.2f})" if 'lcp_score' in context else ""}
{f"CLS: {context.get('cls_value', 'N/A')} (Score: {context.get('cls_score', 0):.2f})" if 'cls_score' in context else ""}

{f"Business Context: {business_context}" if business_context else ""}

Generate 3 specific recommendations to improve this website's performance and user experience."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            # Extract and parse the AI response
            ai_content = response["choices"][0]["message"]["content"]
            recommendations = json.loads(ai_content)

            return {
                "url": context["url"],
                "analysis_timestamp": pagespeed_data.get("analysisUTCTimestamp"),
                "performance_summary": {
                    "performance_score": context["performance_score"],
                    "seo_score": context["seo_score"],
                    "accessibility_score": context["accessibility_score"],
                    "best_practices_score": context["best_practices_score"],
                },
                "ai_recommendations": recommendations,
                "usage": {
                    "model": response.get("model"),
                    "tokens_used": response.get("usage", {}),
                },
            }

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse AI response as JSON: {e}")
            # Return fallback recommendations
            return {
                "url": context["url"],
                "error": "Failed to generate AI insights",
                "fallback_recommendations": self._get_fallback_recommendations(context),
            }

    async def generate_email_content(
        self,
        business_name: str,
        website_issues: List[Dict[str, Any]],
        recipient_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate personalized email content for outreach

        Args:
            business_name: Name of the business
            website_issues: List of identified website issues
            recipient_name: Name of the recipient (if known)

        Returns:
            Dict containing generated email content
        """
        # Prepare issues summary for AI
        issues_summary = []
        for issue in website_issues[:3]:  # Top 3 issues
            issues_summary.append(
                f"- {issue.get('issue', 'Unknown issue')} (Impact: {issue.get('impact', 'medium')})"
            )

        issues_text = "\n".join(issues_summary)

        system_prompt = """You are a professional digital marketing consultant. Write a brief, personalized email to a business owner about their website's performance issues.

The email should be:
- Professional but friendly
- Focused on business benefits
- Include a clear call-to-action
- No more than 150 words
- Not pushy or sales-heavy

Return JSON with 'subject' and 'body' fields."""

        user_prompt = f"""Business: {business_name}
{f"Recipient: {recipient_name}" if recipient_name else ""}

Key Website Issues Found:
{issues_text}

Write a personalized email offering to help improve their website performance."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = await self.chat_completion(
            messages=messages,
            temperature=0.7,
            max_tokens=300,
            response_format={"type": "json_object"},
        )

        try:
            ai_content = response["choices"][0]["message"]["content"]
            email_content = json.loads(ai_content)

            return {
                "business_name": business_name,
                "recipient_name": recipient_name,
                "email_subject": email_content.get(
                    "subject", "Website Performance Insights"
                ),
                "email_body": email_content.get("body", ""),
                "issues_count": len(website_issues),
                "generated_at": response.get("created"),
                "usage": response.get("usage", {}),
            }

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse email content JSON: {e}")
            return {
                "business_name": business_name,
                "error": "Failed to generate email content",
                "fallback_subject": f"Website Performance Report for {business_name}",
                "fallback_body": f"Hi{f' {recipient_name}' if recipient_name else ''},\n\nI noticed some opportunities to improve {business_name}'s website performance. Would you be interested in a free analysis?\n\nBest regards",
            }

    def _get_fallback_recommendations(
        self, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate fallback recommendations when AI fails"""
        recommendations = []

        if context.get("performance_score", 1) < 0.7:
            recommendations.append(
                {
                    "issue": "Poor website performance score",
                    "impact": "high",
                    "effort": "medium",
                    "improvement": "Optimize images and enable compression",
                }
            )

        if context.get("seo_score", 1) < 0.8:
            recommendations.append(
                {
                    "issue": "SEO optimization needed",
                    "impact": "high",
                    "effort": "low",
                    "improvement": "Add meta descriptions and optimize page titles",
                }
            )

        if context.get("accessibility_score", 1) < 0.8:
            recommendations.append(
                {
                    "issue": "Accessibility improvements needed",
                    "impact": "medium",
                    "effort": "medium",
                    "improvement": "Add alt text to images and improve color contrast",
                }
            )

        return recommendations[:3]  # Return max 3
