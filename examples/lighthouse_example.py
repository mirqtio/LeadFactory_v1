#!/usr/bin/env python3
"""
Example of using the Lighthouse assessor to analyze website performance
"""

import asyncio

from d3_assessment.assessors.lighthouse import LighthouseAssessor
from d3_assessment.coordinator import AssessmentCoordinator
from d3_assessment.models import AssessmentType


async def test_lighthouse_directly():
    """Test the Lighthouse assessor directly"""
    print("=== Testing Lighthouse Assessor Directly ===")

    assessor = LighthouseAssessor()

    # Check if available
    if not assessor.is_available():
        print("Lighthouse assessor is not available. Check feature flag or Playwright installation.")
        return

    # Assess a website
    result = await assessor.assess(url="https://example.com", business_data={"business_id": "example-123"})

    print(f"\nStatus: {result.status}")
    print(f"Cost: ${result.cost}")

    if result.status == "completed":
        lighthouse_data = result.data.get("lighthouse_json", {})

        print("\nScores:")
        scores = lighthouse_data.get("scores", {})
        for metric, score in scores.items():
            print(f"  {metric}: {score}/100")

        print("\nCore Web Vitals:")
        cwv = lighthouse_data.get("core_web_vitals", {})
        print(f"  LCP: {cwv.get('lcp')}ms")
        print(f"  FID: {cwv.get('fid')}ms")
        print(f"  CLS: {cwv.get('cls')}")

        print("\nTop Opportunities:")
        opportunities = lighthouse_data.get("opportunities", [])
        for opp in opportunities[:3]:
            print(f"  - {opp['title']} (saves {opp['savings_ms']}ms)")
    else:
        print(f"Error: {result.error_message}")


async def test_with_coordinator():
    """Test Lighthouse through the assessment coordinator"""
    print("\n\n=== Testing Lighthouse via Coordinator ===")

    coordinator = AssessmentCoordinator()

    # Run assessment
    result = await coordinator.execute_comprehensive_assessment(
        business_id="test-business-456",
        url="https://example.com",
        assessment_types=[AssessmentType.LIGHTHOUSE],
        industry="technology",
    )

    print(f"\nTotal assessments: {result.total_assessments}")
    print(f"Completed: {result.completed_assessments}")
    print(f"Failed: {result.failed_assessments}")
    print(f"Total cost: ${result.total_cost_usd}")

    # Check Lighthouse results
    if AssessmentType.LIGHTHOUSE in result.partial_results:
        lighthouse_result = result.partial_results[AssessmentType.LIGHTHOUSE]

        print(f"\nLighthouse Performance Score: {lighthouse_result.performance_score}")
        print(f"Accessibility Score: {lighthouse_result.accessibility_score}")
        print(f"SEO Score: {lighthouse_result.seo_score}")
        print(f"PWA Score: {lighthouse_result.pwa_score}")

        # Access full data
        full_data = lighthouse_result.assessment_metadata.get("lighthouse_json", {})
        if full_data.get("is_stub"):
            print("\n(Using stub data - set USE_STUBS=false for real analysis)")
    else:
        print("\nNo Lighthouse results available")
        if AssessmentType.LIGHTHOUSE in result.errors:
            print(f"Error: {result.errors[AssessmentType.LIGHTHOUSE]}")


async def main():
    """Run example tests"""
    # Test direct usage
    await test_lighthouse_directly()

    # Test via coordinator
    await test_with_coordinator()


if __name__ == "__main__":
    # Note: Set these environment variables as needed:
    # - ENABLE_LIGHTHOUSE=true to enable the feature
    # - USE_STUBS=false to run real Lighthouse audits (requires Playwright)
    asyncio.run(main())
