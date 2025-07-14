"""
Batch Processor for Report Runner

Resilient batch processing engine with error isolation, concurrency control,
and integration with d6_reports for individual report generation.
"""
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError

from core.config import get_settings
from core.logging import get_logger
from d6_reports.generator import GenerationOptions, ReportGenerator
from database.session import SessionLocal
from lead_explorer.repository import LeadRepository

from .cost_calculator import get_cost_calculator
from .models import BatchReport, BatchReportLead, BatchStatus, LeadProcessingStatus
from .websocket_manager import get_connection_manager

logger = get_logger("batch_processor")


@dataclass
class BatchProcessingResult:
    """Result of batch processing operation"""

    batch_id: str
    total_leads: int
    successful: int
    failed: int
    skipped: int
    total_cost: float
    duration_seconds: float
    error_message: Optional[str] = None


@dataclass
class LeadProcessingResult:
    """Result of processing a single lead"""

    lead_id: str
    success: bool
    report_url: Optional[str] = None
    actual_cost: Optional[float] = None
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    quality_score: Optional[float] = None


class BatchProcessor:
    """Main batch processing engine"""

    def __init__(self):
        self.settings = get_settings()
        self.connection_manager = get_connection_manager()
        self.cost_calculator = get_cost_calculator()
        self.report_generator = ReportGenerator()

        # Processing configuration
        self.max_concurrent_leads = getattr(self.settings, "BATCH_MAX_CONCURRENT_LEADS", 5)
        self.default_timeout_seconds = 30
        self.max_retries = 3

        # Thread pool for CPU-bound tasks
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_concurrent_leads)

    async def process_batch(self, batch_id: str) -> BatchProcessingResult:
        """
        Process a complete batch of leads

        Args:
            batch_id: ID of the batch to process

        Returns:
            BatchProcessingResult with processing statistics
        """
        logger.info(f"Starting batch processing for {batch_id}")
        start_time = datetime.utcnow()

        try:
            # Get batch and validate
            with SessionLocal() as db:
                batch = db.query(BatchReport).filter_by(id=batch_id).first()
                if not batch:
                    raise ValueError(f"Batch {batch_id} not found")

                if batch.status != BatchStatus.PENDING:
                    raise ValueError(f"Batch {batch_id} is not in pending status")

                # Mark batch as running
                batch.status = BatchStatus.RUNNING
                batch.started_at = start_time
                db.commit()

            # Broadcast start notification
            await self.connection_manager.broadcast_progress(
                batch_id,
                {"status": "started", "message": "Batch processing started", "started_at": start_time.isoformat()},
            )

            # Get leads to process
            leads_to_process = await self._get_batch_leads(batch_id)
            if not leads_to_process:
                raise ValueError(f"No leads found for batch {batch_id}")

            logger.info(f"Processing {len(leads_to_process)} leads for batch {batch_id}")

            # Process leads with concurrency control
            results = await self._process_leads_concurrently(batch_id, leads_to_process)

            # Calculate final statistics
            successful = sum(1 for r in results if r.success)
            failed = sum(1 for r in results if not r.success)
            total_cost = sum(r.actual_cost or 0 for r in results)

            # Update batch completion
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            await self._complete_batch(batch_id, successful, failed, total_cost, end_time)

            # Broadcast completion
            await self.connection_manager.broadcast_completion(
                batch_id,
                {
                    "status": "completed",
                    "total_leads": len(results),
                    "successful": successful,
                    "failed": failed,
                    "total_cost": total_cost,
                    "duration_seconds": duration,
                    "completed_at": end_time.isoformat(),
                },
            )

            logger.info(f"Batch {batch_id} completed: {successful} successful, {failed} failed")

            return BatchProcessingResult(
                batch_id=batch_id,
                total_leads=len(results),
                successful=successful,
                failed=failed,
                skipped=0,
                total_cost=total_cost,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.error(f"Batch processing failed for {batch_id}: {str(e)}")

            # Mark batch as failed
            await self._fail_batch(batch_id, str(e))

            # Broadcast error
            await self.connection_manager.broadcast_error(batch_id, str(e), "BATCH_PROCESSING_ERROR")

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            return BatchProcessingResult(
                batch_id=batch_id,
                total_leads=0,
                successful=0,
                failed=0,
                skipped=0,
                total_cost=0.0,
                duration_seconds=duration,
                error_message=str(e),
            )

    async def _get_batch_leads(self, batch_id: str) -> List[BatchReportLead]:
        """Get all leads for a batch, ordered by processing order"""
        with SessionLocal() as db:
            leads = (
                db.query(BatchReportLead)
                .filter_by(batch_id=batch_id)
                .filter_by(status=LeadProcessingStatus.PENDING)
                .order_by(BatchReportLead.order_index)
                .all()
            )
            return leads

    async def _process_leads_concurrently(
        self, batch_id: str, leads: List[BatchReportLead]
    ) -> List[LeadProcessingResult]:
        """Process leads with controlled concurrency"""
        semaphore = asyncio.Semaphore(self.max_concurrent_leads)
        tasks = []

        for lead in leads:
            task = asyncio.create_task(self._process_single_lead_with_semaphore(semaphore, batch_id, lead))
            tasks.append(task)

        # Process with progress updates
        results = []
        completed_count = 0

        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                results.append(result)
                completed_count += 1

                # Update progress
                progress_percentage = (completed_count / len(leads)) * 100

                await self._update_batch_progress(
                    batch_id,
                    completed_count,
                    sum(1 for r in results if r.success),
                    sum(1 for r in results if not r.success),
                    progress_percentage,
                    result.lead_id,
                )

                # Broadcast progress update (throttled)
                await self.connection_manager.broadcast_progress(
                    batch_id,
                    {
                        "processed": completed_count,
                        "total": len(leads),
                        "successful": sum(1 for r in results if r.success),
                        "failed": sum(1 for r in results if not r.success),
                        "progress_percentage": progress_percentage,
                        "current_lead": result.lead_id,
                        "last_result": {
                            "lead_id": result.lead_id,
                            "success": result.success,
                            "error": result.error_message,
                        },
                    },
                )

            except Exception as e:
                logger.error(f"Error processing lead in batch {batch_id}: {str(e)}")
                # Create failed result for error case
                results.append(
                    LeadProcessingResult(
                        lead_id="unknown", success=False, error_message=str(e), error_code="PROCESSING_ERROR"
                    )
                )

        return results

    async def _process_single_lead_with_semaphore(
        self, semaphore: asyncio.Semaphore, batch_id: str, batch_lead: BatchReportLead
    ) -> LeadProcessingResult:
        """Process single lead with concurrency control"""
        async with semaphore:
            return await self._process_single_lead(batch_id, batch_lead)

    async def _process_single_lead(self, batch_id: str, batch_lead: BatchReportLead) -> LeadProcessingResult:
        """Process a single lead with error isolation"""
        lead_id = batch_lead.lead_id
        start_time = datetime.utcnow()

        try:
            logger.debug(f"Processing lead {lead_id} in batch {batch_id}")

            # Mark lead as processing
            await self._update_lead_status(batch_lead.id, LeadProcessingStatus.PROCESSING, start_time)

            # Get lead data
            lead_data = await self._get_lead_data(lead_id)
            if not lead_data:
                raise ValueError(f"Lead {lead_id} not found or deleted")

            # Generate report using d6_reports
            report_result = await self._generate_report_for_lead(lead_data)

            # Calculate actual cost (simplified for now)
            actual_cost = await self._calculate_actual_cost(lead_data, report_result)

            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Mark lead as completed
            await self._update_lead_completion(
                batch_lead.id,
                report_result.get("report_url"),
                actual_cost,
                report_result.get("quality_score"),
                end_time,
            )

            logger.debug(f"Successfully processed lead {lead_id}")

            return LeadProcessingResult(
                lead_id=lead_id,
                success=True,
                report_url=report_result.get("report_url"),
                actual_cost=actual_cost,
                processing_time_ms=processing_time_ms,
                quality_score=report_result.get("quality_score"),
            )

        except Exception as e:
            logger.error(f"Failed to process lead {lead_id}: {str(e)}")

            end_time = datetime.utcnow()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # Check if lead should be retried
            if batch_lead.is_retryable:
                await self._schedule_retry(batch_lead.id)
                error_code = "RETRY_SCHEDULED"
            else:
                await self._update_lead_failure(batch_lead.id, str(e), "PROCESSING_FAILED", end_time)
                error_code = "PROCESSING_FAILED"

            return LeadProcessingResult(
                lead_id=lead_id,
                success=False,
                processing_time_ms=processing_time_ms,
                error_message=str(e),
                error_code=error_code,
            )

    async def _get_lead_data(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Get lead data for report generation"""
        try:
            with SessionLocal() as db:
                lead_repo = LeadRepository(db)
                lead = lead_repo.get_lead_by_id(lead_id)

                if not lead:
                    return None

                return {
                    "id": lead.id,
                    "email": lead.email,
                    "domain": lead.domain,
                    "company_name": lead.company_name,
                    "contact_name": lead.contact_name,
                    "enrichment_status": lead.enrichment_status.value,
                    "source": lead.source,
                }
        except Exception as e:
            logger.error(f"Error getting lead data for {lead_id}: {str(e)}")
            return None

    async def _generate_report_for_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate report for a single lead using d6_reports"""
        try:
            # Run report generation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()

            generation_options = GenerationOptions(
                include_pdf=True, include_html=True, timeout_seconds=self.default_timeout_seconds
            )

            # Generate report using d6_reports
            result = await loop.run_in_executor(
                self.thread_pool, self._generate_report_sync, lead_data, generation_options
            )

            return result

        except Exception as e:
            logger.error(f"Report generation failed for lead {lead_data.get('id')}: {str(e)}")
            raise

    def _generate_report_sync(self, lead_data: Dict[str, Any], options: GenerationOptions) -> Dict[str, Any]:
        """Synchronous report generation wrapper"""
        try:
            # This would integrate with the actual d6_reports generator
            # For now, simulate report generation

            business_id = lead_data.get("id")
            report_url = f"/reports/{business_id}/{uuid.uuid4()}.pdf"

            # Simulate processing time
            import time

            time.sleep(0.1)  # Simulate some processing

            return {
                "success": True,
                "report_url": report_url,
                "quality_score": 0.85,  # Mock quality score
                "generation_time_ms": 100,
                "file_size_bytes": 1024 * 50,  # 50KB mock
            }

        except Exception as e:
            logger.error(f"Sync report generation failed: {str(e)}")
            raise

    async def _calculate_actual_cost(self, lead_data: Dict[str, Any], report_result: Dict[str, Any]) -> float:
        """Calculate actual cost for lead processing"""
        try:
            # Use cost calculator to estimate actual cost
            # This would track actual API calls made during processing

            # For now, use a simplified calculation
            base_cost = 0.25  # Base report generation cost
            enrichment_cost = 0.15 if lead_data.get("enrichment_status") != "completed" else 0
            assessment_cost = 0.30  # Assessment and analysis

            return base_cost + enrichment_cost + assessment_cost

        except Exception as e:
            logger.warning(f"Error calculating actual cost: {str(e)}")
            return 0.50  # Default cost estimate

    async def _update_lead_status(self, batch_lead_id: str, status: LeadProcessingStatus, timestamp: datetime):
        """Update lead processing status"""
        try:
            with SessionLocal() as db:
                batch_lead = db.query(BatchReportLead).filter_by(id=batch_lead_id).first()
                if batch_lead:
                    batch_lead.status = status
                    if status == LeadProcessingStatus.PROCESSING:
                        batch_lead.started_at = timestamp
                    db.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error updating lead status {batch_lead_id}: {str(e)}")

    async def _update_lead_completion(
        self,
        batch_lead_id: str,
        report_url: Optional[str],
        actual_cost: Optional[float],
        quality_score: Optional[float],
        completed_at: datetime,
    ):
        """Update lead completion with results"""
        try:
            with SessionLocal() as db:
                batch_lead = db.query(BatchReportLead).filter_by(id=batch_lead_id).first()
                if batch_lead:
                    batch_lead.mark_completed(report_url, actual_cost, quality_score)
                    db.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error updating lead completion {batch_lead_id}: {str(e)}")

    async def _update_lead_failure(self, batch_lead_id: str, error_message: str, error_code: str, failed_at: datetime):
        """Update lead failure with error details"""
        try:
            with SessionLocal() as db:
                batch_lead = db.query(BatchReportLead).filter_by(id=batch_lead_id).first()
                if batch_lead:
                    batch_lead.mark_failed(error_message, error_code)
                    db.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error updating lead failure {batch_lead_id}: {str(e)}")

    async def _schedule_retry(self, batch_lead_id: str):
        """Schedule lead for retry"""
        try:
            with SessionLocal() as db:
                batch_lead = db.query(BatchReportLead).filter_by(id=batch_lead_id).first()
                if batch_lead and batch_lead.is_retryable:
                    batch_lead.increment_retry()
                    db.commit()
                    logger.info(f"Scheduled retry {batch_lead.retry_count} for lead {batch_lead_id}")
        except SQLAlchemyError as e:
            logger.error(f"Error scheduling retry for {batch_lead_id}: {str(e)}")

    async def _update_batch_progress(
        self,
        batch_id: str,
        processed: int,
        successful: int,
        failed: int,
        progress_percentage: float,
        current_lead_id: str,
    ):
        """Update batch progress statistics"""
        try:
            with SessionLocal() as db:
                batch = db.query(BatchReport).filter_by(id=batch_id).first()
                if batch:
                    batch.update_progress(processed, successful, failed, current_lead_id)
                    db.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error updating batch progress {batch_id}: {str(e)}")

    async def _complete_batch(
        self, batch_id: str, successful: int, failed: int, total_cost: float, completed_at: datetime
    ):
        """Mark batch as completed with final statistics"""
        try:
            with SessionLocal() as db:
                batch = db.query(BatchReport).filter_by(id=batch_id).first()
                if batch:
                    batch.status = BatchStatus.COMPLETED
                    batch.completed_at = completed_at
                    batch.successful_leads = successful
                    batch.failed_leads = failed
                    batch.actual_cost_usd = total_cost
                    batch.progress_percentage = 100.0

                    # Update results summary
                    batch.results_summary = {
                        "total_leads": batch.total_leads,
                        "successful": successful,
                        "failed": failed,
                        "success_rate": batch.success_rate,
                        "total_cost": float(total_cost),
                        "cost_per_lead": float(total_cost / batch.total_leads) if batch.total_leads > 0 else 0,
                        "duration_seconds": batch.duration_seconds,
                    }

                    db.commit()
                    logger.info(f"Batch {batch_id} marked as completed")
        except SQLAlchemyError as e:
            logger.error(f"Error completing batch {batch_id}: {str(e)}")

    async def _fail_batch(self, batch_id: str, error_message: str):
        """Mark batch as failed"""
        try:
            with SessionLocal() as db:
                batch = db.query(BatchReport).filter_by(id=batch_id).first()
                if batch:
                    batch.status = BatchStatus.FAILED
                    batch.error_message = error_message
                    batch.completed_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Batch {batch_id} marked as failed: {error_message}")
        except SQLAlchemyError as e:
            logger.error(f"Error failing batch {batch_id}: {str(e)}")


# Singleton instance
_batch_processor = None


def get_batch_processor() -> BatchProcessor:
    """Get singleton batch processor instance"""
    global _batch_processor
    if not _batch_processor:
        _batch_processor = BatchProcessor()
    return _batch_processor


async def start_batch_processing(batch_id: str) -> BatchProcessingResult:
    """
    Convenience function to start batch processing

    Args:
        batch_id: ID of the batch to process

    Returns:
        BatchProcessingResult with processing statistics
    """
    processor = get_batch_processor()
    return await processor.process_batch(batch_id)
