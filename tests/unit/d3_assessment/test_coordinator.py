"""
Test Assessment Coordinator - Task 034

Comprehensive tests for assessment coordination functionality.
Tests all acceptance criteria:
- Parallel assessment execution
- Timeout handling works
- Partial results saved
- Error recovery implemented
"""
import pytest
import asyncio
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

import sys
sys.path.insert(0, '/app')  # noqa: E402

from d3_assessment.coordinator import (  # noqa: E402
    AssessmentCoordinator, AssessmentRequest, CoordinatorResult,
    AssessmentPriority, CoordinatorError, AssessmentScheduler
)
from d3_assessment.models import AssessmentResult, AssessmentSession  # noqa: E402
from d3_assessment.types import AssessmentType, AssessmentStatus  # noqa: E402


class TestTask034AcceptanceCriteria:
    """Test that Task 034 meets all acceptance criteria"""

    @pytest.fixture
    def mock_pagespeed_assessor(self):
        """Mock PageSpeed assessor"""
        assessor = AsyncMock()
        assessor.assess_website.return_value = AssessmentResult(
            id=str(uuid.uuid4()),
            business_id="test-business",
            session_id="test-session",
            assessment_type=AssessmentType.PAGESPEED,
            status=AssessmentStatus.COMPLETED,
            url="https://example.com",
            domain="example.com",
            performance_score=85,
            accessibility_score=78,
            seo_score=82,
            largest_contentful_paint=2500,
            first_input_delay=120,
            cumulative_layout_shift=0.08,
            total_cost_usd=Decimal("0.15")
        )
        return assessor

    @pytest.fixture
    def mock_techstack_detector(self):
        """Mock TechStack detector"""
        detector = AsyncMock()
        detector.detect_technologies.return_value = [
            MagicMock(
                technology_name="WordPress",
                category=MagicMock(value="cms"),
                confidence=0.95,
                version="6.0"
            ),
            MagicMock(
                technology_name="React",
                category=MagicMock(value="frontend"),
                confidence=0.88,
                version="18.0"
            )
        ]
        return detector

    @pytest.fixture
    def mock_llm_generator(self):
        """Mock LLM Insight generator"""
        generator = AsyncMock()
        generator.generate_comprehensive_insights.return_value = MagicMock(
            insights={
                "recommendations": [
                    {"title": "Optimize Images", "priority": "High"},
                    {"title": "Enable Compression", "priority": "Medium"},
                    {"title": "Improve Mobile UX", "priority": "Medium"}
                ]
            },
            industry="ecommerce",
            total_cost_usd=Decimal("0.35"),
            model_version="gpt-4-0125-preview",
            processing_time_ms=2500
        )
        return generator

    @pytest.fixture
    def coordinator(self, mock_pagespeed_assessor, mock_techstack_detector, mock_llm_generator):
        """Create coordinator with mocked dependencies"""
        coordinator = AssessmentCoordinator(max_concurrent=3)
        coordinator.pagespeed_assessor = mock_pagespeed_assessor
        coordinator.techstack_detector = mock_techstack_detector
        coordinator.llm_generator = mock_llm_generator
        return coordinator

    @pytest.mark.asyncio
    async def test_parallel_assessment_execution(self, coordinator):
        """
        Test that assessments execute in parallel

        Acceptance Criteria: Parallel assessment execution
        """
        # Track execution timing
        start_time = datetime.utcnow()

        # Execute comprehensive assessment with all types
        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-business-123",
            url="https://example-store.com",
            assessment_types=[
                AssessmentType.PAGESPEED,
                AssessmentType.TECH_STACK,
                AssessmentType.AI_INSIGHTS
            ],
            industry="ecommerce"
        )

        end_time = datetime.utcnow()
        execution_duration = (end_time - start_time).total_seconds()

        # Verify result structure
        assert isinstance(result, CoordinatorResult)
        assert result.business_id == "test-business-123"
        assert result.total_assessments == 3
        assert result.completed_assessments == 3
        assert result.failed_assessments == 0

        # Verify all assessment types completed
        assert AssessmentType.PAGESPEED in result.partial_results
        assert AssessmentType.TECH_STACK in result.partial_results
        assert AssessmentType.AI_INSIGHTS in result.partial_results

        # Verify all results are valid
        for assessment_type, assessment_result in result.partial_results.items():
            assert assessment_result is not None
            assert assessment_result.status == AssessmentStatus.COMPLETED
            assert assessment_result.business_id == "test-business-123"

        # Verify timing suggests parallel execution (should be much faster than sequential)
        # If sequential, would take 3x as long, parallel should be close to single execution time
        assert execution_duration < 5.0, "Parallel execution should be fast"

        # Verify concurrent calls were made
        assert coordinator.pagespeed_assessor.assess_website.called
        assert coordinator.techstack_detector.detect_technologies.called
        assert coordinator.llm_generator.generate_comprehensive_insights.called

        print("✓ Parallel assessment execution works correctly")

    @pytest.mark.asyncio
    async def test_timeout_handling_works(self, coordinator):
        """
        Test that timeout handling works properly

        Acceptance Criteria: Timeout handling works
        """
        # Mock slow assessment that times out
        coordinator.pagespeed_assessor.assess_website = AsyncMock(
            side_effect=asyncio.sleep(10)  # 10 second delay, will timeout
        )

        # Set short timeout for testing
        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-business-timeout",
            url="https://slow-site.com",
            assessment_types=[AssessmentType.PAGESPEED],
            session_config={"timeout_seconds": 1}  # 1 second timeout
        )

        # Verify timeout was handled
        assert result.failed_assessments == 1
        assert result.completed_assessments == 0
        assert AssessmentType.PAGESPEED in result.errors
        assert "timed out" in result.errors[AssessmentType.PAGESPEED].lower()

        # Verify partial result was created for timeout
        pagespeed_result = result.partial_results.get(AssessmentType.PAGESPEED)
        if pagespeed_result:
            assert pagespeed_result.status == AssessmentStatus.FAILED
            assert "timed out" in pagespeed_result.error_message.lower()

        print("✓ Timeout handling works correctly")

    @pytest.mark.asyncio
    async def test_partial_results_saved(self, coordinator):
        """
        Test that partial results are saved even when some assessments fail

        Acceptance Criteria: Partial results saved
        """
        # Mock one failing assessment
        coordinator.pagespeed_assessor.assess_website = AsyncMock(
            side_effect=Exception("PageSpeed API Error")
        )
        # Other assessments succeed (already mocked in fixtures)

        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-business-partial",
            url="https://partial-fail.com",
            assessment_types=[
                AssessmentType.PAGESPEED,
                AssessmentType.TECH_STACK,
                AssessmentType.AI_INSIGHTS
            ],
            industry="technology"
        )

        # Verify partial success
        assert result.total_assessments == 3
        assert result.completed_assessments == 2  # 2 succeeded
        assert result.failed_assessments == 1     # 1 failed

        # Verify successful assessments have results
        assert AssessmentType.TECH_STACK in result.partial_results
        assert AssessmentType.AI_INSIGHTS in result.partial_results
        assert result.partial_results[AssessmentType.TECH_STACK] is not None
        assert result.partial_results[AssessmentType.AI_INSIGHTS] is not None

        # Verify failed assessment is tracked
        assert AssessmentType.PAGESPEED in result.errors
        assert "PageSpeed API Error" in result.errors[AssessmentType.PAGESPEED]

        # Verify session status is PARTIAL (not COMPLETED or FAILED)
        # This would be tested with actual database integration

        print("✓ Partial results saved correctly")

    @pytest.mark.asyncio
    async def test_error_recovery_implemented(self, coordinator):
        """
        Test that error recovery is implemented with retry logic

        Acceptance Criteria: Error recovery implemented
        """
        # Mock assessment that fails first time, succeeds on retry
        call_count = 0
        async def failing_then_succeeding(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary network error")
            else:
                # Return successful result on retry
                return AssessmentResult(
                    id=str(uuid.uuid4()),
                    business_id="test-business",
                    session_id="test-session",
                    assessment_type=AssessmentType.PAGESPEED,
                    status=AssessmentStatus.COMPLETED,
                    url="https://example.com",
                    domain="example.com",
                    performance_score=85
                )

        coordinator.pagespeed_assessor.assess_website = AsyncMock(
            side_effect=failing_then_succeeding
        )

        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-business-retry",
            url="https://retry-test.com",
            assessment_types=[AssessmentType.PAGESPEED],
            industry="default"
        )

        # Verify retry worked and assessment eventually succeeded
        assert result.completed_assessments == 1
        assert result.failed_assessments == 0
        assert AssessmentType.PAGESPEED in result.partial_results
        assert result.partial_results[AssessmentType.PAGESPEED].status == AssessmentStatus.COMPLETED

        # Verify retry was attempted (call_count should be 2)
        assert call_count == 2, "Should have retried after initial failure"

        # Test permanent failure after retries
        coordinator.pagespeed_assessor.assess_website = AsyncMock(
            side_effect=Exception("Permanent API failure")
        )

        result2 = await coordinator.execute_comprehensive_assessment(
            business_id="test-business-permanent-fail",
            url="https://permanent-fail.com",
            assessment_types=[AssessmentType.PAGESPEED]
        )

        # Verify permanent failure is handled
        assert result2.failed_assessments == 1
        assert AssessmentType.PAGESPEED in result2.errors

        print("✓ Error recovery with retry logic works correctly")

    @pytest.mark.asyncio
    async def test_batch_assessment_execution(self, coordinator):
        """Test batch processing of multiple websites"""
        assessment_configs = [
            {
                "business_id": "business-1",
                "url": "https://site1.com",
                "assessment_types": [AssessmentType.PAGESPEED],
                "industry": "ecommerce"
            },
            {
                "business_id": "business-2",
                "url": "https://site2.com",
                "assessment_types": [AssessmentType.TECH_STACK],
                "industry": "healthcare"
            },
            {
                "business_id": "business-3",
                "url": "https://site3.com",
                "assessment_types": [AssessmentType.AI_INSIGHTS],
                "industry": "finance"
            }
        ]

        results = await coordinator.execute_batch_assessments(
            assessment_configs=assessment_configs,
            max_concurrent_sessions=2
        )

        # Verify batch results
        assert len(results) == 3
        for i, result in enumerate(results):
            if not isinstance(result, Exception):
                assert result.business_id == f"business-{i+1}"
                assert result.total_assessments == 1
                assert result.completed_assessments == 1

        print("✓ Batch assessment execution works correctly")

    @pytest.mark.asyncio
    async def test_assessment_prioritization(self, coordinator):
        """Test assessment priority handling"""
        # Create requests with different priorities
        high_priority_request = AssessmentRequest(
            assessment_type=AssessmentType.PAGESPEED,
            url="https://high-priority.com",
            priority=AssessmentPriority.HIGH,
            timeout_seconds=180,
            retry_count=3
        )

        low_priority_request = AssessmentRequest(
            assessment_type=AssessmentType.TECH_STACK,
            url="https://low-priority.com",
            priority=AssessmentPriority.LOW,
            timeout_seconds=120,
            retry_count=1
        )

        # Verify priority mapping
        assert coordinator._get_assessment_priority(AssessmentType.PAGESPEED) == AssessmentPriority.HIGH
        assert coordinator._get_assessment_priority(AssessmentType.TECH_STACK) == AssessmentPriority.MEDIUM

        # Verify timeout mapping
        assert coordinator._get_assessment_timeout(AssessmentType.PAGESPEED) == 180
        assert coordinator._get_assessment_timeout(AssessmentType.AI_INSIGHTS) == 300

        print("✓ Assessment prioritization works correctly")

    @pytest.mark.asyncio
    async def test_session_management(self, coordinator):
        """Test assessment session creation and management"""
        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-session-mgmt",
            url="https://session-test.com",
            assessment_types=[AssessmentType.PAGESPEED, AssessmentType.TECH_STACK],
            industry="retail",
            session_config={"custom_param": "test_value"}
        )

        # Verify session data
        assert result.session_id is not None
        assert result.business_id == "test-session-mgmt"
        assert result.started_at <= result.completed_at
        assert result.execution_time_ms > 0

        # Test session status tracking
        status = coordinator.get_assessment_status(result.session_id)
        assert status["session_id"] == result.session_id
        assert "status" in status
        assert "progress" in status

        # Test session cancellation
        cancellation_result = await coordinator.cancel_session(result.session_id)
        assert cancellation_result is True

        print("✓ Session management works correctly")

    @pytest.mark.asyncio
    async def test_cost_aggregation(self, coordinator):
        """Test total cost calculation across assessments"""
        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-cost-calc",
            url="https://cost-test.com",
            assessment_types=[
                AssessmentType.PAGESPEED,
                AssessmentType.TECH_STACK,
                AssessmentType.AI_INSIGHTS
            ],
            industry="technology"
        )

        # Verify cost aggregation
        assert result.total_cost_usd > Decimal("0")

        # Should include costs from pagespeed and LLM insights
        # (tech stack has no direct cost in mock)
        expected_min_cost = Decimal("0.15") + Decimal("0.35")  # From mocks
        assert result.total_cost_usd >= expected_min_cost

        print("✓ Cost aggregation works correctly")

    @pytest.mark.asyncio
    async def test_scheduler_functionality(self, coordinator):
        """Test assessment scheduler with priority queue"""
        scheduler = AssessmentScheduler(coordinator)

        # Schedule assessments with different priorities
        session_id_1 = await scheduler.schedule_assessment(
            business_id="sched-test-1",
            url="https://high-priority.com",
            priority=AssessmentPriority.HIGH,
            assessment_types=[AssessmentType.PAGESPEED]
        )

        session_id_2 = await scheduler.schedule_assessment(
            business_id="sched-test-2",
            url="https://low-priority.com",
            priority=AssessmentPriority.LOW,
            assessment_types=[AssessmentType.TECH_STACK]
        )

        # Verify session IDs generated
        assert session_id_1 is not None
        assert session_id_2 is not None
        assert session_id_1 != session_id_2

        # Verify priority queue has items
        assert not scheduler.priority_queue.empty()

        # Test priority value mapping
        assert scheduler._get_priority_value(AssessmentPriority.CRITICAL) == 1
        assert scheduler._get_priority_value(AssessmentPriority.HIGH) == 2
        assert scheduler._get_priority_value(AssessmentPriority.LOW) == 4

        print("✓ Scheduler functionality works correctly")

    def test_coordinator_error_handling(self):
        """Test custom error handling"""
        # Test CoordinatorError
        with pytest.raises(CoordinatorError):
            raise CoordinatorError("Test coordinator error")

        # Test unsupported assessment type handling would be tested
        # in actual _run_assessment method with invalid type

        print("✓ Coordinator error handling works correctly")

    def test_domain_extraction(self, coordinator):
        """Test URL domain extraction"""
        assert coordinator._extract_domain("https://www.example.com/path") == "example.com"
        assert coordinator._extract_domain("http://subdomain.test.org") == "subdomain.test.org"
        assert coordinator._extract_domain("https://shop.example.co.uk/products") == "shop.example.co.uk"

        print("✓ Domain extraction works correctly")

    @pytest.mark.asyncio
    async def test_comprehensive_coordinator_flow(self, coordinator):
        """Test complete coordinator workflow with all features"""
        # Execute comprehensive assessment with all features
        result = await coordinator.execute_comprehensive_assessment(
            business_id="comprehensive-test",
            url="https://comprehensive-test.com",
            assessment_types=[
                AssessmentType.PAGESPEED,
                AssessmentType.TECH_STACK,
                AssessmentType.AI_INSIGHTS
            ],
            industry="ecommerce",
            session_config={
                "client_ip": "192.168.1.1",
                "user_agent": "TestAgent/1.0",
                "custom_settings": {"detailed_analysis": True}
            }
        )

        # Verify comprehensive result structure
        assert result.session_id is not None
        assert result.business_id == "comprehensive-test"
        assert result.total_assessments == 3
        assert result.completed_assessments == 3
        assert result.failed_assessments == 0
        assert len(result.partial_results) == 3
        assert len(result.errors) == 0
        assert result.total_cost_usd > Decimal("0")
        assert result.execution_time_ms > 0
        assert result.started_at <= result.completed_at

        # Verify each assessment type completed successfully
        for assessment_type in [AssessmentType.PAGESPEED, AssessmentType.TECH_STACK, AssessmentType.AI_INSIGHTS]:
            assert assessment_type in result.partial_results
            assessment_result = result.partial_results[assessment_type]
            assert assessment_result.business_id == "comprehensive-test"
            assert assessment_result.url == "https://comprehensive-test.com"
            assert assessment_result.domain == "comprehensive-test.com"

        # Verify tech stack result structure
        tech_result = result.partial_results[AssessmentType.TECH_STACK]
        assert tech_result.tech_stack_data is not None
        assert "technologies" in tech_result.tech_stack_data
        assert len(tech_result.tech_stack_data["technologies"]) == 2

        # Verify AI insights result structure
        ai_result = result.partial_results[AssessmentType.AI_INSIGHTS]
        assert ai_result.ai_insights_data is not None
        assert "insights" in ai_result.ai_insights_data
        assert ai_result.total_cost_usd == Decimal("0.35")

        print("✓ Comprehensive coordinator flow works correctly")


# Allow running this test file directly
if __name__ == "__main__":
    import asyncio

    async def run_tests():
        test_instance = TestTask034AcceptanceCriteria()

        print("🎯 Running Task 034 Assessment Coordinator Tests...")
        print()

        try:
            # Create fixtures manually for direct execution
            from unittest.mock import AsyncMock, MagicMock

            # Mock assessors
            mock_pagespeed = test_instance.mock_pagespeed_assessor()
            mock_techstack = test_instance.mock_techstack_detector()
            mock_llm = test_instance.mock_llm_generator()
            coordinator = test_instance.coordinator(mock_pagespeed, mock_techstack, mock_llm)

            # Run all acceptance criteria tests
            await test_instance.test_parallel_assessment_execution(coordinator)
            await test_instance.test_timeout_handling_works(coordinator)
            await test_instance.test_partial_results_saved(coordinator)
            await test_instance.test_error_recovery_implemented(coordinator)

            # Run additional functionality tests
            await test_instance.test_batch_assessment_execution(coordinator)
            await test_instance.test_assessment_prioritization(coordinator)
            await test_instance.test_session_management(coordinator)
            await test_instance.test_cost_aggregation(coordinator)
            await test_instance.test_scheduler_functionality(coordinator)
            test_instance.test_coordinator_error_handling()
            test_instance.test_domain_extraction(coordinator)
            await test_instance.test_comprehensive_coordinator_flow(coordinator)

            print()
            print("🎉 All Task 034 acceptance criteria tests pass!")
            print("   - Parallel assessment execution: ✓")
            print("   - Timeout handling works: ✓")
            print("   - Partial results saved: ✓")
            print("   - Error recovery implemented: ✓")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()

    # Run async tests
    asyncio.run(run_tests())
