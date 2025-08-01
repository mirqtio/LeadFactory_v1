"""
Lineage tracking implementation
"""

from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from core.config import settings
from d6_reports.lineage.compressor import compress_lineage_data
from d6_reports.lineage.models import ReportLineage, ReportLineageAudit


@dataclass
class LineageData:
    """Data structure for lineage information"""

    lead_id: str
    pipeline_run_id: str
    template_version_id: str
    pipeline_start_time: datetime
    pipeline_end_time: datetime
    pipeline_logs: dict[str, Any]
    raw_inputs: dict[str, Any]


class LineageTracker:
    """
    Tracks and manages report generation lineage
    """

    def __init__(self, session: Session | AsyncSession):
        self.session = session

    def capture_lineage(
        self,
        report_generation_id: str,
        lineage_data: LineageData,
    ) -> Union[ReportLineage | None, "Awaitable[ReportLineage | None]"]:
        """
        Capture lineage information for a report generation

        Automatically detects sync vs async session and routes accordingly.

        Args:
            report_generation_id: ID of the report generation
            lineage_data: Lineage data to capture

        Returns:
            Created ReportLineage instance or coroutine for async sessions
        """
        # Detect if this is an async session
        if isinstance(self.session, AsyncSession):
            # Return coroutine for async session
            return self._capture_lineage_async(report_generation_id, lineage_data)
        # Handle sync session immediately
        return self._capture_lineage_sync(report_generation_id, lineage_data)

    def _capture_lineage_sync(
        self,
        report_generation_id: str,
        lineage_data: LineageData,
    ) -> ReportLineage | None:
        """Synchronous implementation of lineage capture"""
        if not getattr(settings, "ENABLE_REPORT_LINEAGE", True):
            return None

        try:
            # Prepare data for compression
            data_to_compress = {
                "lead_id": lineage_data.lead_id,
                "pipeline_run_id": lineage_data.pipeline_run_id,
                "template_version_id": lineage_data.template_version_id,
                "pipeline_start_time": lineage_data.pipeline_start_time.isoformat(),
                "pipeline_end_time": lineage_data.pipeline_end_time.isoformat(),
                "pipeline_logs": lineage_data.pipeline_logs,
                "raw_inputs": lineage_data.raw_inputs,
            }

            # Compress the data
            compressed_data, compression_ratio = compress_lineage_data(data_to_compress)

            # Create lineage record
            lineage = ReportLineage(
                report_generation_id=report_generation_id,
                lead_id=lineage_data.lead_id,
                pipeline_run_id=lineage_data.pipeline_run_id,
                template_version_id=lineage_data.template_version_id,
                pipeline_start_time=lineage_data.pipeline_start_time,
                pipeline_end_time=lineage_data.pipeline_end_time,
                pipeline_logs=lineage_data.pipeline_logs.get("summary", {}),
                raw_inputs_compressed=compressed_data,
                raw_inputs_size_bytes=len(compressed_data),
                compression_ratio=compression_ratio,
            )

            self.session.add(lineage)
            self.session.commit()

            return lineage

        except Exception as e:
            # Log error but don't fail report generation
            print(f"Failed to capture lineage: {e}")
            self.session.rollback()
            return None

    async def _capture_lineage_async(
        self,
        report_generation_id: str,
        lineage_data: LineageData,
    ) -> ReportLineage | None:
        """Asynchronous implementation of lineage capture"""
        if not getattr(settings, "ENABLE_REPORT_LINEAGE", True):
            return None

        try:
            # Prepare data for compression
            data_to_compress = {
                "lead_id": lineage_data.lead_id,
                "pipeline_run_id": lineage_data.pipeline_run_id,
                "template_version_id": lineage_data.template_version_id,
                "pipeline_start_time": lineage_data.pipeline_start_time.isoformat(),
                "pipeline_end_time": lineage_data.pipeline_end_time.isoformat(),
                "pipeline_logs": lineage_data.pipeline_logs,
                "raw_inputs": lineage_data.raw_inputs,
            }

            # Compress the data
            compressed_data, compression_ratio = compress_lineage_data(data_to_compress)

            # Create lineage record
            lineage = ReportLineage(
                report_generation_id=report_generation_id,
                lead_id=lineage_data.lead_id,
                pipeline_run_id=lineage_data.pipeline_run_id,
                template_version_id=lineage_data.template_version_id,
                pipeline_start_time=lineage_data.pipeline_start_time,
                pipeline_end_time=lineage_data.pipeline_end_time,
                pipeline_logs=lineage_data.pipeline_logs.get("summary", {}),
                raw_inputs_compressed=compressed_data,
                raw_inputs_size_bytes=len(compressed_data),
                compression_ratio=compression_ratio,
            )

            self.session.add(lineage)
            await self.session.commit()

            return lineage

        except Exception as e:
            # Log error but don't fail report generation
            print(f"Failed to capture lineage: {e}")
            await self.session.rollback()
            return None

    def record_access(
        self,
        lineage_id: str,
        action: str,
        user_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ReportLineageAudit | None:
        """
        Record access to lineage data

        Args:
            lineage_id: ID of the lineage record
            action: Action performed (view, download, etc.)
            user_id: ID of the user accessing
            ip_address: IP address of the request
            user_agent: User agent string

        Returns:
            Created audit record or None if recording fails
        """
        try:
            # Create audit record
            audit = ReportLineageAudit(
                lineage_id=lineage_id,
                action=action,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            self.session.add(audit)

            # Update lineage access tracking
            lineage = self.session.get(ReportLineage, lineage_id)
            if lineage:
                lineage.record_access(user_id, ip_address)

            self.session.commit()

            return audit

        except Exception as e:
            print(f"Failed to record lineage access: {e}")
            self.session.rollback()
            return None

    def get_lineage_by_report(self, report_generation_id: str) -> ReportLineage | None:
        """
        Get lineage data for a report generation

        Args:
            report_generation_id: ID of the report generation

        Returns:
            ReportLineage instance or None if not found
        """
        from sqlalchemy import select

        result = self.session.execute(
            select(ReportLineage).where(ReportLineage.report_generation_id == report_generation_id)
        )
        return result.scalar_one_or_none()

    def search_lineage(
        self,
        lead_id: str | None = None,
        pipeline_run_id: str | None = None,
        template_version_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[ReportLineage]:
        """
        Search lineage records by criteria

        Args:
            lead_id: Filter by lead ID
            pipeline_run_id: Filter by pipeline run ID
            template_version_id: Filter by template version ID
            start_date: Filter by creation date start
            end_date: Filter by creation date end
            limit: Maximum number of results

        Returns:
            List of matching ReportLineage instances
        """
        from sqlalchemy import select

        query = select(ReportLineage)

        if lead_id:
            query = query.where(ReportLineage.lead_id == lead_id)

        if pipeline_run_id:
            query = query.where(ReportLineage.pipeline_run_id == pipeline_run_id)

        if template_version_id:
            query = query.where(ReportLineage.template_version_id == template_version_id)

        if start_date:
            query = query.where(ReportLineage.created_at >= start_date)

        if end_date:
            query = query.where(ReportLineage.created_at <= end_date)

        query = query.order_by(ReportLineage.created_at.desc()).limit(limit)

        result = self.session.execute(query)
        return result.scalars().all()
