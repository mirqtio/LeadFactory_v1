#!/usr/bin/env python3
"""
Helper functions to run assessments through the LeadFactory pipeline.
Wraps the AssessmentCoordinator to provide a simpler interface.
"""
import asyncio
from typing import Optional, List
from datetime import datetime

from d3_assessment.coordinator import AssessmentCoordinator, CoordinatorResult
from d3_assessment.types import AssessmentType
from d3_assessment.models import AssessmentResult
from database import SessionLocal
from database.models import Business


async def assess_business_simple(
    business_id: str,
    assessment_types: Optional[List[str]] = None
) -> CoordinatorResult:
    """
    Simple wrapper to assess a business.
    
    Args:
        business_id: The business ID to assess
        assessment_types: List of assessment types to run (default: all)
        
    Returns:
        CoordinatorResult with assessment outcomes
    """
    session = SessionLocal()
    
    try:
        # Get business
        business = session.query(Business).filter_by(id=business_id).first()
        if not business:
            raise ValueError(f"Business not found: {business_id}")
            
        # Default to all assessment types
        if not assessment_types:
            assessment_types = [
                AssessmentType.PAGESPEED,
                AssessmentType.TECH_STACK,
                AssessmentType.AI_INSIGHTS
            ]
        else:
            assessment_types = [AssessmentType(t) for t in assessment_types]
        
        # Create coordinator
        coordinator = AssessmentCoordinator()
        
        # Run assessment
        result = await coordinator.execute_comprehensive_assessment(
            business_id=business_id,
            url=business.website or business.url,
            assessment_types=assessment_types,
            industry=business.categories[0] if business.categories else None,
            session_config=None
        )
        
        return result
        
    finally:
        session.close()


def run_assessment_sync(business_id: str, assessment_types: Optional[List[str]] = None) -> CoordinatorResult:
    """Synchronous wrapper for assess_business_simple."""
    return asyncio.run(assess_business_simple(business_id, assessment_types))


def save_assessment_to_db(result: CoordinatorResult) -> List[str]:
    """
    Save assessment results to database.
    
    Returns:
        List of assessment IDs created
    """
    session = SessionLocal()
    assessment_ids = []
    
    try:
        # Save each assessment result
        for assessment_type, assessment in result.partial_results.items():
            if assessment:
                # Ensure we have proper fields
                if not hasattr(assessment, 'url'):
                    assessment.url = assessment.website_url
                if not hasattr(assessment, 'domain'):
                    assessment.domain = assessment.website_domain
                    
                session.add(assessment)
                assessment_ids.append(assessment.id)
                
        session.commit()
        return assessment_ids
        
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: assessment_helper.py <business_id> [assessment_types]")
        print("Example: assessment_helper.py 123-456 pagespeed,tech_stack")
        sys.exit(1)
        
    business_id = sys.argv[1]
    assessment_types = sys.argv[2].split(',') if len(sys.argv) > 2 else None
    
    try:
        result = run_assessment_sync(business_id, assessment_types)
        
        print(f"Assessment completed!")
        print(f"Total: {result.total_assessments}")
        print(f"Completed: {result.completed_assessments}")
        print(f"Failed: {result.failed_assessments}")
        
        if result.errors:
            print("\nErrors:")
            for atype, error in result.errors.items():
                print(f"  {atype}: {error}")
                
        # Save to database
        ids = save_assessment_to_db(result)
        print(f"\nSaved {len(ids)} assessments to database")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()