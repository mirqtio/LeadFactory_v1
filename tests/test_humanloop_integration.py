"""
Test Humanloop integration and prompt loading
"""

import pytest

# Mark entire module as integration test, slow for CI optimization and xfail for Phase 0.5
pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.xfail(reason="Humanloop integration is a Phase 0.5 feature"),
]
from pathlib import Path  # noqa: E402

from d0_gateway.providers.humanloop import HumanloopClient  # noqa: E402


@pytest.mark.asyncio
async def test_load_prompt():
    """Test loading prompt from markdown file"""
    client = HumanloopClient()

    # Test loading website analysis prompt
    prompt = await client.load_prompt("website_analysis_v1")

    assert prompt["slug"] == "website_analysis_v1"
    assert prompt["model"] == "gpt-4"
    assert prompt["temperature"] == 0.1
    assert prompt["max_tokens"] == 4000
    assert prompt["supports_vision"] is False
    assert "You are an expert web analyst" in prompt["content"]


@pytest.mark.asyncio
async def test_load_vision_prompt():
    """Test loading vision prompt"""
    client = HumanloopClient()

    prompt = await client.load_prompt("website_screenshot_analysis_v1")

    assert prompt["slug"] == "website_screenshot_analysis_v1"
    assert prompt["model"] == "gpt-4o-mini"
    assert prompt["supports_vision"] is True
    assert "web-design auditor" in prompt["content"]


@pytest.mark.asyncio
async def test_prompt_formatting():
    """Test prompt variable formatting"""
    client = HumanloopClient()

    # Test simple variable replacement
    template = "Hello {name}, your score is {score}."
    inputs = {"name": "John", "score": 95}

    formatted = client._format_prompt(template, inputs)
    assert formatted == "Hello John, your score is 95."

    # Test conditional sections
    template = "Results: {results_section}"
    inputs = {"results_section": "Score: 100", "results": True}

    formatted = client._format_prompt(template, inputs)
    assert formatted == "Results: Score: 100"


@pytest.mark.asyncio
async def test_list_available_prompts():
    """Test that all expected prompts are available"""
    prompts_dir = Path(__file__).parent.parent / "prompts"
    expected_prompts = [
        "website_analysis_v1",
        "technical_analysis_v1",
        "industry_benchmark_v1",
        "quick_wins_v1",
        "website_screenshot_analysis_v1",
        "performance_analysis_v1",
        "email_generation_v1",
    ]

    for prompt_slug in expected_prompts:
        prompt_file = prompts_dir / f"{prompt_slug}.md"
        assert prompt_file.exists(), f"Missing prompt file: {prompt_slug}.md"


if __name__ == "__main__":
    import asyncio

    # Run basic tests
    asyncio.run(test_load_prompt())
    asyncio.run(test_load_vision_prompt())
    asyncio.run(test_list_available_prompts())
    print("✅ All Humanloop integration tests passed!")
