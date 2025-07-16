"""
Integration tests for lineage tracking across the report generation pipeline
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import text

from d6_reports.lineage_integration import LineageCapture, create_report_with_lineage
from d6_reports.models import ReportGeneration, ReportStatus


class TestLineageIntegration:
    """Integration tests for lineage capture in report generation"""

    @pytest.mark.asyncio
    async def test_full_lineage_capture_flow(self, async_db_session, test_report_template):
        """Test complete lineage capture flow during report generation"""
        # Create report with lineage
        report, pipeline_run_id = await create_report_with_lineage(
            session=async_db_session,
            business_id="business-123",
            template_id=test_report_template.id,
            template_version="v1.0.0",
            user_id="user-456",
            order_id="order-789",
            report_data={"test": "data"},
        )

        assert report.id is not None
        assert pipeline_run_id is not None
        assert report.status == ReportStatus.PENDING

        # Simulate pipeline execution with lineage capture
        lineage_capture = LineageCapture(async_db_session)

        # Load existing pipeline context
        lineage_capture._pipeline_context[pipeline_run_id] = {
            "lead_id": "business-123",
            "template_version": "v1.0.0",
            "start_time": datetime.utcnow() - timedelta(seconds=30),
            "logs": [],
            "raw_inputs": {"test": "data"},
        }

        # Log pipeline events
        lineage_capture.log_pipeline_event(pipeline_run_id, "info", "Starting report generation")
        lineage_capture.log_pipeline_event(pipeline_run_id, "info", "Loading business data")
        lineage_capture.add_raw_input(pipeline_run_id, "business_data", {"name": "Test Business"})
        lineage_capture.log_pipeline_event(pipeline_run_id, "info", "Generating PDF")

        # Complete pipeline and capture lineage
        success = await lineage_capture.capture_on_completion(
            report_generation_id=report.id,
            pipeline_run_id=pipeline_run_id,
            success=True,
        )

        assert success is True

        # Verify lineage was captured
        lineage = await async_db_session.execute(
            text("SELECT * FROM report_lineage WHERE report_generation_id = :id"), {"id": report.id}
        )
        lineage_record = lineage.first()

        assert lineage_record is not None

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Infrastructure dependencies not yet set up")
    async def test_lineage_capture_on_failure(self, async_db_session, test_report_template):
        """Test lineage capture when report generation fails"""
        # Create report
        report, pipeline_run_id = await create_report_with_lineage(
            session=async_db_session,
            business_id="business-fail",
            template_id=test_report_template.id,
            template_version="v1.0.0",
        )

        # Simulate pipeline failure
        lineage_capture = LineageCapture(async_db_session)
        lineage_capture._pipeline_context[pipeline_run_id] = {
            "lead_id": "business-fail",
            "template_version": "v1.0.0",
            "start_time": datetime.utcnow() - timedelta(seconds=10),
            "logs": [],
            "raw_inputs": {},
        }

        # Log error event
        lineage_capture.log_pipeline_event(
            pipeline_run_id, "error", "PDF generation failed", {"error": "Timeout exceeded"}
        )

        # Capture lineage with failure
        success = await lineage_capture.capture_on_completion(
            report_generation_id=report.id,
            pipeline_run_id=pipeline_run_id,
            success=False,
            error_data={"error": "PDF generation timeout"},
        )

        assert success is True  # Lineage capture itself succeeded

        # Verify error was captured in lineage
        lineage = await async_db_session.execute(
            text("SELECT * FROM report_lineage WHERE report_generation_id = :id"), {"id": report.id}
        )
        lineage_record = lineage.first()

        assert lineage_record is not None
        # Compressed data should contain error information

    @pytest.mark.asyncio
    async def test_lineage_with_report_generator(self, async_db_session, test_report_template):
        """Test lineage integration with actual report generator"""
        # This would require mocking the ReportGenerator to use lineage capture
        # For now, we'll test the lineage capture service directly

        lineage_capture = LineageCapture(async_db_session)

        # Start pipeline
        pipeline_run_id = await lineage_capture.start_pipeline(
            lead_id="business-gen",
            template_version="v2.0.0",
            initial_data={"source": "integration_test"},
        )

        # Simulate report generation steps
        lineage_capture.log_pipeline_event(pipeline_run_id, "info", "Initializing report generator")

        lineage_capture.add_raw_input(pipeline_run_id, "pagespeed_data", {"performance_score": 85, "fcp": 1.2})

        lineage_capture.log_pipeline_event(pipeline_run_id, "info", "Template rendered successfully")

        # Create report record
        report = ReportGeneration(
            business_id="business-gen",
            template_id=test_report_template.id,
            configuration={"pipeline_run_id": pipeline_run_id},
        )
        async_db_session.add(report)
        await async_db_session.commit()

        # Complete and capture
        success = await lineage_capture.capture_on_completion(
            report_generation_id=report.id,
            pipeline_run_id=pipeline_run_id,
            success=True,
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_100_percent_capture_requirement(self, async_db_session, test_report_template):
        """Test that 100% of new PDFs have lineage row captured"""
        captured_count = 0
        total_count = 10

        # Create multiple reports
        for i in range(total_count):
            report, pipeline_run_id = await create_report_with_lineage(
                session=async_db_session,
                business_id=f"business-{i}",
                template_id=test_report_template.id,
                template_version="v1.0.0",
            )

            # Simulate completion
            lineage_capture = LineageCapture(async_db_session)
            lineage_capture._pipeline_context[pipeline_run_id] = {
                "lead_id": f"business-{i}",
                "template_version": "v1.0.0",
                "start_time": datetime.utcnow() - timedelta(seconds=5),
                "logs": [],
                "raw_inputs": {},
            }

            success = await lineage_capture.capture_on_completion(
                report_generation_id=report.id,
                pipeline_run_id=pipeline_run_id,
                success=True,
            )

            if success:
                captured_count += 1

        # Verify 100% capture rate
        assert captured_count == total_count

        # Verify all reports have lineage
        result = await async_db_session.execute(
            text("""
            SELECT COUNT(*) as total,
                   COUNT(l.id) as with_lineage
            FROM d6_report_generations r
            LEFT JOIN report_lineage l ON r.id = l.report_generation_id
            """)
        )
        counts = result.first()

        assert counts.total == total_count
        assert counts.with_lineage == total_count

    @pytest.mark.asyncio
    async def test_lineage_does_not_block_report_generation(self, async_db_session, test_report_template):
        """Test that lineage capture failure doesn't block report generation"""
        # Create report
        report = ReportGeneration(
            business_id="business-noblock",
            template_id=test_report_template.id,
        )
        async_db_session.add(report)
        await async_db_session.commit()

        # Mock compression to fail
        with patch("d6_reports.lineage.tracker.compress_lineage_data") as mock_compress:
            mock_compress.side_effect = Exception("Compression failed")

            lineage_capture = LineageCapture(async_db_session)
            pipeline_run_id = await lineage_capture.start_pipeline(
                lead_id="business-noblock",
                template_version="v1.0.0",
            )

            # Capture should handle error gracefully
            success = await lineage_capture.capture_on_completion(
                report_generation_id=report.id,
                pipeline_run_id=pipeline_run_id,
                success=True,
            )

            # Lineage capture failed but didn't raise exception
            assert success is False

        # Report should still exist and be unaffected
        await async_db_session.refresh(report)
        assert report.id is not None
