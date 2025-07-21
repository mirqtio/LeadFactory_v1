"""
Anthrasite Design System

This module provides access to design tokens extracted from the Anthrasite Design
System style guide. Tokens include colors, typography, spacing, animation timings,
and responsive breakpoints.

Usage:
    from design import tokens, colors, typography, spacing

    # Access color values
    primary_blue = colors.primary.synthesis_blue
    success_color = colors.status.success

    # Use typography scale
    heading_style = typography.scale.h1

    # Access spacing values
    small_padding = spacing.scale.sm
"""

import json
from pathlib import Path
from typing import Any, Dict, NamedTuple, Optional

# Load design tokens from JSON file
_TOKENS_PATH = Path(__file__).parent / "design_tokens.json"

with open(_TOKENS_PATH, encoding="utf-8") as f:
    tokens: dict[str, Any] = json.load(f)


class ColorToken(NamedTuple):
    """Represents a color token with value and optional metadata."""

    value: str
    usage: str | None = None
    contrast: dict[str, str] | None = None


class TypographyToken(NamedTuple):
    """Represents a typography token with size, weight, and line height."""

    size: str
    weight: str
    lineHeight: str


class ColorCategory:
    """Container for color tokens in a category."""

    def __init__(self, color_data: dict[str, Any]):
        for name, data in color_data.items():
            # Convert hyphens to underscores for valid Python attributes
            attr_name = name.replace("-", "_")
            if isinstance(data, dict):
                setattr(
                    self,
                    attr_name,
                    ColorToken(value=data.get("value", ""), usage=data.get("usage"), contrast=data.get("contrast")),
                )
            else:
                # Handle simple string values for backward compatibility
                setattr(self, attr_name, ColorToken(value=data))


class TypographyScale:
    """Container for typography scale tokens."""

    def __init__(self, scale_data: dict[str, dict[str, str]]):
        for name, data in scale_data.items():
            # Convert hyphens to underscores for valid Python attributes
            attr_name = name.replace("-", "_")
            setattr(
                self,
                attr_name,
                TypographyToken(size=data["size"], weight=data["weight"], lineHeight=data["lineHeight"]),
            )


class SpacingScale:
    """Container for spacing scale tokens."""

    def __init__(self, scale_data: dict[str, str]):
        for name, value in scale_data.items():
            # Convert special names for valid Python attributes
            attr_name = name.replace("-", "_").replace("2xl", "xxl").replace("3xl", "xxxl")
            setattr(self, attr_name, value)


class AnimationTokens:
    """Container for animation tokens."""

    def __init__(self, animation_data: dict[str, dict[str, str]]):
        self.duration = type("Duration", (), animation_data["duration"])()
        # Convert hyphenated keys to underscored attributes
        easing_attrs = {}
        for key, value in animation_data["easing"].items():
            attr_name = key.replace("-", "_")
            easing_attrs[attr_name] = value
        self.easing = type("Easing", (), easing_attrs)()


class BreakpointTokens:
    """Container for responsive breakpoint tokens."""

    def __init__(self, breakpoint_data: dict[str, str]):
        for name, value in breakpoint_data.items():
            setattr(self, name, value)


# Create token objects for easy access
colors = type(
    "Colors",
    (),
    {
        "primary": ColorCategory(tokens["colors"]["primary"]),
        "status": ColorCategory(tokens["colors"]["status"]),
        "functional": ColorCategory(tokens["colors"]["functional"]),
    },
)()

typography = type(
    "Typography",
    (),
    {"fontFamily": tokens["typography"]["fontFamily"], "scale": TypographyScale(tokens["typography"]["scale"])},
)()

spacing = type("Spacing", (), {"base": tokens["spacing"]["base"], "scale": SpacingScale(tokens["spacing"]["scale"])})()

animation = AnimationTokens(tokens["animation"])

breakpoints = BreakpointTokens(tokens["breakpoints"])


def get_color_value(category: str, name: str) -> str:
    """
    Get a color value by category and name.

    Args:
        category (str): Color category ('primary', 'status', 'functional').
        name (str): Color name within the category.

    Returns:
        str: Hex color value.

    Raises:
        KeyError: If category or color name not found.
    """
    color_data = tokens["colors"][category][name]
    if isinstance(color_data, dict):
        return str(color_data["value"])
    return str(color_data)


def get_typography_css(scale_name: str) -> str:
    """
    Generate CSS properties for a typography scale.

    Args:
        scale_name (str): Typography scale name (e.g., 'h1', 'body').

    Returns:
        str: CSS properties string.
    """
    scale = tokens["typography"]["scale"][scale_name]
    return f"font-size: {str(scale['size'])}; font-weight: {str(scale['weight'])}; line-height: {str(scale['lineHeight'])};"


def get_spacing_value(scale_name: str) -> str:
    """
    Get a spacing value by scale name.

    Args:
        scale_name (str): Spacing scale name (e.g., 'sm', 'lg').

    Returns:
        str: Spacing value with units.
    """
    return str(tokens["spacing"]["scale"][scale_name])


def validate_tokens() -> bool:
    """
    Validate that all required tokens are present and well-formed.

    Returns:
        bool: True if validation passes.

    Raises:
        ValueError: If validation fails with details.
    """
    required_structure: dict[str, Any] = {
        "colors": {
            "primary": 3,  # Expected number of primary colors
            "status": 3,  # Expected number of status colors
            "functional": 4,  # Expected number of functional colors
        },
        "typography": {"scale": 9},  # Expected number of typography scales
        "spacing": {"scale": 7},  # Expected number of spacing scales
        "animation": {"duration": 4},  # Expected number of animation durations
        "breakpoints": 3,  # Expected number of breakpoints
    }

    # Validate color counts
    colors_req = required_structure["colors"]
    if isinstance(colors_req, dict):
        for category, expected_count in colors_req.items():
            actual_count = len(tokens["colors"][category])
            if actual_count != expected_count:
                raise ValueError(f"Expected {expected_count} {category} colors, got {actual_count}")

    # Validate typography scale count
    scale_count = len(tokens["typography"]["scale"])
    typography_req = required_structure["typography"]
    if isinstance(typography_req, dict):
        expected_scale_count = typography_req["scale"]
        if scale_count != expected_scale_count:
            raise ValueError(f"Expected {expected_scale_count} typography scales, got {scale_count}")

    # Validate spacing scale count
    spacing_count = len(tokens["spacing"]["scale"])
    spacing_req = required_structure["spacing"]
    if isinstance(spacing_req, dict):
        expected_spacing_count = spacing_req["scale"]
        if spacing_count != expected_spacing_count:
            raise ValueError(f"Expected {expected_spacing_count} spacing scales, got {spacing_count}")

    # Validate animation duration count
    duration_count = len(tokens["animation"]["duration"])
    animation_req = required_structure["animation"]
    if isinstance(animation_req, dict):
        expected_duration_count = animation_req["duration"]
        if duration_count != expected_duration_count:
            raise ValueError(f"Expected {expected_duration_count} animation durations, got {duration_count}")

    # Validate breakpoint count
    breakpoint_count = len(tokens["breakpoints"])
    expected_breakpoint_count = required_structure["breakpoints"]
    if breakpoint_count != expected_breakpoint_count:
        raise ValueError(f"Expected {expected_breakpoint_count} breakpoints, got {breakpoint_count}")

    return True


# Export main components
__all__ = [
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


# Validate tokens on import
validate_tokens()
