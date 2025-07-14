"""
Tests for design token usage functionality.

Tests cover:
- Token import functionality
- Usage in style generation
- Backward compatibility
- Helper function behavior
"""

import pytest

import design
from design import (
    ColorToken,
    TypographyToken,
    animation,
    breakpoints,
    colors,
    get_color_value,
    get_spacing_value,
    get_typography_css,
    spacing,
    tokens,
    typography,
)


class TestTokenUsage:
    """Test suite for design token usage and integration."""

    def test_tokens_import(self):
        """Test that tokens can be imported successfully."""
        # Test direct import
        assert hasattr(design, "tokens")
        assert hasattr(design, "colors")
        assert hasattr(design, "typography")
        assert hasattr(design, "spacing")
        assert hasattr(design, "animation")
        assert hasattr(design, "breakpoints")

        # Test that tokens is a dictionary
        assert isinstance(tokens, dict)
        assert len(tokens) > 0

    def test_color_object_access(self):
        """Test accessing colors through object notation."""
        # Test primary color access
        assert hasattr(colors.primary, "anthracite")
        assert hasattr(colors.primary, "white")
        assert hasattr(colors.primary, "synthesis_blue")  # Note: hyphen becomes underscore

        # Test status color access
        assert hasattr(colors.status, "critical")
        assert hasattr(colors.status, "warning")
        assert hasattr(colors.status, "success")

        # Test functional color access
        assert hasattr(colors.functional, "neutral")
        assert hasattr(colors.functional, "light_bg")  # Note: hyphen becomes underscore
        assert hasattr(colors.functional, "border")
        assert hasattr(colors.functional, "dark_text")  # Note: hyphen becomes underscore

    def test_color_token_values(self):
        """Test that color tokens have correct values."""
        # Test primary colors
        assert colors.primary.anthracite.value == "#0a0a0a"
        assert colors.primary.white.value == "#ffffff"
        assert colors.primary.synthesis_blue.value == "#0066ff"

        # Test status colors
        assert colors.status.critical.value == "#dc2626"
        assert colors.status.warning.value == "#f59e0b"
        assert colors.status.success.value == "#10b981"

    def test_color_token_metadata(self):
        """Test that color tokens include metadata."""
        # Test that status colors have usage descriptions
        assert colors.status.critical.usage is not None
        assert "critical" in colors.status.critical.usage.lower()

        assert colors.status.warning.usage is not None
        assert "warning" in colors.status.warning.usage.lower() or "medium" in colors.status.warning.usage.lower()

        assert colors.status.success.usage is not None
        assert "success" in colors.status.success.usage.lower() or "positive" in colors.status.success.usage.lower()

    def test_color_token_contrast_data(self):
        """Test that color tokens include contrast information where available."""
        # Check if any colors have contrast data
        has_contrast = False

        for category in [colors.primary, colors.status, colors.functional]:
            for attr_name in dir(category):
                if not attr_name.startswith("_"):
                    color_token = getattr(category, attr_name)
                    if isinstance(color_token, ColorToken) and color_token.contrast:
                        has_contrast = True
                        assert isinstance(color_token.contrast, dict)
                        # Contrast ratios should be strings with :1 format
                        for ratio in color_token.contrast.values():
                            assert isinstance(ratio, str)
                            assert ":1" in ratio

        # At least some colors should have contrast data
        assert has_contrast, "No colors found with contrast information"

    def test_typography_object_access(self):
        """Test accessing typography through object notation."""
        # Test font family access
        assert hasattr(typography, "fontFamily")
        assert isinstance(typography.fontFamily, str)

        # Test scale access
        assert hasattr(typography, "scale")
        assert hasattr(typography.scale, "display")
        assert hasattr(typography.scale, "h1")
        assert hasattr(typography.scale, "h2")
        assert hasattr(typography.scale, "body")
        assert hasattr(typography.scale, "body_large")  # Note: hyphen becomes underscore
        assert hasattr(typography.scale, "body_small")  # Note: hyphen becomes underscore

    def test_typography_token_values(self):
        """Test that typography tokens have correct structure."""
        # Test display typography
        display = typography.scale.display
        assert isinstance(display, TypographyToken)
        assert display.size == "72px"
        assert display.weight == "300"
        assert display.lineHeight == "0.9"

        # Test h1 typography
        h1 = typography.scale.h1
        assert isinstance(h1, TypographyToken)
        assert h1.size == "48px"
        assert h1.weight == "400"
        assert h1.lineHeight == "1.1"

    def test_spacing_object_access(self):
        """Test accessing spacing through object notation."""
        # Test base spacing
        assert hasattr(spacing, "base")
        assert spacing.base == "8px"

        # Test scale access
        assert hasattr(spacing, "scale")
        assert hasattr(spacing.scale, "xs")
        assert hasattr(spacing.scale, "sm")
        assert hasattr(spacing.scale, "md")
        assert hasattr(spacing.scale, "lg")
        assert hasattr(spacing.scale, "xl")
        assert hasattr(spacing.scale, "xxl")  # Note: 2xl becomes xxl
        assert hasattr(spacing.scale, "xxxl")  # Note: 3xl becomes xxxl

    def test_spacing_values(self):
        """Test that spacing values follow 8px base unit system."""
        # Test base value
        assert spacing.base == "8px"

        # Test scale values
        assert spacing.scale.xs == "8px"
        assert spacing.scale.sm == "16px"
        assert spacing.scale.md == "24px"
        assert spacing.scale.lg == "32px"
        assert spacing.scale.xl == "48px"
        assert spacing.scale.xxl == "64px"
        assert spacing.scale.xxxl == "80px"

    def test_animation_object_access(self):
        """Test accessing animation tokens through object notation."""
        # Test duration access
        assert hasattr(animation, "duration")
        assert hasattr(animation.duration, "micro")
        assert hasattr(animation.duration, "standard")
        assert hasattr(animation.duration, "page")
        assert hasattr(animation.duration, "data")

        # Test easing access
        assert hasattr(animation, "easing")
        assert hasattr(animation.easing, "out")
        assert hasattr(animation.easing, "in_out")  # Note: hyphen becomes underscore

    def test_animation_values(self):
        """Test that animation values have correct format."""
        # Test durations
        assert animation.duration.micro == "150ms"
        assert animation.duration.standard == "200ms"
        assert animation.duration.page == "300ms"
        assert animation.duration.data == "400ms"

        # Test easing functions
        assert animation.easing.out == "ease-out"
        assert animation.easing.in_out == "ease-in-out"

    def test_breakpoint_object_access(self):
        """Test accessing breakpoints through object notation."""
        assert hasattr(breakpoints, "mobile")
        assert hasattr(breakpoints, "tablet")
        assert hasattr(breakpoints, "desktop")

    def test_breakpoint_values(self):
        """Test that breakpoint values are correct."""
        assert breakpoints.mobile == "640px"
        assert breakpoints.tablet == "1024px"
        assert breakpoints.desktop == "1200px"

    def test_get_color_value_function(self):
        """Test get_color_value helper function."""
        # Test primary colors
        assert get_color_value("primary", "anthracite") == "#0a0a0a"
        assert get_color_value("primary", "white") == "#ffffff"
        assert get_color_value("primary", "synthesis-blue") == "#0066ff"

        # Test status colors
        assert get_color_value("status", "critical") == "#dc2626"
        assert get_color_value("status", "warning") == "#f59e0b"
        assert get_color_value("status", "success") == "#10b981"

        # Test functional colors
        assert get_color_value("functional", "neutral") == "#6b7280"

    def test_get_color_value_error_handling(self):
        """Test get_color_value error handling."""
        # Test invalid category
        with pytest.raises(KeyError):
            get_color_value("invalid", "anthracite")

        # Test invalid color name
        with pytest.raises(KeyError):
            get_color_value("primary", "invalid")

    def test_get_typography_css_function(self):
        """Test get_typography_css helper function."""
        # Test display typography CSS
        display_css = get_typography_css("display")
        assert "font-size: 72px" in display_css
        assert "font-weight: 300" in display_css
        assert "line-height: 0.9" in display_css

        # Test h1 typography CSS
        h1_css = get_typography_css("h1")
        assert "font-size: 48px" in h1_css
        assert "font-weight: 400" in h1_css
        assert "line-height: 1.1" in h1_css

        # Test body typography CSS
        body_css = get_typography_css("body")
        assert "font-size: 16px" in body_css
        assert "font-weight: 400" in body_css
        assert "line-height: 1.6" in body_css

    def test_get_typography_css_format(self):
        """Test that get_typography_css returns valid CSS format."""
        css = get_typography_css("h1")

        # Should contain CSS property-value pairs
        assert ":" in css
        assert ";" in css

        # Should contain all three properties
        properties = css.split(";")
        property_names = []
        for prop in properties:
            if prop.strip():
                name = prop.split(":")[0].strip()
                property_names.append(name)

        assert "font-size" in property_names
        assert "font-weight" in property_names
        assert "line-height" in property_names

    def test_get_typography_css_error_handling(self):
        """Test get_typography_css error handling."""
        # Test invalid scale name
        with pytest.raises(KeyError):
            get_typography_css("invalid")

    def test_get_spacing_value_function(self):
        """Test get_spacing_value helper function."""
        # Test spacing scale values
        assert get_spacing_value("xs") == "8px"
        assert get_spacing_value("sm") == "16px"
        assert get_spacing_value("md") == "24px"
        assert get_spacing_value("lg") == "32px"
        assert get_spacing_value("xl") == "48px"
        assert get_spacing_value("2xl") == "64px"
        assert get_spacing_value("3xl") == "80px"

    def test_get_spacing_value_error_handling(self):
        """Test get_spacing_value error handling."""
        # Test invalid scale name
        with pytest.raises(KeyError):
            get_spacing_value("invalid")

    def test_color_token_namedtuple(self):
        """Test ColorToken namedtuple functionality."""
        # Test that color tokens are ColorToken instances
        color_token = colors.primary.anthracite
        assert isinstance(color_token, ColorToken)

        # Test namedtuple fields
        assert hasattr(color_token, "value")
        assert hasattr(color_token, "usage")
        assert hasattr(color_token, "contrast")

        # Test that we can access fields by index
        assert color_token[0] == color_token.value
        assert color_token[1] == color_token.usage
        assert color_token[2] == color_token.contrast

    def test_typography_token_namedtuple(self):
        """Test TypographyToken namedtuple functionality."""
        # Test that typography tokens are TypographyToken instances
        type_token = typography.scale.h1
        assert isinstance(type_token, TypographyToken)

        # Test namedtuple fields
        assert hasattr(type_token, "size")
        assert hasattr(type_token, "weight")
        assert hasattr(type_token, "lineHeight")

        # Test that we can access fields by index
        assert type_token[0] == type_token.size
        assert type_token[1] == type_token.weight
        assert type_token[2] == type_token.lineHeight

    def test_backward_compatibility_dict_access(self):
        """Test backward compatibility with direct dictionary access."""
        # Test that tokens can still be accessed as a dictionary
        assert tokens["colors"]["primary"]["anthracite"]["value"] == "#0a0a0a"
        assert tokens["typography"]["fontFamily"] == "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
        assert tokens["spacing"]["base"] == "8px"

    def test_style_generation_example(self):
        """Test usage example for generating styles."""
        # Example: Create CSS for a button component
        button_styles = {
            "background_color": colors.primary.synthesis_blue.value,
            "color": colors.primary.white.value,
            "padding": f"{spacing.scale.sm} {spacing.scale.md}",
            "font_size": typography.scale.body.size,
            "font_weight": typography.scale.body.weight,
            "border_radius": "8px",
            "transition": f"all {animation.duration.standard} {animation.easing.out}",
        }

        # Verify button styles are generated correctly
        assert button_styles["background_color"] == "#0066ff"
        assert button_styles["color"] == "#ffffff"
        assert button_styles["padding"] == "16px 24px"
        assert button_styles["font_size"] == "16px"
        assert button_styles["font_weight"] == "400"
        assert button_styles["transition"] == "all 200ms ease-out"

    def test_responsive_design_example(self):
        """Test usage example for responsive design."""
        # Example: Create responsive breakpoint media queries
        media_queries = {
            "mobile": f"@media (max-width: {breakpoints.mobile})",
            "tablet": f"@media (min-width: {breakpoints.mobile}) and (max-width: {breakpoints.tablet})",
            "desktop": f"@media (min-width: {breakpoints.desktop})",
        }

        # Verify media queries are generated correctly
        assert media_queries["mobile"] == "@media (max-width: 640px)"
        assert media_queries["tablet"] == "@media (min-width: 640px) and (max-width: 1024px)"
        assert media_queries["desktop"] == "@media (min-width: 1200px)"

    def test_semantic_color_usage(self):
        """Test semantic usage of status colors."""
        # Example: Alert component color mapping
        alert_colors = {
            "error": colors.status.critical.value,
            "warning": colors.status.warning.value,
            "success": colors.status.success.value,
            "info": colors.primary.synthesis_blue.value,
        }

        # Verify semantic color mapping
        assert alert_colors["error"] == "#dc2626"
        assert alert_colors["warning"] == "#f59e0b"
        assert alert_colors["success"] == "#10b981"
        assert alert_colors["info"] == "#0066ff"

    def test_typography_scale_usage(self):
        """Test typography scale usage in component hierarchy."""
        # Example: Article heading hierarchy
        article_typography = {
            "title": get_typography_css("display"),
            "heading": get_typography_css("h1"),
            "subheading": get_typography_css("h2"),
            "section_title": get_typography_css("h3"),
            "body_text": get_typography_css("body"),
            "caption": get_typography_css("caption"),
        }

        # Verify all typography styles are generated
        for style_name, css in article_typography.items():
            assert isinstance(css, str)
            assert "font-size:" in css
            assert "font-weight:" in css
            assert "line-height:" in css

    def test_spacing_system_usage(self):
        """Test spacing system usage for consistent layouts."""
        # Example: Card component spacing
        card_spacing = {
            "margin_bottom": spacing.scale.lg,
            "padding": spacing.scale.md,
            "inner_spacing": spacing.scale.sm,
            "section_gap": spacing.scale.xl,
        }

        # Verify spacing values
        assert card_spacing["margin_bottom"] == "32px"
        assert card_spacing["padding"] == "24px"
        assert card_spacing["inner_spacing"] == "16px"
        assert card_spacing["section_gap"] == "48px"

    def test_animation_timing_usage(self):
        """Test animation timing usage for consistent interactions."""
        # Example: UI animation specifications
        ui_animations = {
            "hover_effect": f"transform {animation.duration.micro} {animation.easing.out}",
            "modal_slide": f"transform {animation.duration.standard} {animation.easing.in_out}",
            "page_transition": f"opacity {animation.duration.page} {animation.easing.out}",
            "data_loading": f"opacity {animation.duration.data} {animation.easing.in_out}",
        }

        # Verify animation specifications
        assert ui_animations["hover_effect"] == "transform 150ms ease-out"
        assert ui_animations["modal_slide"] == "transform 200ms ease-in-out"
        assert ui_animations["page_transition"] == "opacity 300ms ease-out"
        assert ui_animations["data_loading"] == "opacity 400ms ease-in-out"

    def test_module_exports(self):
        """Test that all expected items are exported from the module."""
        expected_exports = [
            "tokens",
            "colors",
            "typography",
            "spacing",
            "animation",
            "breakpoints",
            "get_color_value",
            "get_typography_css",
            "get_spacing_value",
            "validate_tokens",
            "ColorToken",
            "TypographyToken",
        ]

        for export_name in expected_exports:
            assert hasattr(design, export_name), f"Missing export: {export_name}"
            assert export_name in design.__all__, f"Export not in __all__: {export_name}"

    def test_integration_with_existing_codebase(self):
        """Test that design tokens can integrate with existing code patterns."""
        # Example: Creating a theme object that might be used in a React/Vue component
        theme = {
            "colors": {
                "primary": colors.primary.synthesis_blue.value,
                "background": colors.functional.light_bg.value,
                "text": colors.functional.dark_text.value,
                "border": colors.functional.border.value,
            },
            "fonts": {
                "family": typography.fontFamily,
                "sizes": {
                    "large": typography.scale.body_large.size,
                    "normal": typography.scale.body.size,
                    "small": typography.scale.body_small.size,
                },
            },
            "space": [spacing.scale.xs, spacing.scale.sm, spacing.scale.md, spacing.scale.lg, spacing.scale.xl],
        }

        # Verify theme structure
        assert theme["colors"]["primary"] == "#0066ff"
        assert theme["fonts"]["family"].startswith("-apple-system")
        assert theme["fonts"]["sizes"]["normal"] == "16px"
        assert len(theme["space"]) == 5
        assert theme["space"][0] == "8px"  # xs
        assert theme["space"][4] == "48px"  # xl
