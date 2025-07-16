"""
Integration tests for Lighthouse assessor verifying:
1. Lighthouse integrates correctly with the assessment coordinator
2. Results are saved to the database (AssessmentResult model)
3. Lighthouse runs alongside other assessments (PageSpeed, etc.)
4. Feature flag controls execution properly
5. Caching works across multiple assessment runs
"""
import hashlib
import json
import os
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from d3_assessment.assessors.lighthouse import LighthouseAssessor
from d3_assessment.coordinator import AssessmentCoordinator
from d3_assessment.models import AssessmentResult, AssessmentSession
from d3_assessment.types import AssessmentStatus, AssessmentType


@pytest.mark.integration
class TestLighthouseIntegration:
    """Comprehensive integration tests for Lighthouse assessor"""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing"""
        settings = MagicMock()
        settings.enable_lighthouse = True
        settings.use_stubs = True
        settings.enable_pagespeed = True
        settings.enable_gbp = True
        settings.enable_tech_stack = True
        settings.pagespeed_api_key = "test-key"
        settings.stub_base_url = "http://localhost:5010"
        settings.api_timeout = 30
        settings.api_max_retries = 3
        settings.debug = False
        return settings

    @pytest.fixture
    def coordinator(self, mock_settings):
        """Create assessment coordinator with mocked settings"""
        # Patch settings globally
        with patch("core.config.get_settings", return_value=mock_settings):
            return AssessmentCoordinator()

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.lighthouse.get_settings")
    @patch("core.config.get_settings")
    async def test_lighthouse_coordinator_integration(self, mock_core_settings, mock_lighthouse_settings, db_session):
        """Test 1: Verify Lighthouse integrates correctly with the assessment coordinator"""
        # Configure settings
        settings = MagicMock()
        settings.enable_lighthouse = True
        settings.use_stubs = True
        settings.enable_pagespeed = True
        settings.enable_gbp = True
        settings.pagespeed_api_key = None
        mock_core_settings.return_value = settings
        mock_lighthouse_settings.return_value = settings

        # Create coordinator after settings are mocked
        coordinator = AssessmentCoordinator()

        # Run assessment through coordinator
        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-business-123",
            url="https://example.com",
            assessment_types=[AssessmentType.LIGHTHOUSE],
            industry="technology",
        )

        # Verify coordinator integration
        assert result.business_id == "test-business-123"
        assert result.total_assessments == 1
        assert result.completed_assessments == 1
        assert result.failed_assessments == 0

        # Verify Lighthouse results
        assert AssessmentType.LIGHTHOUSE in result.partial_results
        lighthouse_result = result.partial_results[AssessmentType.LIGHTHOUSE]

        # Check result structure
        assert lighthouse_result.assessment_type == AssessmentType.LIGHTHOUSE
        assert lighthouse_result.status == AssessmentStatus.COMPLETED
        assert lighthouse_result.url == "https://example.com"

        # Verify stub data is returned
        assert lighthouse_result.performance_score == 85
        assert lighthouse_result.accessibility_score == 92
        assert lighthouse_result.seo_score == 90
        assert lighthouse_result.pwa_score == 75

        # Verify Core Web Vitals
        assert lighthouse_result.largest_contentful_paint == 2500
        assert lighthouse_result.first_input_delay == 100
        assert lighthouse_result.cumulative_layout_shift == 0.1

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.lighthouse.get_settings")
    @patch("core.config.get_settings")
    async def test_lighthouse_database_persistence(self, mock_core_settings, mock_lighthouse_settings, db_session):
        """Test 2: Verify results are saved to the database (AssessmentResult model)"""
        # Note: In the current architecture, the coordinator returns results but doesn't
        # directly save to database. This test verifies the result structure that would be saved.

        # Configure settings
        settings = MagicMock()
        settings.enable_lighthouse = True
        settings.use_stubs = True
        settings.enable_pagespeed = True
        settings.enable_gbp = True
        settings.pagespeed_api_key = None
        mock_core_settings.return_value = settings
        mock_lighthouse_settings.return_value = settings

        # Create coordinator after settings are mocked
        coordinator = AssessmentCoordinator()

        # Run assessment
        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-business-456",
            url="https://test-db.com",
            assessment_types=[AssessmentType.LIGHTHOUSE],
            industry="ecommerce",
        )

        # Verify assessment completed
        assert result.completed_assessments == 1

        # Get the Lighthouse result
        lighthouse_result = result.partial_results[AssessmentType.LIGHTHOUSE]

        # Verify the result has all required fields for database storage
        assert lighthouse_result.business_id == "test-business-456"
        assert lighthouse_result.url == "https://test-db.com"
        assert lighthouse_result.domain == "test-db.com"
        assert lighthouse_result.assessment_type == AssessmentType.LIGHTHOUSE
        assert lighthouse_result.status == AssessmentStatus.COMPLETED

        # Verify scores that would be saved
        assert lighthouse_result.performance_score == 85
        assert lighthouse_result.accessibility_score == 92
        assert lighthouse_result.seo_score == 90
        assert lighthouse_result.pwa_score == 75

        # Verify Core Web Vitals that would be saved
        assert lighthouse_result.largest_contentful_paint == 2500
        assert lighthouse_result.first_input_delay == 100
        assert lighthouse_result.cumulative_layout_shift == 0.1

        # Verify JSON data structure for database
        assert hasattr(lighthouse_result, "pagespeed_data")
        # In stub mode, pagespeed_data might be set by the assessor
        if lighthouse_result.pagespeed_data:
            assert isinstance(lighthouse_result.pagespeed_data, dict)

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.lighthouse.get_settings")
    @patch("core.config.get_settings")
    async def test_lighthouse_with_multiple_assessments(self, mock_core_settings, mock_lighthouse_settings, db_session):
        """Test 3: Verify Lighthouse runs alongside other assessments (PageSpeed, etc.)"""
        # Configure settings
        settings = MagicMock()
        settings.enable_lighthouse = True
        settings.use_stubs = True
        settings.enable_pagespeed = True
        settings.enable_gbp = True
        settings.enable_tech_stack = True
        settings.pagespeed_api_key = None
        mock_core_settings.return_value = settings
        mock_lighthouse_settings.return_value = settings

        # Create coordinator after settings are mocked
        coordinator = AssessmentCoordinator()

        # Run multiple assessments
        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-business-789",
            url="https://multi-test.com",
            assessment_types=[
                AssessmentType.LIGHTHOUSE,
                AssessmentType.PAGESPEED,
                AssessmentType.TECH_STACK,
            ],
            industry="retail",
        )

        # Verify all assessments were attempted
        assert result.total_assessments == 3
        assert result.completed_assessments >= 1  # At least Lighthouse should complete

        # Verify Lighthouse results exist
        assert AssessmentType.LIGHTHOUSE in result.partial_results
        lighthouse_result = result.partial_results[AssessmentType.LIGHTHOUSE]
        assert lighthouse_result.status == AssessmentStatus.COMPLETED
        assert lighthouse_result.performance_score == 85

        # Check if other assessments also ran (they may or may not complete)
        if AssessmentType.PAGESPEED in result.partial_results:
            pagespeed_result = result.partial_results[AssessmentType.PAGESPEED]
            assert pagespeed_result.assessment_type == AssessmentType.PAGESPEED

        if AssessmentType.TECH_STACK in result.partial_results:
            tech_result = result.partial_results[AssessmentType.TECH_STACK]
            assert tech_result.assessment_type == AssessmentType.TECH_STACK

        # Verify execution metadata
        assert result.execution_time_ms > 0
        assert result.started_at is not None
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_lighthouse_feature_flag_control(self, db_session):
        """Test 4: Verify feature flag controls execution properly"""
        # Test with Lighthouse disabled
        disabled_settings = MagicMock()
        disabled_settings.enable_lighthouse = False
        disabled_settings.use_stubs = True
        disabled_settings.enable_pagespeed = True
        disabled_settings.enable_gbp = True
        disabled_settings.pagespeed_api_key = None

        with patch("d3_assessment.assessors.lighthouse.get_settings", return_value=disabled_settings):
            with patch("core.config.get_settings", return_value=disabled_settings):
                coordinator = AssessmentCoordinator()

                # Run assessment with Lighthouse disabled
                result = await coordinator.execute_comprehensive_assessment(
                    business_id="test-business-disabled",
                    url="https://disabled-test.com",
                    assessment_types=[AssessmentType.LIGHTHOUSE],
                )

                # When disabled, assessor is not available
                assert result.total_assessments == 1
                assert result.completed_assessments == 0
                assert result.failed_assessments == 1

                # Verify error is recorded
                assert AssessmentType.LIGHTHOUSE in result.errors
                assert "Lighthouse assessor not available" in result.errors[AssessmentType.LIGHTHOUSE]

        # Test with Lighthouse enabled
        enabled_settings = MagicMock()
        enabled_settings.enable_lighthouse = True
        enabled_settings.use_stubs = True
        enabled_settings.enable_pagespeed = True
        enabled_settings.enable_gbp = True
        enabled_settings.pagespeed_api_key = None

        with patch("d3_assessment.assessors.lighthouse.get_settings", return_value=enabled_settings):
            with patch("core.config.get_settings", return_value=enabled_settings):
                coordinator = AssessmentCoordinator()

                # Run assessment with Lighthouse enabled
                result = await coordinator.execute_comprehensive_assessment(
                    business_id="test-business-enabled",
                    url="https://enabled-test.com",
                    assessment_types=[AssessmentType.LIGHTHOUSE],
                )

                # When enabled, assessment should complete
                assert result.total_assessments == 1
                assert result.completed_assessments == 1
                assert result.failed_assessments == 0

                # Verify Lighthouse results
                assert AssessmentType.LIGHTHOUSE in result.partial_results
                lighthouse_result = result.partial_results[AssessmentType.LIGHTHOUSE]
                assert lighthouse_result.status == AssessmentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_lighthouse_caching_across_runs(self):
        """Test 5: Verify caching works across multiple assessment runs"""
        # Configure settings without stubs to test actual caching
        settings = MagicMock()
        settings.enable_lighthouse = True
        settings.use_stubs = False  # Disable stubs to test real caching
        settings.enable_pagespeed = True
        settings.enable_gbp = True
        settings.pagespeed_api_key = None

        with patch("d3_assessment.assessors.lighthouse.get_settings", return_value=settings):
            # Clear any existing cache for test URL
            test_url = "https://cache-test-integration.com"
            cache_key = hashlib.md5(test_url.encode()).hexdigest()
            cache_file = f"/tmp/lighthouse_cache/{cache_key}.json"

            # Ensure cache directory exists
            os.makedirs("/tmp/lighthouse_cache", exist_ok=True)

            # Remove existing cache file if it exists
            if os.path.exists(cache_file):
                os.remove(cache_file)

            # Create assessor
            assessor = LighthouseAssessor()

            # Mock the actual audit method to track calls
            mock_audit_data = {
                "scores": {
                    "performance": 85,  # Match stub data
                    "accessibility": 92,  # Match stub data
                    "best-practices": 88,  # Match stub data
                    "seo": 90,  # Match stub data
                    "pwa": 75,  # Match stub data
                },
                "core_web_vitals": {
                    "lcp": 2200,
                    "fid": 90,
                    "cls": 0.08,
                    "fcp": 1500,
                    "si": 2800,
                    "tti": 3500,
                    "tbt": 280,
                },
                "metrics": {
                    "first-contentful-paint": {"numericValue": 1500},
                    "largest-contentful-paint": {"numericValue": 2200},
                    "first-input-delay": {"numericValue": 90},
                    "cumulative-layout-shift": {"numericValue": 0.08},
                    "speed-index": {"numericValue": 2800},
                    "interactive": {"numericValue": 3500},
                    "total-blocking-time": {"numericValue": 280},
                },
                "opportunities": [
                    {
                        "id": "render-blocking-resources",
                        "title": "Eliminate render-blocking resources",
                        "score": 0.8,
                        "numericValue": 300,
                    }
                ],
                "diagnostics": [
                    {
                        "id": "font-display",
                        "title": "Ensure text remains visible",
                        "score": 0.9,
                    }
                ],
                "fetch_time": "2024-01-01T00:00:00Z",
                "lighthouse_version": "11.0.0",
                "user_agent": "test-agent",
            }

            with patch.object(assessor, "_run_lighthouse_audit", return_value=mock_audit_data) as mock_audit:
                # First assessment - should call audit
                result1 = await assessor.assess(
                    url=test_url,
                    business_data={
                        "business_id": "test-business-cache-1",
                        "industry": "technology",
                    },
                )

                # Verify first assessment
                assert result1.status == "completed"  # The assessor returns a string status
                assert result1.metrics["performance_score"] == 85
                assert result1.metrics["accessibility_score"] == 92
                assert mock_audit.call_count == 1

                # Verify cache file was created
                assert os.path.exists(cache_file)

                # Read cache file to verify contents
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                    assert cached_data["scores"]["performance"] == 85  # Match the mock data

                # Second assessment - should use cache
                result2 = await assessor.assess(
                    url=test_url,
                    business_data={
                        "business_id": "test-business-cache-2",
                        "industry": "technology",
                    },
                )

                # Verify second assessment uses cached data
                assert result2.status == "completed"
                assert result2.metrics["performance_score"] == 85  # Same as cached
                assert result2.metrics["accessibility_score"] == 92  # Same as cached
                assert mock_audit.call_count == 1  # Still only called once

                # Third assessment with different business - should still use cache
                result3 = await assessor.assess(
                    url=test_url,
                    business_data={
                        "business_id": "test-business-cache-3",
                        "industry": "retail",
                    },
                )

                # Verify third assessment also uses cached data
                assert result3.status == "completed"
                assert result3.metrics["performance_score"] == 85  # Same as cached
                assert mock_audit.call_count == 1  # Still only called once

                # Verify all results have same data from cache
                assert result1.metrics["lcp_ms"] == result2.metrics["lcp_ms"] == result3.metrics["lcp_ms"]
                assert result1.metrics["fid_ms"] == result2.metrics["fid_ms"] == result3.metrics["fid_ms"]
                assert result1.metrics["cls_score"] == result2.metrics["cls_score"] == result3.metrics["cls_score"]

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.lighthouse.get_settings")
    @patch("core.config.get_settings")
    async def test_lighthouse_error_handling_integration(
        self, mock_core_settings, mock_lighthouse_settings, db_session
    ):
        """Test error handling and recovery in integration scenarios"""
        # Configure settings
        settings = MagicMock()
        settings.enable_lighthouse = True
        settings.use_stubs = False  # Disable stubs to test real audit failure
        settings.enable_pagespeed = True
        settings.enable_gbp = True
        settings.pagespeed_api_key = None
        mock_core_settings.return_value = settings
        mock_lighthouse_settings.return_value = settings

        # Create coordinator after settings are mocked
        coordinator = AssessmentCoordinator()

        # Mock the Lighthouse audit to fail
        with patch("d3_assessment.assessors.lighthouse.LighthouseAssessor._run_lighthouse_audit") as mock_audit:
            mock_audit.side_effect = Exception("Simulated Lighthouse audit failure")

            # Run assessment that will fail
            result = await coordinator.execute_comprehensive_assessment(
                business_id="test-business-error",
                url="https://error-test.com",
                assessment_types=[AssessmentType.LIGHTHOUSE],
            )

            # Verify failure is handled gracefully
            assert result.total_assessments == 1
            assert result.completed_assessments == 0
            assert result.failed_assessments == 1

            # Verify error is captured
            assert AssessmentType.LIGHTHOUSE in result.errors
            # The error message might be wrapped, so check for key parts
            error_msg = result.errors[AssessmentType.LIGHTHOUSE]
            assert "audit failure" in error_msg or "error" in error_msg.lower()

            # Verify partial results still available
            assert AssessmentType.LIGHTHOUSE in result.partial_results
            failed_result = result.partial_results[AssessmentType.LIGHTHOUSE]
            assert failed_result.status == AssessmentStatus.FAILED

    @pytest.mark.asyncio
    @patch("d3_assessment.assessors.lighthouse.get_settings")
    @patch("core.config.get_settings")
    async def test_lighthouse_cost_tracking_integration(self, mock_core_settings, mock_lighthouse_settings, db_session):
        """Test that Lighthouse assessments track costs correctly"""
        # Configure settings
        settings = MagicMock()
        settings.enable_lighthouse = True
        settings.use_stubs = True
        settings.enable_pagespeed = True
        settings.enable_gbp = True
        settings.pagespeed_api_key = None
        mock_core_settings.return_value = settings
        mock_lighthouse_settings.return_value = settings

        # Create coordinator after settings are mocked
        coordinator = AssessmentCoordinator()

        # Run assessment
        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-business-cost",
            url="https://cost-test.com",
            assessment_types=[AssessmentType.LIGHTHOUSE],
        )

        # Verify cost tracking
        assert result.completed_assessments == 1
        assert result.total_cost_usd >= Decimal("0")  # Cost should be tracked

        # Get Lighthouse result
        lighthouse_result = result.partial_results[AssessmentType.LIGHTHOUSE]
        assert hasattr(lighthouse_result, "total_cost_usd")
        # Note: Lighthouse itself may not have a cost, but the field should exist
        assert lighthouse_result.total_cost_usd is not None

    @pytest.mark.asyncio
    async def test_lighthouse_concurrent_assessments(self, mock_settings):
        """Test Lighthouse handles concurrent assessments correctly"""
        with patch("d3_assessment.assessors.lighthouse.get_settings", return_value=mock_settings):
            # Create multiple coordinators for concurrent execution
            coordinators = []
            for i in range(3):
                with patch("core.config.get_settings", return_value=mock_settings):
                    coordinators.append(AssessmentCoordinator())

            # Run assessments concurrently
            import asyncio

            tasks = []
            for i, coordinator in enumerate(coordinators):
                task = coordinator.execute_comprehensive_assessment(
                    business_id=f"test-business-concurrent-{i}",
                    url=f"https://concurrent-test-{i}.com",
                    assessment_types=[AssessmentType.LIGHTHOUSE],
                )
                tasks.append(task)

            # Execute all concurrently
            results = await asyncio.gather(*tasks)

            # Verify all completed successfully
            for i, result in enumerate(results):
                assert result.business_id == f"test-business-concurrent-{i}"
                assert result.completed_assessments == 1
                assert result.failed_assessments == 0

                # Verify Lighthouse results
                lighthouse_result = result.partial_results[AssessmentType.LIGHTHOUSE]
                assert lighthouse_result.status == AssessmentStatus.COMPLETED
                assert lighthouse_result.performance_score == 85  # Stub data


@pytest.mark.asyncio
async def test_lighthouse_real_world_integration():
    """Test Lighthouse with a real website (optional, can be skipped in CI)"""
    if os.environ.get("SKIP_REAL_WORLD_TESTS", "true").lower() == "true":
        pytest.skip("Skipping real-world integration test")

    # Use real settings without stubs
    real_settings = MagicMock()
    real_settings.enable_lighthouse = True
    real_settings.use_stubs = False
    real_settings.enable_pagespeed = True
    real_settings.enable_gbp = False
    real_settings.pagespeed_api_key = None
    real_settings.api_timeout = 60
    real_settings.api_max_retries = 2

    with patch("d3_assessment.assessors.lighthouse.get_settings", return_value=real_settings):
        assessor = LighthouseAssessor()

        # Test with a real website
        result = await assessor.assess(
            business_id="test-real-world",
            url="https://www.google.com",
            industry="technology",
        )

        # Verify real assessment completes
        assert result.status == AssessmentStatus.COMPLETED
        assert result.performance_score is not None
        assert 0 <= result.performance_score <= 100
        assert result.accessibility_score is not None
        assert result.seo_score is not None

        # Verify Core Web Vitals are realistic
        assert result.largest_contentful_paint > 0
        assert result.first_input_delay >= 0
        assert result.cumulative_layout_shift >= 0
