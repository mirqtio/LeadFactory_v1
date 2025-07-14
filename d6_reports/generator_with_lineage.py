"""
Report generator with lineage integration
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from d6_reports.generator import GenerationOptions, GenerationResult, ReportGenerator
from d6_reports.lineage_integration import LineageCapture
from d6_reports.models import ReportGeneration, ReportStatus


class ReportGeneratorWithLineage(ReportGenerator):
    """
    Extended report generator that captures lineage information
    """

    def __init__(self, session: Optional[AsyncSession] = None, **kwargs):
        super().__init__(**kwargs)
        self.session = session
        self._pipeline_run_id = None
        self._lineage_capture = None
        self._report_generation_id = None

    async def generate_report(self, business_id: str, options: Optional[GenerationOptions] = None) -> GenerationResult:
        """
        Generate report with lineage tracking
        """
        if not self.session:
            # No session provided, fall back to regular generation
            return await super().generate_report(business_id, options)

        # Initialize lineage capture
        self._lineage_capture = LineageCapture(self.session)

        # Start pipeline
        template_version = options.template_name if options else "default"
        self._pipeline_run_id = await self._lineage_capture.start_pipeline(
            lead_id=business_id,
            template_version=template_version,
            initial_data={
                "business_id": business_id,
                "options": options.__dict__ if options else {},
                "started_at": datetime.utcnow().isoformat(),
            },
        )

        # Create report generation record
        report = ReportGeneration(
            business_id=business_id,
            template_id=template_version,
            status=ReportStatus.GENERATING,
            started_at=datetime.utcnow(),
            configuration={
                "pipeline_run_id": self._pipeline_run_id,
                "template_version": template_version,
            },
        )
        self.session.add(report)
        await self.session.commit()
        self._report_generation_id = report.id

        # Log start event
        self._lineage_capture.log_pipeline_event(
            self._pipeline_run_id,
            "info",
            f"Started report generation for business {business_id}",
            {"report_id": self._report_generation_id},
        )

        try:
            # Call parent generate_report
            result = await super().generate_report(business_id, options)

            # Update report status
            report.status = ReportStatus.COMPLETED if result.success else ReportStatus.FAILED
            report.completed_at = datetime.utcnow()

            if result.success:
                # Capture successful generation data
                self._lineage_capture.add_raw_input(
                    self._pipeline_run_id,
                    "generation_result",
                    {
                        "data_loading_time_ms": result.data_loading_time_ms,
                        "template_rendering_time_ms": result.template_rendering_time_ms,
                        "pdf_generation_time_ms": result.pdf_generation_time_ms,
                        "generation_time_seconds": result.generation_time_seconds,
                        "warnings": result.warnings,
                    },
                )

                if result.pdf_result and result.pdf_result.success:
                    report.file_size_bytes = result.pdf_result.file_size
                    report.generation_time_seconds = result.generation_time_seconds

                    # Add PDF metadata to lineage
                    self._lineage_capture.add_raw_input(
                        self._pipeline_run_id,
                        "pdf_metadata",
                        {
                            "file_size": result.pdf_result.file_size,
                            "optimization_ratio": result.pdf_result.optimization_ratio,
                        },
                    )
            else:
                report.error_message = result.error_message
                report.failed_at = datetime.utcnow()

            await self.session.commit()

            # Capture lineage on completion
            await self._lineage_capture.capture_on_completion(
                report_generation_id=self._report_generation_id,
                pipeline_run_id=self._pipeline_run_id,
                success=result.success,
                error_data={"error": result.error_message} if not result.success else None,
            )

            return result

        except Exception as e:
            # Handle errors and capture lineage
            report.status = ReportStatus.FAILED
            report.error_message = str(e)
            report.failed_at = datetime.utcnow()
            await self.session.commit()

            # Capture lineage for failure
            await self._lineage_capture.capture_on_completion(
                report_generation_id=self._report_generation_id,
                pipeline_run_id=self._pipeline_run_id,
                success=False,
                error_data={"error": str(e), "type": type(e).__name__},
            )

            raise


async def generate_report_with_lineage(
    session: AsyncSession,
    business_id: str,
    options: Optional[GenerationOptions] = None,
) -> tuple[GenerationResult, str]:
    """
    Generate a report with full lineage tracking

    Args:
        session: Database session
        business_id: ID of the business
        options: Generation options

    Returns:
        Tuple of (GenerationResult, report_generation_id)
    """
    generator = ReportGeneratorWithLineage(session=session)
    result = await generator.generate_report(business_id, options)
    return result, generator._report_generation_id
