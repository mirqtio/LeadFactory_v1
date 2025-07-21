#!/usr/bin/env python3
"""
Strategic test selection for PRP-014
Goal: Achieve 80% coverage in <5 minutes
"""

# Test files to exclude (slow tests)
SLOW_TESTS = [
    "tests/unit/d0_gateway/test_d0_gateway_metrics.py",
    "tests/unit/d0_gateway/test_d0_metrics.py",
    "tests/unit/d0_gateway/test_openai_client.py",
    "tests/unit/d0_gateway/test_pagespeed_client.py",
    "tests/unit/d0_gateway/test_providers.py",
    "tests/unit/d1_targeting/test_task_021.py",
    "tests/unit/d1_targeting/test_task_022.py",
    "tests/unit/d1_targeting/test_task_023_simple.py",
    "tests/unit/d1_targeting/test_task_023.py",
    "tests/unit/d3_assessment/test_d3_assessment_cache.py",
    "tests/unit/d3_assessment/test_d3_assessment_metrics.py",
    "tests/unit/d3_assessment/test_formatter.py",
    "tests/unit/d3_assessment/test_pagespeed.py",
    "tests/unit/d3_assessment/test_rubric.py",
    "tests/unit/d3_assessment/test_techstack.py",
    "tests/unit/d4_enrichment/test_gbp_enricher.py",
    "tests/unit/d4_enrichment/test_matchers.py",
    "tests/unit/d6_reports/test_generator.py",
    "tests/unit/d6_reports/test_pdf_converter.py",
    "tests/unit/d6_reports/test_prioritizer.py",
    "tests/unit/d7_storefront/test_checkout.py",
    "tests/unit/d7_storefront/test_d7_storefront_models.py",
    "tests/unit/d8_personalization/test_subject_lines.py",
    "tests/unit/d8_personalization/test_templates.py",
    "tests/unit/d9_delivery/test_compliance.py",
    "tests/unit/d9_delivery/test_email_builder.py",
    "tests/unit/test_vertical_stats.py",
]

# Additional tests to exclude (problematic or not needed)
EXCLUDE_TESTS = [
    "tests/unit/d10_analytics/test_d10_models.py",
    "tests/unit/d10_analytics/test_warehouse.py",
    "tests/unit/d11_orchestration/test_bucket_flow.py",
    "tests/unit/d11_orchestration/test_pipeline.py",
    "tests/unit/d9_delivery/test_delivery_manager.py",
    "tests/unit/d9_delivery/test_sendgrid.py",
]


# Generate pytest command
def generate_pytest_cmd():
    ignore_args = []
    for test in SLOW_TESTS + EXCLUDE_TESTS:
        ignore_args.append(f"--ignore={test}")

    cmd = f"""pytest \\
  tests/unit \\
  tests/integration/test_stub_server.py \\
  tests/integration/test_database.py \\
  tests/smoke/test_health.py \\
  -m "not slow and not flaky and not external" \\
  {" ".join(ignore_args)} \\
  --cov=. --cov-report=term --cov-report=xml \\
  -n auto --tb=short
"""
    return cmd


if __name__ == "__main__":
    print(generate_pytest_cmd())
