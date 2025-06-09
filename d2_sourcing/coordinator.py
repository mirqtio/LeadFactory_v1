"""
Sourcing Coordinator - Task 028

Orchestrates the complete business sourcing workflow, coordinating between
scraping, deduplication, and data validation with comprehensive monitoring.

Acceptance Criteria:
- Batch processing works
- Status updates correct
- Error handling complete
- Metrics tracked
"""
import asyncio
import time
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
import json

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from core.config import get_settings
from core.logging import get_logger
from database.session import SessionLocal
from database.models import Business
from .models import YelpMetadata, SourcedLocation
from .yelp_scraper import YelpScraper, ScrapingResult, ScrapingStatus
from .deduplicator import BusinessDeduplicator, DuplicateMatch, MergeResult, find_and_merge_duplicates
from .exceptions import (
    SourcingException,
    YelpAPIException,
    DeduplicationException,
    BatchQuotaException,
    ErrorRecoveryException
)


class CoordinatorStatus(Enum):
    """Status of the sourcing coordinator"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    SCRAPING = "scraping"
    DEDUPLICATING = "deduplicating"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class BatchStatus(Enum):
    """Status of a sourcing batch"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"
    CANCELLED = "cancelled"


@dataclass
class SourcingBatch:
    """Represents a batch of sourcing operations"""
    id: str
    location: str
    search_terms: List[str]
    categories: List[str]
    max_results: int
    status: BatchStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Progress tracking
    total_expected: int = 0
    scraped_count: int = 0
    duplicates_found: int = 0
    duplicates_merged: int = 0
    validation_passed: int = 0
    validation_failed: int = 0

    # Metrics
    scraping_time: float = 0.0
    deduplication_time: float = 0.0
    validation_time: float = 0.0
    total_time: float = 0.0

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.utcnow()


@dataclass
class CoordinatorMetrics:
    """Comprehensive metrics for the sourcing coordinator"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None

    # Batch metrics
    total_batches: int = 0
    completed_batches: int = 0
    failed_batches: int = 0

    # Business metrics
    total_businesses_scraped: int = 0
    total_duplicates_found: int = 0
    total_duplicates_merged: int = 0
    total_businesses_validated: int = 0

    # Performance metrics
    avg_scraping_time_per_batch: float = 0.0
    avg_deduplication_time_per_batch: float = 0.0
    avg_validation_time_per_batch: float = 0.0
    total_processing_time: float = 0.0

    # Error metrics
    scraping_errors: int = 0
    deduplication_errors: int = 0
    validation_errors: int = 0
    quota_exceeded_count: int = 0

    # Quality metrics
    duplicate_rate: float = 0.0
    validation_pass_rate: float = 0.0
    data_completeness_avg: float = 0.0


class SourcingCoordinator:
    """
    Orchestrates the complete business sourcing workflow

    Coordinates scraping, deduplication, and validation with comprehensive
    monitoring, error handling, and metrics tracking.
    """

    def __init__(self, session: Optional[Session] = None):
        """Initialize the sourcing coordinator"""
        self.settings = get_settings()
        self.logger = get_logger("sourcing_coordinator", domain="d2")
        self.session = session or SessionLocal()

        # Component initialization
        self.scraper = None  # Initialized async
        self.deduplicator = BusinessDeduplicator(session=self.session)

        # Coordinator state
        self.status = CoordinatorStatus.IDLE
        self.current_batch = None
        self.batch_queue = []
        self.active_batches = {}
        self.completed_batches = {}

        # Metrics and monitoring
        self.session_id = str(uuid.uuid4())
        self.metrics = CoordinatorMetrics(
            session_id=self.session_id,
            start_time=datetime.utcnow()
        )

        # Configuration
        self.max_concurrent_batches = getattr(self.settings, 'MAX_CONCURRENT_SOURCING_BATCHES', 3)
        self.batch_timeout_minutes = getattr(self.settings, 'SOURCING_BATCH_TIMEOUT_MINUTES', 60)
        self.auto_deduplicate = getattr(self.settings, 'AUTO_DEDUPLICATE_SOURCING', True)
        self.validate_scraped_data = getattr(self.settings, 'VALIDATE_SCRAPED_DATA', True)

    async def initialize(self):
        """Initialize async components"""
        self.status = CoordinatorStatus.INITIALIZING
        self.logger.info("Initializing sourcing coordinator")

        try:
            # Initialize scraper
            self.scraper = YelpScraper(session=self.session)

            self.status = CoordinatorStatus.IDLE
            self.logger.info("Sourcing coordinator initialized successfully")

        except Exception as e:
            self.status = CoordinatorStatus.FAILED
            self.logger.error(f"Failed to initialize coordinator: {e}")
            raise SourcingException(f"Coordinator initialization failed: {e}")

    def create_batch(
        self,
        location: str,
        search_terms: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        max_results: int = 1000
    ) -> str:
        """
        Create a new sourcing batch

        Acceptance Criteria: Batch processing works
        """
        batch = SourcingBatch(
            id=str(uuid.uuid4()),
            location=location,
            search_terms=search_terms or [],
            categories=categories or [],
            max_results=max_results,
            status=BatchStatus.PENDING,
            created_at=datetime.utcnow()
        )

        self.batch_queue.append(batch)
        self.metrics.total_batches += 1

        self.logger.info(f"Created batch {batch.id} for location '{location}' with {max_results} max results")
        return batch.id

    async def process_batch(self, batch_id: str) -> SourcingBatch:
        """
        Process a single sourcing batch

        Acceptance Criteria: Batch processing works, Status updates correct, Error handling complete
        """
        try:
            batch = self._get_batch(batch_id)
            if not batch:
                raise SourcingException(f"Batch {batch_id} not found")

            # Update status and tracking
            batch.status = BatchStatus.RUNNING
            batch.started_at = datetime.utcnow()
            self.current_batch = batch
            self.active_batches[batch_id] = batch

            self.logger.info(f"Starting batch {batch_id} processing")
            batch_start_time = time.time()

            # Step 1: Scraping
            await self._process_scraping_phase(batch)

            # Step 2: Deduplication (if enabled)
            if self.auto_deduplicate and batch.scraped_count > 0:
                await self._process_deduplication_phase(batch)

            # Step 3: Validation (if enabled)
            if self.validate_scraped_data and batch.scraped_count > 0:
                await self._process_validation_phase(batch)

            # Complete batch
            batch.total_time = time.time() - batch_start_time
            batch.status = BatchStatus.COMPLETED
            batch.completed_at = datetime.utcnow()

            self._update_metrics_for_completed_batch(batch)
            self.completed_batches[batch_id] = batch
            del self.active_batches[batch_id]

            self.logger.info(
                f"Batch {batch_id} completed successfully: "
                f"{batch.scraped_count} scraped, {batch.duplicates_merged} merged, "
                f"{batch.validation_passed} validated in {batch.total_time:.2f}s"
            )

            return batch

        except Exception as e:
            # Error handling
            if batch_id in self.active_batches:
                batch = self.active_batches[batch_id]
                batch.status = BatchStatus.FAILED
                batch.error_message = str(e)
                batch.completed_at = datetime.utcnow()

                self.metrics.failed_batches += 1
                del self.active_batches[batch_id]

            self.logger.error(f"Batch {batch_id} failed: {e}")
            raise ErrorRecoveryException(f"Batch processing failed: {e}", original_error=e)

    async def _process_scraping_phase(self, batch: SourcingBatch):
        """Process the scraping phase of a batch"""
        self.status = CoordinatorStatus.SCRAPING
        phase_start = time.time()

        try:
            # Build search parameters
            search_params = {}
            if batch.categories:
                search_params['categories'] = batch.categories

            if batch.search_terms:
                # Process multiple search terms
                all_businesses = []
                for term in batch.search_terms:
                    result = await self.scraper.search_businesses(
                        location=batch.location,
                        term=term,
                        max_results=batch.max_results // len(batch.search_terms),
                        **search_params
                    )

                    if result.status == ScrapingStatus.COMPLETED:
                        all_businesses.extend(result.businesses)
                    else:
                        self.metrics.scraping_errors += 1
                        if result.status == ScrapingStatus.QUOTA_EXCEEDED:
                            self.metrics.quota_exceeded_count += 1
                            raise BatchQuotaException("Scraping quota exceeded")

                # Combine results
                scraping_result = ScrapingResult(
                    status=ScrapingStatus.COMPLETED,
                    total_results=len(all_businesses),
                    fetched_count=len(all_businesses),
                    error_count=0,
                    quota_used=len(batch.search_terms),
                    duration_seconds=time.time() - phase_start,
                    businesses=all_businesses
                )
            else:
                # Single location-based search
                scraping_result = await self.scraper.search_businesses(
                    location=batch.location,
                    max_results=batch.max_results,
                    **search_params
                )

            # Process scraping results
            if scraping_result.status == ScrapingStatus.COMPLETED:
                batch.scraped_count = len(scraping_result.businesses)
                batch.total_expected = scraping_result.total_results

                # Save scraped businesses to database
                for business_data in scraping_result.businesses:
                    try:
                        business_id = await self.scraper.save_business_data(business_data)
                        self.logger.debug(f"Saved business {business_id}")
                    except Exception as e:
                        self.logger.warning(f"Failed to save business: {e}")
                        self.metrics.scraping_errors += 1

                self.metrics.total_businesses_scraped += batch.scraped_count

            else:
                # Handle scraping failures
                self.metrics.scraping_errors += 1
                if scraping_result.status == ScrapingStatus.QUOTA_EXCEEDED:
                    self.metrics.quota_exceeded_count += 1
                    raise BatchQuotaException("Scraping quota exceeded during batch processing")
                else:
                    raise SourcingException(f"Scraping failed: {scraping_result.error_message}")

            batch.scraping_time = time.time() - phase_start
            self.logger.info(f"Scraping phase completed: {batch.scraped_count} businesses in {batch.scraping_time:.2f}s")

        except Exception as e:
            batch.scraping_time = time.time() - phase_start
            self.logger.error(f"Scraping phase failed: {e}")
            raise

    async def _process_deduplication_phase(self, batch: SourcingBatch):
        """Process the deduplication phase of a batch"""
        self.status = CoordinatorStatus.DEDUPLICATING
        phase_start = time.time()

        try:
            # Get businesses for this batch (recent additions)
            recent_businesses = self.session.query(Business).filter(
                and_(
                    Business.created_at >= batch.started_at,
                    Business.is_active == True
                )
            ).all()

            business_ids = [b.id for b in recent_businesses]

            if business_ids:
                # Find and merge duplicates
                stats = find_and_merge_duplicates(
                    business_ids=business_ids,
                    confidence_threshold=0.7,
                    auto_merge_threshold=0.9
                )

                batch.duplicates_found = stats.get('duplicates_identified', 0)
                batch.duplicates_merged = stats.get('merges_completed', 0)

                self.metrics.total_duplicates_found += batch.duplicates_found
                self.metrics.total_duplicates_merged += batch.duplicates_merged

                self.logger.info(
                    f"Deduplication completed: {batch.duplicates_found} duplicates found, "
                    f"{batch.duplicates_merged} merged"
                )

            batch.deduplication_time = time.time() - phase_start

        except Exception as e:
            batch.deduplication_time = time.time() - phase_start
            self.metrics.deduplication_errors += 1
            self.logger.error(f"Deduplication phase failed: {e}")
            # Don't fail the entire batch for deduplication errors

    async def _process_validation_phase(self, batch: SourcingBatch):
        """Process the validation phase of a batch"""
        self.status = CoordinatorStatus.VALIDATING
        phase_start = time.time()

        try:
            # Get businesses for validation
            recent_businesses = self.session.query(Business).filter(
                and_(
                    Business.created_at >= batch.started_at,
                    Business.is_active == True
                )
            ).all()

            validation_passed = 0
            validation_failed = 0

            for business in recent_businesses:
                try:
                    if self._validate_business_data(business):
                        validation_passed += 1
                    else:
                        validation_failed += 1
                        # Mark business for review
                        business.needs_review = True

                except Exception as e:
                    validation_failed += 1
                    self.logger.warning(f"Validation error for business {business.id}: {e}")

            batch.validation_passed = validation_passed
            batch.validation_failed = validation_failed

            self.metrics.total_businesses_validated += validation_passed
            self.metrics.validation_errors += validation_failed

            # Commit validation updates
            self.session.commit()

            batch.validation_time = time.time() - phase_start

            self.logger.info(
                f"Validation completed: {validation_passed} passed, {validation_failed} failed"
            )

        except Exception as e:
            batch.validation_time = time.time() - phase_start
            self.metrics.validation_errors += 1
            self.logger.error(f"Validation phase failed: {e}")
            # Don't fail the entire batch for validation errors

    def _validate_business_data(self, business: Business) -> bool:
        """Validate a business record"""
        # Required fields validation
        if not business.name or len(business.name.strip()) == 0:
            return False

        # Must have at least one contact method
        if not any([business.phone, business.email, business.website]):
            return False

        # Address validation (if present)
        if business.address and len(business.address.strip()) < 10:
            return False

        # Coordinate validation (if present)
        if business.latitude is not None:
            if not (-90 <= business.latitude <= 90):
                return False

        if business.longitude is not None:
            if not (-180 <= business.longitude <= 180):
                return False

        # Phone validation (if present)
        if business.phone:
            # Basic phone validation - must contain digits
            digits = ''.join(filter(str.isdigit, business.phone))
            if len(digits) < 10:
                return False

        return True

    def _get_batch(self, batch_id: str) -> Optional[SourcingBatch]:
        """Get batch by ID from any queue"""
        # Check active batches
        if batch_id in self.active_batches:
            return self.active_batches[batch_id]

        # Check completed batches
        if batch_id in self.completed_batches:
            return self.completed_batches[batch_id]

        # Check queue
        for batch in self.batch_queue:
            if batch.id == batch_id:
                return batch

        return None

    def _update_metrics_for_completed_batch(self, batch: SourcingBatch):
        """
        Update coordinator metrics when a batch completes

        Acceptance Criteria: Metrics tracked
        """
        self.metrics.completed_batches += 1

        # Update timing averages
        if self.metrics.completed_batches > 0:
            total_batches = self.metrics.completed_batches

            # Update scraping time average
            old_avg_scraping = self.metrics.avg_scraping_time_per_batch
            self.metrics.avg_scraping_time_per_batch = (
                (old_avg_scraping * (total_batches - 1) + batch.scraping_time) / total_batches
            )

            # Update deduplication time average
            old_avg_dedup = self.metrics.avg_deduplication_time_per_batch
            self.metrics.avg_deduplication_time_per_batch = (
                (old_avg_dedup * (total_batches - 1) + batch.deduplication_time) / total_batches
            )

            # Update validation time average
            old_avg_validation = self.metrics.avg_validation_time_per_batch
            self.metrics.avg_validation_time_per_batch = (
                (old_avg_validation * (total_batches - 1) + batch.validation_time) / total_batches
            )

        # Update quality metrics
        if self.metrics.total_businesses_scraped > 0:
            self.metrics.duplicate_rate = (
                self.metrics.total_duplicates_found / self.metrics.total_businesses_scraped
            )

        validated_total = self.metrics.total_businesses_validated + self.metrics.validation_errors
        if validated_total > 0:
            self.metrics.validation_pass_rate = (
                self.metrics.total_businesses_validated / validated_total
            )

    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """
        Get detailed status of a batch

        Acceptance Criteria: Status updates correct
        """
        batch = self._get_batch(batch_id)
        if not batch:
            return {"error": f"Batch {batch_id} not found"}

        progress_percentage = 0.0
        if batch.total_expected > 0:
            # Calculate progress based on completed steps
            steps_completed = 0
            total_steps = 3  # scraping, deduplication, validation

            if batch.scraped_count > 0:
                steps_completed += 1
            if batch.duplicates_found >= 0:  # Deduplication attempted
                steps_completed += 1
            if batch.validation_passed + batch.validation_failed > 0:  # Validation attempted
                steps_completed += 1

            progress_percentage = (steps_completed / total_steps) * 100

        return {
            "batch_id": batch.id,
            "status": batch.status.value,
            "location": batch.location,
            "search_terms": batch.search_terms,
            "categories": batch.categories,
            "progress_percentage": progress_percentage,
            "created_at": batch.created_at.isoformat(),
            "started_at": batch.started_at.isoformat() if batch.started_at else None,
            "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
            "error_message": batch.error_message,
            "metrics": {
                "total_expected": batch.total_expected,
                "scraped_count": batch.scraped_count,
                "duplicates_found": batch.duplicates_found,
                "duplicates_merged": batch.duplicates_merged,
                "validation_passed": batch.validation_passed,
                "validation_failed": batch.validation_failed,
                "scraping_time": batch.scraping_time,
                "deduplication_time": batch.deduplication_time,
                "validation_time": batch.validation_time,
                "total_time": batch.total_time
            }
        }

    def get_coordinator_status(self) -> Dict[str, Any]:
        """
        Get comprehensive coordinator status

        Acceptance Criteria: Status updates correct, Metrics tracked
        """
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "current_batch": self.current_batch.id if self.current_batch else None,
            "queued_batches": len(self.batch_queue),
            "active_batches": len(self.active_batches),
            "completed_batches": len(self.completed_batches),
            "configuration": {
                "max_concurrent_batches": self.max_concurrent_batches,
                "batch_timeout_minutes": self.batch_timeout_minutes,
                "auto_deduplicate": self.auto_deduplicate,
                "validate_scraped_data": self.validate_scraped_data
            },
            "metrics": {
                "session_start": self.metrics.start_time.isoformat(),
                "total_batches": self.metrics.total_batches,
                "completed_batches": self.metrics.completed_batches,
                "failed_batches": self.metrics.failed_batches,
                "total_businesses_scraped": self.metrics.total_businesses_scraped,
                "total_duplicates_found": self.metrics.total_duplicates_found,
                "total_duplicates_merged": self.metrics.total_duplicates_merged,
                "total_businesses_validated": self.metrics.total_businesses_validated,
                "avg_scraping_time_per_batch": self.metrics.avg_scraping_time_per_batch,
                "avg_deduplication_time_per_batch": self.metrics.avg_deduplication_time_per_batch,
                "avg_validation_time_per_batch": self.metrics.avg_validation_time_per_batch,
                "scraping_errors": self.metrics.scraping_errors,
                "deduplication_errors": self.metrics.deduplication_errors,
                "validation_errors": self.metrics.validation_errors,
                "quota_exceeded_count": self.metrics.quota_exceeded_count,
                "duplicate_rate": self.metrics.duplicate_rate,
                "validation_pass_rate": self.metrics.validation_pass_rate
            }
        }

    async def process_multiple_batches(self, batch_configs: List[Dict[str, Any]]) -> List[str]:
        """
        Process multiple batches with concurrency control

        Acceptance Criteria: Batch processing works
        """
        batch_ids = []

        # Create all batches
        for config in batch_configs:
            batch_id = self.create_batch(**config)
            batch_ids.append(batch_id)

        # Process batches with concurrency limit
        semaphore = asyncio.Semaphore(self.max_concurrent_batches)

        async def process_with_semaphore(batch_id):
            async with semaphore:
                try:
                    await self.process_batch(batch_id)
                except Exception as e:
                    self.logger.error(f"Batch {batch_id} failed: {e}")

        # Execute all batches concurrently
        tasks = [process_with_semaphore(bid) for bid in batch_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        return batch_ids

    def pause_processing(self):
        """Pause the coordinator"""
        self.status = CoordinatorStatus.PAUSED
        self.logger.info("Coordinator paused")

    def resume_processing(self):
        """Resume the coordinator"""
        self.status = CoordinatorStatus.IDLE
        self.logger.info("Coordinator resumed")

    def cancel_batch(self, batch_id: str) -> bool:
        """Cancel a batch"""
        batch = self._get_batch(batch_id)
        if not batch:
            return False

        if batch.status in [BatchStatus.PENDING, BatchStatus.RUNNING]:
            batch.status = BatchStatus.CANCELLED
            batch.completed_at = datetime.utcnow()

            # Remove from active processing
            if batch_id in self.active_batches:
                del self.active_batches[batch_id]

            # Remove from queue
            self.batch_queue = [b for b in self.batch_queue if b.id != batch_id]

            # Move to completed batches
            self.completed_batches[batch_id] = batch

            self.logger.info(f"Cancelled batch {batch_id}")
            return True

        return False

    def cleanup_completed_batches(self, max_age_hours: int = 24):
        """Clean up old completed batches"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        to_remove = []
        for batch_id, batch in self.completed_batches.items():
            if batch.completed_at and batch.completed_at < cutoff_time:
                to_remove.append(batch_id)

        for batch_id in to_remove:
            del self.completed_batches[batch_id]

        self.logger.info(f"Cleaned up {len(to_remove)} old completed batches")

    async def shutdown(self):
        """Shutdown the coordinator gracefully"""
        self.logger.info("Shutting down sourcing coordinator")

        # Cancel active batches
        for batch_id in list(self.active_batches.keys()):
            self.cancel_batch(batch_id)

        # Close scraper if needed
        if self.scraper and hasattr(self.scraper, '_http_session') and self.scraper._http_session:
            await self.scraper._http_session.close()

        # Finalize metrics
        self.metrics.end_time = datetime.utcnow()
        self.metrics.total_processing_time = (
            self.metrics.end_time - self.metrics.start_time
        ).total_seconds()

        self.status = CoordinatorStatus.IDLE
        self.logger.info("Coordinator shutdown complete")


# Convenience functions for common coordinator operations

async def process_location_batch(
    location: str,
    categories: Optional[List[str]] = None,
    max_results: int = 1000
) -> Dict[str, Any]:
    """
    Convenience function to process a single location batch

    Returns batch status and metrics
    """
    coordinator = SourcingCoordinator()
    await coordinator.initialize()

    try:
        batch_id = coordinator.create_batch(
            location=location,
            categories=categories,
            max_results=max_results
        )

        await coordinator.process_batch(batch_id)
        return coordinator.get_batch_status(batch_id)

    finally:
        await coordinator.shutdown()


async def process_multiple_locations(
    locations: List[str],
    categories: Optional[List[str]] = None,
    max_results_per_location: int = 500
) -> Dict[str, Any]:
    """
    Convenience function to process multiple locations concurrently

    Returns coordinator status and all batch results
    """
    coordinator = SourcingCoordinator()
    await coordinator.initialize()

    try:
        batch_configs = [
            {
                "location": location,
                "categories": categories,
                "max_results": max_results_per_location
            }
            for location in locations
        ]

        batch_ids = await coordinator.process_multiple_batches(batch_configs)

        # Get results for all batches
        batch_results = {}
        for batch_id in batch_ids:
            batch_results[batch_id] = coordinator.get_batch_status(batch_id)

        return {
            "coordinator_status": coordinator.get_coordinator_status(),
            "batch_results": batch_results
        }

    finally:
        await coordinator.shutdown()
