"""
Integration tests for Lighthouse assessor with coordinator
"""

from unittest.mock import MagicMock, patch

import pytest

from d3_assessment.coordinator import AssessmentCoordinator
from d3_assessment.models import AssessmentType
from d3_assessment.types import AssessmentStatus


@pytest.mark.integration
class TestLighthouseIntegration:
    """Test Lighthouse assessor integration with coordinator"""

    @pytest.fixture
    def coordinator(self):
        """Create assessment coordinator"""
        return AssessmentCoordinator()

    @patch("d3_assessment.assessors.lighthouse.get_settings")
    @patch("core.config.get_settings")
    async def test_lighthouse_assessment_with_stubs(self, mock_core_settings, mock_lighthouse_settings):
        """Test Lighthouse assessment through coordinator with stubs"""
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

        # Run comprehensive assessment including Lighthouse
        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-business-123",
            url="https://example.com",
            assessment_types=[AssessmentType.LIGHTHOUSE],
            industry="technology",
        )

        # Verify result structure
        assert result.business_id == "test-business-123"
        assert result.total_assessments == 1
        assert result.completed_assessments == 1
        assert result.failed_assessments == 0

        # Check Lighthouse results
        assert AssessmentType.LIGHTHOUSE in result.partial_results
        lighthouse_result = result.partial_results[AssessmentType.LIGHTHOUSE]

        assert lighthouse_result.assessment_type == AssessmentType.LIGHTHOUSE
        assert lighthouse_result.status == AssessmentStatus.COMPLETED
        assert lighthouse_result.performance_score == 85
        assert lighthouse_result.accessibility_score == 92
        assert lighthouse_result.seo_score == 90
        assert lighthouse_result.pwa_score == 75

        # Check Core Web Vitals
        assert lighthouse_result.largest_contentful_paint == 2500
        assert lighthouse_result.first_input_delay == 100
        assert lighthouse_result.cumulative_layout_shift == 0.1

    @patch("d3_assessment.assessors.lighthouse.get_settings")
    @patch("core.config.get_settings")
    async def test_lighthouse_assessment_disabled(self, mock_core_settings, mock_lighthouse_settings):
        """Test Lighthouse assessment when feature is disabled"""
        # Configure settings
        settings = MagicMock()
        settings.enable_lighthouse = False
        settings.use_stubs = False
        settings.enable_pagespeed = True
        settings.enable_gbp = True
        settings.pagespeed_api_key = None
        mock_core_settings.return_value = settings
        mock_lighthouse_settings.return_value = settings

        # Create coordinator after settings are mocked
        coordinator = AssessmentCoordinator()

        # Run assessment
        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-business-123",
            url="https://example.com",
            assessment_types=[AssessmentType.LIGHTHOUSE],
            industry="technology",
        )

        # When feature is disabled, assessor is not available so it fails
        assert result.total_assessments == 1
        assert result.completed_assessments == 0
        assert result.failed_assessments == 1

        # Lighthouse should be in results with failed status
        assert AssessmentType.LIGHTHOUSE in result.partial_results
        lighthouse_result = result.partial_results[AssessmentType.LIGHTHOUSE]
        assert lighthouse_result.status == AssessmentStatus.FAILED

        # Check error in errors dict
        assert AssessmentType.LIGHTHOUSE in result.errors
        assert "Lighthouse assessor not available" in result.errors[AssessmentType.LIGHTHOUSE]

    @patch("d3_assessment.assessors.lighthouse.get_settings")
    @patch("core.config.get_settings")
    async def test_lighthouse_with_other_assessments(self, mock_core_settings, mock_lighthouse_settings):
        """Test Lighthouse running alongside other assessments"""
        # Configure settings for all assessors
        settings = MagicMock()
        settings.enable_lighthouse = True
        settings.use_stubs = True
        settings.enable_pagespeed = True
        settings.enable_gbp = True
        settings.pagespeed_api_key = "test-key"
        settings.stub_base_url = "http://localhost:5010"
        settings.api_timeout = 30
        settings.api_max_retries = 3
        settings.debug = False
        mock_core_settings.return_value = settings
        mock_lighthouse_settings.return_value = settings

        # Create coordinator after settings are mocked
        coordinator = AssessmentCoordinator()

        # Run multiple assessments - just Lighthouse and Tech Stack
        result = await coordinator.execute_comprehensive_assessment(
            business_id="test-business-123",
            url="https://example.com",
            assessment_types=[AssessmentType.LIGHTHOUSE, AssessmentType.TECH_STACK],
            industry="technology",
        )

        # Verify assessments completed
        assert result.total_assessments == 2
        assert result.completed_assessments >= 1  # At least Lighthouse

        # Check Lighthouse results exist
        assert AssessmentType.LIGHTHOUSE in result.partial_results
        lighthouse_result = result.partial_results[AssessmentType.LIGHTHOUSE]

        # Lighthouse uses stub data
        assert lighthouse_result.performance_score == 85
        assert lighthouse_result.accessibility_score == 92
        assert lighthouse_result.seo_score == 90

    @patch("d3_assessment.assessors.lighthouse.get_settings")
    @patch("core.config.get_settings")
    async def test_lighthouse_caching(self, mock_core_settings, mock_lighthouse_settings):
        """Test that Lighthouse results are cached"""
        # Configure settings
        settings = MagicMock()
        settings.enable_lighthouse = True
        settings.use_stubs = False
        settings.enable_pagespeed = True
        settings.enable_gbp = True
        settings.pagespeed_api_key = None
        mock_core_settings.return_value = settings
        mock_lighthouse_settings.return_value = settings

        # Mock the Lighthouse CLI availability check
        with patch("d3_assessment.assessors.lighthouse.LighthouseAssessor.is_available", return_value=True):
            # Create coordinator after settings are mocked
            coordinator = AssessmentCoordinator()

        # Clear any existing cache for this URL
        import hashlib
        import os

        cache_key = hashlib.md5(b"https://cache-test.example.com").hexdigest()
        cache_file = f"/tmp/lighthouse_cache/{cache_key}.json"
        if os.path.exists(cache_file):
            os.remove(cache_file)

        # Mock the audit method to track calls
        with patch("d3_assessment.assessors.lighthouse.LighthouseAssessor._run_lighthouse_audit") as mock_audit:
            mock_audit.return_value = {
                "scores": {"performance": 80},
                "core_web_vitals": {"lcp": 2000},
                "metrics": {},
                "opportunities": [],
                "diagnostics": [],
                "fetch_time": "2024-01-01T00:00:00Z",
                "lighthouse_version": "11.0.0",
                "user_agent": "test",
            }

            # First assessment - should run audit
            result1 = await coordinator.execute_comprehensive_assessment(
                business_id="test-business-123",
                url="https://cache-test.example.com",
                assessment_types=[AssessmentType.LIGHTHOUSE],
            )

            # Second assessment - should use cache
            result2 = await coordinator.execute_comprehensive_assessment(
                business_id="test-business-456",
                url="https://cache-test.example.com",
                assessment_types=[AssessmentType.LIGHTHOUSE],
            )

            # Audit should only be called once due to caching
            assert mock_audit.call_count == 1

            # Both results should have the same data
            lighthouse1 = result1.partial_results.get(AssessmentType.LIGHTHOUSE)
            lighthouse2 = result2.partial_results.get(AssessmentType.LIGHTHOUSE)

            # Should have results for both
            assert lighthouse1 is not None
            assert lighthouse2 is not None
            assert lighthouse1.performance_score == 80  # From mock data
            assert lighthouse2.performance_score == 80  # Same data from cache
