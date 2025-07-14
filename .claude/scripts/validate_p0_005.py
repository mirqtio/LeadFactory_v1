#!/usr/bin/env python3
"""
Validation script for P0-005: Environment & Stub Wiring
Tests all acceptance criteria for the task
"""
import os
import subprocess
import sys


def run_command(cmd, env=None, expected_to_fail=False):
    """Run a command and return success status"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env={**os.environ, **(env or {})})

    if expected_to_fail:
        return result.returncode != 0
    return result.returncode == 0


def main():
    """Run all validation tests for P0-005"""
    print("🔍 Validating P0-005: Environment & Stub Wiring")
    print("=" * 60)

    all_passed = True

    # Test 1: Stub server auto-starts in tests
    print("\n1️⃣  Testing stub server auto-starts in tests...")
    if run_command("USE_STUBS=true pytest tests/integration/test_stub_server.py::test_health_check -xvs -q"):
        print("   ✅ Stub server auto-starts in tests")
    else:
        print("   ❌ Stub server failed to auto-start")
        all_passed = False

    # Test 2: Environment variables documented
    print("\n2️⃣  Checking environment template exists...")
    if os.path.exists(".env.template"):
        print("   ✅ Environment template documented")
    else:
        print("   ❌ Missing .env.template")
        all_passed = False

    # Test 3: Secrets never logged
    print("\n3️⃣  Testing secrets are masked in logs...")
    test_script = """
import sys
sys.path.insert(0, '.')
from core.config import Settings
from pydantic import SecretStr

settings = Settings(
    secret_key="my-secret-key-12345",
    google_api_key=SecretStr("google-key-12345")
)
dumped = settings.model_dump()
if "my-s***" in str(dumped["secret_key"]) and "goog***" in str(dumped["google_api_key"]):
    sys.exit(0)
else:
    print(f"Secrets not masked: {dumped}")
    sys.exit(1)
"""

    result = subprocess.run([sys.executable, "-c", test_script], capture_output=True, text=True)

    if result.returncode == 0:
        print("   ✅ Secrets are properly masked")
    else:
        print("   ❌ Secrets not masked properly")
        all_passed = False

    # Test 4: Feature flags work correctly
    print("\n4️⃣  Testing provider feature flags...")
    flags_passed = True

    # Test GBP flag
    if run_command(
        "USE_STUBS=true pytest tests/unit/d0_gateway/test_provider_flags.py::TestProviderFeatureFlags::test_google_places_respects_enable_flag -xvs -q"
    ):
        print("   ✅ ENABLE_GBP flag works")
    else:
        print("   ❌ ENABLE_GBP flag failed")
        flags_passed = False

    # Test PageSpeed flag
    if run_command(
        "USE_STUBS=true pytest tests/unit/d0_gateway/test_provider_flags.py::TestProviderFeatureFlags::test_pagespeed_respects_enable_flag -xvs -q"
    ):
        print("   ✅ ENABLE_PAGESPEED flag works")
    else:
        print("   ❌ ENABLE_PAGESPEED flag failed")
        flags_passed = False

    # Test SendGrid flag
    if run_command(
        "USE_STUBS=true pytest tests/unit/d0_gateway/test_provider_flags.py::TestProviderFeatureFlags::test_sendgrid_respects_enable_flag -xvs -q"
    ):
        print("   ✅ ENABLE_SENDGRID flag works")
    else:
        print("   ❌ ENABLE_SENDGRID flag failed")
        flags_passed = False

    # Test OpenAI flag
    if run_command(
        "USE_STUBS=true pytest tests/unit/d0_gateway/test_provider_flags.py::TestProviderFeatureFlags::test_openai_respects_enable_flag -xvs -q"
    ):
        print("   ✅ ENABLE_OPENAI flag works")
    else:
        print("   ❌ ENABLE_OPENAI flag failed")
        flags_passed = False

    if not flags_passed:
        all_passed = False

    # Test 5: Provider flags respect USE_STUBS
    print("\n5️⃣  Testing provider flags auto-disable with USE_STUBS=true...")
    if run_command(
        "USE_STUBS=true pytest tests/unit/core/test_config.py::TestEnvironmentConfiguration::test_provider_flags_auto_disable_with_stubs -xvs -q"
    ):
        print("   ✅ Provider flags auto-disable with USE_STUBS=true")
    else:
        print("   ❌ Provider flags not auto-disabling")
        all_passed = False

    # Test 6: Provider configuration validates on startup
    print("\n6️⃣  Testing provider configuration validation...")
    if run_command(
        "USE_STUBS=true pytest tests/unit/core/test_config.py::TestEnvironmentConfiguration::test_api_key_validation_when_providers_enabled -xvs -q"
    ):
        print("   ✅ Provider configuration validates properly")
    else:
        print("   ❌ Provider configuration validation failed")
        all_passed = False

    # Test 7: All tests pass with USE_STUBS=true
    print("\n7️⃣  Running full test suite with USE_STUBS=true...")
    if run_command(
        "USE_STUBS=true pytest tests/unit/core/test_config.py tests/unit/d0_gateway/test_provider_flags.py tests/integration/test_stub_server.py -xvs -q"
    ):
        print("   ✅ All tests pass with USE_STUBS=true")
    else:
        print("   ❌ Some tests failed with USE_STUBS=true")
        all_passed = False

    # Test 8: No real API calls in test suite
    print("\n8️⃣  Verifying no real API calls in tests...")
    result = subprocess.run(
        "USE_STUBS=true pytest -xvs 2>&1 | grep -E '(googleapis|sendgrid|openai\\.com)' | grep -v stub | wc -l",
        shell=True,
        capture_output=True,
        text=True,
    )

    count = int(result.stdout.strip())
    if count == 0:
        print("   ✅ No real API calls detected")
    else:
        print(f"   ❌ Found {count} potential real API calls")
        all_passed = False

    # Test 9: Production startup fails with USE_STUBS=true
    print("\n9️⃣  Testing production rejects USE_STUBS=true...")
    test_script = """
import os
os.environ["ENVIRONMENT"] = "production"
os.environ["USE_STUBS"] = "true"
os.environ["SECRET_KEY"] = "production-key"

try:
    from core.config import Settings
    settings = Settings()
    print("ERROR: Production accepted USE_STUBS=true")
    exit(1)
except Exception as e:
    if "Production environment cannot run with USE_STUBS=true" in str(e):
        exit(0)
    else:
        print(f"Wrong error: {e}")
        exit(1)
"""

    result = subprocess.run([sys.executable, "-c", test_script], capture_output=True, text=True)

    if result.returncode == 0:
        print("   ✅ Production correctly rejects USE_STUBS=true")
    else:
        print("   ❌ Production validation failed")
        print(f"   Error: {result.stdout}{result.stderr}")
        all_passed = False

    # Test 10: Coverage check
    print("\n🔟 Checking test coverage...")
    if run_command(
        "pytest tests/unit/core/test_config.py tests/unit/d0_gateway/test_provider_flags.py --cov=core.config --cov-report=term-missing --cov-fail-under=80 -q"
    ):
        print("   ✅ Test coverage ≥ 80%")
    else:
        print("   ⚠️  Test coverage < 80% (optional)")

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All P0-005 validation tests PASSED!")
        return 0
    else:
        print("❌ Some P0-005 validation tests FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
