"""
Batch Scheduler for D1 Targeting Domain

Manages creation and scheduling of campaign batches with priority-based allocation,
quota tracking, and fair distribution across campaigns.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.config import get_settings
from core.logging import get_logger
from database.session import SessionLocal

from .models import Campaign, CampaignBatch, CampaignTarget, TargetUniverse
from .quota_tracker import QuotaTracker
from .types import BatchProcessingStatus, BatchSchedule, CampaignStatus


class BatchScheduler:
    """
    Handles batch creation and scheduling for campaigns with priority-based allocation
    """

    def __init__(self, session: Session | None = None):
        self.logger = get_logger("batch_scheduler", domain="d1")
        self.session = session or SessionLocal()
        self.settings = get_settings()
        self.quota_tracker = QuotaTracker(session=self.session)

        # Default batch settings
        self.default_batch_settings = BatchSchedule()

    def create_daily_batches(self, target_date: datetime | None = None) -> list[str]:
        """
        Create daily batches for all active campaigns

        Args:
            target_date: Date to create batches for (defaults to today)

        Returns:
            List of created batch IDs

        Acceptance Criteria:
        - Daily batch creation works
        - No duplicate batches
        """
        if target_date is None:
            target_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        self.logger.info(f"Creating daily batches for {target_date.date()}")

        try:
            # Get all active campaigns that need batches
            campaigns = self._get_campaigns_needing_batches(target_date)

            created_batch_ids = []
            total_daily_quota = self.quota_tracker.get_daily_quota()

            if not campaigns:
                self.logger.info("No campaigns need batches for today")
                return created_batch_ids

            # Calculate priority-based allocation
            allocations = self._calculate_priority_allocations(campaigns, total_daily_quota)

            # Create batches for each campaign
            for campaign, allocation in allocations.items():
                if allocation["quota"] > 0:
                    batch_ids = self._create_campaign_batches(campaign, allocation, target_date)
                    created_batch_ids.extend(batch_ids)

            self.session.commit()
            self.logger.info(f"Created {len(created_batch_ids)} batches for {len(allocations)} campaigns")

            return created_batch_ids

        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Failed to create daily batches: {str(e)}")
            raise

    def _get_campaigns_needing_batches(self, target_date: datetime) -> list[Campaign]:
        """Get campaigns that need batch creation for the target date"""
        # Find campaigns that are running and don't have batches for target_date
        existing_batch_campaigns = (
            self.session.query(CampaignBatch.campaign_id)
            .filter(func.date(CampaignBatch.scheduled_at) == target_date.date())
            .distinct()
            .subquery()
        )

        campaigns = (
            self.session.query(Campaign)
            .filter(
                Campaign.status == CampaignStatus.RUNNING.value,
                Campaign.id.notin_(existing_batch_campaigns),
            )
            .join(TargetUniverse)
            .filter(TargetUniverse.is_active)
            .all()
        )

        return campaigns

    def _calculate_priority_allocations(
        self, campaigns: list[Campaign], total_quota: int
    ) -> dict[Campaign, dict[str, Any]]:
        """
        Calculate priority-based quota allocation across campaigns

        Acceptance Criteria:
        - Quota allocation fair
        - Priority-based scheduling
        """
        if not campaigns:
            return {}

        allocations = {}

        # Calculate priority scores for each campaign
        campaign_priorities = []
        for campaign in campaigns:
            priority_score = self._calculate_campaign_priority(campaign)
            remaining_targets = self._get_remaining_targets_count(campaign)

            campaign_priorities.append(
                {
                    "campaign": campaign,
                    "priority": priority_score,
                    "remaining_targets": remaining_targets,
                    "batch_settings": self._get_campaign_batch_settings(campaign),
                }
            )

        # Sort by priority (highest first)
        campaign_priorities.sort(key=lambda x: x["priority"], reverse=True)

        # Allocate quota based on priority and fair distribution
        remaining_quota = total_quota

        for campaign_info in campaign_priorities:
            campaign = campaign_info["campaign"]
            remaining_targets = campaign_info["remaining_targets"]
            batch_settings = campaign_info["batch_settings"]

            if remaining_quota <= 0 or remaining_targets <= 0:
                allocations[campaign] = {"quota": 0, "batch_settings": batch_settings}
                continue

            # Calculate fair allocation
            # Higher priority campaigns get more, but ensure some quota for others
            min_allocation = min(
                batch_settings.batch_size,
                remaining_targets,
                remaining_quota // len(campaigns),
            )
            priority_bonus = int(remaining_quota * 0.1 * (campaign_info["priority"] / 100))

            allocated_quota = min(remaining_targets, min_allocation + priority_bonus, remaining_quota)

            allocations[campaign] = {
                "quota": allocated_quota,
                "batch_settings": batch_settings,
                "priority": campaign_info["priority"],
            }

            remaining_quota -= allocated_quota

        return allocations

    def _calculate_campaign_priority(self, campaign: Campaign) -> float:
        """Calculate priority score for campaign (0-100)"""
        score = 50.0  # Base score

        # Factor in campaign age (newer campaigns get slight boost)
        days_running = (datetime.utcnow() - campaign.actual_start).days if campaign.actual_start else 0
        if days_running < 7:
            score += 10

        # Factor in performance metrics
        if campaign.total_targets > 0:
            conversion_rate = campaign.converted_targets / campaign.total_targets
            response_rate = (
                campaign.responded_targets / campaign.contacted_targets if campaign.contacted_targets > 0 else 0
            )

            score += conversion_rate * 30  # Up to 30 points for conversion
            score += response_rate * 20  # Up to 20 points for response rate

        # Factor in target universe size (larger universes get slight priority)
        if hasattr(campaign, "target_universe") and campaign.target_universe.actual_size > 1000:
            score += 5

        return min(100.0, max(0.0, score))

    def _get_remaining_targets_count(self, campaign: Campaign) -> int:
        """Get count of targets not yet processed for campaign"""
        processed_count = (
            self.session.query(CampaignTarget)
            .filter(
                CampaignTarget.campaign_id == campaign.id,
                CampaignTarget.status.in_(["contacted", "responded", "converted", "excluded"]),
            )
            .count()
        )

        return max(0, campaign.total_targets - processed_count)

    def _get_campaign_batch_settings(self, campaign: Campaign) -> BatchSchedule:
        """Get batch settings for campaign"""
        if campaign.batch_settings:
            # Parse stored batch settings
            settings_dict = campaign.batch_settings
            return BatchSchedule(
                batch_size=settings_dict.get("batch_size", self.default_batch_settings.batch_size),
                max_concurrent_batches=settings_dict.get(
                    "max_concurrent_batches",
                    self.default_batch_settings.max_concurrent_batches,
                ),
                delay_between_batches_seconds=settings_dict.get(
                    "delay_between_batches_seconds",
                    self.default_batch_settings.delay_between_batches_seconds,
                ),
                max_daily_targets=settings_dict.get("max_daily_targets", self.default_batch_settings.max_daily_targets),
            )
        return self.default_batch_settings

    def _create_campaign_batches(
        self, campaign: Campaign, allocation: dict[str, Any], target_date: datetime
    ) -> list[str]:
        """Create batches for a specific campaign"""
        batch_settings = allocation["batch_settings"]
        total_quota = allocation["quota"]

        batch_ids = []
        remaining_quota = total_quota
        batch_number = self._get_next_batch_number(campaign.id, target_date)

        while remaining_quota > 0:
            batch_size = min(batch_settings.batch_size, remaining_quota)

            # Schedule batch at appropriate time during allowed hours
            scheduled_time = self._calculate_batch_schedule_time(target_date, batch_number, batch_settings)

            # Create batch record
            batch = CampaignBatch(
                campaign_id=campaign.id,
                batch_number=batch_number,
                batch_size=batch_size,
                status=BatchProcessingStatus.PENDING.value,
                scheduled_at=scheduled_time,
            )

            self.session.add(batch)
            self.session.flush()  # Get the ID

            batch_ids.append(batch.id)
            remaining_quota -= batch_size
            batch_number += 1

            # Respect max concurrent batches limit
            if len(batch_ids) >= batch_settings.max_concurrent_batches:
                break

        self.logger.info(f"Created {len(batch_ids)} batches for campaign {campaign.id} with total quota {total_quota}")
        return batch_ids

    def _get_next_batch_number(self, campaign_id: str, target_date: datetime) -> int:
        """Get next batch number for campaign on target date"""
        max_batch = (
            self.session.query(func.max(CampaignBatch.batch_number))
            .filter(
                CampaignBatch.campaign_id == campaign_id,
                func.date(CampaignBatch.scheduled_at) == target_date.date(),
            )
            .scalar()
        )

        return (max_batch or 0) + 1

    def _calculate_batch_schedule_time(
        self, target_date: datetime, batch_number: int, batch_settings: BatchSchedule
    ) -> datetime:
        """Calculate when to schedule a batch"""
        # Start at allowed hours start time
        start_time = datetime.combine(target_date.date(), batch_settings.allowed_hours_start)

        # Add delay based on batch number
        delay_minutes = (batch_number - 1) * (batch_settings.delay_between_batches_seconds // 60)
        scheduled_time = start_time + timedelta(minutes=delay_minutes)

        # Ensure we don't exceed allowed hours
        end_time = datetime.combine(target_date.date(), batch_settings.allowed_hours_end)
        if scheduled_time >= end_time:
            scheduled_time = start_time  # Wrap to next day or start time

        return scheduled_time

    def get_pending_batches(self, limit: int | None = None) -> list[CampaignBatch]:
        """Get pending batches ready for processing"""
        query = (
            self.session.query(CampaignBatch)
            .filter(
                CampaignBatch.status == BatchProcessingStatus.PENDING.value,
                CampaignBatch.scheduled_at <= datetime.utcnow(),
            )
            .order_by(CampaignBatch.scheduled_at)
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def mark_batch_processing(self, batch_id: str) -> bool:
        """Mark batch as processing"""
        batch = self.session.query(CampaignBatch).filter_by(id=batch_id).first()
        if not batch:
            return False

        batch.status = BatchProcessingStatus.PROCESSING.value
        batch.started_at = datetime.utcnow()
        self.session.commit()

        return True

    def mark_batch_completed(
        self,
        batch_id: str,
        targets_processed: int,
        targets_contacted: int,
        targets_failed: int = 0,
    ) -> bool:
        """Mark batch as completed with results"""
        batch = self.session.query(CampaignBatch).filter_by(id=batch_id).first()
        if not batch:
            return False

        batch.status = BatchProcessingStatus.COMPLETED.value
        batch.completed_at = datetime.utcnow()
        batch.targets_processed = targets_processed
        batch.targets_contacted = targets_contacted
        batch.targets_failed = targets_failed

        self.session.commit()

        # Update quota tracker
        self.quota_tracker.record_batch_completion(batch_id, targets_processed)

        return True

    def mark_batch_failed(self, batch_id: str, error_message: str) -> bool:
        """Mark batch as failed"""
        batch = self.session.query(CampaignBatch).filter_by(id=batch_id).first()
        if not batch:
            return False

        batch.status = BatchProcessingStatus.FAILED.value
        batch.error_message = error_message
        batch.retry_count += 1

        # Schedule retry if within limits
        if batch.retry_count < 3:  # Max 3 retries
            batch.status = BatchProcessingStatus.PENDING.value
            batch.scheduled_at = datetime.utcnow() + timedelta(minutes=5 * batch.retry_count)

        self.session.commit()
        return True

    def get_batch_status_summary(self, campaign_id: str | None = None) -> dict[str, int]:
        """Get summary of batch statuses"""
        query = self.session.query(CampaignBatch.status, func.count(CampaignBatch.id).label("count"))

        if campaign_id:
            query = query.filter(CampaignBatch.campaign_id == campaign_id)

        results = query.group_by(CampaignBatch.status).all()

        summary = {status.value: 0 for status in BatchProcessingStatus}
        for status, count in results:
            summary[status] = count

        return summary

    def cleanup_old_batches(self, days_old: int = 30) -> int:
        """Clean up old completed/failed batches"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        deleted_count = (
            self.session.query(CampaignBatch)
            .filter(
                CampaignBatch.status.in_(
                    [
                        BatchProcessingStatus.COMPLETED.value,
                        BatchProcessingStatus.FAILED.value,
                    ]
                ),
                CampaignBatch.completed_at < cutoff_date,
            )
            .delete()
        )

        self.session.commit()
        return deleted_count
