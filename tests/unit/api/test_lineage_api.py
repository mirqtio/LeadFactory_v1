"""
Unit tests for the lineage API endpoints (P0-023)
"""

import gzip
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool

from database.base import Base
from d6_reports.lineage.models import ReportLineage, ReportLineageAudit
from d6_reports.models import ReportTemplate, ReportGeneration, ReportType, TemplateFormat


@pytest.fixture(scope="function")
def db_session():
    """Create a database session for testing"""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)

    Session = scoped_session(sessionmaker(bind=engine))
    session = Session()

    yield session

    session.close()
    Session.remove()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def test_client():
    """Create a test client for API testing"""
    from main import app
    return TestClient(app)


@pytest.fixture
def sample_report_and_lineage(db_session):
    """Create sample report generation and lineage data"""
    # Create template
    template = ReportTemplate(
        id="test-template-001",
        name="test_template",
        display_name="Test Template",
        description="Test template for unit tests",
        template_type=ReportType.BUSINESS_AUDIT,
        format=TemplateFormat.HTML,
        version="1.0.0",
        html_template="<html>{{content}}</html>",
        css_styles="body { font-family: Arial; }",
        is_active=True,
        is_default=True,
    )
    db_session.add(template)
    db_session.commit()

    # Create report generation
    report = ReportGeneration(
        business_id="business-123",
        template_id=template.id,
    )
    db_session.add(report)
    db_session.commit()

    # Create lineage with compressed data
    raw_data = {
        "lead_id": "lead-123",
        "pipeline_run_id": "run-456",
        "business_data": {"name": "Test Business", "website": "test.com"},
        "assessment_results": {"score": 85, "issues": ["Issue 1", "Issue 2"]},
    }
    compressed_data = gzip.compress(json.dumps(raw_data).encode('utf-8'))

    lineage = ReportLineage(
        report_generation_id=report.id,
        lead_id="lead-123",
        pipeline_run_id="run-456",
        template_version_id="v1.0.0",
        pipeline_start_time=datetime.utcnow() - timedelta(minutes=5),
        pipeline_end_time=datetime.utcnow(),
        pipeline_logs=json.dumps({
            "events": [
                {"timestamp": "2025-01-01T10:00:00", "event": "Pipeline started"},
                {"timestamp": "2025-01-01T10:05:00", "event": "Pipeline completed"}
            ],
            "summary": {"total_events": 2, "duration_seconds": 300}
        }),
        raw_inputs_compressed=compressed_data,
        raw_inputs_size_bytes=len(compressed_data),
        compression_ratio=75.0,
    )
    db_session.add(lineage)
    db_session.commit()

    return report, lineage


class TestLineageAPI:
    """Test suite for lineage API endpoints"""

    def test_get_lineage_by_report_id(self, test_client: TestClient, sample_report_and_lineage, db_session):
        """Test retrieving lineage by report ID"""
        report, lineage = sample_report_and_lineage

        # Override the get_db dependency
        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get(f"/api/lineage/{report.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == lineage.id
        assert data["report_id"] == report.id
        assert data["lead_id"] == "lead-123"
        assert data["pipeline_run_id"] == "run-456"
        assert data["template_version_id"] == "v1.0.0"
        assert "created_at" in data
        assert data["pipeline_logs_size"] > 0
        assert data["raw_inputs_size"] == lineage.raw_inputs_size_bytes

    def test_search_lineage(self, test_client: TestClient, sample_report_and_lineage, db_session):
        """Test searching lineage records"""
        report, lineage = sample_report_and_lineage

        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        # Search without filters
        response = test_client.get("/api/lineage/search")
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1
        assert results[0]["lead_id"] == "lead-123"

        # Search by lead_id
        response = test_client.get("/api/lineage/search", params={"lead_id": "lead-123"})
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1

        # Search with non-existent lead_id
        response = test_client.get("/api/lineage/search", params={"lead_id": "non-existent"})
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 0

    def test_view_pipeline_logs(self, test_client: TestClient, sample_report_and_lineage, db_session):
        """Test viewing pipeline logs"""
        report, lineage = sample_report_and_lineage

        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get(f"/api/lineage/{lineage.id}/logs")

        assert response.status_code == 200
        data = response.json()

        assert data["lineage_id"] == lineage.id
        assert data["report_id"] == report.id
        assert "logs" in data
        assert data["logs"]["summary"]["total_events"] == 2

    def test_download_raw_inputs(self, test_client: TestClient, sample_report_and_lineage, db_session):
        """Test downloading compressed raw inputs"""
        report, lineage = sample_report_and_lineage

        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get(f"/api/lineage/{lineage.id}/download")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/gzip"
        assert "attachment" in response.headers["content-disposition"]

        # Verify content is valid gzip
        decompressed = gzip.decompress(response.content)
        data = json.loads(decompressed)
        assert data["lead_id"] == "lead-123"

    def test_get_panel_stats(self, test_client: TestClient, sample_report_and_lineage, db_session):
        """Test getting lineage panel statistics"""
        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get("/api/lineage/panel/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["total_records"] == 1
        assert "recent_records_24h" in data
        assert "template_distribution" in data
        assert "total_storage_mb" in data

    def test_error_handling(self, test_client: TestClient, db_session):
        """Test error handling for non-existent resources"""
        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        # Non-existent report
        response = test_client.get("/api/lineage/non-existent-report")
        assert response.status_code == 404

        # Non-existent lineage for logs
        response = test_client.get("/api/lineage/non-existent-id/logs")
        assert response.status_code == 404

        # Non-existent lineage for download
        response = test_client.get("/api/lineage/non-existent-id/download")
        assert response.status_code == 404

    def test_audit_logging(self, test_client: TestClient, sample_report_and_lineage, db_session):
        """Test that API calls create audit logs"""
        report, lineage = sample_report_and_lineage

        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        # View lineage
        test_client.get(f"/api/lineage/{report.id}")

        # Check audit log was created
        audit = db_session.query(ReportLineageAudit).filter(
            ReportLineageAudit.lineage_id == lineage.id
        ).first()

        assert audit is not None
        assert audit.action == "view_lineage"

        # View logs
        test_client.get(f"/api/lineage/{lineage.id}/logs")

        # Check second audit log
        audits = db_session.query(ReportLineageAudit).filter(
            ReportLineageAudit.lineage_id == lineage.id
        ).all()

        assert len(audits) == 2
        assert audits[1].action == "view_logs"
