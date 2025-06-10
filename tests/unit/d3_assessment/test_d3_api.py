"""
Test Assessment API Endpoints - Task 035

Comprehensive tests for assessment API functionality.
Tests all acceptance criteria:
- Trigger assessment endpoint
- Status checking works
- Results retrieval API
- Proper error responses
"""
import asyncio
import sys
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, "/app")  # noqa: E402

from d3_assessment.api import (assessment_sessions, coordinator,  # noqa: E402
                               router)
from d3_assessment.coordinator import CoordinatorResult  # noqa: E402
from d3_assessment.models import AssessmentResult  # noqa: E402
from d3_assessment.types import AssessmentStatus, AssessmentType  # noqa: E402

# Create test app
test_app = FastAPI()
test_app.include_router(router)
client = TestClient(test_app)


class TestTask035AcceptanceCriteria:
    """Test that Task 035 meets all acceptance criteria"""

    def setup_method(self):
        """Setup for each test"""
        # Clear assessment sessions
        assessment_sessions.clear()

        # Mock coordinator methods
        self.mock_coordinator = AsyncMock()

    @pytest.fixture
    def sample_trigger_request(self):
        """Sample trigger assessment request"""
        return {
            "business_id": "biz_test123",
            "url": "https://example-store.com",
            "assessment_types": ["pagespeed", "tech_stack", "ai_insights"],
            "industry": "ecommerce",
            "priority": "high",
            "session_config": {"detailed_analysis": True},
        }

    @pytest.fixture
    def sample_coordinator_result(self):
        """Sample coordinator result for testing"""
        return CoordinatorResult(
            session_id="sess_test123456",
            business_id="biz_test123",
            total_assessments=3,
            completed_assessments=3,
            failed_assessments=0,
            partial_results={
                AssessmentType.PAGESPEED: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id="biz_test123",
                    session_id="sess_test123456",
                    assessment_type=AssessmentType.PAGESPEED,
                    status=AssessmentStatus.COMPLETED,
                    url="https://example-store.com",
                    domain="example-store.com",
                    performance_score=85,
                    accessibility_score=78,
                    seo_score=92,
                    largest_contentful_paint=2500,
                    first_input_delay=120,
                    cumulative_layout_shift=0.08,
                    speed_index=3200,
                    time_to_interactive=4100,
                ),
                AssessmentType.TECH_STACK: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id="biz_test123",
                    session_id="sess_test123456",
                    assessment_type=AssessmentType.TECH_STACK,
                    status=AssessmentStatus.COMPLETED,
                    url="https://example-store.com",
                    domain="example-store.com",
                    tech_stack_data={
                        "technologies": [
                            {
                                "technology_name": "WordPress",
                                "category": "cms",
                                "confidence": 0.95,
                                "version": "6.0",
                            },
                            {
                                "technology_name": "WooCommerce",
                                "category": "ecommerce",
                                "confidence": 0.90,
                                "version": "7.0",
                            },
                        ]
                    },
                ),
                AssessmentType.AI_INSIGHTS: AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id="biz_test123",
                    session_id="sess_test123456",
                    assessment_type=AssessmentType.AI_INSIGHTS,
                    status=AssessmentStatus.COMPLETED,
                    url="https://example-store.com",
                    domain="example-store.com",
                    ai_insights_data={
                        "insights": {
                            "recommendations": [
                                {
                                    "title": "Optimize Image Loading",
                                    "priority": "High",
                                    "impact": "Reduce LCP by 30%",
                                },
                                {
                                    "title": "Enable Compression",
                                    "priority": "Medium",
                                    "impact": "Reduce file sizes by 60%",
                                },
                                {
                                    "title": "Improve Mobile UX",
                                    "priority": "Medium",
                                    "impact": "Better mobile conversion",
                                },
                            ],
                            "industry_insights": {
                                "industry": "ecommerce",
                                "competitive_advantage": "Fast loading improves conversion rates",
                            },
                            "summary": {
                                "overall_health": "Good performance with improvement opportunities"
                            },
                        },
                        "model_version": "gpt-4-0125-preview",
                        "total_cost_usd": 0.35,
                    },
                    total_cost_usd=Decimal("0.35"),
                ),
            },
            errors={},
            total_cost_usd=Decimal("0.50"),
            execution_time_ms=150000,
            started_at=datetime.utcnow() - timedelta(minutes=3),
            completed_at=datetime.utcnow(),
        )

    def test_trigger_assessment_endpoint(self, sample_trigger_request):
        """
        Test triggering assessment endpoint works correctly

        Acceptance Criteria: Trigger assessment endpoint
        """
        with patch("d3_assessment.api.coordinator") as mock_coord:
            # Mock the coordinator execution
            mock_coord.execute_comprehensive_assessment = AsyncMock()

            response = client.post(
                "/api/v1/assessments/trigger", json=sample_trigger_request
            )

            # Verify response structure
            assert response.status_code == 200
            data = response.json()

            # Check required fields
            assert "session_id" in data
            assert "business_id" in data
            assert "status" in data
            assert "total_assessments" in data
            assert "estimated_completion_time" in data
            assert "tracking_url" in data

            # Verify values
            assert data["business_id"] == "biz_test123"
            assert data["status"] == "running"
            assert data["total_assessments"] == 3
            assert data["tracking_url"].startswith("/api/v1/assessments/")
            assert data["tracking_url"].endswith("/status")

            # Verify session ID format
            session_id = data["session_id"]
            assert session_id.startswith("sess_")
            assert len(session_id) == 17  # "sess_" + 12 hex chars

        print("✓ Trigger assessment endpoint works correctly")

    def test_trigger_assessment_validation_errors(self):
        """Test trigger assessment with validation errors"""
        # Test missing required fields
        response = client.post("/api/v1/assessments/trigger", json={})
        assert response.status_code == 422

        # Test invalid URL
        invalid_request = {
            "business_id": "biz_test123",
            "url": "not-a-valid-url",
            "industry": "ecommerce",
        }
        response = client.post("/api/v1/assessments/trigger", json=invalid_request)
        assert response.status_code == 422

        # Test invalid priority
        invalid_priority_request = {
            "business_id": "biz_test123",
            "url": "https://example.com",
            "priority": "invalid_priority",
        }
        response = client.post(
            "/api/v1/assessments/trigger", json=invalid_priority_request
        )
        assert response.status_code == 422

        # Test invalid industry
        invalid_industry_request = {
            "business_id": "biz_test123",
            "url": "https://example.com",
            "industry": "invalid_industry",
        }
        response = client.post(
            "/api/v1/assessments/trigger", json=invalid_industry_request
        )
        assert response.status_code == 422

        print("✓ Trigger assessment validation errors handled correctly")

    def test_status_checking_works(self, sample_coordinator_result):
        """
        Test status checking endpoint works correctly

        Acceptance Criteria: Status checking works
        """
        session_id = "sess_test123456"

        # Test with completed assessment
        assessment_sessions[session_id] = sample_coordinator_result

        response = client.get(f"/api/v1/assessments/{session_id}/status")
        assert response.status_code == 200

        data = response.json()

        # Check required fields
        assert "session_id" in data
        assert "business_id" in data
        assert "status" in data
        assert "progress" in data
        assert "total_assessments" in data
        assert "completed_assessments" in data
        assert "failed_assessments" in data
        assert "started_at" in data

        # Verify values for completed assessment
        assert data["session_id"] == session_id
        assert data["business_id"] == "biz_test123"
        assert data["status"] == "completed"
        assert data["progress"] == "3/3 complete"
        assert data["total_assessments"] == 3
        assert data["completed_assessments"] == 3
        assert data["failed_assessments"] == 0
        assert data["completed_at"] is not None
        assert data["errors"] is None

        print("✓ Status checking works for completed assessment")

        # Test with running assessment (not in sessions)
        running_session_id = "sess_running123"
        with patch(
            "d3_assessment.api.coordinator.get_assessment_status"
        ) as mock_status:
            mock_status.return_value = {
                "status": "running",
                "progress": "1/3 complete",
                "total_assessments": 3,
                "completed_assessments": 1,
                "estimated_completion": datetime.utcnow() + timedelta(minutes=5),
            }

            response = client.get(f"/api/v1/assessments/{running_session_id}/status")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "running"
            assert data["current_step"] == "Processing assessments..."
            assert data["estimated_completion"] is not None

        print("✓ Status checking works for running assessment")

    def test_status_checking_validation_errors(self):
        """Test status checking with validation errors"""
        # Test invalid session ID
        response = client.get("/api/v1/assessments/invalid/status")
        assert response.status_code == 400

        data = response.json()
        # Error details are nested in the 'detail' field
        assert "detail" in data
        detail = data["detail"]
        assert "error" in detail
        assert detail["error"] == "validation_error"

        print("✓ Status checking validation errors handled correctly")

    def test_results_retrieval_api(self, sample_coordinator_result):
        """
        Test results retrieval API works correctly

        Acceptance Criteria: Results retrieval API
        """
        session_id = "sess_test123456"
        assessment_sessions[session_id] = sample_coordinator_result

        response = client.get(f"/api/v1/assessments/{session_id}/results")
        assert response.status_code == 200

        data = response.json()

        # Check required fields
        assert "session_id" in data
        assert "business_id" in data
        assert "url" in data
        assert "domain" in data
        assert "status" in data
        assert "total_assessments" in data
        assert "completed_assessments" in data
        assert "started_at" in data
        assert "completed_at" in data
        assert "execution_time_ms" in data
        assert "total_cost_usd" in data

        # Verify assessment results
        assert data["session_id"] == session_id
        assert data["business_id"] == "biz_test123"
        assert data["url"] == "https://example-store.com"
        assert data["domain"] == "example-store.com"
        assert data["status"] == "completed"
        assert data["total_assessments"] == 3
        assert data["completed_assessments"] == 3
        assert data["failed_assessments"] == 0
        assert float(data["total_cost_usd"]) == 0.50
        assert data["execution_time_ms"] == 150000

        # Check PageSpeed results
        assert "pagespeed_results" in data
        pagespeed = data["pagespeed_results"]
        assert pagespeed["performance_score"] == 85
        assert pagespeed["accessibility_score"] == 78
        assert pagespeed["seo_score"] == 92
        assert pagespeed["largest_contentful_paint"] == 2500
        assert pagespeed["first_input_delay"] == 120
        assert pagespeed["cumulative_layout_shift"] == 0.08

        # Check Tech Stack results
        assert "tech_stack_results" in data
        tech_stack = data["tech_stack_results"]
        assert len(tech_stack) == 2
        assert tech_stack[0]["technology_name"] == "WordPress"
        assert tech_stack[0]["category"] == "cms"
        assert tech_stack[0]["confidence"] == 0.95
        assert tech_stack[1]["technology_name"] == "WooCommerce"

        # Check AI Insights results
        assert "ai_insights_results" in data
        ai_insights = data["ai_insights_results"]
        assert len(ai_insights["recommendations"]) == 3
        assert ai_insights["recommendations"][0]["title"] == "Optimize Image Loading"
        assert ai_insights["industry_insights"]["industry"] == "ecommerce"
        assert ai_insights["ai_model_version"] == "gpt-4-0125-preview"
        assert float(ai_insights["processing_cost_usd"]) == 0.35

        print("✓ Results retrieval API works correctly")

    def test_results_retrieval_not_found(self):
        """Test results retrieval for non-existent session"""
        response = client.get("/api/v1/assessments/sess_notfound/results")
        assert response.status_code == 404

        data = response.json()
        # Error details are nested in the 'detail' field
        assert "detail" in data
        detail = data["detail"]
        assert "error" in detail
        assert detail["error"] == "not_found"
        assert "not found" in detail["message"].lower()

        print("✓ Results retrieval handles not found correctly")

    def test_results_retrieval_still_running(self):
        """Test results retrieval for still running assessment"""
        session_id = "sess_running123"

        # Create a running assessment result
        running_result = CoordinatorResult(
            session_id=session_id,
            business_id="biz_test123",
            total_assessments=3,
            completed_assessments=1,  # Still running
            failed_assessments=0,
            partial_results={},
            errors={},
            total_cost_usd=Decimal("0"),
            execution_time_ms=30000,
            started_at=datetime.utcnow() - timedelta(minutes=1),
            completed_at=datetime.utcnow(),
        )

        assessment_sessions[session_id] = running_result

        response = client.get(f"/api/v1/assessments/{session_id}/results")
        assert response.status_code == 409

        data = response.json()
        # Error details are nested in the 'detail' field
        assert "detail" in data
        detail = data["detail"]
        assert "error" in detail
        assert detail["error"] == "assessment_running"

        print("✓ Results retrieval handles running assessment correctly")

    def test_proper_error_responses(self):
        """
        Test that proper error responses are returned

        Acceptance Criteria: Proper error responses
        """
        # Test 404 error format
        response = client.get("/api/v1/assessments/sess_notfound/results")
        assert response.status_code == 404

        error_data = response.json()
        # Error details are nested in the 'detail' field
        assert "detail" in error_data
        detail = error_data["detail"]
        assert "error" in detail
        assert "message" in detail
        assert "timestamp" in detail
        assert detail["error"] == "not_found"

        # Test validation error format (422 uses standard FastAPI format)
        response = client.post("/api/v1/assessments/trigger", json={})
        assert response.status_code == 422

        error_data = response.json()
        # 422 responses use standard FastAPI validation error format
        assert "detail" in error_data
        assert isinstance(error_data["detail"], list)
        assert len(error_data["detail"]) > 0

        # Test validation error for invalid business ID
        invalid_request = {
            "business_id": "ab",  # Too short
            "url": "https://example.com",
        }
        response = client.post("/api/v1/assessments/trigger", json=invalid_request)
        assert response.status_code == 400

        error_data = response.json()
        # 400 responses use our custom error format
        assert "detail" in error_data
        detail = error_data["detail"]
        assert detail["error"] == "validation_error"
        assert "Business ID must be at least 3 characters" in detail["message"]

        print("✓ Proper error responses implemented correctly")

    def test_batch_assessment_endpoint(self):
        """Test batch assessment functionality"""
        batch_request = {
            "assessments": [
                {
                    "business_id": "biz_test1",
                    "url": "https://site1.com",
                    "industry": "ecommerce",
                },
                {
                    "business_id": "biz_test2",
                    "url": "https://site2.com",
                    "industry": "healthcare",
                },
            ],
            "max_concurrent": 2,
            "batch_id": "batch_test123",
        }

        with patch(
            "d3_assessment.api.coordinator.execute_batch_assessments"
        ) as mock_batch:
            mock_batch.return_value = []

            response = client.post("/api/v1/assessments/batch", json=batch_request)
            assert response.status_code == 200

            data = response.json()
            assert "batch_id" in data
            assert "total_assessments" in data
            assert "session_ids" in data
            assert "tracking_url" in data

            assert data["batch_id"] == "batch_test123"
            assert data["total_assessments"] == 2
            assert len(data["session_ids"]) == 2

        print("✓ Batch assessment endpoint works correctly")

    def test_cancel_assessment_endpoint(self):
        """Test assessment cancellation"""
        session_id = "sess_cancel123"

        with patch("d3_assessment.api.coordinator.cancel_session") as mock_cancel:
            mock_cancel.return_value = True

            response = client.delete(f"/api/v1/assessments/{session_id}")
            assert response.status_code == 200

            data = response.json()
            assert "message" in data
            assert session_id in data["message"]

        print("✓ Cancel assessment endpoint works correctly")

    def test_health_check_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/api/v1/assessments/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "uptime_seconds" in data
        assert "dependencies" in data

        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert isinstance(data["uptime_seconds"], int)
        assert isinstance(data["dependencies"], dict)

        print("✓ Health check endpoint works correctly")

    def test_api_error_handling_edge_cases(self):
        """Test edge cases in API error handling"""
        # Test extremely short business ID
        response = client.get("/api/v1/assessments/a/status")
        assert response.status_code == 400

        # Test extremely short session ID
        response = client.get("/api/v1/assessments/sess_a/status")
        assert response.status_code == 400

        # Test batch with too many assessments
        large_batch = {
            "assessments": [
                {"business_id": f"biz_{i}", "url": f"https://site{i}.com"}
                for i in range(51)  # More than max allowed
            ]
        }
        response = client.post("/api/v1/assessments/batch", json=large_batch)
        assert response.status_code == 422

        # Test batch with empty assessments list
        empty_batch = {"assessments": []}
        response = client.post("/api/v1/assessments/batch", json=empty_batch)
        assert response.status_code == 422

        print("✓ API error handling edge cases work correctly")

    def test_api_response_schemas(
        self, sample_trigger_request, sample_coordinator_result
    ):
        """Test that API responses match expected schemas"""
        # Test trigger response schema
        with patch("d3_assessment.api.coordinator") as mock_coord:
            mock_coord.execute_comprehensive_assessment = AsyncMock()

            response = client.post(
                "/api/v1/assessments/trigger", json=sample_trigger_request
            )
            data = response.json()

            # Validate trigger response fields
            required_fields = [
                "session_id",
                "business_id",
                "status",
                "total_assessments",
                "estimated_completion_time",
                "tracking_url",
            ]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"

        # Test status response schema
        session_id = "sess_test123456"
        assessment_sessions[session_id] = sample_coordinator_result

        response = client.get(f"/api/v1/assessments/{session_id}/status")
        data = response.json()

        status_required_fields = [
            "session_id",
            "business_id",
            "status",
            "progress",
            "total_assessments",
            "completed_assessments",
            "failed_assessments",
            "started_at",
        ]
        for field in status_required_fields:
            assert field in data, f"Missing required field: {field}"

        # Test results response schema
        response = client.get(f"/api/v1/assessments/{session_id}/results")
        data = response.json()

        results_required_fields = [
            "session_id",
            "business_id",
            "url",
            "domain",
            "status",
            "total_assessments",
            "completed_assessments",
            "started_at",
            "completed_at",
            "execution_time_ms",
            "total_cost_usd",
        ]
        for field in results_required_fields:
            assert field in data, f"Missing required field: {field}"

        print("✓ API response schemas are correct")

    def test_comprehensive_api_flow(self, sample_trigger_request):
        """Test complete API workflow from trigger to results"""
        with patch("d3_assessment.api.coordinator") as mock_coord:
            # Mock coordinator execution to return a proper result
            mock_result = CoordinatorResult(
                session_id="test-session-id",
                business_id="test-business",
                total_assessments=3,
                completed_assessments=0,  # Show running status initially
                failed_assessments=0,
                partial_results={},
                errors={},
                total_cost_usd=Decimal("0.50"),
                execution_time_ms=1000,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
            mock_coord.execute_comprehensive_assessment = AsyncMock(return_value=mock_result)
            mock_coord.get_assessment_status.return_value = {
                "status": "running",
                "progress": "50%",
                "total_assessments": 3,
                "completed_assessments": 1,
                "estimated_completion": None,
            }
            mock_coord.cancel_session.return_value = True

            # 1. Trigger assessment
            trigger_response = client.post(
                "/api/v1/assessments/trigger", json=sample_trigger_request
            )
            assert trigger_response.status_code == 200

            session_id = trigger_response.json()["session_id"]

            # 2. Check status (running)
            status_response = client.get(f"/api/v1/assessments/{session_id}/status")
            assert status_response.status_code == 200
            assert status_response.json()["status"] == "running"

            # 3. Simulate completion by adding to sessions
            completed_result = CoordinatorResult(
                session_id=session_id,
                business_id="biz_test123",
                total_assessments=3,
                completed_assessments=3,
                failed_assessments=0,
                partial_results={
                    AssessmentType.PAGESPEED: AssessmentResult(
                        id=str(uuid.uuid4()),
                        business_id="biz_test123",
                        session_id=session_id,
                        assessment_type=AssessmentType.PAGESPEED,
                        status=AssessmentStatus.COMPLETED,
                        url="https://example-store.com",
                        domain="example-store.com",
                        performance_score=85,
                    )
                },
                errors={},
                total_cost_usd=Decimal("0.25"),
                execution_time_ms=120000,
                started_at=datetime.utcnow() - timedelta(minutes=2),
                completed_at=datetime.utcnow(),
            )
            assessment_sessions[session_id] = completed_result

            # 4. Check status (completed)
            status_response = client.get(f"/api/v1/assessments/{session_id}/status")
            assert status_response.status_code == 200
            assert status_response.json()["status"] == "completed"

            # 5. Get results
            results_response = client.get(f"/api/v1/assessments/{session_id}/results")
            assert results_response.status_code == 200

            results_data = results_response.json()
            assert results_data["session_id"] == session_id
            assert results_data["status"] == "completed"
            assert results_data["total_assessments"] == 3

        print("✓ Comprehensive API flow works correctly")


# Allow running this test file directly
if __name__ == "__main__":
    import asyncio

    async def run_tests():
        test_instance = TestTask035AcceptanceCriteria()

        print("🌐 Running Task 035 Assessment API Tests...")
        print()

        try:
            # Setup
            test_instance.setup_method()

            # Create fixtures manually for direct execution
            sample_trigger_request = {
                "business_id": "biz_test123",
                "url": "https://example-store.com",
                "assessment_types": ["pagespeed", "tech_stack", "ai_insights"],
                "industry": "ecommerce",
                "priority": "high",
            }

            sample_coordinator_result = test_instance.sample_coordinator_result()

            # Run all acceptance criteria tests
            test_instance.test_trigger_assessment_endpoint(sample_trigger_request)
            test_instance.test_trigger_assessment_validation_errors()
            test_instance.test_status_checking_works(sample_coordinator_result)
            test_instance.test_status_checking_validation_errors()
            test_instance.test_results_retrieval_api(sample_coordinator_result)
            test_instance.test_results_retrieval_not_found()
            test_instance.test_results_retrieval_still_running()
            test_instance.test_proper_error_responses()

            # Run additional functionality tests
            test_instance.test_batch_assessment_endpoint()
            test_instance.test_cancel_assessment_endpoint()
            test_instance.test_health_check_endpoint()
            test_instance.test_api_error_handling_edge_cases()
            test_instance.test_api_response_schemas(
                sample_trigger_request, sample_coordinator_result
            )
            test_instance.test_comprehensive_api_flow(sample_trigger_request)

            print()
            print("🎉 All Task 035 acceptance criteria tests pass!")
            print("   - Trigger assessment endpoint: ✓")
            print("   - Status checking works: ✓")
            print("   - Results retrieval API: ✓")
            print("   - Proper error responses: ✓")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()

    # Run async tests
    asyncio.run(run_tests())
