"""
Run all PRD v1.2 smoke tests
Verifies all external APIs are working before running full pipeline
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.config import settings


async def run_all_smoke_tests():
    """Run all smoke tests and report results"""
    print("=" * 60)
    print("PRD v1.2 SMOKE TESTS")
    print("=" * 60)

    results = {}

    # Test 1: Yelp API
    print("\n1. Testing Yelp API...")
    if settings.yelp_api_key:
        try:
            from test_smoke_yelp import TestYelpSmoke

            test = TestYelpSmoke()
            await test.test_yelp_search()
            await test.test_yelp_rate_limit()
            results["yelp"] = "✓ PASS"
        except Exception as e:
            results["yelp"] = f"✗ FAIL: {e}"
    else:
        results["yelp"] = "⚠️  SKIP: No API key"

    # Test 2: Hunter.io API
    print("\n2. Testing Hunter.io API...")
    if settings.hunter_api_key:
        try:
            from test_smoke_hunter import TestHunterSmoke

            test = TestHunterSmoke()
            await test.test_hunter_domain_search()
            await test.test_hunter_cost_tracking()
            results["hunter"] = "✓ PASS"
        except Exception as e:
            results["hunter"] = f"✗ FAIL: {e}"
    else:
        results["hunter"] = "⚠️  SKIP: No API key"

    # Test 3: SEMrush API
    print("\n3. Testing SEMrush API...")
    if settings.semrush_api_key:
        try:
            from test_smoke_semrush import TestSEMrushSmoke

            test = TestSEMrushSmoke()
            await test.test_semrush_domain_overview()
            await test.test_semrush_cost_tracking()
            results["semrush"] = "✓ PASS"
        except Exception as e:
            results["semrush"] = f"✗ FAIL: {e}"
    else:
        results["semrush"] = "⚠️  SKIP: No API key"

    # Test 4: ScreenshotOne API
    print("\n4. Testing ScreenshotOne API...")
    if settings.screenshotone_key:
        try:
            from test_smoke_screenshotone import TestScreenshotOneSmoke

            test = TestScreenshotOneSmoke()
            await test.test_screenshot_capture()
            await test.test_screenshot_cost_tracking()
            results["screenshotone"] = "✓ PASS"
        except Exception as e:
            results["screenshotone"] = f"✗ FAIL: {e}"
    else:
        results["screenshotone"] = "⚠️  SKIP: No API key"

    # Test 5: OpenAI Vision API
    print("\n5. Testing OpenAI GPT-4o Vision API...")
    if settings.openai_api_key:
        try:
            from test_smoke_openai_vision import TestOpenAIVisionSmoke

            test = TestOpenAIVisionSmoke()
            await test.test_vision_basic()
            await test.test_vision_cost_tracking()
            results["openai_vision"] = "✓ PASS"
        except Exception as e:
            results["openai_vision"] = f"✗ FAIL: {e}"
    else:
        results["openai_vision"] = "⚠️  SKIP: No API key"

    # Test 6: Google Business Profile API
    print("\n6. Testing Google Business Profile API...")
    if settings.google_api_key:
        try:
            from test_smoke_gbp import TestGBPSmoke

            test = TestGBPSmoke()
            await test.test_gbp_find_place()
            await test.test_gbp_cost_tracking()
            results["gbp"] = "✓ PASS"
        except Exception as e:
            results["gbp"] = f"✗ FAIL: {e}"
    else:
        results["gbp"] = "⚠️  SKIP: No API key"

    # Test 7: Data Axle API (optional)
    print("\n7. Testing Data Axle API (optional)...")
    if settings.data_axle_api_key:
        try:
            from test_smoke_data_axle import TestDataAxleSmoke

            test = TestDataAxleSmoke()
            await test.test_dataaxle_enrich()
            results["data_axle"] = "✓ PASS"
        except Exception as e:
            results["data_axle"] = f"✗ FAIL: {e}"
    else:
        results["data_axle"] = "⚠️  SKIP: No API key (optional)"

    # Summary
    print("\n" + "=" * 60)
    print("SMOKE TEST RESULTS")
    print("=" * 60)

    for api, result in results.items():
        print(f"{api:20} {result}")

    # Check if all required APIs passed
    required_apis = [
        "yelp",
        "hunter",
        "semrush",
        "screenshotone",
        "openai_vision",
        "gbp",
    ]
    failed_required = [
        api for api in required_apis if results.get(api, "").startswith("✗")
    ]

    print("\n" + "=" * 60)
    if failed_required:
        print(f"❌ FAILED: {len(failed_required)} required API(s) failed")
        print(f"   Failed APIs: {', '.join(failed_required)}")
        return False
    else:
        passed = sum(1 for r in results.values() if r.startswith("✓"))
        print(f"✅ PASSED: All required APIs working ({passed} APIs tested)")
        return True


def check_environment():
    """Check environment configuration"""
    print("\nEnvironment Configuration:")
    print("-" * 30)
    print(f"Yelp API Key:        {'✓' if settings.yelp_api_key else '✗'}")
    print(f"Hunter API Key:      {'✓' if settings.hunter_api_key else '✗'}")
    print(f"SEMrush API Key:     {'✓' if settings.semrush_api_key else '✗'}")
    print(f"ScreenshotOne Key:   {'✓' if settings.screenshotone_key else '✗'}")
    print(f"OpenAI API Key:      {'✓' if settings.openai_api_key else '✗'}")
    print(f"Google API Key:      {'✓' if settings.google_api_key else '✗'}")
    print(
        f"Data Axle API Key:   {'✓' if settings.data_axle_api_key else '✗'} (optional)"
    )
    print(f"\nMax Daily Yelp Calls: {settings.max_daily_yelp_calls}")
    print(f"Max Daily Emails:     {settings.max_daily_emails}")


if __name__ == "__main__":
    check_environment()

    # Run smoke tests
    success = asyncio.run(run_all_smoke_tests())

    # Exit with appropriate code
    sys.exit(0 if success else 1)
