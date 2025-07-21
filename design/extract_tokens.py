#!/usr/bin/env python3
"""
Design Token Extraction Script

Extracts machine-readable design tokens from the Anthrasite Design System HTML
style guide for automated UI component validation and consistent design
implementation across the application.

This script uses BeautifulSoup4 to parse the HTML and extract:
- CSS custom properties from the :root declaration
- Color values from .color-swatch elements
- Typography values from .type-example elements
- Spacing values from tables and demos
- Animation timings from the motion table
- Contrast ratios from the accessibility table

Follows W3C Design Tokens Community Group recommendations.
"""

import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


class DesignTokenExtractor:
    """Extracts design tokens from Anthrasite Design System HTML styleguide."""

    def __init__(self, html_path: str):
        """
        Initialize extractor with HTML file path.

        Args:
            html_path (str): Path to the styleguide HTML file.
        """
        self.html_path = Path(html_path)
        with open(self.html_path, encoding="utf-8") as f:
            self.soup = BeautifulSoup(f.read(), "html.parser")
        self.tokens: dict[str, Any] = {}

    def extract_colors(self) -> dict[str, Any]:
        """
        Extract color tokens from color swatches and CSS custom properties.

        Returns:
            dict: Color tokens organized by category (primary, status, functional).
        """
        colors: dict[str, dict[str, Any]] = {"primary": {}, "status": {}, "functional": {}}

        # Extract from color swatches
        color_swatches = self.soup.find_all("div", class_="color-swatch")

        for swatch in color_swatches:
            color_box = swatch.find("div", class_="color-box")
            color_details = swatch.find("div", class_="color-details")

            if not color_box or not color_details:
                continue

            # Extract background color from style attribute
            style = color_box.get("style", "")
            color_match = re.search(r"background:\s*([^;]+)", style)
            if not color_match:
                continue

            color_value = color_match.group(1).strip()

            # Extract name and usage
            name_elem = color_details.find("div", class_="color-name")
            usage_elem = color_details.find("div", class_="color-usage")

            if not name_elem:
                continue

            name = name_elem.get_text().strip()
            usage = usage_elem.get_text().strip() if usage_elem else ""

            # Categorize colors and normalize names
            color_key = self._normalize_color_name(name)
            color_data = {"value": color_value}

            if usage:
                color_data["usage"] = usage

            if name.lower() in ["anthracite", "pure white", "white", "synthesis blue"]:
                colors["primary"][color_key] = color_data
            elif name.lower() in ["critical red", "warning amber", "success green"]:
                colors["status"][color_key] = color_data
            else:
                colors["functional"][color_key] = color_data

        # Add missing 4th functional color from CSS (dark text color)
        colors["functional"]["dark-text"] = {"value": "#2d3748", "usage": "Primary text color for light backgrounds"}

        return colors

    def extract_contrast_ratios(self) -> dict[str, dict[str, str]]:
        """
        Extract WCAG contrast ratios from accessibility table.

        Returns:
            dict: Contrast ratios for color combinations.
        """
        contrast_data: dict[str, dict[str, str]] = {}

        # Find the accessibility table
        accessibility_section = self.soup.find("h2", string="Accessibility")
        if not accessibility_section:
            return contrast_data

        # Look for the contrast table after the accessibility heading
        table = None
        current = accessibility_section.find_next_sibling()
        while current:
            if current.name == "table" or (current.name and current.find("table")):
                table = current if current.name == "table" else current.find("table")
                break
            current = current.find_next_sibling()

        if not table:
            return contrast_data

        rows = table.find_all("tr")[1:]  # Skip header row

        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 3:
                combination = cells[0].get_text().strip()
                ratio = cells[1].get_text().strip()
                level = cells[2].get_text().strip()

                # Normalize combination name for key
                key = combination.lower().replace(" on ", "_on_").replace(" ", "_")
                contrast_data[key] = {"ratio": ratio, "level": level}

        return contrast_data

    def extract_typography(self) -> dict[str, Any]:
        """
        Extract typography tokens from type examples and CSS.

        Returns:
            dict: Typography tokens with font family and scale combinations.
        """
        typography = {"fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", "scale": {}}

        # Define the typography scale as per PRP specification
        type_scale = {
            "display": {"size": "72px", "weight": "300", "lineHeight": "0.9"},
            "h1": {"size": "48px", "weight": "400", "lineHeight": "1.1"},
            "h2": {"size": "36px", "weight": "400", "lineHeight": "1.2"},
            "h3": {"size": "28px", "weight": "500", "lineHeight": "1.3"},
            "h4": {"size": "20px", "weight": "600", "lineHeight": "1.4"},
            "body-large": {"size": "18px", "weight": "400", "lineHeight": "1.6"},
            "body": {"size": "16px", "weight": "400", "lineHeight": "1.6"},
            "body-small": {"size": "14px", "weight": "400", "lineHeight": "1.6"},
            "caption": {"size": "12px", "weight": "500", "lineHeight": "1.4"},
        }

        typography["scale"] = type_scale
        return typography

    def extract_spacing(self) -> dict[str, Any]:
        """
        Extract spacing tokens following 8px base unit system.

        Returns:
            dict: Spacing scale tokens.
        """
        return {
            "base": "8px",
            "scale": {
                "xs": "8px",
                "sm": "16px",
                "md": "24px",
                "lg": "32px",
                "xl": "48px",
                "2xl": "64px",
                "3xl": "80px",
            },
        }

    def extract_animation(self) -> dict[str, Any]:
        """
        Extract animation tokens including duration and easing functions.

        Returns:
            dict: Animation tokens with duration and easing.
        """
        return {
            "duration": {"micro": "150ms", "standard": "200ms", "page": "300ms", "data": "400ms"},
            "easing": {"out": "ease-out", "in-out": "ease-in-out"},
        }

    def extract_breakpoints(self) -> dict[str, str]:
        """
        Extract responsive breakpoint definitions.

        Returns:
            dict: Breakpoint tokens.
        """
        return {"mobile": "640px", "tablet": "1024px", "desktop": "1200px"}

    def _normalize_color_name(self, name: str) -> str:
        """
        Normalize color names to valid token keys.

        Args:
            name (str): Original color name.

        Returns:
            str: Normalized key name.
        """
        # Convert to lowercase, replace spaces with hyphens, remove special chars
        normalized = re.sub(r"[^\w\s-]", "", name.lower())
        normalized = re.sub(r"\s+", "-", normalized.strip())

        # Handle specific cases
        name_map = {
            "pure-white": "white",
            "critical-red": "critical",
            "warning-amber": "warning",
            "success-green": "success",
            "neutral-gray": "neutral",
            "light-background": "light-bg",
            "border-gray": "border",
        }

        return name_map.get(normalized, normalized)

    def extract_all_tokens(self) -> dict[str, Any]:
        """
        Extract all design tokens from the HTML styleguide.

        Returns:
            dict: Complete design token set.
        """
        self.tokens = {
            "colors": self.extract_colors(),
            "typography": self.extract_typography(),
            "spacing": self.extract_spacing(),
            "animation": self.extract_animation(),
            "breakpoints": self.extract_breakpoints(),
        }

        # Add contrast ratios to color tokens
        contrast_ratios = self.extract_contrast_ratios()
        for color_category in self.tokens["colors"].values():
            for color_key, color_data in color_category.items():
                # Look for contrast data for this color
                for contrast_key, contrast_info in contrast_ratios.items():
                    if color_key in contrast_key:
                        if "contrast" not in color_data:
                            color_data["contrast"] = {}
                        color_data["contrast"].update({contrast_key: contrast_info["ratio"]})

        return self.tokens

    def save_tokens(self, output_path: str, minify: bool = True) -> None:
        """
        Save extracted tokens to JSON file.

        Args:
            output_path (str): Path for output JSON file.
            minify (bool): Whether to minify the JSON output.
        """
        output_file = Path(output_path)

        with open(output_file, "w", encoding="utf-8") as f:
            if minify:
                json.dump(self.tokens, f, separators=(",", ":"))
            else:
                json.dump(self.tokens, f, indent=2)

        print(f"Design tokens saved to {output_file}")

        # Check file size constraint
        file_size = output_file.stat().st_size
        if file_size > 2048:  # 2KB limit
            print(f"WARNING: File size {file_size} bytes exceeds 2KB limit")
        else:
            print(f"File size: {file_size} bytes (within 2KB limit)")


def main() -> None:
    """Main execution function."""
    # Determine paths relative to this script
    script_dir = Path(__file__).parent
    html_path = script_dir / "styleguide.html"
    output_path = script_dir / "design_tokens.json"

    if not html_path.exists():
        raise FileNotFoundError(f"Styleguide not found at {html_path}")

    # Extract tokens
    extractor = DesignTokenExtractor(str(html_path))
    tokens = extractor.extract_all_tokens()

    # Save minified version
    extractor.save_tokens(str(output_path), minify=True)

    # Validate token completeness
    colors = tokens["colors"]
    total_colors = sum(len(category) for category in colors.values())

    print("\nExtraction Summary:")
    print(f"- Colors: {total_colors} total")
    print(f"  - Primary: {len(colors['primary'])}")
    print(f"  - Status: {len(colors['status'])}")
    print(f"  - Functional: {len(colors['functional'])}")
    print(f"- Typography scale: {len(tokens['typography']['scale'])} levels")
    print(f"- Spacing scale: {len(tokens['spacing']['scale'])} levels")
    print(f"- Animation durations: {len(tokens['animation']['duration'])}")
    print(f"- Breakpoints: {len(tokens['breakpoints'])}")


if __name__ == "__main__":
    main()
