"""
Unit tests for lineage API endpoints - updated for current implementation
"""

import gzip
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from d6_reports.lineage.models import ReportLineage, ReportLineageAudit


class TestLineageAPIv2:
    """Test suite for lineage API endpoints"""

    @pytest.fixture
    def sample_lineage_data(self, db_session, test_report_template):
        """Create sample lineage data for tests"""
        from d6_reports.models import ReportGeneration
        
        # First create the report generation
        report = ReportGeneration(
            id="report-001",
            business_id="business-123",
            template_id=test_report_template.id,
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

        return lineage

    def test_get_lineage_by_report_id(self, test_client: TestClient, sample_lineage_data, db_session):
        """Test retrieving lineage by report ID"""
        lineage = sample_lineage_data

        # Override the get_db dependency to use our test session
        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get(f"/api/lineage/{lineage.report_generation_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == lineage.id
        assert data["report_id"] == lineage.report_generation_id
        assert data["lead_id"] == "lead-123"
        assert data["pipeline_run_id"] == "run-456"
        assert data["template_version_id"] == "v1.0.0"
        assert "created_at" in data
        assert data["pipeline_logs_size"] > 0
        assert data["raw_inputs_size"] == lineage.raw_inputs_size_bytes

        # Verify audit log was created
        audit = db_session.query(ReportLineageAudit).filter(
            ReportLineageAudit.lineage_id == lineage.id
        ).first()
        assert audit is not None
        assert audit.action == "view_lineage"

    def test_search_lineage_no_filters(self, test_client: TestClient, db_session):
        """Test searching lineage records without filters"""
        # Create multiple lineages
        for i in range(3):
            lineage = ReportLineage(
                report_generation_id=f"report-{i:03d}",
                lead_id=f"lead-{i}",
                pipeline_run_id=f"run-{i}",
                template_version_id="v1.0.0",
                pipeline_start_time=datetime.utcnow() - timedelta(days=i),
                pipeline_end_time=datetime.utcnow() - timedelta(days=i),
            )
            db_session.add(lineage)
        db_session.commit()

        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get("/api/lineage/search")
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 3
        
        # Should be ordered by created_at descending
        assert results[0]["lead_id"] == "lead-0"
        assert results[1]["lead_id"] == "lead-1"
        assert results[2]["lead_id"] == "lead-2"

    def test_search_lineage_with_filters(self, test_client: TestClient, sample_lineage_data, db_session):
        """Test searching lineage records with filters"""
        # Add another lineage
        lineage2 = ReportLineage(
            report_generation_id="report-002",
            lead_id="lead-456",
            pipeline_run_id="run-789",
            template_version_id="v2.0.0",
            pipeline_start_time=datetime.utcnow(),
            pipeline_end_time=datetime.utcnow(),
        )
        db_session.add(lineage2)
        db_session.commit()

        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        # Search by lead_id
        response = test_client.get("/api/lineage/search", params={"lead_id": "lead-123"})
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1
        assert results[0]["lead_id"] == "lead-123"

        # Search by template_version_id
        response = test_client.get("/api/lineage/search", params={"template_version_id": "v2.0.0"})
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1
        assert results[0]["template_version_id"] == "v2.0.0"

    def test_view_pipeline_logs(self, test_client: TestClient, sample_lineage_data, db_session):
        """Test viewing pipeline logs"""
        lineage = sample_lineage_data

        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get(f"/api/lineage/{lineage.id}/logs")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["lineage_id"] == lineage.id
        assert data["report_id"] == lineage.report_generation_id
        assert "logs" in data
        assert data["logs"]["summary"]["total_events"] == 2
        assert data["log_size"] > 0

        # Verify audit log
        audits = db_session.query(ReportLineageAudit).filter(
            ReportLineageAudit.lineage_id == lineage.id,
            ReportLineageAudit.action == "view_logs"
        ).all()
        assert len(audits) == 1

    def test_download_raw_inputs(self, test_client: TestClient, sample_lineage_data, db_session):
        """Test downloading compressed raw inputs"""
        lineage = sample_lineage_data

        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get(f"/api/lineage/{lineage.id}/download")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/gzip"
        assert "attachment" in response.headers["content-disposition"]
        assert f"lineage_{lineage.id}_raw_inputs.json.gz" in response.headers["content-disposition"]
        
        # Verify content is valid gzip
        decompressed = gzip.decompress(response.content)
        data = json.loads(decompressed)
        assert data["lead_id"] == "lead-123"
        assert data["pipeline_run_id"] == "run-456"

        # Verify audit log
        audit = db_session.query(ReportLineageAudit).filter(
            ReportLineageAudit.lineage_id == lineage.id,
            ReportLineageAudit.action == "download_raw_inputs"
        ).first()
        assert audit is not None

    def test_get_panel_stats(self, test_client: TestClient, db_session):
        """Test getting lineage panel statistics"""
        # Create test data
        for i in range(5):
            lineage = ReportLineage(
                report_generation_id=f"report-{i:03d}",
                lead_id=f"lead-{i}",
                pipeline_run_id=f"run-{i}",
                template_version_id="v1.0.0" if i < 3 else "v2.0.0",
                pipeline_start_time=datetime.utcnow() - timedelta(hours=i*6),
                pipeline_end_time=datetime.utcnow() - timedelta(hours=i*6),
                raw_inputs_size_bytes=1024 * (i + 1),
                created_at=datetime.utcnow() - timedelta(hours=i*6)
            )
            db_session.add(lineage)
        db_session.commit()

        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.get("/api/lineage/panel/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_records"] == 5
        assert data["recent_records_24h"] >= 4  # At least 4 created in last 24h
        assert len(data["template_distribution"]) == 2
        assert data["template_distribution"][0]["version"] == "v1.0.0"
        assert data["template_distribution"][0]["count"] == 3
        assert data["total_storage_mb"] > 0

    def test_delete_lineage(self, test_client: TestClient, sample_lineage_data, db_session):
        """Test deleting a lineage record"""
        lineage = sample_lineage_data

        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        response = test_client.delete(f"/api/lineage/{lineage.id}")
        
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

        # Verify lineage was deleted
        deleted = db_session.query(ReportLineage).filter(
            ReportLineage.id == lineage.id
        ).first()
        assert deleted is None

    def test_error_handling(self, test_client: TestClient, db_session):
        """Test error handling for non-existent resources"""
        from database.session import get_db
        def override_get_db():
            yield db_session
        test_client.app.dependency_overrides[get_db] = override_get_db

        # Non-existent report
        response = test_client.get("/api/lineage/non-existent-report")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

        # Non-existent lineage for logs
        response = test_client.get("/api/lineage/non-existent-id/logs")
        assert response.status_code == 404

        # Non-existent lineage for download
        response = test_client.get("/api/lineage/non-existent-id/download")
        assert response.status_code == 404

        # Delete non-existent lineage
        response = test_client.delete("/api/lineage/non-existent-id")
        assert response.status_code == 404