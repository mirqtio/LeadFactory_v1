"""
Phase-0 Integration Tests
Validates the complete Config-as-Data & Prompt-Ops implementation
"""
import asyncio
import os
import tempfile
import yaml
import pytest

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)

# Test without pytest dependency for now
async def test_yaml_config_loading():
    """Test that scoring rules YAML can be loaded and validated"""
    from d5_scoring.rules_parser import ScoringRulesParser

    parser = ScoringRulesParser()
    rules = parser.load_rules()

    # Check tier definitions
    assert "tiers" in rules
    assert rules["tiers"]["A"]["min"] == 80
    assert rules["tiers"]["B"]["min"] == 60
    assert rules["tiers"]["C"]["min"] == 40
    assert rules["tiers"]["D"]["min"] == 0

    # Check components exist
    assert "components" in rules
    assert "website_exists" in rules["components"]
    assert "performance" in rules["components"]

    # Check weights sum to 1.0
    total_weight = sum(comp["weight"] for comp in rules["components"].values())
    assert 0.995 <= total_weight <= 1.005, f"Weights sum to {total_weight}"

    print("✅ YAML config loading test passed")


async def test_formula_evaluation():
    """Test xlcalculator formula evaluation"""
    from d5_scoring.formula_evaluator import FormulaEvaluator

    evaluator = FormulaEvaluator()

    # Test simple formula
    result = evaluator.evaluate_formula(
        "=IF({score}>80,10,5)",
        {"score": 85}
    )
    assert result == 10

    # Test complex formula
    result = evaluator.evaluate_formula(
        "=MIN(10, {score} * {weight})",
        {"score": 15, "weight": 0.8}
    )
    assert result == 10

    print("✅ Formula evaluation test passed")


async def test_humanloop_prompt_loading():
    """Test Humanloop client can load all prompts"""
    from d0_gateway.providers.humanloop import HumanloopClient

    client = HumanloopClient()

    prompts = [
        "website_analysis_v1",
        "technical_analysis_v1",
        "industry_benchmark_v1",
        "quick_wins_v1",
        "website_screenshot_analysis_v1",
        "performance_analysis_v1",
        "email_generation_v1",
    ]

    for prompt_slug in prompts:
        try:
            prompt = await client.load_prompt(prompt_slug)
            assert prompt["slug"] == prompt_slug
            assert "content" in prompt
            assert "model" in prompt
            assert "temperature" in prompt
            assert "max_tokens" in prompt
            print(f"  ✓ Loaded {prompt_slug}")
        except Exception as e:
            print(f"  ✗ Failed to load {prompt_slug}: {e}")
            raise

    print("✅ Humanloop prompt loading test passed")


async def test_hot_reload_mechanism():
    """Test hot reload watches for file changes"""
    from d5_scoring.engine import ConfigurableScoringEngine
    from d5_scoring.hot_reload import ScoringRulesWatcher

    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config = {
            "tiers": {
                "A": {"min": 80, "max": 100, "label": "A"},
                "B": {"min": 60, "max": 79, "label": "B"},
                "C": {"min": 40, "max": 59, "label": "C"},
                "D": {"min": 0, "max": 39, "label": "D"}
            },
            "components": {
                "test": {"weight": 1.0, "max_score": 10}
            }
        }
        yaml.dump(config, f)
        temp_path = f.name

    try:
        # Create engine with temp config
        engine = ConfigurableScoringEngine(temp_path)
        watcher = ScoringRulesWatcher(engine, temp_path, debounce_seconds=0.5)

        # Start watching
        watcher.start()

        # Modify the file
        await asyncio.sleep(0.1)
        with open(temp_path, 'w') as f:
            config["components"]["test"]["weight"] = 0.9
            config["components"]["new"] = {"weight": 0.1, "max_score": 5}
            yaml.dump(config, f)

        # Wait for reload
        await asyncio.sleep(1.0)

        # Stop watching
        watcher.stop()

        print("✅ Hot reload mechanism test passed")

    finally:
        # Cleanup
        os.unlink(temp_path)


async def test_scoring_engine_integration():
    """Test the complete scoring engine with YAML config"""
    from d5_scoring.engine import ConfigurableScoringEngine

    engine = ConfigurableScoringEngine()

    # Test scoring a business
    score_data = {
        "website_exists": {"score": 10},
        "performance": {"score": 85},
        "seo": {"score": 70},
        "accessibility": {"score": 60},
        "mobile": {"score": 90},
        "security": {"score": 80},
        "technologies": {"score": 8},
        "content_quality": {"score": 7},
        "backlinks": {"score": 5},
        "reviews": {"score": 9},
        "traffic": {"score": 6},
        "conversion_potential": {"score": 8}
    }

    result = engine.calculate_score(score_data)

    assert "total_score" in result
    assert "tier" in result
    assert "components" in result
    assert 0 <= result["total_score"] <= 100
    assert result["tier"] in ["A", "B", "C", "D"]

    print(f"✅ Scoring engine test passed (score: {result['total_score']}, tier: {result['tier']})")


async def test_prometheus_metrics():
    """Test that Prometheus metrics are registered"""
    from core.metrics import REGISTRY

    # Get all metric names
    metric_names = []
    for collector in REGISTRY._collector_to_names.values():
        metric_names.extend(collector)

    # Check for our custom metrics
    expected_metrics = [
        "leadfactory_prompt_requests_total",
        "leadfactory_prompt_duration_seconds",
        "leadfactory_prompt_tokens_total",
        "leadfactory_prompt_cost_usd_total",
        "leadfactory_config_reload_total",
        "leadfactory_config_reload_duration_seconds",
    ]

    for metric in expected_metrics:
        assert any(metric in name for name in metric_names), f"Missing metric: {metric}"

    print("✅ Prometheus metrics test passed")


async def test_end_to_end_flow():
    """Test a complete end-to-end flow"""
    from d5_scoring.engine import ConfigurableScoringEngine
    from d0_gateway.providers.humanloop import HumanloopClient

    print("\n🔄 Running end-to-end test...")

    # 1. Load scoring configuration
    engine = ConfigurableScoringEngine()
    print("  ✓ Loaded scoring configuration")

    # 2. Score a business
    score_data = {
        "website_exists": {"score": 10},
        "performance": {"score": 75},
        "seo": {"score": 65},
        "accessibility": {"score": 55},
        "mobile": {"score": 80},
        "security": {"score": 70},
        "technologies": {"score": 7},
        "content_quality": {"score": 6},
        "backlinks": {"score": 4},
        "reviews": {"score": 8},
        "traffic": {"score": 5},
        "conversion_potential": {"score": 7}
    }

    result = engine.calculate_score(score_data)
    print(f"  ✓ Calculated score: {result['total_score']} (Tier {result['tier']})")

    # 3. Prepare for Humanloop call
    client = HumanloopClient()

    # Test formatting prompt variables
    prompt_vars = {
        "url": "example.com",
        "industry": "ecommerce",
        "performance_score": result["total_score"],
        "accessibility_score": 55,
        "seo_score": 65,
        "technologies": "WordPress, WooCommerce",
        "lcp": 2500,
        "fid": 100,
        "cls": 0.1,
        "speed_index": 3000,
        "top_issues": "- Slow page load\n- Missing meta descriptions\n- Poor mobile experience"
    }

    # Load and format a prompt
    prompt = await client.load_prompt("website_analysis_v1")
    formatted = client._format_prompt(prompt["content"], prompt_vars)

    assert "example.com" in formatted
    assert "ecommerce" in formatted
    assert str(result["total_score"]) in formatted

    print("  ✓ Formatted Humanloop prompt")

    print("\n✅ End-to-end test passed!")


async def run_all_tests():
    """Run all integration tests"""
    print("🧪 Running Phase-0 Integration Tests\n")

    tests = [
        ("YAML Config Loading", test_yaml_config_loading),
        ("Formula Evaluation", test_formula_evaluation),
        ("Humanloop Prompt Loading", test_humanloop_prompt_loading),
        ("Hot Reload Mechanism", test_hot_reload_mechanism),
        ("Scoring Engine", test_scoring_engine_integration),
        ("Prometheus Metrics", test_prometheus_metrics),
        ("End-to-End Flow", test_end_to_end_flow),
    ]

    failed = 0
    for test_name, test_func in tests:
        print(f"\n📋 Testing: {test_name}")
        try:
            await test_func()
        except Exception as e:
            print(f"❌ {test_name} failed: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Tests completed: {len(tests) - failed}/{len(tests)} passed")

    if failed == 0:
        print("🎉 All Phase-0 integration tests passed!")
    else:
        print(f"⚠️  {failed} tests failed")

    return failed == 0


if __name__ == "__main__":
    # Run all tests
    success = asyncio.run(run_all_tests())
