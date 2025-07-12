"""
Unit tests for lineage models
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from d6_reports.lineage.models import ReportLineage, ReportLineageAudit
from d6_reports.models import ReportGeneration, ReportStatus, ReportType


class TestLineageModels:
    """Test suite for lineage model functionality"""

    def test_create_report_lineage(self, db_session, test_report_template):
        """Test creating a report lineage record"""
        # Create report generation first
        report = ReportGeneration(
            business_id="business-123",
            template_id=test_report_template.id,
            report_type=ReportType.BUSINESS_AUDIT,
            status=ReportStatus.COMPLETED,
        )
        db_session.add(report)
        db_session.commit()

        # Create lineage
        lineage = ReportLineage(
            report_generation_id=report.id,
            lead_id="lead-123",
            pipeline_run_id="run-456",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow() - timedelta(minutes=5),
            pipeline_end_time=datetime.utcnow(),
            pipeline_logs={"events": ["start", "process", "complete"]},
            raw_inputs_compressed=b"compressed data",
            raw_inputs_size_bytes=1024,
            compression_ratio=75.5,
        )
        db_session.add(lineage)
        db_session.commit()

        # Verify creation
        assert lineage.id is not None
        assert lineage.lead_id == "lead-123"
        assert lineage.pipeline_run_id == "run-456"
        assert lineage.access_count == 0
        assert lineage.last_accessed_at is None

    def test_report_lineage_constraints(self, db_session, test_report_template):
        """Test database constraints on lineage model"""
        # Create report
        report = ReportGeneration(
            business_id="business-123",
            template_id=test_report_template.id,
        )
        db_session.add(report)
        db_session.commit()

        # Test unique constraint on report_generation_id
        lineage1 = ReportLineage(
            report_generation_id=report.id,
            lead_id="lead-123",
            pipeline_run_id="run-456",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow(),
            pipeline_end_time=datetime.utcnow(),
        )
        db_session.add(lineage1)
        db_session.commit()

        # Try to create duplicate
        lineage2 = ReportLineage(
            report_generation_id=report.id,  # Same report ID
            lead_id="lead-456",
            pipeline_run_id="run-789",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow(),
            pipeline_end_time=datetime.utcnow(),
        )
        db_session.add(lineage2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_pipeline_duration_calculation(self, db_session, test_report_template):
        """Test pipeline duration calculation"""
        report = ReportGeneration(
            business_id="business-123",
            template_id=test_report_template.id,
        )
        db_session.add(report)
        db_session.commit()

        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=45.5)

        lineage = ReportLineage(
            report_generation_id=report.id,
            lead_id="lead-123",
            pipeline_run_id="run-456",
            template_version_id="v1.0.0",
            pipeline_start_time=start_time,
            pipeline_end_time=end_time,
        )

        # Calculate duration manually
        duration = (lineage.pipeline_end_time - lineage.pipeline_start_time).total_seconds()
        assert duration == pytest.approx(45.5, rel=0.1)

    def test_access_count_default(self, db_session, test_report_template):
        """Test access count default value"""
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

        # Check default access count
        assert lineage.access_count == 0
        assert lineage.last_accessed_at is None

    def test_lineage_audit_creation(self, db_session, test_report_template):
        """Test creating lineage audit records"""
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

        # Create audit record
        audit = ReportLineageAudit(
            lineage_id=lineage.id,
            action="view",
            user_id="user-123",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        db_session.add(audit)
        db_session.commit()

        # Verify
        assert audit.id is not None
        assert audit.action == "view"
        assert audit.user_id == "user-123"
        assert audit.accessed_at is not None

    def test_cascade_delete(self, db_session, test_report_template):
        """Test cascade deletion of lineage when report is deleted"""
        # Create report, lineage, and audit
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

        audit = ReportLineageAudit(
            lineage_id=lineage.id,
            action="view",
        )
        db_session.add(audit)
        db_session.commit()

        lineage_id = lineage.id
        audit_id = audit.id

        # Delete report
        db_session.delete(report)
        db_session.commit()

        # Verify cascade
        assert db_session.get(ReportLineage, lineage_id) is None
        assert db_session.get(ReportLineageAudit, audit_id) is None

    def test_check_constraints(self, db_session, test_report_template):
        """Test check constraints on lineage fields"""
        report = ReportGeneration(
            business_id="business-123",
            template_id=test_report_template.id,
        )
        db_session.add(report)
        db_session.commit()

        # Test negative raw_inputs_size_bytes
        lineage = ReportLineage(
            report_generation_id=report.id,
            lead_id="lead-123",
            pipeline_run_id="run-456",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow(),
            pipeline_end_time=datetime.utcnow(),
            raw_inputs_size_bytes=-100,  # Invalid
        )
        db_session.add(lineage)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()

        # Test compression_ratio out of range
        lineage2 = ReportLineage(
            report_generation_id=report.id,
            lead_id="lead-123",
            pipeline_run_id="run-456",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow(),
            pipeline_end_time=datetime.utcnow(),
            compression_ratio=150.0,  # Invalid (> 100)
        )
        db_session.add(lineage2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()