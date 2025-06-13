#!/usr/bin/env python3
"""Test assessment in Docker environment"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from d3_assessment.coordinator import AssessmentCoordinator
from d3_assessment.types import AssessmentType

async def test_assessment():
    """Test assessment with fixed PageSpeed"""
    url = "https://www.investinyakima.com/"
    business_id = "07a80cdc-3c94-48df-9351-5ba097026806"
    
    print(f"Testing assessment for URL: {url}")
    print(f"Business ID: {business_id}")
    
    # Set up coordinator
    coordinator = AssessmentCoordinator()
    
    # Run assessments with all types
    try:
        result = await coordinator.execute_comprehensive_assessment(
            business_id, 
            url,
            assessment_types=[
                AssessmentType.PAGESPEED,
                AssessmentType.TECH_STACK,
                AssessmentType.AI_INSIGHTS
            ]
        )
        
        print(f"\n✅ Assessment completed!")
        print(f"Total assessments: {result.total_assessments}")
        print(f"Successful: {result.completed_assessments}")
        print(f"Failed: {result.failed_assessments}")
        
        # Show results for each assessment
        for assessment_type, assessment in result.partial_results.items():
            print(f"\n{assessment.assessment_type.value}:")
            print(f"  Status: {assessment.status.value}")
            if assessment.status.value == "completed":
                if assessment.assessment_type == AssessmentType.PAGESPEED:
                    print(f"  Performance Score: {assessment.performance_score}")
                    print(f"  SEO Score: {assessment.seo_score}")
                    print(f"  Accessibility Score: {assessment.accessibility_score}")
                elif assessment.assessment_type == AssessmentType.TECH_STACK:
                    print(f"  Technologies Found: {assessment.tech_count}")
                elif assessment.assessment_type == AssessmentType.AI_INSIGHTS:
                    print(f"  Insights Generated: {assessment.insights_count}")
            else:
                print(f"  Error: {assessment.error_message}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error running assessment: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_assessment())
    if result and result.completed_assessments == result.total_assessments:
        print("\n✅ All assessments completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Some assessments failed")
        sys.exit(1)