"""
Bucket enrichment flow for Phase 0.5
Task ET-07: Nightly bucket_enrichment Prefect flow

This flow reads businesses from dim_lead, enriches them with bucket
assignments, and updates the database with geo_bucket and vert_bucket values.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

try:
    from prefect import flow, task
    from prefect.deployments import Deployment
    from prefect.logging import get_run_logger
    from prefect.server.schemas.schedules import CronSchedule
    
    PREFECT_AVAILABLE = True
except ImportError:
    # Mock imports for testing
    PREFECT_AVAILABLE = False
    
    def flow(*args, **kwargs):
        def decorator(func):
            func.retries = kwargs.get("retries", 0)
            func.retry_delay_seconds = kwargs.get("retry_delay_seconds", 0)
            return func
        return decorator
        
    def task(*args, **kwargs):
        def decorator(func):
            func.retries = kwargs.get("retries", 0)
            func.retry_delay_seconds = kwargs.get("retry_delay_seconds", 0)
            return func
        return decorator
        
    def get_run_logger():
        import logging
        return logging.getLogger(__name__)
        
    class Deployment:
        @classmethod
        def build_from_flow(cls, **kwargs):
            return cls()
            
    class CronSchedule:
        def __init__(self, cron):
            self.cron = cron

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from d1_targeting.bucket_loader import get_bucket_loader
from database.models import Business
from database.session import SessionLocal


@task(
    name="load-bucket-features",
    description="Load bucket feature mappings from CSV",
    retries=1,
    retry_delay_seconds=60
)
def load_bucket_features() -> Dict[str, int]:
    """Load bucket feature data from CSV files"""
    logger = get_run_logger()
    logger.info("Loading bucket features from CSV")
    
    loader = get_bucket_loader()
    stats = loader.get_stats()
    
    logger.info(f"Loaded features: {stats['total_zip_codes']} ZIPs, {stats['total_categories']} categories")
    logger.info(f"Unique buckets: {stats['unique_geo_buckets']} geo, {stats['unique_vert_buckets']} vertical")
    
    return stats


@task(
    name="get-unenriched-businesses",
    description="Fetch businesses without bucket assignments",
    retries=2,
    retry_delay_seconds=120
)
def get_unenriched_businesses(batch_size: int = 1000) -> List[Dict]:
    """Get businesses that need bucket enrichment"""
    logger = get_run_logger()
    
    businesses = []
    
    with SessionLocal() as db:
        # Find businesses without bucket assignments
        stmt = select(Business).where(
            (Business.geo_bucket.is_(None)) | (Business.vert_bucket.is_(None))
        ).limit(batch_size)
        
        results = db.execute(stmt).scalars().all()
        
        for business in results:
            businesses.append({
                'id': business.id,
                'name': business.name,
                'zip_code': business.zip_code,
                'categories': business.categories or []
            })
    
    logger.info(f"Found {len(businesses)} businesses needing bucket enrichment")
    return businesses


@task(
    name="enrich-business-buckets",
    description="Assign bucket values to businesses",
    retries=1,
    retry_delay_seconds=60
)
def enrich_business_buckets(businesses: List[Dict]) -> List[Dict]:
    """Enrich businesses with bucket assignments"""
    logger = get_run_logger()
    loader = get_bucket_loader()
    
    enriched = []
    missing_geo = 0
    missing_vert = 0
    
    for business in businesses:
        # Get bucket assignments
        enriched_biz = loader.enrich_business(business)
        
        if enriched_biz['geo_bucket'] is None:
            missing_geo += 1
            
        if enriched_biz['vert_bucket'] is None:
            missing_vert += 1
            
        enriched.append(enriched_biz)
    
    logger.info(
        f"Enriched {len(enriched)} businesses "
        f"({missing_geo} missing geo, {missing_vert} missing vertical)"
    )
    
    return enriched


@task(
    name="update-business-buckets",
    description="Update database with bucket assignments",
    retries=2,
    retry_delay_seconds=180
)
def update_business_buckets(enriched_businesses: List[Dict]) -> Dict[str, int]:
    """Update businesses with bucket values"""
    logger = get_run_logger()
    
    updated_count = 0
    error_count = 0
    
    with SessionLocal() as db:
        for business in enriched_businesses:
            try:
                # Update business with bucket values
                stmt = update(Business).where(
                    Business.id == business['id']
                ).values(
                    geo_bucket=business['geo_bucket'],
                    vert_bucket=business['vert_bucket'],
                    updated_at=datetime.utcnow()
                )
                
                result = db.execute(stmt)
                
                if result.rowcount > 0:
                    updated_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to update business {business['id']}: {e}")
                error_count += 1
        
        db.commit()
    
    logger.info(f"Updated {updated_count} businesses, {error_count} errors")
    
    return {
        'updated': updated_count,
        'errors': error_count
    }


@flow(
    name="bucket-enrichment-flow",
    description="Enrich businesses with geo and vertical buckets",
    retries=2,
    retry_delay_seconds=300
)
def bucket_enrichment_flow(
    batch_size: int = 1000,
    max_batches: int = 10
) -> Dict[str, int]:
    """
    Main bucket enrichment flow
    
    Args:
        batch_size: Number of businesses per batch
        max_batches: Maximum batches to process in one run
        
    Returns:
        Summary statistics
    """
    logger = get_run_logger()
    logger.info(f"Starting bucket enrichment flow (batch_size={batch_size})")
    
    # Load feature data
    feature_stats = load_bucket_features()
    
    total_updated = 0
    total_errors = 0
    batches_processed = 0
    
    # Process in batches
    for batch_num in range(max_batches):
        # Get businesses needing enrichment
        businesses = get_unenriched_businesses(batch_size)
        
        if not businesses:
            logger.info("No more businesses to enrich")
            break
            
        # Enrich with buckets
        enriched = enrich_business_buckets(businesses)
        
        # Update database
        update_stats = update_business_buckets(enriched)
        
        total_updated += update_stats['updated']
        total_errors += update_stats['errors']
        batches_processed += 1
        
        logger.info(f"Batch {batch_num + 1} complete: {update_stats['updated']} updated")
    
    # Final summary
    summary = {
        'batches_processed': batches_processed,
        'total_updated': total_updated,
        'total_errors': total_errors,
        'feature_stats': feature_stats
    }
    
    logger.info(
        f"Bucket enrichment complete: {total_updated} updated, "
        f"{total_errors} errors in {batches_processed} batches"
    )
    
    return summary


def create_nightly_deployment() -> Deployment:
    """Create deployment for nightly bucket enrichment"""
    
    deployment = Deployment.build_from_flow(
        flow=bucket_enrichment_flow,
        name="nightly-bucket-enrichment",
        schedule=CronSchedule(cron="0 3 * * *"),  # 3 AM daily
        work_queue_name="lead-generation",
        parameters={
            "batch_size": 1000,
            "max_batches": 100  # Process up to 100k businesses per night
        },
        description="Nightly enrichment of businesses with geo and vertical buckets",
        tags=["bucket-enrichment", "nightly", "phase-0.5"]
    )
    
    return deployment


# Manual trigger for testing
async def trigger_bucket_enrichment(
    batch_size: int = 100,
    max_batches: int = 1
) -> Dict[str, int]:
    """Manually trigger bucket enrichment"""
    
    result = bucket_enrichment_flow(
        batch_size=batch_size,
        max_batches=max_batches
    )
    
    return result


if __name__ == "__main__":
    # Test with small batch
    import asyncio
    
    async def test():
        result = await trigger_bucket_enrichment(batch_size=10, max_batches=1)
        print(f"Test result: {result}")
        
    asyncio.run(test())