"""
Unit tests for the Lighthouse assessor
"""
import asyncio
import json
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from d3_assessment.assessors.lighthouse import LighthouseAssessor
from d3_assessment.exceptions import AssessmentTimeoutError
from d3_assessment.models import AssessmentType


class TestLighthouseAssessor:
    """Test Lighthouse assessor functionality"""

    @pytest.fixture
    def assessor(self):
        """Create a Lighthouse assessor instance"""
        return LighthouseAssessor()

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with Lighthouse enabled"""
        settings = MagicMock()
        settings.enable_lighthouse = True
        settings.use_stubs = False
        return settings

    def test_assessment_type(self, assessor):
        """Test that assessment type is correct"""
        assert assessor.assessment_type == AssessmentType.LIGHTHOUSE

    def test_timeout_configuration(self, assessor):
        """Test timeout is set to 30 seconds"""
        assert assessor.timeout == 30

    def test_cache_directory_creation(self):
        """Test that cache directory is created on init"""
        assessor = LighthouseAssessor()
        assert os.path.exists(assessor.cache_dir)

    def test_calculate_cost(self, assessor):
        """Test that cost is 0 (local execution)"""
        assert assessor.calculate_cost() == 0.0

    @patch("d3_assessment.assessors.lighthouse.get_settings")
    async def test_feature_disabled(self, mock_get_settings, assessor):
        """Test behavior when feature is disabled"""
        # Configure mock
        mock_settings = MagicMock()
        mock_settings.enable_lighthouse = False
        mock_get_settings.return_value = mock_settings

        # Run assessment
        result = await assessor.assess(url="https://example.com", business_data={"business_id": "test123"})

        # Verify result
        assert result.assessment_type == AssessmentType.LIGHTHOUSE
        assert result.status == "skipped"
        assert result.error_message == "Lighthouse feature is disabled"
        assert result.data == {"lighthouse_json": {}}

    @patch("d3_assessment.assessors.lighthouse.get_settings")
    async def test_stub_data(self, mock_get_settings, assessor):
        """Test stub data when USE_STUBS=true"""
        # Configure mock
        mock_settings = MagicMock()
        mock_settings.enable_lighthouse = True
        mock_settings.use_stubs = True
        mock_get_settings.return_value = mock_settings

        # Run assessment
        result = await assessor.assess(url="https://example.com", business_data={"business_id": "test123"})

        # Verify result
        assert result.assessment_type == AssessmentType.LIGHTHOUSE
        assert result.status == "completed"
        assert result.cost == 0.0

        # Check stub data
        lighthouse_data = result.data["lighthouse_json"]
        assert lighthouse_data["is_stub"] is True
        assert lighthouse_data["scores"]["performance"] == 85
        assert lighthouse_data["scores"]["accessibility"] == 92
        assert lighthouse_data["scores"]["best-practices"] == 88
        assert lighthouse_data["scores"]["seo"] == 90
        assert lighthouse_data["scores"]["pwa"] == 75

        # Check metrics
        assert result.metrics["performance_score"] == 85
        assert result.metrics["accessibility_score"] == 92
        assert result.metrics["lcp_ms"] == 2500
        assert result.metrics["fid_ms"] == 100
        assert result.metrics["cls_score"] == 0.1

    def test_cache_key_generation(self, assessor):
        """Test cache key generation for URLs"""
        url1 = "https://example.com"
        url2 = "https://example.com/page"

        key1 = assessor._get_cache_key(url1)
        key2 = assessor._get_cache_key(url2)

        # Keys should be different for different URLs
        assert key1 != key2

        # Same URL should produce same key
        assert key1 == assessor._get_cache_key(url1)

    @patch("os.path.exists")
    @patch("builtins.open", create=True)
    def test_cached_result_valid(self, mock_open, mock_exists, assessor):
        """Test retrieving valid cached result"""
        # Mock cache file exists
        mock_exists.return_value = True

        # Mock file content
        cached_data = {"scores": {"performance": 90}}
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = json.dumps(cached_data)
        mock_open.return_value = mock_file

        # Mock file time (recent)
        with patch("os.path.getmtime") as mock_getmtime:
            mock_getmtime.return_value = datetime.now().timestamp()

            result = assessor._get_cached_result("https://example.com")

        assert result == cached_data

    @patch("os.path.exists")
    def test_cached_result_expired(self, mock_exists, assessor):
        """Test that expired cache is not returned"""
        # Mock cache file exists
        mock_exists.return_value = True

        # Mock file time (8 days old - expired)
        with patch("os.path.getmtime") as mock_getmtime:
            eight_days_ago = datetime.now().timestamp() - (8 * 24 * 60 * 60)
            mock_getmtime.return_value = eight_days_ago

            result = assessor._get_cached_result("https://example.com")

        assert result is None

    @patch("d3_assessment.assessors.lighthouse.get_settings")
    async def test_timeout_handling(self, mock_get_settings, assessor):
        """Test timeout handling during assessment"""
        # Configure mock
        mock_settings = MagicMock()
        mock_settings.enable_lighthouse = True
        mock_settings.use_stubs = False
        mock_get_settings.return_value = mock_settings

        # Mock the audit to timeout
        with patch.object(assessor, "_get_cached_result", return_value=None):
            with patch.object(assessor, "_run_lighthouse_audit") as mock_audit:
                # Make the audit take longer than timeout
                async def slow_audit(url):
                    await asyncio.sleep(40)  # Longer than 30s timeout
                    return {}

                mock_audit.side_effect = slow_audit

                # Should raise timeout error
                with pytest.raises(AssessmentTimeoutError) as exc_info:
                    await assessor.assess(url="https://example.com", business_data={"business_id": "test123"})

                assert "Lighthouse audit timed out after 30s" in str(exc_info.value)

    @patch("d3_assessment.assessors.lighthouse.get_settings")
    async def test_playwright_not_installed(self, mock_get_settings, assessor):
        """Test error when Playwright is not installed"""
        # Configure mock
        mock_settings = MagicMock()
        mock_settings.enable_lighthouse = True
        mock_settings.use_stubs = False
        mock_get_settings.return_value = mock_settings

        # Mock ImportError for playwright
        with patch.object(assessor, "_get_cached_result", return_value=None):
            # Patch the _run_lighthouse_audit method to raise ImportError
            with patch.object(assessor, "_run_lighthouse_audit") as mock_audit:
                mock_audit.side_effect = ImportError("Playwright is required for Lighthouse assessor")

                result = await assessor.assess(url="https://example.com", business_data={"business_id": "test123"})

                assert result.status == "failed"
                assert "Playwright is required" in result.error_message

    def test_is_available_with_stubs(self, assessor):
        """Test availability check with stubs enabled"""
        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_settings:
            settings = MagicMock()
            settings.enable_lighthouse = True
            settings.use_stubs = True
            mock_settings.return_value = settings

            assert assessor.is_available() is True

    def test_is_available_feature_disabled(self, assessor):
        """Test availability check with feature disabled"""
        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_settings:
            settings = MagicMock()
            settings.enable_lighthouse = False
            mock_settings.return_value = settings

            assert assessor.is_available() is False

    def test_is_available_no_playwright(self, assessor):
        """Test availability check without Playwright"""
        with patch("d3_assessment.assessors.lighthouse.get_settings") as mock_settings:
            settings = MagicMock()
            settings.enable_lighthouse = True
            settings.use_stubs = False
            mock_settings.return_value = settings

            # Mock playwright import failure
            with patch("builtins.__import__", side_effect=ImportError):
                assert assessor.is_available() is False
