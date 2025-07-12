"""
Tests for design token extraction logic.

Tests cover:
- Color extraction from swatches
- Typography extraction from examples
- Spacing extraction from tables
- CSS custom property parsing
- Error handling for missing elements
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from bs4 import BeautifulSoup

from design.extract_tokens import DesignTokenExtractor


class TestDesignTokenExtractor:
    """Test suite for DesignTokenExtractor class."""

    @pytest.fixture
    def sample_html(self):
        """Provide sample HTML content for testing."""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Test Style Guide</title></head>
        <body>
            <!-- Color Swatches -->
            <div class="color-swatch">
                <div class="color-box" style="background: #0066ff;">Primary Blue</div>
                <div class="color-details">
                    <div class="color-name">Synthesis Blue</div>
                    <div class="color-value">#0066ff</div>
                    <div class="color-usage">Primary actions, links</div>
                </div>
            </div>
            
            <div class="color-swatch">
                <div class="color-box" style="background: #dc2626;">Critical Red</div>
                <div class="color-details">
                    <div class="color-name">Critical Red</div>
                    <div class="color-value">#dc2626</div>
                    <div class="color-usage">Critical issues</div>
                </div>
            </div>
            
            <div class="color-swatch">
                <div class="color-box" style="background: #6b7280;">Neutral Gray</div>
                <div class="color-details">
                    <div class="color-name">Neutral Gray</div>
                    <div class="color-value">#6b7280</div>
                    <div class="color-usage">Secondary text</div>
                </div>
            </div>
            
            <!-- Accessibility Section -->
            <h2>Accessibility</h2>
            <table>
                <tr><th>Combination</th><th>Ratio</th><th>WCAG Level</th></tr>
                <tr><td>White on Anthracite</td><td>20.4:1</td><td>AAA</td></tr>
                <tr><td>Synthesis Blue on White</td><td>8.2:1</td><td>AAA</td></tr>
            </table>
        </body>
        </html>
        """

    @pytest.fixture
    def temp_html_file(self, sample_html):
        """Create temporary HTML file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(sample_html)
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink()

    @pytest.fixture
    def extractor(self, temp_html_file):
        """Create DesignTokenExtractor instance with test HTML."""
        return DesignTokenExtractor(temp_html_file)

    def test_initialization(self, temp_html_file):
        """Test extractor initialization with valid HTML file."""
        extractor = DesignTokenExtractor(temp_html_file)
        assert extractor.html_path == Path(temp_html_file)
        assert extractor.soup is not None
        assert isinstance(extractor.soup, BeautifulSoup)

    def test_initialization_file_not_found(self):
        """Test extractor initialization with non-existent file."""
        with pytest.raises(FileNotFoundError):
            DesignTokenExtractor("/nonexistent/file.html")

    def test_extract_colors_basic(self, extractor):
        """Test basic color extraction from swatches."""
        colors = extractor.extract_colors()
        
        # Check structure
        assert "primary" in colors
        assert "status" in colors
        assert "functional" in colors
        
        # Check specific colors were extracted
        assert "synthesis-blue" in colors["primary"]
        assert "critical" in colors["status"]
        assert "neutral" in colors["functional"]
        
        # Check color values
        assert colors["primary"]["synthesis-blue"]["value"] == "#0066ff"
        assert colors["status"]["critical"]["value"] == "#dc2626"
        assert colors["functional"]["neutral"]["value"] == "#6b7280"

    def test_extract_colors_with_usage(self, extractor):
        """Test color extraction includes usage descriptions."""
        colors = extractor.extract_colors()
        
        # Check usage descriptions are included
        assert colors["primary"]["synthesis-blue"]["usage"] == "Primary actions, links"
        assert colors["status"]["critical"]["usage"] == "Critical issues"
        assert colors["functional"]["neutral"]["usage"] == "Secondary text"

    def test_extract_colors_adds_missing_functional(self, extractor):
        """Test that missing 4th functional color is added."""
        colors = extractor.extract_colors()
        
        # Check that dark-text color was added
        assert "dark-text" in colors["functional"]
        assert colors["functional"]["dark-text"]["value"] == "#2d3748"
        assert "usage" in colors["functional"]["dark-text"]

    def test_extract_colors_malformed_swatch(self, temp_html_file):
        """Test color extraction handles malformed swatches gracefully."""
        malformed_html = """
        <div class="color-swatch">
            <div class="color-box">No style attribute</div>
            <div class="color-details">
                <div class="color-name">Test Color</div>
            </div>
        </div>
        """
        
        with open(temp_html_file, 'w') as f:
            f.write(f"<html><body>{malformed_html}</body></html>")
            
        extractor = DesignTokenExtractor(temp_html_file)
        colors = extractor.extract_colors()
        
        # Should still work and include the added functional color
        assert len(colors["functional"]) >= 1  # At least dark-text

    def test_normalize_color_name(self, extractor):
        """Test color name normalization."""
        # Test specific mappings
        assert extractor._normalize_color_name("Pure White") == "white"
        assert extractor._normalize_color_name("Critical Red") == "critical"
        assert extractor._normalize_color_name("Warning Amber") == "warning"
        assert extractor._normalize_color_name("Success Green") == "success"
        
        # Test general normalization
        assert extractor._normalize_color_name("Some Complex Name!") == "some-complex-name"
        assert extractor._normalize_color_name("  Spaced  Name  ") == "spaced-name"

    def test_extract_contrast_ratios(self, extractor):
        """Test contrast ratio extraction from accessibility table."""
        contrast_ratios = extractor.extract_contrast_ratios()
        
        assert "white_on_anthracite" in contrast_ratios
        assert "synthesis_blue_on_white" in contrast_ratios
        
        assert contrast_ratios["white_on_anthracite"]["ratio"] == "20.4:1"
        assert contrast_ratios["white_on_anthracite"]["level"] == "AAA"
        
        assert contrast_ratios["synthesis_blue_on_white"]["ratio"] == "8.2:1"
        assert contrast_ratios["synthesis_blue_on_white"]["level"] == "AAA"

    def test_extract_contrast_ratios_no_accessibility_section(self, temp_html_file):
        """Test contrast ratio extraction when no accessibility section exists."""
        simple_html = "<html><body><h1>No accessibility section</h1></body></html>"
        
        with open(temp_html_file, 'w') as f:
            f.write(simple_html)
            
        extractor = DesignTokenExtractor(temp_html_file)
        contrast_ratios = extractor.extract_contrast_ratios()
        
        assert contrast_ratios == {}

    def test_extract_typography(self, extractor):
        """Test typography token extraction."""
        typography = extractor.extract_typography()
        
        # Check structure
        assert "fontFamily" in typography
        assert "scale" in typography
        
        # Check font family
        assert typography["fontFamily"] == "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
        
        # Check scale structure
        scale = typography["scale"]
        assert "display" in scale
        assert "h1" in scale
        assert "body" in scale
        
        # Check scale properties
        assert scale["display"]["size"] == "72px"
        assert scale["display"]["weight"] == "300"
        assert scale["display"]["lineHeight"] == "0.9"
        
        assert scale["h1"]["size"] == "48px"
        assert scale["h1"]["weight"] == "400"
        assert scale["h1"]["lineHeight"] == "1.1"

    def test_extract_spacing(self, extractor):
        """Test spacing token extraction."""
        spacing = extractor.extract_spacing()
        
        assert "base" in spacing
        assert "scale" in spacing
        
        assert spacing["base"] == "8px"
        
        scale = spacing["scale"]
        assert scale["xs"] == "8px"
        assert scale["sm"] == "16px"
        assert scale["md"] == "24px"
        assert scale["lg"] == "32px"
        assert scale["xl"] == "48px"
        assert scale["2xl"] == "64px"
        assert scale["3xl"] == "80px"
        
        # Verify 8px base unit system
        assert len(scale) == 7

    def test_extract_animation(self, extractor):
        """Test animation token extraction."""
        animation = extractor.extract_animation()
        
        assert "duration" in animation
        assert "easing" in animation
        
        # Check durations
        durations = animation["duration"]
        assert durations["micro"] == "150ms"
        assert durations["standard"] == "200ms"
        assert durations["page"] == "300ms"
        assert durations["data"] == "400ms"
        
        # Check easing functions
        easing = animation["easing"]
        assert easing["out"] == "ease-out"
        assert easing["in-out"] == "ease-in-out"

    def test_extract_breakpoints(self, extractor):
        """Test responsive breakpoint extraction."""
        breakpoints = extractor.extract_breakpoints()
        
        assert "mobile" in breakpoints
        assert "tablet" in breakpoints
        assert "desktop" in breakpoints
        
        assert breakpoints["mobile"] == "640px"
        assert breakpoints["tablet"] == "1024px"
        assert breakpoints["desktop"] == "1200px"

    def test_extract_all_tokens(self, extractor):
        """Test complete token extraction."""
        tokens = extractor.extract_all_tokens()
        
        # Check all sections are present
        assert "colors" in tokens
        assert "typography" in tokens
        assert "spacing" in tokens
        assert "animation" in tokens
        assert "breakpoints" in tokens
        
        # Check token counts match PRP requirements
        colors = tokens["colors"]
        total_colors = sum(len(category) for category in colors.values())
        assert total_colors == 10  # 3 primary + 3 status + 4 functional
        
        assert len(colors["primary"]) == 3
        assert len(colors["status"]) == 3
        assert len(colors["functional"]) == 4
        
        assert len(tokens["typography"]["scale"]) == 9
        assert len(tokens["spacing"]["scale"]) == 7
        assert len(tokens["animation"]["duration"]) == 4
        assert len(tokens["breakpoints"]) == 3

    def test_extract_all_tokens_adds_contrast_to_colors(self, extractor):
        """Test that contrast ratios are added to color tokens."""
        tokens = extractor.extract_all_tokens()
        
        # Check that some colors have contrast information
        colors = tokens["colors"]
        found_contrast = False
        
        for category in colors.values():
            for color_data in category.values():
                if "contrast" in color_data:
                    found_contrast = True
                    break
            if found_contrast:
                break
                
        assert found_contrast, "No contrast ratios found in color tokens"

    def test_save_tokens(self, extractor, tmp_path):
        """Test token saving to JSON file."""
        output_path = tmp_path / "test_tokens.json"
        
        # Extract tokens and save
        tokens = extractor.extract_all_tokens()
        extractor.save_tokens(str(output_path), minify=True)
        
        # Verify file was created
        assert output_path.exists()
        
        # Verify file contents
        with open(output_path, 'r') as f:
            saved_tokens = json.load(f)
            
        assert saved_tokens == tokens
        
        # Verify file size constraint
        file_size = output_path.stat().st_size
        assert file_size <= 2048, f"File size {file_size} exceeds 2KB limit"

    def test_save_tokens_unminified(self, extractor, tmp_path):
        """Test saving unminified tokens."""
        output_path = tmp_path / "test_tokens_pretty.json"
        
        extractor.extract_all_tokens()
        extractor.save_tokens(str(output_path), minify=False)
        
        # Verify file was created and is formatted
        with open(output_path, 'r') as f:
            content = f.read()
            
        # Unminified should have newlines and indentation
        assert '\n' in content
        assert '  ' in content  # Check for indentation

    def test_main_function_execution(self, monkeypatch, tmp_path):
        """Test main function execution."""
        from design import extract_tokens
        
        # Mock the paths to use test directory
        test_html = tmp_path / "styleguide.html"
        test_output = tmp_path / "design_tokens.json"
        
        # Create a minimal test HTML file
        with open(test_html, 'w') as f:
            f.write("""
            <html><body>
                <div class="color-swatch">
                    <div class="color-box" style="background: #0066ff;">Test</div>
                    <div class="color-details">
                        <div class="color-name">Test Color</div>
                    </div>
                </div>
            </body></html>
            """)
        
        # Mock Path(__file__).parent to return our test directory
        def mock_path_parent():
            return tmp_path
            
        with patch('design.extract_tokens.Path') as mock_path:
            mock_path(__file__).parent = tmp_path
            mock_path.return_value.parent = tmp_path
            mock_path.side_effect = lambda x: Path(x) if not x == extract_tokens.__file__ else MagicMock(parent=tmp_path)
            
            # Run main function
            extract_tokens.main()
            
            # Verify output file was created
            assert test_output.exists()

    def test_error_handling_missing_elements(self, temp_html_file):
        """Test error handling when HTML elements are missing."""
        # Create HTML with missing elements
        minimal_html = "<html><body><h1>Minimal HTML</h1></body></html>"
        
        with open(temp_html_file, 'w') as f:
            f.write(minimal_html)
            
        extractor = DesignTokenExtractor(temp_html_file)
        
        # Should not raise exceptions
        colors = extractor.extract_colors()
        contrast = extractor.extract_contrast_ratios()
        
        # Should return default structures
        assert isinstance(colors, dict)
        assert "primary" in colors
        assert "status" in colors
        assert "functional" in colors
        
        # Should have at least the added functional color
        assert len(colors["functional"]) >= 1
        
        assert isinstance(contrast, dict)

    def test_edge_case_empty_color_details(self, temp_html_file):
        """Test handling of color swatches with empty details."""
        html_with_empty_details = """
        <html><body>
            <div class="color-swatch">
                <div class="color-box" style="background: #0066ff;">Color</div>
                <div class="color-details">
                    <!-- Empty details -->
                </div>
            </div>
        </body></html>
        """
        
        with open(temp_html_file, 'w') as f:
            f.write(html_with_empty_details)
            
        extractor = DesignTokenExtractor(temp_html_file)
        colors = extractor.extract_colors()
        
        # Should handle gracefully and still include functional color
        assert len(colors["functional"]) >= 1

    def test_malformed_style_attribute(self, temp_html_file):
        """Test handling of malformed style attributes."""
        html_with_malformed_style = """
        <html><body>
            <div class="color-swatch">
                <div class="color-box" style="invalid-css: value;">Color</div>
                <div class="color-details">
                    <div class="color-name">Test</div>
                </div>
            </div>
        </body></html>
        """
        
        with open(temp_html_file, 'w') as f:
            f.write(html_with_malformed_style)
            
        extractor = DesignTokenExtractor(temp_html_file)
        colors = extractor.extract_colors()
        
        # Should handle gracefully
        assert isinstance(colors, dict)
        assert len(colors["functional"]) >= 1  # At least the added color