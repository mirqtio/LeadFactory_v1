#!/usr/bin/env python3
"""
Validate production readiness without complex dependencies
"""

import sys
from pathlib import Path


def check_file_exists(filepath, description):
    """Check if a critical file exists"""
    if Path(filepath).exists():
        print(f"✅ {description}: {filepath}")
        return True
    print(f"❌ {description}: {filepath} NOT FOUND")
    return False


def check_config_keys():
    """Check if all required config keys are defined"""
    try:
        with open("core/config.py") as f:
            config_content = f.read()

        # Check for the field names in the Settings class
        required_keys = [
            "database_url",
            # "yelp_api_key", removed per P0-009
            "sendgrid_api_key",
            "stripe_secret_key",
            "openai_api_key",
            "google_api_key",  # Note: it's google_api_key not GOOGLE_PAGESPEED_API_KEY
            "data_axle_api_key",
            "hunter_api_key",
            "cost_budget_usd",
        ]

        missing = []
        for key in required_keys:
            # Check if the field is defined in the Settings class
            if f"{key}:" not in config_content:
                missing.append(key)

        if missing:
            print(f"❌ Missing config keys: {', '.join(missing)}")
            return False
        print(f"✅ All {len(required_keys)} required config keys present")
        return True
    except Exception as e:
        print(f"❌ Error checking config: {e}")
        return False


def check_docker_files():
    """Check Docker configuration"""
    docker_files = [
        ("Dockerfile", "Production Dockerfile"),
        ("Dockerfile.test", "Test Dockerfile"),
        ("docker-compose.yml", "Docker Compose"),
        ("docker-compose.production.yml", "Production Compose"),
    ]

    all_exist = True
    for filepath, desc in docker_files:
        if not check_file_exists(filepath, desc):
            all_exist = False

    return all_exist


def check_database_migrations():
    """Check if migrations are set up"""
    migrations_dir = Path("alembic/versions")
    if not migrations_dir.exists():
        print("❌ Migrations directory not found")
        return False

    migrations = list(migrations_dir.glob("*.py"))
    migration_count = len([m for m in migrations if not m.name.startswith("__")])

    if migration_count >= 4:  # Initial + analytics + cost tracking + buckets
        print(f"✅ Database migrations: {migration_count} migrations found")
        return True
    print(f"❌ Database migrations: Only {migration_count} found (expected at least 4)")
    return False


def check_phase_05_implementation():
    """Check Phase 0.5 specific implementations"""
    # First check if we have the providers directory
    providers_dir = Path("d0_gateway/providers")
    if not providers_dir.exists():
        print(f"❌ Providers directory not found: {providers_dir}")
        return False

    # Check for specific Phase 0.5 files and features
    phase_05_checks = []

    # Check for Data Axle provider
    dataaxle_files = list(providers_dir.glob("*dataaxle*"))
    if dataaxle_files:
        print(f"✅ Data Axle provider: {dataaxle_files[0]}")
    else:
        print("❌ Data Axle provider: Not found")
        phase_05_checks.append(False)

    # Check for Hunter provider
    hunter_files = list(providers_dir.glob("*hunter*"))
    if hunter_files:
        print(f"✅ Hunter provider: {hunter_files[0]}")
    else:
        print("❌ Hunter provider: Not found")
        phase_05_checks.append(False)

    # Check for cost tracking in config
    if Path("core/config.py").exists():
        with open("core/config.py") as f:
            if "cost_budget_usd" in f.read():
                print("✅ Cost tracking: cost_budget_usd in config")
            else:
                print("❌ Cost tracking: cost_budget_usd not in config")
                phase_05_checks.append(False)

    # Check for bucket columns in models or migrations
    migrations_dir = Path("alembic/versions")
    bucket_migration_found = False
    for migration in migrations_dir.glob("*.py"):
        with open(migration) as f:
            if "bucket" in f.read().lower():
                print(f"✅ Bucket columns migration: {migration.name}")
                bucket_migration_found = True
                break
    if not bucket_migration_found:
        print("❌ Bucket columns migration: Not found")
        phase_05_checks.append(False)

    # Check for bucket profit notebook
    notebook_path = Path("analytics/notebooks/bucket_profit.ipynb")
    if notebook_path.exists():
        print(f"✅ Bucket profit notebook: {notebook_path}")
    else:
        print(f"❌ Bucket profit notebook: {notebook_path} not found")
        phase_05_checks.append(False)

    return all(check for check in phase_05_checks) if phase_05_checks else True


def check_critical_endpoints():
    """Check if critical API endpoints are registered"""
    try:
        with open("main.py") as f:
            main_content = f.read()

        endpoints = [
            "targeting_router",
            "assessment_router",
            "storefront_router",
            "analytics_router",
            "orchestration_router",
        ]

        missing = []
        for endpoint in endpoints:
            if endpoint not in main_content or f"# {endpoint}" in main_content:
                missing.append(endpoint)

        if missing:
            print(f"❌ Missing API routers: {', '.join(missing)}")
            return False
        print(f"✅ All {len(endpoints)} critical API routers registered")
        return True
    except Exception as e:
        print(f"❌ Error checking endpoints: {e}")
        return False


def check_test_coverage():
    """Check test file existence"""
    test_domains = [
        "d0_gateway",
        "d1_targeting",
        "d2_sourcing",
        "d3_assessment",
        "d4_enrichment",
        "d5_scoring",
        "d6_reports",
        "d7_storefront",
        "d8_personalization",
        "d9_delivery",
        "d10_analytics",
        "d11_orchestration",
    ]

    missing_tests = []
    for domain in test_domains:
        test_dir = Path(f"tests/unit/{domain}")
        if not test_dir.exists() or not list(test_dir.glob("test_*.py")):
            missing_tests.append(domain)

    if missing_tests:
        print(f"❌ Missing tests for: {', '.join(missing_tests)}")
        return False
    print(f"✅ Test coverage: All {len(test_domains)} domains have tests")
    return True


def main():
    """Run all validation checks"""
    print("\n" + "=" * 60)
    print("LEADFACTORY PRODUCTION VALIDATION")
    print("=" * 60 + "\n")

    checks = [
        ("Configuration Keys", check_config_keys),
        ("Docker Files", check_docker_files),
        ("Database Migrations", check_database_migrations),
        ("Phase 0.5 Implementation", check_phase_05_implementation),
        ("API Endpoints", check_critical_endpoints),
        ("Test Coverage", check_test_coverage),
    ]

    results = []
    for name, check_func in checks:
        print(f"\nChecking {name}...")
        print("-" * 40)
        result = check_func()
        results.append((name, result))

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\nTotal: {passed}/{total} checks passed")

    if passed == total:
        print("\n🎉 All validation checks PASSED!")
        print("The system is ready for production deployment.")
        return 0
    print(f"\n❌ {total - passed} validation checks FAILED.")
    print("Please fix these issues before deploying to production.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
