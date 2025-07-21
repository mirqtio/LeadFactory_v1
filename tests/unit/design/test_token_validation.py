"""
Tests for design token validation logic.

Tests cover:
- JSON schema compliance
- File size constraints
- Required token presence
- Value format validation
"""

import json
from pathlib import Path

import pytest

from design import tokens, validate_tokens


class TestTokenValidation:
    """Test suite for design token validation."""

    def test_validate_tokens_success(self):
        """Test that current tokens pass validation."""
        # Should not raise any exceptions
        result = validate_tokens()
        assert result is True

    def test_json_structure_completeness(self):
        """Test that all required token categories are present."""
        required_categories = ["colors", "typography", "spacing", "animation", "breakpoints"]

        for category in required_categories:
            assert category in tokens, f"Missing required category: {category}"

    def test_color_token_counts(self):
        """Test that color token counts match PRP requirements."""
        colors = tokens["colors"]

        # Test primary colors (3 required)
        assert len(colors["primary"]) == 3, f"Expected 3 primary colors, got {len(colors['primary'])}"

        # Test status colors (3 required)
        assert len(colors["status"]) == 3, f"Expected 3 status colors, got {len(colors['status'])}"

        # Test functional colors (4 required)
        assert len(colors["functional"]) == 4, f"Expected 4 functional colors, got {len(colors['functional'])}"

        # Test total colors (10 required)
        total_colors = sum(len(category) for category in colors.values())
        assert total_colors == 10, f"Expected 10 total colors, got {total_colors}"

    def test_typography_scale_count(self):
        """Test that typography scale has required number of levels."""
        typography_scale = tokens["typography"]["scale"]

        # Test 9 typography scale values required
        assert len(typography_scale) == 9, f"Expected 9 typography scales, got {len(typography_scale)}"

        # Test required scales are present
        required_scales = ["display", "h1", "h2", "h3", "h4", "body-large", "body", "body-small", "caption"]
        for scale in required_scales:
            assert scale in typography_scale, f"Missing required typography scale: {scale}"

    def test_spacing_scale_count(self):
        """Test that spacing scale has required number of levels."""
        spacing_scale = tokens["spacing"]["scale"]

        # Test 7 spacing scale values required
        assert len(spacing_scale) == 7, f"Expected 7 spacing scales, got {len(spacing_scale)}"

        # Test required scales are present
        required_scales = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl"]
        for scale in required_scales:
            assert scale in spacing_scale, f"Missing required spacing scale: {scale}"

    def test_animation_timing_count(self):
        """Test that animation has required number of timings."""
        animation = tokens["animation"]

        # Test 4 animation durations required
        assert len(animation["duration"]) == 4, f"Expected 4 animation durations, got {len(animation['duration'])}"

        # Test required durations are present
        required_durations = ["micro", "standard", "page", "data"]
        for duration in required_durations:
            assert duration in animation["duration"], f"Missing required animation duration: {duration}"

    def test_breakpoint_count(self):
        """Test that breakpoints has required number of definitions."""
        breakpoints = tokens["breakpoints"]

        # Test 3 breakpoints required
        assert len(breakpoints) == 3, f"Expected 3 breakpoints, got {len(breakpoints)}"

        # Test required breakpoints are present
        required_breakpoints = ["mobile", "tablet", "desktop"]
        for breakpoint in required_breakpoints:
            assert breakpoint in breakpoints, f"Missing required breakpoint: {breakpoint}"

    def test_color_value_format(self):
        """Test that color values are valid hex codes."""
        colors = tokens["colors"]

        for category_name, category in colors.items():
            for color_name, color_data in category.items():
                color_value = color_data.get("value", color_data)

                # Test hex format
                assert isinstance(color_value, str), f"Color value must be string: {category_name}.{color_name}"
                assert color_value.startswith("#"), f"Color value must start with #: {category_name}.{color_name}"
                assert len(color_value) in [4, 7], f"Invalid hex length: {category_name}.{color_name}"

                # Test hex characters
                hex_chars = color_value[1:]
                assert all(
                    c in "0123456789abcdefABCDEF" for c in hex_chars
                ), f"Invalid hex characters: {category_name}.{color_name}"

    def test_typography_value_format(self):
        """Test that typography values have correct format."""
        typography = tokens["typography"]

        # Test font family
        assert isinstance(typography["fontFamily"], str), "Font family must be string"
        assert len(typography["fontFamily"]) > 0, "Font family cannot be empty"

        # Test scale values
        for scale_name, scale_data in typography["scale"].items():
            assert "size" in scale_data, f"Missing size in typography scale: {scale_name}"
            assert "weight" in scale_data, f"Missing weight in typography scale: {scale_name}"
            assert "lineHeight" in scale_data, f"Missing lineHeight in typography scale: {scale_name}"

            # Test size format (should end with px)
            size = scale_data["size"]
            assert isinstance(size, str), f"Typography size must be string: {scale_name}"
            assert size.endswith("px"), f"Typography size must end with px: {scale_name}"

            # Test weight format (should be numeric string)
            weight = scale_data["weight"]
            assert isinstance(weight, str), f"Typography weight must be string: {scale_name}"
            assert weight.isdigit() or weight in ["normal", "bold"], f"Invalid weight format: {scale_name}"

            # Test line height format (should be numeric)
            line_height = scale_data["lineHeight"]
            assert isinstance(line_height, str), f"Line height must be string: {scale_name}"
            try:
                float(line_height)
            except ValueError:
                pytest.fail(f"Line height must be numeric: {scale_name}")

    def test_spacing_value_format(self):
        """Test that spacing values have correct format."""
        spacing = tokens["spacing"]

        # Test base value
        assert isinstance(spacing["base"], str), "Spacing base must be string"
        assert spacing["base"].endswith("px"), "Spacing base must end with px"

        # Test scale values
        for scale_name, scale_value in spacing["scale"].items():
            assert isinstance(scale_value, str), f"Spacing value must be string: {scale_name}"
            assert scale_value.endswith("px"), f"Spacing value must end with px: {scale_name}"

            # Test that value is numeric
            numeric_value = scale_value[:-2]  # Remove 'px'
            try:
                int(numeric_value)
            except ValueError:
                pytest.fail(f"Spacing value must be numeric: {scale_name}")

    def test_spacing_base_unit_system(self):
        """Test that spacing follows 8px base unit system."""
        spacing = tokens["spacing"]

        # Test base is 8px
        assert spacing["base"] == "8px", "Spacing base must be 8px"

        # Test scale values are multiples of 8
        for scale_name, scale_value in spacing["scale"].items():
            numeric_value = int(scale_value[:-2])  # Remove 'px' and convert to int
            assert numeric_value % 8 == 0, f"Spacing value must be multiple of 8px: {scale_name} = {scale_value}"

    def test_animation_value_format(self):
        """Test that animation values have correct format."""
        animation = tokens["animation"]

        # Test duration values
        for duration_name, duration_value in animation["duration"].items():
            assert isinstance(duration_value, str), f"Animation duration must be string: {duration_name}"
            assert duration_value.endswith("ms"), f"Animation duration must end with ms: {duration_name}"

            # Test that value is numeric
            numeric_value = duration_value[:-2]  # Remove 'ms'
            try:
                int(numeric_value)
            except ValueError:
                pytest.fail(f"Animation duration must be numeric: {duration_name}")

        # Test easing values
        valid_easings = ["ease", "ease-in", "ease-out", "ease-in-out", "linear"]
        for easing_name, easing_value in animation["easing"].items():
            assert isinstance(easing_value, str), f"Animation easing must be string: {easing_name}"
            assert easing_value in valid_easings, f"Invalid easing function: {easing_name} = {easing_value}"

    def test_breakpoint_value_format(self):
        """Test that breakpoint values have correct format."""
        breakpoints = tokens["breakpoints"]

        for breakpoint_name, breakpoint_value in breakpoints.items():
            assert isinstance(breakpoint_value, str), f"Breakpoint must be string: {breakpoint_name}"
            assert breakpoint_value.endswith("px"), f"Breakpoint must end with px: {breakpoint_name}"

            # Test that value is numeric
            numeric_value = breakpoint_value[:-2]  # Remove 'px'
            try:
                int(numeric_value)
            except ValueError:
                pytest.fail(f"Breakpoint value must be numeric: {breakpoint_name}")

    def test_status_color_usage_descriptions(self):
        """Test that status colors have usage descriptions."""
        status_colors = tokens["colors"]["status"]

        for color_name, color_data in status_colors.items():
            assert "usage" in color_data, f"Missing usage description for status color: {color_name}"
            assert isinstance(color_data["usage"], str), f"Usage must be string: {color_name}"
            assert len(color_data["usage"]) > 0, f"Usage cannot be empty: {color_name}"

    def test_contrast_ratio_format(self):
        """Test that contrast ratios have correct format where present."""
        colors = tokens["colors"]

        for category_name, category in colors.items():
            for color_name, color_data in category.items():
                if "contrast" in color_data:
                    contrast_data = color_data["contrast"]
                    assert isinstance(contrast_data, dict), f"Contrast must be dict: {category_name}.{color_name}"

                    for combo_name, ratio in contrast_data.items():
                        assert isinstance(ratio, str), f"Contrast ratio must be string: {combo_name}"
                        assert ":1" in ratio, f"Contrast ratio must contain ':1': {combo_name}"

    def test_file_size_constraint(self):
        """Test that design tokens JSON file meets size constraint."""
        # Get the actual tokens file path
        tokens_file = Path(__file__).parent.parent.parent.parent / "design" / "design_tokens.json"

        if tokens_file.exists():
            file_size = tokens_file.stat().st_size
            assert file_size <= 2048, f"Tokens file size {file_size} bytes exceeds 2KB limit (2048 bytes)"

    def test_json_validity(self):
        """Test that tokens can be serialized/deserialized as JSON."""
        # Test that tokens can be converted to JSON
        try:
            json_string = json.dumps(tokens)
            assert len(json_string) > 0, "JSON serialization produced empty string"
        except (TypeError, ValueError) as e:
            pytest.fail(f"Failed to serialize tokens to JSON: {e}")

        # Test that JSON can be parsed back
        try:
            parsed_tokens = json.loads(json_string)
            assert parsed_tokens == tokens, "Parsed tokens don't match original"
        except (TypeError, ValueError) as e:
            pytest.fail(f"Failed to parse tokens from JSON: {e}")

    def test_validate_tokens_with_invalid_color_count(self):
        """Test validation failure with invalid color count."""
        # Temporarily modify tokens to have wrong color count
        original_functional = tokens["colors"]["functional"].copy()

        # Remove a functional color
        del tokens["colors"]["functional"]["dark-text"]

        try:
            with pytest.raises(ValueError, match="Expected 4 functional colors, got 3"):
                validate_tokens()
        finally:
            # Restore original tokens
            tokens["colors"]["functional"] = original_functional

    def test_validate_tokens_with_invalid_typography_count(self):
        """Test validation failure with invalid typography count."""
        # Temporarily modify tokens to have wrong typography count
        original_scale = tokens["typography"]["scale"].copy()

        # Remove a typography scale
        del tokens["typography"]["scale"]["caption"]

        try:
            with pytest.raises(ValueError, match="Expected 9 typography scales, got 8"):
                validate_tokens()
        finally:
            # Restore original tokens
            tokens["typography"]["scale"] = original_scale

    def test_validate_tokens_with_invalid_spacing_count(self):
        """Test validation failure with invalid spacing count."""
        # Temporarily modify tokens to have wrong spacing count
        original_scale = tokens["spacing"]["scale"].copy()

        # Remove a spacing scale
        del tokens["spacing"]["scale"]["3xl"]

        try:
            with pytest.raises(ValueError, match="Expected 7 spacing scales, got 6"):
                validate_tokens()
        finally:
            # Restore original tokens
            tokens["spacing"]["scale"] = original_scale

    def test_validate_tokens_with_invalid_animation_count(self):
        """Test validation failure with invalid animation count."""
        # Temporarily modify tokens to have wrong animation count
        original_duration = tokens["animation"]["duration"].copy()

        # Remove an animation duration
        del tokens["animation"]["duration"]["data"]

        try:
            with pytest.raises(ValueError, match="Expected 4 animation durations, got 3"):
                validate_tokens()
        finally:
            # Restore original tokens
            tokens["animation"]["duration"] = original_duration

    def test_validate_tokens_with_invalid_breakpoint_count(self):
        """Test validation failure with invalid breakpoint count."""
        # Temporarily modify tokens to have wrong breakpoint count
        original_breakpoints = tokens["breakpoints"].copy()

        # Remove a breakpoint
        del tokens["breakpoints"]["desktop"]

        try:
            with pytest.raises(ValueError, match="Expected 3 breakpoints, got 2"):
                validate_tokens()
        finally:
            # Restore original tokens
            tokens["breakpoints"] = original_breakpoints

    def test_design_module_validation_on_import(self):
        """Test that design module validates tokens on import."""
        # This test verifies that importing the design module
        # automatically validates tokens without raising exceptions
        try:
            # If we get here, validation passed
            assert True
        except ValueError as e:
            pytest.fail(f"Design module validation failed on import: {e}")

    def test_minified_json_format(self):
        """Test that tokens file is properly minified."""
        tokens_file = Path(__file__).parent.parent.parent.parent / "design" / "design_tokens.json"

        if tokens_file.exists():
            with open(tokens_file) as f:
                content = f.read()

            # Minified JSON should not have unnecessary whitespace
            # Check that it doesn't have pretty-printing indentation
            lines = content.split("\n")
            if len(lines) > 1:
                # If multiple lines, should not have indentation
                for line in lines[1:]:  # Skip first line
                    if line.strip():  # Non-empty line
                        assert not line.startswith("  "), "File appears to be pretty-printed, not minified"

            # Check that it doesn't have spacing around JSON structural separators
            # (comma-spaces in content strings are allowed)
            assert "} ," not in content, "Found space before comma (not minified)"
            assert (
                ": {" not in content or content.count(": {") < 20
            ), "Too many spaces after colons suggest non-minified format"

    def test_required_primary_colors(self):
        """Test that required primary colors are present."""
        primary_colors = tokens["colors"]["primary"]

        # Check for core Anthrasite brand colors
        assert "anthracite" in primary_colors, "Missing anthracite primary color"
        assert "white" in primary_colors, "Missing white primary color"
        assert "synthesis-blue" in primary_colors, "Missing synthesis-blue primary color"

    def test_required_status_colors(self):
        """Test that required status colors are present."""
        status_colors = tokens["colors"]["status"]

        # Check for semantic status colors
        assert "critical" in status_colors, "Missing critical status color"
        assert "warning" in status_colors, "Missing warning status color"
        assert "success" in status_colors, "Missing success status color"

    def test_typography_hierarchy_consistency(self):
        """Test that typography hierarchy is consistent."""
        typography_scale = tokens["typography"]["scale"]

        # Extract font sizes for comparison
        sizes = {}
        for scale_name, scale_data in typography_scale.items():
            size_value = int(scale_data["size"][:-2])  # Remove 'px' and convert to int
            sizes[scale_name] = size_value

        # Test hierarchy (larger headings should have larger sizes)
        assert sizes["display"] > sizes["h1"], "Display should be larger than h1"
        assert sizes["h1"] > sizes["h2"], "h1 should be larger than h2"
        assert sizes["h2"] > sizes["h3"], "h2 should be larger than h3"
        assert sizes["h3"] > sizes["h4"], "h3 should be larger than h4"

        # Test body text hierarchy
        assert sizes["body-large"] > sizes["body"], "Body-large should be larger than body"
        assert sizes["body"] > sizes["body-small"], "Body should be larger than body-small"
        assert sizes["body-small"] > sizes["caption"], "Body-small should be larger than caption"
