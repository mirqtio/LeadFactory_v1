"""
Enrichment Coordinator for Lead Explorer

Coordinates enrichment tasks using existing d4_enrichment infrastructure
and tracks enrichment progress for leads.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any

from core.logging import get_logger
from d4_enrichment.email_enrichment import get_email_enricher
from database.models import EnrichmentStatus
from database.session import SessionLocal

from .repository import LeadRepository

logger = get_logger("lead_explorer_enrichment")


class EnrichmentCoordinator:
    """
    Coordinates enrichment processes for Lead Explorer.

    Integrates with existing d4_enrichment infrastructure to provide
    lead-specific enrichment tracking and status updates.
    """

    def __init__(self):
        self.email_enricher = get_email_enricher()
        self._active_tasks = {}  # Track active enrichment tasks

    async def start_enrichment(self, lead_id: str, lead_data: dict[str, Any]) -> str:
        """
        Start enrichment process for a lead.

        Args:
            lead_id: Lead identifier
            lead_data: Lead data including email/domain

        Returns:
            Task ID for tracking enrichment progress
        """
        task_id = str(uuid.uuid4())

        logger.info(f"Starting enrichment for lead {lead_id} - task_id: {task_id}, lead_data: {lead_data}")

        # Update lead status to IN_PROGRESS
        self._update_lead_status(lead_id, EnrichmentStatus.IN_PROGRESS, task_id)

        # Start async enrichment task
        asyncio.create_task(self._enrich_lead_async(lead_id, lead_data, task_id))

        return task_id

    async def _enrich_lead_async(self, lead_id: str, lead_data: dict[str, Any], task_id: str):
        """
        Perform actual enrichment asynchronously.
        """
        self._active_tasks[task_id] = {"lead_id": lead_id, "status": "running", "started_at": datetime.utcnow()}

        try:
            # Prepare business data for email enrichment
            business_data = self._prepare_business_data(lead_data)

            # Perform email enrichment using existing d4_enrichment
            enriched_email, email_source = await self.email_enricher.enrich_email(business_data)

            # Update lead with enriched data
            self._update_lead_with_enrichment(lead_id, enriched_email=enriched_email, email_source=email_source)

            # Mark enrichment as completed
            self._update_lead_status(lead_id, EnrichmentStatus.COMPLETED, task_id)

            # Update task tracking
            self._active_tasks[task_id].update(
                {
                    "status": "completed",
                    "completed_at": datetime.utcnow(),
                    "enriched_email": enriched_email,
                    "email_source": email_source,
                }
            )

            logger.info(
                f"Enrichment completed for lead {lead_id} - task_id: {task_id}, enriched_email: {bool(enriched_email)}, email_source: {email_source}"
            )

        except Exception as e:
            # Mark enrichment as failed
            error_message = f"Enrichment failed: {str(e)}"
            self._update_lead_status(lead_id, EnrichmentStatus.FAILED, task_id, error_message)

            # Update task tracking
            self._active_tasks[task_id].update({"status": "failed", "completed_at": datetime.utcnow(), "error": str(e)})

            logger.error(f"Enrichment failed for lead {lead_id} - task_id: {task_id}, error: {str(e)}")

    def _prepare_business_data(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """
        Convert lead data to business data format expected by email enricher.
        """
        business_data = {}

        # Map lead fields to business fields
        if lead_data.get("email"):
            business_data["email"] = lead_data["email"]

        if lead_data.get("domain"):
            business_data["domain"] = lead_data["domain"]
            business_data["website"] = f"https://{lead_data['domain']}"

        if lead_data.get("company_name"):
            business_data["name"] = lead_data["company_name"]

        # Add lead ID for tracking
        business_data["lead_id"] = lead_data.get("id")

        return business_data

    def _update_lead_status(self, lead_id: str, status: EnrichmentStatus, task_id: str, error: str | None = None):
        """
        Update lead enrichment status in database.
        """
        try:
            with SessionLocal() as db:
                lead_repo = LeadRepository(db)
                lead_repo.update_enrichment_status(lead_id=lead_id, status=status, task_id=task_id, error=error)
                logger.debug(f"Updated lead {lead_id} status to {status.value}")
        except Exception as e:
            logger.error(f"Failed to update lead {lead_id} status: {str(e)}")

    def _update_lead_with_enrichment(
        self, lead_id: str, enriched_email: str | None = None, email_source: str | None = None
    ):
        """
        Update lead with enriched data.
        """
        try:
            with SessionLocal() as db:
                lead_repo = LeadRepository(db)

                updates = {}
                if enriched_email and not lead_repo.get_lead_by_id(lead_id).email:
                    # Only update email if lead doesn't already have one
                    updates["email"] = enriched_email

                if updates:
                    lead_repo.update_lead(lead_id, updates)
                    logger.info(f"Updated lead {lead_id} with enriched data - updates: {updates}")

        except Exception as e:
            logger.error(f"Failed to update lead {lead_id} with enrichment: {str(e)}")

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """
        Get status of an enrichment task.

        Args:
            task_id: Task identifier

        Returns:
            Task status information or None if not found
        """
        return self._active_tasks.get(task_id)

    def get_lead_enrichment_status(self, lead_id: str) -> dict[str, Any] | None:
        """
        Get enrichment status for a lead from database.

        Args:
            lead_id: Lead identifier

        Returns:
            Lead enrichment status or None if not found
        """
        try:
            with SessionLocal() as db:
                lead_repo = LeadRepository(db)
                lead = lead_repo.get_lead_by_id(lead_id)

                if not lead:
                    return None

                return {
                    "lead_id": lead.id,
                    "enrichment_status": lead.enrichment_status.value,
                    "enrichment_task_id": lead.enrichment_task_id,
                    "enrichment_error": lead.enrichment_error,
                    "email": lead.email,
                    "domain": lead.domain,
                    "updated_at": lead.updated_at,
                }
        except Exception as e:
            logger.error(f"Failed to get enrichment status for lead {lead_id}: {str(e)}")
            return None

    async def trigger_batch_enrichment(self, lead_ids: list) -> dict[str, str]:
        """
        Trigger enrichment for multiple leads.

        Args:
            lead_ids: List of lead identifiers

        Returns:
            Mapping of lead_id to task_id
        """
        task_ids = {}

        with SessionLocal() as db:
            lead_repo = LeadRepository(db)

            for lead_id in lead_ids:
                lead = lead_repo.get_lead_by_id(lead_id)
                if lead and lead.enrichment_status == EnrichmentStatus.PENDING:
                    lead_data = {
                        "id": lead.id,
                        "email": lead.email,
                        "domain": lead.domain,
                        "company_name": lead.company_name,
                    }

                    task_id = await self.start_enrichment(lead_id, lead_data)
                    task_ids[lead_id] = task_id

        logger.info(f"Started batch enrichment for {len(task_ids)} leads")
        return task_ids

    def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """
        Remove completed tasks older than max_age_hours.
        """
        now = datetime.utcnow()
        to_remove = []

        for task_id, task_info in self._active_tasks.items():
            if task_info.get("completed_at"):
                age_hours = (now - task_info["completed_at"]).total_seconds() / 3600
                if age_hours > max_age_hours:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self._active_tasks[task_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} completed enrichment tasks")


# Singleton instance
_enrichment_coordinator = None


def get_enrichment_coordinator() -> EnrichmentCoordinator:
    """Get singleton enrichment coordinator instance"""
    global _enrichment_coordinator
    if not _enrichment_coordinator:
        _enrichment_coordinator = EnrichmentCoordinator()
    return _enrichment_coordinator


async def quick_add_enrichment(
    lead_id: str, email: str | None = None, domain: str | None = None, company_name: str | None = None
) -> str:
    """
    Convenience function for quick-add enrichment.

    Args:
        lead_id: Lead identifier
        email: Lead email (optional)
        domain: Lead domain (optional)
        company_name: Company name (optional)

    Returns:
        Task ID for tracking enrichment
    """
    coordinator = get_enrichment_coordinator()

    lead_data = {"id": lead_id, "email": email, "domain": domain, "company_name": company_name}

    return await coordinator.start_enrichment(lead_id, lead_data)
