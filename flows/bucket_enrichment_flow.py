"""
P1-080: Bucket Enrichment Flow

Processes businesses by industry segment with batch processing,
proper queueing, and scheduling support.

Industry Bucket Strategy:
- Healthcare: High-value, strict budget
- SaaS: Medium-value, normal budget
- Restaurants: Low-value, minimal budget
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

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


from sqlalchemy import and_, func, select, update

from d4_enrichment.coordinator import EnrichmentCoordinator
from d4_enrichment.models import EnrichmentSource
from database.models import Business
from database.session import SessionLocal

logger = logging.getLogger(__name__)


class BucketPriority(Enum):
    """Priority levels for bucket processing"""

    HIGH = "high"  # Healthcare
    MEDIUM = "medium"  # SaaS
    LOW = "low"  # Restaurants
    MINIMAL = "minimal"  # Other


class BucketStrategy(Enum):
    """Processing strategies for different buckets"""

    HEALTHCARE = "healthcare"  # High-value, strict budget
    SAAS = "saas"  # Medium-value, normal budget
    RESTAURANTS = "restaurants"  # Low-value, minimal budget
    DEFAULT = "default"  # Standard processing


@dataclass
class BucketEnrichmentConfig:
    """Configuration for bucket enrichment"""

    strategy: BucketStrategy
    priority: BucketPriority
    max_budget: float
    enrichment_sources: list[EnrichmentSource]
    batch_size: int
    max_concurrent: int
    skip_recent_days: int = 7  # Skip if enriched within N days


@dataclass
class BucketProcessingStats:
    """Statistics for bucket processing"""

    bucket_name: str
    strategy: str
    total_businesses: int = 0
    processed_businesses: int = 0
    enriched_businesses: int = 0
    skipped_businesses: int = 0
    failed_businesses: int = 0
    total_cost: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.processed_businesses == 0:
            return 0.0
        return (self.enriched_businesses / self.processed_businesses) * 100

    @property
    def processing_time(self) -> timedelta | None:
        """Calculate total processing time"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


@dataclass
class BucketQueue:
    """Queue management for bucket processing"""

    buckets: list[tuple[str, BucketEnrichmentConfig]] = field(default_factory=list)
    current_index: int = 0

    def add_bucket(self, bucket_name: str, config: BucketEnrichmentConfig):
        """Add bucket to queue based on priority"""
        # Insert based on priority order
        priority_order = {
            BucketPriority.HIGH: 0,
            BucketPriority.MEDIUM: 1,
            BucketPriority.LOW: 2,
            BucketPriority.MINIMAL: 3,
        }

        insert_index = len(self.buckets)
        for i, (_, existing_config) in enumerate(self.buckets):
            if priority_order[config.priority] < priority_order[existing_config.priority]:
                insert_index = i
                break

        self.buckets.insert(insert_index, (bucket_name, config))

    def get_next(self) -> tuple[str, BucketEnrichmentConfig] | None:
        """Get next bucket to process"""
        if self.current_index < len(self.buckets):
            bucket = self.buckets[self.current_index]
            self.current_index += 1
            return bucket
        return None

    def reset(self):
        """Reset queue for next run"""
        self.current_index = 0


# Bucket configuration mappings
BUCKET_CONFIGS = {
    "healthcare": BucketEnrichmentConfig(
        strategy=BucketStrategy.HEALTHCARE,
        priority=BucketPriority.HIGH,
        max_budget=1000.0,  # Strict budget
        enrichment_sources=[EnrichmentSource.INTERNAL, EnrichmentSource.DATA_AXLE, EnrichmentSource.HUNTER_IO],
        batch_size=50,  # Smaller batches for careful processing
        max_concurrent=3,  # Lower concurrency for quality
        skip_recent_days=30,  # Skip if enriched in last month
    ),
    "saas": BucketEnrichmentConfig(
        strategy=BucketStrategy.SAAS,
        priority=BucketPriority.MEDIUM,
        max_budget=500.0,
        enrichment_sources=[EnrichmentSource.INTERNAL, EnrichmentSource.HUNTER_IO],
        batch_size=100,
        max_concurrent=5,
        skip_recent_days=14,
    ),
    "restaurants": BucketEnrichmentConfig(
        strategy=BucketStrategy.RESTAURANTS,
        priority=BucketPriority.LOW,
        max_budget=100.0,  # Minimal budget
        enrichment_sources=[EnrichmentSource.INTERNAL],
        batch_size=200,  # Larger batches for efficiency
        max_concurrent=10,  # Higher concurrency
        skip_recent_days=7,
    ),
    "default": BucketEnrichmentConfig(
        strategy=BucketStrategy.DEFAULT,
        priority=BucketPriority.MINIMAL,
        max_budget=50.0,
        enrichment_sources=[EnrichmentSource.INTERNAL],
        batch_size=150,
        max_concurrent=8,
        skip_recent_days=7,
    ),
}


@task(
    name="identify-bucket-segments",
    description="Identify unique bucket segments from database",
    retries=2,
    retry_delay_seconds=60,
)
def identify_bucket_segments(limit: int | None = None) -> list[tuple[str, int]]:
    """Identify unique vertical bucket segments and their counts"""
    logger = get_run_logger()
    logger.info("Identifying bucket segments from database")

    segments = []

    with SessionLocal() as db:
        # Get unique vertical buckets with counts
        stmt = (
            select(Business.vert_bucket, func.count(Business.id).label("count"))
            .where(Business.vert_bucket.isnot(None))
            .group_by(Business.vert_bucket)
            .order_by(func.count(Business.id).desc())
        )

        if limit:
            stmt = stmt.limit(limit)

        results = db.execute(stmt).all()

        for bucket, count in results:
            segments.append((bucket, count))

    logger.info(f"Found {len(segments)} unique bucket segments")
    return segments


@task(
    name="build-bucket-queue",
    description="Build priority queue for bucket processing",
    retries=1,
    retry_delay_seconds=30,
)
def build_bucket_queue(segments: list[tuple[str, int]]) -> BucketQueue:
    """Build priority queue based on bucket strategies"""
    logger = get_run_logger()

    queue = BucketQueue()

    for bucket_name, count in segments:
        # Map buckets to strategies
        if "health" in bucket_name.lower() or "medical" in bucket_name.lower():
            config = BUCKET_CONFIGS["healthcare"]
        elif "software" in bucket_name.lower() or "saas" in bucket_name.lower():
            config = BUCKET_CONFIGS["saas"]
        elif "restaurant" in bucket_name.lower() or "food" in bucket_name.lower():
            config = BUCKET_CONFIGS["restaurants"]
        else:
            config = BUCKET_CONFIGS["default"]

        queue.add_bucket(bucket_name, config)
        logger.info(f"Added bucket '{bucket_name}' ({count} businesses) with {config.priority.value} priority")

    return queue


@task(
    name="get-businesses-for-bucket",
    description="Fetch businesses for a specific bucket",
    retries=2,
    retry_delay_seconds=120,
)
def get_businesses_for_bucket(
    bucket_name: str, config: BucketEnrichmentConfig, offset: int = 0
) -> list[dict[str, Any]]:
    """Get businesses for a specific bucket that need enrichment"""
    logger = get_run_logger()

    businesses = []
    cutoff_date = datetime.utcnow() - timedelta(days=config.skip_recent_days)

    with SessionLocal() as db:
        # Find businesses in this bucket that haven't been recently enriched
        stmt = (
            select(Business)
            .where(
                and_(
                    Business.vert_bucket == bucket_name,
                    # Skip recently enriched
                    (Business.last_enriched_at.is_(None)) | (Business.last_enriched_at < cutoff_date),
                )
            )
            .offset(offset)
            .limit(config.batch_size)
        )

        results = db.execute(stmt).scalars().all()

        for business in results:
            businesses.append(
                {
                    "id": business.id,
                    "name": business.name,
                    "website": business.website,
                    "phone": business.phone,
                    "email": business.email,
                    "address": business.address,
                    "city": business.city,
                    "state": business.state,
                    "zip_code": business.zip_code,
                    "categories": business.categories or [],
                    "vert_bucket": business.vert_bucket,
                    "geo_bucket": business.geo_bucket,
                }
            )

    logger.info(f"Found {len(businesses)} businesses in bucket '{bucket_name}' needing enrichment")
    return businesses


@task(
    name="enrich-bucket-batch",
    description="Enrich a batch of businesses from a bucket",
    retries=2,
    retry_delay_seconds=180,
)
async def enrich_bucket_batch(
    businesses: list[dict[str, Any]], config: BucketEnrichmentConfig, bucket_name: str, current_cost: float
) -> tuple[list[dict[str, Any]], float]:
    """Enrich businesses with cost tracking"""
    logger = get_run_logger()

    # Check budget constraint
    if current_cost >= config.max_budget:
        logger.warning(
            f"Budget limit reached for bucket '{bucket_name}': ${current_cost:.2f} >= ${config.max_budget:.2f}"
        )
        return [], current_cost

    # Initialize enrichment coordinator
    coordinator = EnrichmentCoordinator(max_concurrent=config.max_concurrent, skip_recent_enrichments=True)

    # Perform batch enrichment
    logger.info(f"Enriching {len(businesses)} businesses from bucket '{bucket_name}'")

    batch_result = await coordinator.enrich_businesses_batch(
        businesses=businesses, sources=config.enrichment_sources, skip_existing=True
    )

    # Estimate cost (simplified - in real implementation would track actual API costs)
    estimated_cost_per_business = 0.10  # $0.10 per enrichment
    batch_cost = batch_result.successful_enrichments * estimated_cost_per_business

    # Update businesses with enrichment results
    enriched_businesses = []
    for result in batch_result.results:
        if result:
            business_data = next((b for b in businesses if b["id"] == result.business_id), None)
            if business_data:
                # Merge enrichment data
                if result.enriched_data:
                    business_data.update(result.enriched_data)
                business_data["last_enriched_at"] = result.completed_at
                business_data["enrichment_sources"] = result.sources_completed
                enriched_businesses.append(business_data)

    logger.info(
        f"Bucket batch enrichment complete: "
        f"{batch_result.successful_enrichments} enriched, "
        f"{batch_result.skipped_enrichments} skipped, "
        f"{batch_result.failed_enrichments} failed, "
        f"cost: ${batch_cost:.2f}"
    )

    return enriched_businesses, current_cost + batch_cost


@task(
    name="update-enriched-businesses",
    description="Update database with enrichment results",
    retries=2,
    retry_delay_seconds=120,
)
def update_enriched_businesses(enriched_businesses: list[dict[str, Any]]) -> int:
    """Update businesses with enrichment data"""
    logger = get_run_logger()

    updated_count = 0

    with SessionLocal() as db:
        for business_data in enriched_businesses:
            try:
                # Update business record
                stmt = (
                    update(Business)
                    .where(Business.id == business_data["id"])
                    .values(
                        last_enriched_at=business_data.get("last_enriched_at", datetime.utcnow()),
                        updated_at=datetime.utcnow(),
                        # Update any enriched fields
                        website=business_data.get("website") or Business.website,
                        phone=business_data.get("phone") or Business.phone,
                        email=business_data.get("email") or Business.email,
                    )
                )

                result = db.execute(stmt)
                if result.rowcount > 0:
                    updated_count += 1

            except Exception as e:
                logger.error(f"Failed to update business {business_data['id']}: {e}")

        db.commit()

    logger.info(f"Updated {updated_count} businesses with enrichment data")
    return updated_count


@task(
    name="process-single-bucket",
    description="Process all businesses in a single bucket",
    retries=1,
    retry_delay_seconds=300,
)
async def process_single_bucket(bucket_name: str, config: BucketEnrichmentConfig) -> BucketProcessingStats:
    """Process all businesses in a bucket with batching"""
    logger = get_run_logger()

    stats = BucketProcessingStats(bucket_name=bucket_name, strategy=config.strategy.value, started_at=datetime.utcnow())

    offset = 0
    current_cost = 0.0

    logger.info(f"Starting processing for bucket '{bucket_name}' with {config.strategy.value} strategy")

    while current_cost < config.max_budget:
        # Get next batch
        businesses = get_businesses_for_bucket(bucket_name, config, offset)

        if not businesses:
            logger.info(f"No more businesses to process in bucket '{bucket_name}'")
            break

        stats.total_businesses += len(businesses)

        # Enrich batch
        try:
            enriched, new_cost = await enrich_bucket_batch(businesses, config, bucket_name, current_cost)

            current_cost = new_cost
            stats.total_cost = current_cost

            if enriched:
                # Update database
                updated = update_enriched_businesses(enriched)
                stats.enriched_businesses += updated
                stats.processed_businesses += len(businesses)
            else:
                # Budget exhausted or all failed
                stats.skipped_businesses += len(businesses)
                if current_cost >= config.max_budget:
                    logger.warning(f"Budget exhausted for bucket '{bucket_name}'")
                    break

        except Exception as e:
            error_msg = f"Error processing batch in bucket '{bucket_name}': {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            stats.failed_businesses += len(businesses)

        offset += config.batch_size

        # Add small delay between batches
        await asyncio.sleep(1)

    stats.completed_at = datetime.utcnow()

    logger.info(
        f"Completed bucket '{bucket_name}': "
        f"{stats.enriched_businesses}/{stats.total_businesses} enriched, "
        f"cost: ${stats.total_cost:.2f}, "
        f"time: {stats.processing_time}"
    )

    return stats


@flow(
    name="bucket-enrichment-flow",
    description="P1-080: Process businesses by industry segment with budget controls",
    retries=1,
    retry_delay_seconds=600,
)
async def bucket_enrichment_flow(
    max_buckets: int | None = None, total_budget: float = 5000.0, bucket_limit: int | None = None
) -> dict[str, Any]:
    """
    Main bucket enrichment flow

    Args:
        max_buckets: Maximum number of buckets to process (None = all)
        total_budget: Total budget across all buckets
        bucket_limit: Limit buckets to top N by business count

    Returns:
        Flow execution summary
    """
    logger = get_run_logger()
    logger.info(f"Starting bucket enrichment flow (max_buckets={max_buckets}, total_budget=${total_budget:.2f})")

    # Identify bucket segments
    segments = identify_bucket_segments(limit=bucket_limit)

    if not segments:
        logger.warning("No bucket segments found to process")
        return {"status": "no_data", "buckets_processed": 0, "total_enriched": 0, "total_cost": 0.0}

    # Build priority queue
    queue = build_bucket_queue(segments)

    # Process buckets in priority order
    all_stats = []
    total_cost = 0.0
    buckets_processed = 0

    while total_cost < total_budget:
        # Get next bucket
        bucket_info = queue.get_next()
        if not bucket_info:
            logger.info("No more buckets in queue")
            break

        bucket_name, config = bucket_info

        # Check if we should process this bucket
        if max_buckets and buckets_processed >= max_buckets:
            logger.info(f"Reached max buckets limit ({max_buckets})")
            break

        # Adjust bucket budget based on remaining total budget
        remaining_budget = total_budget - total_cost
        if remaining_budget < config.max_budget:
            config.max_budget = remaining_budget
            logger.info(f"Adjusted bucket budget to ${config.max_budget:.2f} (remaining total)")

        # Process bucket
        try:
            stats = await process_single_bucket(bucket_name, config)
            all_stats.append(stats)
            total_cost += stats.total_cost
            buckets_processed += 1

        except Exception as e:
            logger.error(f"Failed to process bucket '{bucket_name}': {e}")
            continue

    # Generate summary
    total_businesses = sum(s.total_businesses for s in all_stats)
    total_enriched = sum(s.enriched_businesses for s in all_stats)
    total_failed = sum(s.failed_businesses for s in all_stats)

    summary = {
        "status": "completed",
        "buckets_processed": buckets_processed,
        "total_businesses": total_businesses,
        "total_enriched": total_enriched,
        "total_failed": total_failed,
        "total_cost": total_cost,
        "average_success_rate": (sum(s.success_rate for s in all_stats) / len(all_stats) if all_stats else 0.0),
        "bucket_stats": [
            {
                "bucket": s.bucket_name,
                "strategy": s.strategy,
                "enriched": s.enriched_businesses,
                "total": s.total_businesses,
                "cost": s.total_cost,
                "success_rate": s.success_rate,
                "errors": len(s.errors),
            }
            for s in all_stats
        ],
    }

    logger.info(
        f"Bucket enrichment flow completed: "
        f"{buckets_processed} buckets, "
        f"{total_enriched} enriched, "
        f"${total_cost:.2f} spent"
    )

    return summary


def create_nightly_deployment() -> Deployment:
    """Create deployment for nightly bucket enrichment"""

    deployment = Deployment.build_from_flow(
        flow=bucket_enrichment_flow,
        name="nightly-bucket-enrichment",
        schedule=CronSchedule(cron="0 2 * * *"),  # 2 AM daily
        work_queue_name="lead-enrichment",
        parameters={
            "max_buckets": None,  # Process all buckets
            "total_budget": 5000.0,  # $5000 daily budget
            "bucket_limit": 50,  # Focus on top 50 buckets by size
        },
        description="P1-080: Nightly enrichment of businesses by industry bucket",
        tags=["bucket-enrichment", "nightly", "p1-080"],
    )

    return deployment


# Manual trigger for testing
async def trigger_bucket_enrichment(max_buckets: int = 3, total_budget: float = 100.0) -> dict[str, Any]:
    """Manually trigger bucket enrichment for testing"""

    result = await bucket_enrichment_flow(
        max_buckets=max_buckets,
        total_budget=total_budget,
        bucket_limit=10,  # Test with top 10 buckets
    )

    return result


if __name__ == "__main__":
    # Test with small configuration
    import asyncio

    async def test():
        result = await trigger_bucket_enrichment(max_buckets=2, total_budget=50.0)
        print(f"Test result: {result}")

    asyncio.run(test())
