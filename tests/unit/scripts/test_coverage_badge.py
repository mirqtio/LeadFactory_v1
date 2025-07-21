#!/usr/bin/env python3
"""
Unit tests for PRP-1061 Coverage Badge Generator
Tests SVG badge generation, coverage parsing, and color determination
"""

import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Import the coverage badge module
import sys
sys.path.append(str(Path(__file__).parent / "../../../scripts"))

from coverage_badge import CoverageBadgeGenerator


class TestCoverageBadgeGenerator:
    """Test CoverageBadgeGenerator functionality."""

    @pytest.fixture
    def generator(self, tmp_path):
        """Create badge generator with temporary output directory."""
        return CoverageBadgeGenerator(output_dir=str(tmp_path / "badges"))

    @pytest.fixture
    def sample_coverage_xml(self, tmp_path):
        """Create sample coverage.xml file for testing."""
        xml_content = '''<?xml version="1.0" ?>
<coverage version="7.0.0" timestamp="1640995200000" lines-valid="100" lines-covered="85" line-rate="0.85" branches-valid="20" branches-covered="16" branch-rate="0.80" complexity="0">
    <sources>
        <source>.</source>
    </sources>
    <packages>
        <package name="." line-rate="0.85" branch-rate="0.80" complexity="0">
            <classes>
                <class name="test_module" filename="test_module.py" complexity="0" line-rate="0.85" branch-rate="0.80">
                    <methods/>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>'''
        xml_path = tmp_path / "coverage.xml"
        xml_path.write_text(xml_content)
        return xml_path

    def test_init_creates_output_directory(self, tmp_path):
        """Test that generator creates output directory."""
        badges_dir = tmp_path / "custom_badges"
        generator = CoverageBadgeGenerator(output_dir=str(badges_dir))
        
        assert badges_dir.exists()
        assert generator.output_dir == badges_dir

    def test_color_thresholds(self, generator):
        """Test color threshold constants."""
        expected_thresholds = {
            90: "brightgreen",
            80: "green", 
            70: "yellow",
            60: "orange",
            0: "red"
        }
        
        assert generator.COLOR_THRESHOLDS == expected_thresholds

    def test_determine_badge_color_excellent(self, generator):
        """Test badge color for excellent coverage (>=90%)."""
        assert generator.determine_badge_color(95.0) == "brightgreen"
        assert generator.determine_badge_color(90.0) == "brightgreen"

    def test_determine_badge_color_good(self, generator):
        """Test badge color for good coverage (80-89%)."""
        assert generator.determine_badge_color(85.0) == "green"
        assert generator.determine_badge_color(80.0) == "green"

    def test_determine_badge_color_fair(self, generator):
        """Test badge color for fair coverage (70-79%)."""
        assert generator.determine_badge_color(75.0) == "yellow"
        assert generator.determine_badge_color(70.0) == "yellow"

    def test_determine_badge_color_poor(self, generator):
        """Test badge color for poor coverage (60-69%)."""
        assert generator.determine_badge_color(65.0) == "orange"
        assert generator.determine_badge_color(60.0) == "orange"

    def test_determine_badge_color_critical(self, generator):
        """Test badge color for critical coverage (<60%)."""
        assert generator.determine_badge_color(50.0) == "red"
        assert generator.determine_badge_color(0.0) == "red"

    def test_get_coverage_from_xml_success(self, generator, sample_coverage_xml):
        """Test successful coverage parsing from XML."""
        coverage = generator.get_coverage_from_xml(sample_coverage_xml)
        assert coverage == 85.0

    def test_get_coverage_from_xml_missing_file(self, generator, tmp_path):
        """Test coverage parsing when XML file doesn't exist."""
        missing_file = tmp_path / "nonexistent.xml"
        coverage = generator.get_coverage_from_xml(missing_file)
        assert coverage is None

    def test_get_coverage_from_xml_invalid_format(self, generator, tmp_path):
        """Test coverage parsing with invalid XML format."""
        invalid_xml = tmp_path / "invalid.xml"
        invalid_xml.write_text("Not valid XML content")
        
        coverage = generator.get_coverage_from_xml(invalid_xml)
        assert coverage is None

    @patch('coverage_badge.subprocess.run')
    def test_get_coverage_from_pytest_success(self, mock_subprocess, generator):
        """Test successful coverage from pytest execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
collecting ... 
test_file.py::test_function PASSED
TOTAL          100     12    88%
        """
        mock_subprocess.return_value = mock_result
        
        coverage = generator.get_coverage_from_pytest()
        assert coverage == 88.0

    @patch('coverage_badge.subprocess.run')
    def test_get_coverage_from_pytest_timeout(self, mock_subprocess, generator, sample_coverage_xml):
        """Test pytest timeout fallback to XML."""
        mock_subprocess.side_effect = subprocess.TimeoutExpired("pytest", 120)
        
        with patch.object(generator, 'get_coverage_from_xml') as mock_xml:
            mock_xml.return_value = 75.0
            coverage = generator.get_coverage_from_pytest()
            
        assert coverage == 75.0
        mock_xml.assert_called_once()

    @patch('coverage_badge.subprocess.run')
    def test_get_coverage_from_pytest_no_total_line(self, mock_subprocess, generator):
        """Test pytest output without TOTAL line."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "No coverage data found"
        mock_subprocess.return_value = mock_result
        
        with patch.object(generator, 'get_coverage_from_xml') as mock_xml:
            mock_xml.return_value = None
            coverage = generator.get_coverage_from_pytest()
            
        assert coverage is None

    def test_generate_svg_badge_content(self, generator):
        """Test SVG badge content generation."""
        svg_content = generator.generate_svg_badge(85.5)
        
        # Check required SVG elements
        assert svg_content.startswith('<svg')
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg_content
        assert 'coverage: 85%' in svg_content  # Rounded percentage
        assert 'coverage</text>' in svg_content
        assert '85%</text>' in svg_content
        assert 'fill="green"' in svg_content  # 85% should be green

    def test_generate_svg_badge_different_colors(self, generator):
        """Test SVG badge generation with different color thresholds."""
        # Test brightgreen (excellent)
        svg_excellent = generator.generate_svg_badge(95.0)
        assert 'fill="brightgreen"' in svg_excellent
        
        # Test yellow (fair)
        svg_fair = generator.generate_svg_badge(75.0)
        assert 'fill="yellow"' in svg_fair
        
        # Test red (critical)
        svg_critical = generator.generate_svg_badge(45.0)
        assert 'fill="red"' in svg_critical

    def test_save_badge_creates_file(self, generator):
        """Test badge saving creates SVG file."""
        badge_path = generator.save_badge(82.5, "test_coverage.svg")
        
        assert badge_path.exists()
        assert badge_path.suffix == ".svg"
        
        # Verify content
        content = badge_path.read_text()
        assert '83%' in content  # Rounded
        assert 'coverage' in content

    def test_save_badge_custom_filename(self, generator):
        """Test badge saving with custom filename."""
        badge_path = generator.save_badge(77.8, "custom_badge.svg")
        
        assert badge_path.name == "custom_badge.svg"
        assert badge_path.exists()
        
        content = badge_path.read_text()
        assert '78%' in content

    def test_generate_json_report(self, generator):
        """Test JSON report generation."""
        with patch('coverage_badge.time.time') as mock_time:
            mock_time.return_value = 1640995200.0
            
            json_path = generator.generate_json_report(85.5, "test_report.json")
            
        assert json_path.exists()
        
        # Verify JSON content
        report_data = json.loads(json_path.read_text())
        
        assert report_data["coverage_percentage"] == 85.5
        assert report_data["timestamp"] == 1640995200.0
        assert report_data["color"] == "green"
        assert report_data["status"] == "passed"  # Above 80%
        assert report_data["threshold"] == 80

    def test_generate_json_report_failed_status(self, generator):
        """Test JSON report generation with failed status."""
        json_path = generator.generate_json_report(75.0, "failed_report.json")
        
        report_data = json.loads(json_path.read_text())
        
        assert report_data["coverage_percentage"] == 75.0
        assert report_data["color"] == "yellow"
        assert report_data["status"] == "failed"  # Below 80%

    def test_run_with_provided_coverage(self, generator):
        """Test run method with provided coverage percentage."""
        success = generator.run(coverage_percentage=88.5)
        
        assert success is True
        
        # Verify badge was created
        badge_path = generator.output_dir / "coverage.svg"
        assert badge_path.exists()
        
        content = badge_path.read_text()
        assert '89%' in content  # Rounded

    @patch.object(CoverageBadgeGenerator, 'get_coverage_from_xml')
    def test_run_with_xml_source(self, mock_xml, generator):
        """Test run method with XML source."""
        mock_xml.return_value = 82.3
        
        success = generator.run(coverage_source="xml")
        
        assert success is True
        mock_xml.assert_called_once()
        
        # Verify badge was created
        badge_path = generator.output_dir / "coverage.svg"
        assert badge_path.exists()

    @patch.object(CoverageBadgeGenerator, 'get_coverage_from_pytest')
    def test_run_with_pytest_source(self, mock_pytest, generator):
        """Test run method with pytest source."""
        mock_pytest.return_value = 79.1
        
        success = generator.run(coverage_source="pytest")
        
        assert success is True
        mock_pytest.assert_called_once()

    @patch.object(CoverageBadgeGenerator, 'get_coverage_from_xml')
    @patch.object(CoverageBadgeGenerator, 'get_coverage_from_pytest')
    def test_run_auto_fallback_to_pytest(self, mock_pytest, mock_xml, generator):
        """Test run method auto mode falls back to pytest when XML unavailable."""
        mock_xml.return_value = None  # XML not available
        mock_pytest.return_value = 81.7
        
        success = generator.run(coverage_source="auto")
        
        assert success is True
        mock_xml.assert_called_once()
        mock_pytest.assert_called_once()

    @patch.object(CoverageBadgeGenerator, 'get_coverage_from_xml')
    @patch.object(CoverageBadgeGenerator, 'get_coverage_from_pytest')
    def test_run_no_coverage_available(self, mock_pytest, mock_xml, generator):
        """Test run method when no coverage data is available."""
        mock_xml.return_value = None
        mock_pytest.return_value = None
        
        success = generator.run(coverage_source="auto")
        
        assert success is False

    def test_run_creates_both_svg_and_json(self, generator):
        """Test run method creates both SVG badge and JSON report."""
        success = generator.run(coverage_percentage=86.4)
        
        assert success is True
        
        # Verify both files exist
        svg_path = generator.output_dir / "coverage.svg"
        json_path = generator.output_dir / "coverage.json"
        
        assert svg_path.exists()
        assert json_path.exists()
        
        # Verify contents
        svg_content = svg_path.read_text()
        assert '86%' in svg_content
        
        json_data = json.loads(json_path.read_text())
        assert json_data["coverage_percentage"] == 86.4

    def test_run_with_exception_during_badge_generation(self, generator):
        """Test run method handles exceptions during badge generation."""
        with patch.object(generator, 'save_badge') as mock_save:
            mock_save.side_effect = Exception("File write error")
            
            success = generator.run(coverage_percentage=85.0)
            
        assert success is False


@pytest.mark.integration
class TestCoverageBadgeIntegration:
    """Integration tests for coverage badge generation."""

    def test_end_to_end_badge_generation(self, tmp_path):
        """Test complete badge generation workflow."""
        # Create generator with temporary directory
        generator = CoverageBadgeGenerator(output_dir=str(tmp_path))
        
        # Run with specific coverage
        success = generator.run(coverage_percentage=87.3)
        
        assert success is True
        
        # Verify files were created
        svg_file = tmp_path / "coverage.svg"
        json_file = tmp_path / "coverage.json"
        
        assert svg_file.exists()
        assert json_file.exists()
        
        # Verify SVG content
        svg_content = svg_file.read_text(encoding='utf-8')
        assert svg_content.startswith('<svg')
        assert '87%' in svg_content
        assert 'coverage' in svg_content
        assert 'brightgreen' in svg_content or 'green' in svg_content
        
        # Verify JSON content
        json_data = json.loads(json_file.read_text(encoding='utf-8'))
        assert json_data["coverage_percentage"] == 87.3
        assert json_data["color"] == "green"
        assert json_data["status"] == "passed"

    def test_badge_color_accuracy_across_thresholds(self, tmp_path):
        """Test badge color accuracy across different coverage thresholds."""
        generator = CoverageBadgeGenerator(output_dir=str(tmp_path))
        
        test_cases = [
            (95.0, "brightgreen"),
            (85.0, "green"),
            (75.0, "yellow"),
            (65.0, "orange"),
            (45.0, "red")
        ]
        
        for coverage, expected_color in test_cases:
            # Generate badge
            success = generator.run(coverage_percentage=coverage)
            assert success is True
            
            # Check SVG content
            svg_content = (tmp_path / "coverage.svg").read_text()
            assert f'fill="{expected_color}"' in svg_content
            
            # Check JSON report
            json_data = json.loads((tmp_path / "coverage.json").read_text())
            assert json_data["color"] == expected_color


if __name__ == "__main__":
    pytest.main([__file__, "-v"])