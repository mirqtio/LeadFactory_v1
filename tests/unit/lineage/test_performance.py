"""
Performance tests for lineage module
"""

import time
import json
import gzip
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from d6_reports.lineage.models import ReportLineage
from d6_reports.models import ReportGeneration


class TestLineagePerformance:
    """Performance tests for lineage requirements"""

    @pytest.fixture
    def large_lineage(self, db_session, test_report_template):
        """Create lineage with large compressed data"""
        report = ReportGeneration(
            business_id="business-perf",
            template_id=test_report_template.id,
        )
        db_session.add(report)
        db_session.commit()

        # Create large but compressible data
        large_data = {
            "lead_id": "lead-perf",
            "pipeline_run_id": "run-perf",
            "pipeline_logs": [f"Event {i}: Processing step {i % 10}" for i in range(10000)],
            "raw_inputs": {
                f"field_{i}": f"value_{i % 100}" * 10 
                for i in range(1000)
            },
        }

        # Compress to ~1.5MB
        compressed = gzip.compress(json.dumps(large_data).encode('utf-8'), compresslevel=6)
        
        lineage = ReportLineage(
            report_generation_id=report.id,
            lead_id="lead-perf",
            pipeline_run_id="run-perf",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow() - timedelta(minutes=10),
            pipeline_end_time=datetime.utcnow(),
            pipeline_logs={"summary": {"total_events": 10000}},
            raw_inputs_compressed=compressed,
            raw_inputs_size_bytes=len(compressed),
            compression_ratio=85.0,
        )
        db_session.add(lineage)
        db_session.commit()

        return lineage

    def test_json_viewer_load_time(self, test_client: TestClient, large_lineage):
        """Test JSON viewer loads in < 500ms as per requirement"""
        # Warm up the connection
        test_client.get("/health")

        # Test multiple times to ensure consistency
        load_times = []
        
        for _ in range(5):
            start_time = time.time()
            response = test_client.get(f"/api/lineage/{large_lineage.id}/logs")
            load_time = time.time() - start_time
            
            assert response.status_code == 200
            load_times.append(load_time)

        # All attempts should be under 500ms
        assert all(t < 0.5 for t in load_times), f"Load times: {load_times}"
        
        # Average should be well under 500ms
        avg_time = sum(load_times) / len(load_times)
        assert avg_time < 0.5, f"Average load time: {avg_time:.3f}s"

    def test_download_size_limit(self, test_client: TestClient, db_session, test_report_template):
        """Test downloads are compressed to ≤2MB as per requirement"""
        report = ReportGeneration(
            business_id="business-size",
            template_id=test_report_template.id,
        )
        db_session.add(report)
        db_session.commit()

        # Create data that would be >2MB uncompressed but ≤2MB compressed
        huge_data = {
            "lead_id": "lead-size",
            "pipeline_run_id": "run-size",
            "huge_logs": ["x" * 1000 for _ in range(3000)],  # ~3MB uncompressed
        }

        # Compress with high compression
        compressed = gzip.compress(json.dumps(huge_data).encode('utf-8'), compresslevel=9)
        
        # Ensure it's under 2MB
        assert len(compressed) <= 2 * 1024 * 1024

        lineage = ReportLineage(
            report_generation_id=report.id,
            lead_id="lead-size",
            pipeline_run_id="run-size",
            template_version_id="v1.0.0",
            pipeline_start_time=datetime.utcnow(),
            pipeline_end_time=datetime.utcnow(),
            raw_inputs_compressed=compressed,
            raw_inputs_size_bytes=len(compressed),
            compression_ratio=90.0,
        )
        db_session.add(lineage)
        db_session.commit()

        # Download and verify size
        response = test_client.get(f"/api/lineage/{lineage.id}/download")
        
        assert response.status_code == 200
        assert len(response.content) <= 2 * 1024 * 1024  # ≤2MB

    def test_batch_status_response_time(self, test_client: TestClient, db_session, test_report_template):
        """Test batch status API responds in <500ms"""
        # Create multiple lineages
        for i in range(100):
            report = ReportGeneration(
                business_id=f"business-batch-{i}",
                template_id=test_report_template.id,
            )
            db_session.add(report)
            db_session.commit()

            lineage = ReportLineage(
                report_generation_id=report.id,
                lead_id=f"lead-batch-{i % 10}",
                pipeline_run_id=f"run-batch-{i}",
                template_version_id="v1.0.0",
                pipeline_start_time=datetime.utcnow() - timedelta(minutes=i),
                pipeline_end_time=datetime.utcnow() - timedelta(minutes=i),
            )
            db_session.add(lineage)
        
        db_session.commit()

        # Test search performance
        start_time = time.time()
        response = test_client.get("/api/lineage/search", params={"limit": 50})
        elapsed = time.time() - start_time

        assert response.status_code == 200
        assert len(response.json()) == 50
        assert elapsed < 0.5, f"Search took {elapsed:.3f}s"

    def test_concurrent_access(self, test_client: TestClient, large_lineage):
        """Test multiple concurrent requests maintain performance"""
        import concurrent.futures
        
        def make_request():
            start_time = time.time()
            response = test_client.get(f"/api/lineage/{large_lineage.id}/logs")
            elapsed = time.time() - start_time
            return response.status_code, elapsed

        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        assert all(status == 200 for status, _ in results)
        
        # All should be under 500ms
        times = [elapsed for _, elapsed in results]
        assert all(t < 0.5 for t in times), f"Request times: {times}"