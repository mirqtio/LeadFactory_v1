"""
Unit tests for lineage API endpoints
"""

import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from d6_reports.lineage.models import ReportLineage, ReportLineageAudit
from d6_reports.models import ReportGeneration


class TestLineageAPI:
    """Test suite for lineage API endpoints"""

    @pytest.fixture
    def app(self):
        """Create FastAPI test app"""
        from fastapi import FastAPI
        from api.lineage.routes import router
        
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def test_client(self, app, db_session):
        """Create test client with database override"""
        from fastapi.testclient import TestClient
        # Import get_db from where the routes import it
        from api.dependencies import get_db
        
        def override_get_db():
            try:
                yield db_session
            finally:
                pass  # Don't close the session here as it's managed by the fixture
        
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as client:
            yield client
        
        app.dependency_overrides.clear()

    @pytest.fixture
    def sample_lineage(self, db_session, test_report_template):
        """Create sample lineage data for tests"""
        # Create report
        report = ReportGeneration(
            business_id="business-123",
            template_id=test_report_template.id,
        )
        db_session.add(report)
        db_session.commit()

        # Create lineage with compressed data
        import gzip

        raw_data = {
            "lead_id": "lead-123",
            "pipeline_run_id": "run-456",
            "raw_inputs": {"field1": "value1", "field2": "value2"},
            "pipeline_logs": ["Event 1", "Event 2", "Event 3"],
        }
        compressed_data = gzip.compress(json.dumps(raw_data).encode("utf-8"))

        lineage = ReportLineage(
            report_generation_id=report.id,
            lead_id="lead-123",
            pipeline_run_id="run-456",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow() - timedelta(minutes=5),
            pipeline_end_time=datetime.utcnow(),
            pipeline_logs={"summary": {"total_events": 3}},
            raw_inputs_compressed=compressed_data,
            raw_inputs_size_bytes=len(compressed_data),
            compression_ratio=50.0,
        )
        db_session.add(lineage)
        db_session.commit()

        return report, lineage

    def test_get_lineage_by_report(self, test_client: TestClient, sample_lineage):
        """Test retrieving lineage by report ID"""
        report, lineage = sample_lineage

        response = test_client.get(f"/api/lineage/{report.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["lineage_id"] == lineage.id
        assert data["report_generation_id"] == report.id
        assert data["lead_id"] == "lead-123"
        assert data["pipeline_run_id"] == "run-456"
        assert data["template_version_id"] == "v1.0.0"
        assert "created_at" in data
        assert "pipeline_duration_seconds" in data
        assert "raw_inputs_size_bytes" in data

    def test_get_lineage_not_found(self, test_client: TestClient):
        """Test retrieving non-existent lineage"""
        response = test_client.get("/api/lineage/invalid-report-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_search_lineage(self, test_client: TestClient, db_session, test_report_template):
        """Test searching lineage records"""
        # Create multiple lineages
        for i in range(3):
            report = ReportGeneration(
                business_id=f"business-{i}",
                template_id=test_report_template.id,
            )
            db_session.add(report)
            db_session.commit()

            lineage = ReportLineage(
                report_generation_id=report.id,
                lead_id="lead-123" if i == 0 else f"lead-{i}",
                pipeline_run_id=f"run-{i}",
                template_version_id="v1.0.0",
                pipeline_start_time=datetime.utcnow() - timedelta(days=i),
                pipeline_end_time=datetime.utcnow() - timedelta(days=i),
            )
            db_session.add(lineage)

        db_session.commit()

        # Search by lead_id
        response = test_client.get("/api/lineage/search", params={"lead_id": "lead-123"})
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1
        assert results[0]["lead_id"] == "lead-123"

        # Search with limit
        response = test_client.get("/api/lineage/search", params={"limit": 2})
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 2

    def test_search_lineage_date_filters(self, test_client: TestClient, sample_lineage):
        """Test searching with date filters"""
        # Search with valid date
        start_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
        response = test_client.get("/api/lineage/search", params={"start_date": start_date})
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1  # Should find our sample lineage created today

    def test_view_lineage_logs(self, test_client: TestClient, sample_lineage):
        """Test viewing lineage logs"""
        report, lineage = sample_lineage

        response = test_client.get(f"/api/lineage/{lineage.id}/logs")

        assert response.status_code == 200
        data = response.json()

        assert data["lineage_id"] == lineage.id
        assert "pipeline_logs" in data
        assert "raw_inputs" in data
        assert "pipeline_start_time" in data
        assert "pipeline_end_time" in data

    def test_view_lineage_logs_not_found(self, test_client: TestClient):
        """Test viewing logs for non-existent lineage"""
        response = test_client.get("/api/lineage/invalid-id/logs")
        assert response.status_code == 404

    def test_download_raw_inputs(self, test_client: TestClient, sample_lineage):
        """Test downloading compressed raw inputs"""
        report, lineage = sample_lineage

        response = test_client.get(f"/api/lineage/{lineage.id}/download")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/gzip"
        assert "attachment" in response.headers["content-disposition"]
        assert f"lineage_{lineage.id}_raw_inputs.json.gz" in response.headers["content-disposition"]

        # Verify content is valid gzip
        import gzip

        decompressed = gzip.decompress(response.content)
        data = json.loads(decompressed)
        assert data["lead_id"] == "lead-123"

    def test_download_no_data(self, test_client: TestClient, db_session, test_report_template):
        """Test downloading when no compressed data exists"""
        # Create lineage without compressed data
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
            raw_inputs_compressed=None,  # No data
        )
        db_session.add(lineage)
        db_session.commit()

        response = test_client.get(f"/api/lineage/{lineage.id}/download")
        assert response.status_code == 404  # API returns 404 for no raw inputs

    def test_audit_logging(self, test_client: TestClient, sample_lineage, db_session):
        """Test that API calls create audit logs"""
        report, lineage = sample_lineage

        # View lineage
        test_client.get(f"/api/lineage/{report.id}")

        # Check audit log was created
        audit = db_session.query(ReportLineageAudit).filter(ReportLineageAudit.lineage_id == lineage.id).first()

        assert audit is not None
        assert audit.action == "view_lineage"

        # View logs
        test_client.get(f"/api/lineage/{lineage.id}/logs")

        # Check second audit log
        audits = db_session.query(ReportLineageAudit).filter(ReportLineageAudit.lineage_id == lineage.id).all()

        assert len(audits) == 2
        assert audits[1].action == "view_logs"

        # Download
        test_client.get(f"/api/lineage/{lineage.id}/download")

        # Check third audit log
        audits = db_session.query(ReportLineageAudit).filter(ReportLineageAudit.lineage_id == lineage.id).all()

        assert len(audits) == 3
        assert audits[2].action == "download_raw_inputs"

    def test_response_time_performance(self, test_client: TestClient, sample_lineage):
        """Test that JSON viewer loads in < 500ms"""
        report, lineage = sample_lineage

        import time

        start_time = time.time()

        response = test_client.get(f"/api/lineage/{lineage.id}/logs")

        elapsed_time = time.time() - start_time

        assert response.status_code == 200
        assert elapsed_time < 0.5  # Should load in under 500ms
