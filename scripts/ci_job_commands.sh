#!/bin/bash
# CI Job Commands - Example pytest commands for each CI job type
# This file demonstrates the commands that would be used in the optimized CI pipeline

echo "🚀 CI Job Commands for Optimized Pipeline"
echo "========================================"

# Job 1: Fast Feedback (Critical & Smoke Tests)
echo -e "\n1. FAST FEEDBACK JOB"
echo "Purpose: Immediate feedback on critical functionality"
echo "Target Runtime: < 1 minute"
echo "Command:"
echo "  python -m pytest -v -m 'critical or smoke' --tb=short -n 4"
echo "Note: Currently limited by lack of marked critical tests"

# Job 2: Unit Tests
echo -e "\n2. UNIT TESTS JOB"
echo "Purpose: Validate core business logic without external dependencies"
echo "Target Runtime: 3-5 minutes"
echo "Command:"
echo "  python -m pytest -v tests/unit -m 'not integration and not slow and not e2e' --tb=short -n auto"
echo "Alternative (by exclusion):"
echo "  python -m pytest -v -m 'not integration and not slow and not e2e and not phase_future' tests/unit --tb=short -n auto"

# Job 3: Integration Tests
echo -e "\n3. INTEGRATION TESTS JOB"
echo "Purpose: Validate database and external service interactions"
echo "Target Runtime: 8-10 minutes"
echo "Command:"
echo "  python -m pytest -v -m 'integration' --tb=short -n 2"
echo "Dependencies: PostgreSQL, stub server"

# Job 4: Domain-Specific Tests (can run in parallel)
echo -e "\n4. DOMAIN-SPECIFIC JOBS (Parallel)"

echo -e "\n4a. Data Pipeline Tests"
echo "Domains: d0_gateway, d1_targeting, d2_sourcing, d3_assessment, d4_enrichment"
echo "Command:"
echo "  python -m pytest -v tests/unit/d0_gateway tests/unit/d1_targeting tests/unit/d2_sourcing tests/unit/d3_assessment tests/unit/d4_enrichment -m 'not slow and not integration' --tb=short -n 4"

echo -e "\n4b. Business Logic Tests"
echo "Domains: d5_scoring, d6_reports, d7_storefront, d8_personalization"
echo "Command:"
echo "  python -m pytest -v tests/unit/d5_scoring tests/unit/d6_reports tests/unit/d7_storefront tests/unit/d8_personalization -m 'not slow and not integration' --tb=short -n 4"

echo -e "\n4c. Delivery & Orchestration Tests"
echo "Domains: d9_delivery, d10_analytics, d11_orchestration"
echo "Command:"
echo "  python -m pytest -v tests/unit/d9_delivery tests/unit/d10_analytics tests/unit/d11_orchestration -m 'not slow and not integration' --tb=short -n 4"

# Job 5: Full Validation
echo -e "\n5. FULL VALIDATION JOB"
echo "Purpose: Complete test suite with coverage reporting"
echo "Target Runtime: 10-15 minutes"
echo "Command:"
echo "  python -m pytest -v -m 'not slow and not phase_future' --tb=short --cov=. --cov-report=xml --cov-report=term --cov-report=html:coverage/html --junitxml=test-results/junit.xml -n auto"
echo "Note: Runs after other jobs pass, generates all reports"

# Additional specialized jobs
echo -e "\n6. ADDITIONAL SPECIALIZED JOBS"

echo -e "\n6a. Security Tests (Optional)"
echo "Command:"
echo "  python -m pytest -v -m 'security' --tb=short"

echo -e "\n6b. Performance Tests (Nightly)"
echo "Command:"
echo "  python -m pytest -v -m 'performance' --tb=short"

echo -e "\n6c. E2E Tests (Pre-deployment)"
echo "Command:"
echo "  python -m pytest -v tests/e2e -m 'not slow' --tb=short"

# Docker-specific commands
echo -e "\n🐳 DOCKER COMPOSE VARIANTS"
echo "All above commands should be wrapped in docker-compose for CI:"
echo "Example:"
echo "  docker compose -f docker-compose.test.yml run --rm test \\"
echo "    python -m pytest -v -m 'critical or smoke' --tb=short -n 4"

# Local testing shortcuts
echo -e "\n💻 LOCAL TESTING SHORTCUTS"
echo "For developers to run specific job types locally:"
echo ""
echo "# Quick check (critical tests)"
echo "make test-critical"
echo ""
echo "# Before pushing (unit tests)"
echo "make test-unit"
echo ""
echo "# Full validation (matches CI)"
echo "make test-full"

# Debugging commands
echo -e "\n🔧 DEBUGGING COMMANDS"
echo "When a specific job fails:"
echo ""
echo "# Run failing test with verbose output"
echo "python -m pytest -vvs path/to/test_file.py::test_function_name"
echo ""
echo "# Run with debugging"
echo "python -m pytest --pdb path/to/test_file.py::test_function_name"
echo ""
echo "# Run specific domain tests"
echo "python -m pytest -v tests/unit/d3_assessment -k 'test_name_pattern'"

# Coverage analysis
echo -e "\n📊 COVERAGE ANALYSIS"
echo "To analyze coverage for specific components:"
echo ""
echo "# Coverage for specific package"
echo "python -m pytest --cov=app.d3_assessment --cov-report=term-missing tests/unit/d3_assessment"
echo ""
echo "# Generate HTML coverage report"
echo "python -m pytest --cov=. --cov-report=html tests/unit"
echo "# Then open coverage/html/index.html"

echo -e "\n✅ Benefits of Job Separation:"
echo "- Fast feedback on critical failures (< 1 minute)"
echo "- Parallel execution reduces total time by ~50%"
echo "- Easier to identify and debug specific failures"
echo "- Can selectively re-run failed job types"
echo "- Better resource utilization in CI"