"""
Simple test to verify Humanloop integration
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from d0_gateway.providers.humanloop import HumanloopClient


async def test_prompts():
    """Test loading all prompts"""
    client = HumanloopClient()

    prompts_to_test = [
        ("website_analysis_v1", "gpt-4", 4000),
        ("technical_analysis_v1", "gpt-4", 2000),
        ("industry_benchmark_v1", "gpt-4", 1200),
        ("quick_wins_v1", "gpt-4", 1000),
        ("website_screenshot_analysis_v1", "gpt-4o-mini", 500),
        ("performance_analysis_v1", "gpt-4o-mini", 500),
        ("email_generation_v1", "gpt-4o-mini", 300),
    ]

    print("Testing Humanloop prompt loading...")
    for prompt_slug, expected_model, expected_tokens in prompts_to_test:
        try:
            prompt = await client.load_prompt(prompt_slug)
            print(f"✅ {prompt_slug}: model={prompt['model']}, max_tokens={prompt['max_tokens']}")

            # Verify model and tokens match
            assert prompt["model"] == expected_model, f"Model mismatch for {prompt_slug}"
            assert prompt["max_tokens"] == expected_tokens, f"Token mismatch for {prompt_slug}"

        except Exception as e:
            print(f"❌ {prompt_slug}: {e}")
            raise

    print("\n✅ All prompts loaded successfully!")

    # Test formatting
    print("\nTesting prompt formatting...")
    template = "Business: {business_name}, Score: {performance_score:.2f}"
    inputs = {"business_name": "Acme Corp", "performance_score": 85.5}
    formatted = client._format_prompt(template, inputs)
    print(f"Formatted: {formatted}")
    assert formatted == "Business: Acme Corp, Score: 85.50"

    print("✅ Formatting test passed!")


if __name__ == "__main__":
    asyncio.run(test_prompts())
