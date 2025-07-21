#!/usr/bin/env python3
"""
Unit tests for PRP-1061 Quality Gate
Tests the quality gate functionality, Redis evidence integration, and PRP promotion validation
"""

import json
import subprocess

# Import the quality gate module
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import fakeredis
import pytest

sys.path.append(str(Path(__file__).parent / "../../../scripts"))

from quality_gate import QualityGate, QualityGateConfig, QualityResults


class TestQualityGateConfig:
    """Test QualityGateConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = QualityGateConfig()

        assert config.redis_url == "redis://localhost:6379"
        assert config.prp_id is None
        assert config.coverage_threshold == 80
        assert config.ruff_strict_mode is False
        assert config.max_execution_seconds == 120
        assert config.enable_ruff_enforcement is False
        assert config.parallel_legacy_tools is True
        assert config.quality_gate_strict_mode is False

    def test_custom_config(self):
        """Test custom configuration values."""
        config = QualityGateConfig(
            redis_url="redis://test:6380",
            prp_id="P1-001",
            coverage_threshold=90,
            enable_ruff_enforcement=True,
            max_execution_seconds=180,
        )

        assert config.redis_url == "redis://test:6380"
        assert config.prp_id == "P1-001"
        assert config.coverage_threshold == 90
        assert config.enable_ruff_enforcement is True
        assert config.max_execution_seconds == 180


class TestQualityResults:
    """Test QualityResults model."""

    def test_default_results(self):
        """Test default results structure."""
        results = QualityResults(
            success=True, execution_time_seconds=45.5, ruff_clean=True, coverage_percentage=85.2, coverage_passed=True
        )

        assert results.success is True
        assert results.execution_time_seconds == 45.5
        assert results.ruff_clean is True
        assert results.coverage_percentage == 85.2
        assert results.coverage_passed is True
        assert results.ruff_errors == []
        assert results.ruff_warnings == []
        assert results.ruff_fixes_applied == 0
        assert results.missing_lines == {}
        assert results.evidence_keys == {}
        assert results.promotion_ready is False


class TestQualityGate:
    """Test QualityGate functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create a fake Redis client for testing."""
        return fakeredis.FakeRedis(decode_responses=True)

    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        return QualityGateConfig(
            redis_url="redis://localhost:6379",
            prp_id="P1-061",
            coverage_threshold=80,
            enable_ruff_enforcement=False,
            max_execution_seconds=120,
        )

    @pytest.fixture
    def quality_gate(self, test_config, mock_redis):
        """Create quality gate instance with mocked Redis."""
        with patch("quality_gate.redis.from_url") as mock_from_url:
            mock_from_url.return_value = mock_redis
            gate = QualityGate(test_config)
            gate.redis_client = mock_redis
            return gate

    def test_init_with_redis_success(self, test_config):
        """Test successful Redis connection during initialization."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("quality_gate.redis.from_url") as mock_from_url:
            mock_from_url.return_value = mock_redis
            gate = QualityGate(test_config)

            assert gate.config == test_config
            assert gate.redis_client == mock_redis
            mock_from_url.assert_called_once_with(test_config.redis_url, decode_responses=True)
            mock_redis.ping.assert_called_once()

    def test_init_with_redis_failure(self, test_config):
        """Test Redis connection failure during initialization."""
        with patch("quality_gate.redis.from_url") as mock_from_url:
            mock_from_url.side_effect = Exception("Connection failed")
            gate = QualityGate(test_config)

            assert gate.config == test_config
            assert gate.redis_client is None

    def test_run_success_flow(self, quality_gate):
        """Test successful quality gate execution flow."""
        # Mock all subprocess calls
        with patch.object(quality_gate, "_run_ruff_linting") as mock_ruff, patch.object(
            quality_gate, "_run_coverage_analysis"
        ) as mock_coverage, patch.object(quality_gate, "_write_evidence_to_redis") as mock_evidence, patch.object(
            quality_gate, "_validate_prp_promotion_readiness"
        ) as mock_promotion, patch.object(
            quality_gate, "_generate_coverage_badge"
        ) as mock_badge:
            # Setup mocks
            mock_ruff.return_value = (True, {"errors": [], "warnings": [], "fixes_applied": 0})
            mock_coverage.return_value = (True, {"percentage": 85.5, "report": "Test report"})
            mock_evidence.return_value = {"lint_clean": "prp:P1-061:lint_clean"}
            mock_promotion.return_value = True

            # Execute
            results = quality_gate.run()

            # Verify results
            assert results.success is True
            assert results.ruff_clean is True
            assert results.coverage_passed is True
            assert results.coverage_percentage == 85.5
            assert results.promotion_ready is True
            assert results.execution_time_seconds > 0

            # Verify method calls
            mock_ruff.assert_called_once()
            mock_coverage.assert_called_once()
            mock_evidence.assert_called_once()
            mock_promotion.assert_called_once()
            mock_badge.assert_called_once_with(85.5)

    def test_run_ruff_failure(self, quality_gate):
        """Test quality gate execution with Ruff failures."""
        with patch.object(quality_gate, "_run_ruff_linting") as mock_ruff, patch.object(
            quality_gate, "_run_coverage_analysis"
        ) as mock_coverage:
            # Setup failing Ruff
            mock_ruff.return_value = (False, {"errors": ["E501: line too long"], "warnings": []})
            mock_coverage.return_value = (True, {"percentage": 85.5})

            # Execute
            results = quality_gate.run()

            # Verify results
            assert results.success is False  # Should fail due to Ruff
            assert results.ruff_clean is False
            assert results.ruff_errors == ["E501: line too long"]

    def test_run_coverage_failure(self, quality_gate):
        """Test quality gate execution with coverage failures."""
        with patch.object(quality_gate, "_run_ruff_linting") as mock_ruff, patch.object(
            quality_gate, "_run_coverage_analysis"
        ) as mock_coverage:
            # Setup failing coverage
            mock_ruff.return_value = (True, {"errors": [], "warnings": []})
            mock_coverage.return_value = (False, {"percentage": 75.0})  # Below threshold

            # Execute
            results = quality_gate.run()

            # Verify results
            assert results.success is False  # Should fail due to coverage
            assert results.coverage_passed is False
            assert results.coverage_percentage == 75.0

    @patch("quality_gate.subprocess.run")
    def test_ruff_linting_success(self, mock_subprocess, quality_gate):
        """Test successful Ruff linting execution."""
        # Mock successful subprocess calls
        mock_check = Mock()
        mock_check.returncode = 0
        mock_check.stdout = "All checks passed"

        mock_format = Mock()
        mock_format.returncode = 0
        mock_format.stdout = "Formatted 0 files"

        mock_subprocess.side_effect = [mock_check, mock_format]

        with patch.object(quality_gate, "_check_zero_tolerance_rules") as mock_zero_tolerance:
            mock_zero_tolerance.return_value = []  # No violations

            success, data = quality_gate._run_ruff_linting()

            assert success is True
            assert data["errors"] == []
            assert len(mock_subprocess.call_args_list) == 2

    @patch("quality_gate.subprocess.run")
    def test_ruff_linting_zero_tolerance_violations(self, mock_subprocess, quality_gate):
        """Test Ruff linting with zero-tolerance violations."""
        # Mock subprocess calls
        mock_check = Mock()
        mock_check.returncode = 0
        mock_check.stdout = "Fixed some issues"

        mock_format = Mock()
        mock_format.returncode = 0

        mock_subprocess.side_effect = [mock_check, mock_format]

        with patch.object(quality_gate, "_check_zero_tolerance_rules") as mock_zero_tolerance:
            mock_zero_tolerance.return_value = ["E501: line too long", "F401: unused import"]

            success, data = quality_gate._ruff_linting()

            assert success is False
            assert len(data["errors"]) == 2
            assert "E501: line too long" in data["errors"]

    @patch("quality_gate.subprocess.run")
    def test_coverage_analysis_success(self, mock_subprocess, quality_gate):
        """Test successful coverage analysis."""
        # Mock pytest output with coverage
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
        test_file.py    10      2    80%   5-6
        TOTAL          100     15    85%
        """
        mock_subprocess.return_value = mock_result

        success, data = quality_gate._run_coverage_analysis()

        assert success is True
        assert data["percentage"] == 85.0
        assert "TOTAL" in data["report"]

    @patch("quality_gate.subprocess.run")
    def test_coverage_analysis_below_threshold(self, mock_subprocess, quality_gate):
        """Test coverage analysis below threshold."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
        TOTAL          100     25    75%
        """
        mock_subprocess.return_value = mock_result

        success, data = quality_gate._run_coverage_analysis()

        assert success is False  # Below 80% threshold
        assert data["percentage"] == 75.0

    def test_parse_coverage_percentage_from_output(self, quality_gate):
        """Test parsing coverage percentage from pytest output."""
        output = """
        test_file.py    50      5    90%   10-15
        other_file.py   30      3    90%   20-22
        TOTAL          100     12    88%
        """

        percentage = quality_gate._parse_coverage_percentage(output)
        assert percentage == 88.0

    def test_parse_coverage_percentage_no_match(self, quality_gate):
        """Test parsing coverage percentage when no match found."""
        output = "No coverage data found"

        percentage = quality_gate._parse_coverage_percentage(output)
        assert percentage == 0.0

    def test_write_evidence_to_redis(self, quality_gate, mock_redis):
        """Test writing evidence to Redis."""
        results = QualityResults(
            success=True, execution_time_seconds=45.0, ruff_clean=True, coverage_percentage=85.2, coverage_passed=True
        )

        evidence_keys = quality_gate._write_evidence_to_redis(results)

        # Verify Redis keys were set
        assert mock_redis.get("prp:P1-061:lint_clean") == "true"
        assert mock_redis.get("prp:P1-061:coverage_pct") == "85.2"

        # Verify evidence keys returned
        assert "lint_clean" in evidence_keys
        assert "coverage_pct" in evidence_keys
        assert "quality_report" in evidence_keys

    def test_write_evidence_no_redis(self, test_config):
        """Test evidence writing when Redis is unavailable."""
        gate = QualityGate(test_config)
        gate.redis_client = None

        results = QualityResults(
            success=True, execution_time_seconds=45.0, ruff_clean=True, coverage_percentage=85.2, coverage_passed=True
        )

        evidence_keys = gate._write_evidence_to_redis(results)
        assert evidence_keys == {}

    def test_validate_promotion_criteria_all_pass(self, quality_gate):
        """Test promotion criteria validation when all criteria pass."""
        results = QualityResults(
            success=True,
            execution_time_seconds=60.0,  # Under 120s limit
            ruff_clean=True,
            coverage_percentage=85.0,
            coverage_passed=True,
        )

        is_valid = quality_gate._validate_promotion_criteria(results)
        assert is_valid is True

    def test_validate_promotion_criteria_timeout(self, quality_gate):
        """Test promotion criteria validation with timeout failure."""
        results = QualityResults(
            success=False,
            execution_time_seconds=150.0,  # Over 120s limit
            ruff_clean=True,
            coverage_percentage=85.0,
            coverage_passed=True,
        )

        is_valid = quality_gate._validate_promotion_criteria(results)
        assert is_valid is False

    def test_validate_prp_promotion_readiness_success(self, quality_gate, mock_redis, tmp_path):
        """Test successful PRP promotion readiness validation."""
        # Create mock promote.lua script
        script_path = tmp_path / "redis_scripts" / "promote.lua"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("-- Mock Lua script")

        # Mock Redis script operations
        mock_redis.script_load.return_value = "script_sha"
        mock_redis.evalsha.return_value = [1, "{}"]  # Success, no missing fields

        results = QualityResults(
            success=True, execution_time_seconds=45.0, ruff_clean=True, coverage_percentage=85.0, coverage_passed=True
        )

        with patch("quality_gate.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.return_value = "-- Mock Lua script"

            is_ready = quality_gate._validate_prp_promotion_readiness(results)

        assert is_ready is True

    def test_validate_prp_promotion_readiness_missing_fields(self, quality_gate, mock_redis):
        """Test PRP promotion readiness validation with missing fields."""
        # Mock Redis script operations
        mock_redis.script_load.return_value = "script_sha"
        mock_redis.evalsha.return_value = [0, '["lint_clean"]']  # Failure, missing lint_clean

        results = QualityResults(
            success=True,
            execution_time_seconds=45.0,
            ruff_clean=False,  # This would cause missing lint_clean
            coverage_percentage=85.0,
            coverage_passed=True,
        )

        with patch("quality_gate.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.read_text.return_value = "-- Mock Lua script"

            is_ready = quality_gate._validate_prp_promotion_readiness(results)

        assert is_ready is False

    def test_generate_coverage_badge(self, quality_gate, tmp_path):
        """Test coverage badge generation."""
        # Create temporary docs/badges directory
        badges_dir = tmp_path / "docs" / "badges"

        with patch("quality_gate.Path") as mock_path:
            mock_path.return_value.mkdir = Mock()
            mock_path.return_value.__truediv__ = lambda self, other: tmp_path / "docs" / "badges" / other
            badge_path = tmp_path / "docs" / "badges" / "coverage.svg"

            # Mock the write_text method
            mock_badge_path = Mock()
            mock_badge_path.write_text = Mock()

            with patch("quality_gate.Path", return_value=mock_badge_path):
                quality_gate._generate_coverage_badge(85.5)

            # Verify write_text was called (SVG content)
            mock_badge_path.write_text.assert_called_once()

            # Verify SVG content contains expected values
            svg_content = mock_badge_path.write_text.call_args[0][0]
            assert "85%" in svg_content
            assert "coverage" in svg_content


@pytest.mark.integration
class TestQualityGateIntegration:
    """Integration tests for quality gate with real Redis."""

    def test_end_to_end_with_fake_redis(self):
        """Test end-to-end execution with fake Redis."""
        config = QualityGateConfig(
            prp_id="P1-061-test", coverage_threshold=75, enable_ruff_enforcement=False  # Lower threshold for test
        )

        # Use fake Redis for integration test
        fake_redis = fakeredis.FakeRedis(decode_responses=True)

        with patch("quality_gate.redis.from_url") as mock_from_url, patch(
            "quality_gate.subprocess.run"
        ) as mock_subprocess:
            mock_from_url.return_value = fake_redis

            # Mock successful subprocess calls
            mock_check = Mock(returncode=0, stdout="All good")
            mock_format = Mock(returncode=0, stdout="Formatted")
            mock_pytest = Mock(returncode=0, stdout="TOTAL    100    20    80%")

            mock_subprocess.side_effect = [mock_check, mock_format, mock_pytest]

            gate = QualityGate(config)

            with patch.object(gate, "_check_zero_tolerance_rules") as mock_zero_tolerance, patch.object(
                gate, "_generate_coverage_badge"
            ) as mock_badge, patch("quality_gate.Path") as mock_path:
                mock_zero_tolerance.return_value = []  # No violations
                mock_path.return_value.exists.return_value = True
                mock_path.return_value.read_text.return_value = "-- Mock Lua script"

                results = gate.run()

                # Verify successful execution
                assert results.success is True
                assert results.ruff_clean is True
                assert results.coverage_passed is True
                assert results.coverage_percentage == 80.0

                # Verify Redis evidence was written
                assert fake_redis.get("prp:P1-061-test:lint_clean") == "true"
                assert fake_redis.get("prp:P1-061-test:coverage_pct") == "80.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
