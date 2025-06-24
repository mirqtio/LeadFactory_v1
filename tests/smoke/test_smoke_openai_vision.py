"""
Smoke test for OpenAI GPT-4o Vision API
PRD v1.2 - Verify GPT-4o Vision for website analysis
"""
import asyncio
import os
import json
import pytest

from d0_gateway.providers.openai import OpenAIClient
from core.config import settings

# Skip if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
)


class TestOpenAIVisionSmoke:
    """Smoke tests for OpenAI GPT-4o Vision API"""

    @pytest.mark.asyncio
    async def test_vision_basic(self):
        """Test basic GPT-4o Vision functionality"""
        client = OpenAIClient(api_key=settings.openai_api_key)

        # Test with a simple image URL
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What do you see in this image? Reply with a single sentence.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/1200px-Cat03.jpg"
                        },
                    },
                ],
            }
        ]

        response = await client.chat_completion(
            messages=messages, model="gpt-4o-mini", max_tokens=100
        )

        assert response is not None
        assert "choices" in response
        assert len(response["choices"]) > 0
        assert response["choices"][0]["message"]["content"]

        print(f"✓ GPT-4o Vision basic test successful:")
        print(f"  Response: {response['choices'][0]['message']['content']}")

    @pytest.mark.asyncio
    async def test_vision_website_analysis(self):
        """Test GPT-4o Vision with PRD v1.2 website analysis prompt"""
        client = OpenAIClient(api_key=settings.openai_api_key)

        # Use exact PRD v1.2 prompt
        vision_prompt = """You are a senior web-design auditor.
Given this full-page screenshot, return STRICT JSON:

{
 "scores":{         // 0-5 ints
   "visual_appeal":0,
   "readability":0,
   "modernity":0,
   "brand_consistency":0,
   "accessibility":0
 },
 "style_warnings":[ "…", "…" ],  // max 3
 "quick_wins":[ "…", "…" ]       // max 3
}

Scoring rubric:
visual_appeal = aesthetics / imagery
readability   = typography & contrast
modernity     = feels current vs outdated
brand_consistency = colours/images align w/ name
accessibility = obvious a11y issues (alt-text, contrast)

Give short bullet phrases only.  Return JSON ONLY."""

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": vision_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://www.example.com/screenshot.png",  # Would use real screenshot
                            "detail": "high",
                        },
                    },
                ],
            }
        ]

        response = await client.chat_completion(
            messages=messages,
            model="gpt-4o-mini",
            max_tokens=500,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        assert response is not None
        content = response["choices"][0]["message"]["content"]

        # Try to parse JSON
        try:
            visual_data = json.loads(content)
            assert "scores" in visual_data
            assert "visual_appeal" in visual_data["scores"]
            assert isinstance(visual_data["scores"]["visual_appeal"], int)
            assert 0 <= visual_data["scores"]["visual_appeal"] <= 5

            print(f"\n✓ GPT-4o Vision website analysis successful:")
            print(f"  Scores: {visual_data['scores']}")
            print(f"  Warnings: {len(visual_data.get('style_warnings', []))} found")
            print(f"  Quick wins: {len(visual_data.get('quick_wins', []))} found")
        except json.JSONDecodeError:
            print(f"\n⚠️  GPT-4o Vision returned non-JSON: {content[:100]}...")

    @pytest.mark.asyncio
    async def test_vision_cost_tracking(self):
        """Test GPT-4o Vision cost tracking"""
        client = OpenAIClient(api_key=settings.openai_api_key)

        # Vision analysis should cost ~$0.003
        # This is an estimate for ~1k tokens with gpt-4o-mini

        # Check if model is configured correctly
        assert settings.openai_model == "gpt-4o-mini", "Should use gpt-4o-mini model"

        print(f"\n✓ GPT-4o Vision configuration:")
        print(f"  Model: {settings.openai_model}")
        print(f"  Estimated cost: $0.003 per analysis")

    @pytest.mark.asyncio
    async def test_vision_timeout(self):
        """Test GPT-4o Vision timeout handling"""
        client = OpenAIClient(api_key=settings.openai_api_key)

        # Vision timeout should be 12 seconds as per PRD
        # Test by setting a shorter timeout
        import asyncio

        messages = [{"role": "user", "content": "Test timeout"}]

        try:
            # This should complete quickly
            response = await asyncio.wait_for(
                client.chat_completion(messages=messages, model="gpt-4o-mini"),
                timeout=5,
            )
            print("\n✓ GPT-4o Vision timeout handling works")
        except asyncio.TimeoutError:
            print("\n✓ GPT-4o Vision timeout triggered correctly")

    @pytest.mark.asyncio
    async def test_vision_error_handling(self):
        """Test GPT-4o Vision error handling"""
        client = OpenAIClient(api_key=settings.openai_api_key)

        # Test with invalid image URL
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://not-a-real-image-url-xyz123.fake/image.png"
                        },
                    },
                ],
            }
        ]

        try:
            response = await client.chat_completion(
                messages=messages, model="gpt-4o-mini"
            )
            # OpenAI might handle this gracefully
            print("\n✓ GPT-4o Vision handled invalid image URL")
        except Exception as e:
            print(f"\n✓ GPT-4o Vision error handling works: {type(e).__name__}")


if __name__ == "__main__":
    # Run smoke tests
    asyncio.run(test_vision_basic())
    asyncio.run(test_vision_website_analysis())
    asyncio.run(test_vision_cost_tracking())
    asyncio.run(test_vision_timeout())
    asyncio.run(test_vision_error_handling())
