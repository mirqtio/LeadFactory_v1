"""
Unit tests for lineage tracker
"""

from datetime import datetime, timedelta
from unittest.mock import patch

from d6_reports.lineage.models import ReportLineage
from d6_reports.lineage.tracker import LineageData, LineageTracker
from d6_reports.models import ReportGeneration, ReportType


class TestLineageTracker:
    """Test suite for lineage tracking functionality"""

    def test_capture_lineage_success(self, db_session, test_report_template):
        """Test successful lineage capture"""
        # Create report generation
        report = ReportGeneration(
            business_id="business-123",
            template_id=test_report_template.id,
            report_type=ReportType.BUSINESS_AUDIT,
        )
        db_session.add(report)
        db_session.commit()

        # Create lineage data
        lineage_data = LineageData(
            lead_id="lead-123",
            pipeline_run_id="run-456",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow() - timedelta(minutes=2),
            pipeline_end_time=datetime.utcnow(),
            pipeline_logs={"events": ["start", "process", "complete"]},
            raw_inputs={"input1": "value1", "input2": "value2"},
        )

        # Capture lineage
        tracker = LineageTracker(db_session)
        lineage = tracker.capture_lineage(report.id, lineage_data)

        assert lineage is not None
        assert lineage.report_generation_id == report.id
        assert lineage.lead_id == "lead-123"
        assert lineage.pipeline_run_id == "run-456"
        assert lineage.raw_inputs_compressed is not None
        assert lineage.compression_ratio > 0

    def test_capture_lineage_with_feature_flag_disabled(self, db_session, test_report_template):
        """Test lineage capture when feature flag is disabled"""
        report = ReportGeneration(
            business_id="business-123",
            template_id=test_report_template.id,
        )
        db_session.add(report)
        db_session.commit()

        lineage_data = LineageData(
            lead_id="lead-123",
            pipeline_run_id="run-456",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow(),
            pipeline_end_time=datetime.utcnow(),
            pipeline_logs={},
            raw_inputs={},
        )

        # Disable feature flag
        with patch("d6_reports.lineage.tracker.settings") as mock_settings:
            mock_settings.ENABLE_REPORT_LINEAGE = False

            tracker = LineageTracker(db_session)
            lineage = tracker.capture_lineage(report.id, lineage_data)

            assert lineage is None

    def test_capture_lineage_with_error(self, db_session):
        """Test lineage capture handles errors gracefully"""
        # Invalid report ID
        lineage_data = LineageData(
            lead_id="lead-123",
            pipeline_run_id="run-456",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow(),
            pipeline_end_time=datetime.utcnow(),
            pipeline_logs={},
            raw_inputs={},
        )

        tracker = LineageTracker(db_session)
        lineage = tracker.capture_lineage("invalid-report-id", lineage_data)

        # Should return None on error
        assert lineage is None

    def test_record_access(self, db_session, test_report_template):
        """Test recording lineage access"""
        # Create report and lineage
        report = ReportGeneration(
            business_id="business-123",
            template_id=test_report_template.id,
        )
        db_session.add(report)
        db_session.commit()

        lineage = ReportLineage(
            report_generation_id=report.id,
            lead_id="lead-123",
            pipeline_run_id="run-456",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow(),
            pipeline_end_time=datetime.utcnow(),
        )
        db_session.add(lineage)
        db_session.commit()

        # Record access
        tracker = LineageTracker(db_session)
        audit = tracker.record_access(
            lineage_id=lineage.id,
            action="view",
            user_id="user-123",
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
        )

        assert audit is not None
        assert audit.action == "view"
        assert audit.user_id == "user-123"
        assert audit.ip_address == "192.168.1.1"

        # Refresh lineage to check access count
        db_session.refresh(lineage)
        assert lineage.access_count == 1

    def test_get_lineage_by_report(self, db_session, test_report_template):
        """Test retrieving lineage by report ID"""
        # Create report and lineage
        report = ReportGeneration(
            business_id="business-123",
            template_id=test_report_template.id,
        )
        db_session.add(report)
        db_session.commit()

        lineage = ReportLineage(
            report_generation_id=report.id,
            lead_id="lead-123",
            pipeline_run_id="run-456",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow(),
            pipeline_end_time=datetime.utcnow(),
        )
        db_session.add(lineage)
        db_session.commit()

        # Retrieve lineage
        tracker = LineageTracker(db_session)
        found_lineage = tracker.get_lineage_by_report(report.id)

        assert found_lineage is not None
        assert found_lineage.id == lineage.id
        assert found_lineage.lead_id == "lead-123"

        # Test not found
        not_found = tracker.get_lineage_by_report("invalid-id")
        assert not_found is None

    def test_search_lineage(self, db_session, test_report_template):
        """Test searching lineage records"""
        # Create multiple reports and lineages
        for i in range(5):
            report = ReportGeneration(
                business_id=f"business-{i}",
                template_id=test_report_template.id,
            )
            db_session.add(report)
            db_session.commit()

            lineage = ReportLineage(
                report_generation_id=report.id,
                lead_id=f"lead-{i % 2}",  # Alternate between lead-0 and lead-1
                pipeline_run_id=f"run-{i}",
                template_version_id="v1.0.0",
                pipeline_start_time=datetime.utcnow() - timedelta(days=i),
                pipeline_end_time=datetime.utcnow() - timedelta(days=i),
            )
            db_session.add(lineage)

        db_session.commit()

        tracker = LineageTracker(db_session)

        # Search by lead_id
        results = tracker.search_lineage(lead_id="lead-0")
        assert len(results) == 3  # lead-0 appears 3 times (i=0,2,4)

        # Search by date range
        start_date = datetime.utcnow() - timedelta(days=3)
        results = tracker.search_lineage(start_date=start_date)
        assert len(results) >= 3  # At least 3 records in last 3 days

        # Search with limit
        results = tracker.search_lineage(limit=2)
        assert len(results) == 2

    def test_capture_large_lineage_data(self, db_session, test_report_template):
        """Test capturing large lineage data that requires compression"""
        report = ReportGeneration(
            business_id="business-123",
            template_id=test_report_template.id,
        )
        db_session.add(report)
        db_session.commit()

        # Create large lineage data
        large_logs = [f"Event {i}: " + "x" * 100 for i in range(1000)]
        large_inputs = {f"field_{i}": f"value_{i}" * 50 for i in range(500)}

        lineage_data = LineageData(
            lead_id="lead-123",
            pipeline_run_id="run-456",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow() - timedelta(minutes=5),
            pipeline_end_time=datetime.utcnow(),
            pipeline_logs={"events": large_logs},
            raw_inputs=large_inputs,
        )

        tracker = LineageTracker(db_session)
        lineage = tracker.capture_lineage(report.id, lineage_data)

        assert lineage is not None
        assert lineage.raw_inputs_compressed is not None
        assert lineage.raw_inputs_size_bytes > 0
        assert lineage.compression_ratio > 0

        # Verify compression worked
        original_size = len(str(lineage_data.pipeline_logs) + str(lineage_data.raw_inputs))
        compressed_size = lineage.raw_inputs_size_bytes
        assert compressed_size < original_size  # Should be compressed
