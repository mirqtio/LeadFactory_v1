#!/usr/bin/env python3
"""
Coverage Badge Generator for PRP-1061
Generates shields.io-compatible SVG badges from coverage data
"""

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


class CoverageBadgeGenerator:
    """Generates coverage badges in shields.io format."""

    # Color thresholds for badge colors (matches profiles/lint.yaml)
    COLOR_THRESHOLDS = {
        90: "brightgreen",  # Excellent
        80: "green",  # Good
        70: "yellow",  # Fair
        60: "orange",  # Poor
        0: "red",  # Critical
    }

    def __init__(self, output_dir: str = "docs/badges"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_coverage_from_xml(self, xml_path: Path) -> Optional[float]:
        """Extract coverage percentage from coverage.xml file."""
        try:
            if not xml_path.exists():
                print(f"⚠️  Coverage XML file not found: {xml_path}")
                return None

            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Find coverage element and extract line-rate
            coverage_elem = root.find(".//coverage")
            if coverage_elem is not None:
                line_rate = float(coverage_elem.get("line-rate", 0))
                return round(line_rate * 100, 2)

            print("⚠️  No coverage element found in XML")
            return None

        except Exception as e:
            print(f"❌ Failed to parse coverage XML: {e}")
            return None

    def get_coverage_from_pytest(self) -> Optional[float]:
        """Run pytest with coverage to get current coverage percentage."""
        try:
            print("🧪 Running pytest with coverage to get current stats...")

            result = subprocess.run(
                ["pytest", "--cov=.", "--cov-report=xml:coverage.xml", "--cov-report=term-missing", "--tb=no", "-q"],
                capture_output=True,
                text=True,
                timeout=120,
            )

            # Parse coverage from output
            for line in result.stdout.split("\n"):
                if "TOTAL" in line and "%" in line:
                    parts = line.split()
                    for part in parts:
                        if part.endswith("%"):
                            return float(part.rstrip("%"))

            # Fallback to XML file
            return self.get_coverage_from_xml(Path("coverage.xml"))

        except subprocess.TimeoutExpired:
            print("❌ Pytest timeout - using existing coverage.xml")
            return self.get_coverage_from_xml(Path("coverage.xml"))
        except Exception as e:
            print(f"❌ Failed to run pytest: {e}")
            return self.get_coverage_from_xml(Path("coverage.xml"))

    def determine_badge_color(self, coverage_percentage: float) -> str:
        """Determine badge color based on coverage percentage."""
        for threshold in sorted(self.COLOR_THRESHOLDS.keys(), reverse=True):
            if coverage_percentage >= threshold:
                return self.COLOR_THRESHOLDS[threshold]
        return "red"

    def generate_svg_badge(self, coverage_percentage: float) -> str:
        """Generate SVG badge content for coverage percentage."""
        color = self.determine_badge_color(coverage_percentage)

        # SVG template with dynamic values
        svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="104" height="20" role="img" aria-label="coverage: {coverage_percentage:.0f}%">
<title>coverage: {coverage_percentage:.0f}%</title>
<linearGradient id="s" x2="0" y2="100%">
<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
<stop offset="1" stop-opacity=".1"/>
</linearGradient>
<clipPath id="r">
<rect width="104" height="20" rx="3" fill="#fff"/>
</clipPath>
<g clip-path="url(#r)">
<rect width="63" height="20" fill="#555"/>
<rect x="63" width="41" height="20" fill="{color}"/>
<rect width="104" height="20" fill="url(#s)"/>
</g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="110">
<text aria-hidden="true" x="325" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="530">coverage</text>
<text x="325" y="140" transform="scale(.1)" textLength="530">coverage</text>
<text aria-hidden="true" x="825" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="310">{coverage_percentage:.0f}%</text>
<text x="825" y="140" transform="scale(.1)" textLength="310">{coverage_percentage:.0f}%</text>
</g>
</svg>"""
        return svg_content

    def save_badge(self, coverage_percentage: float, filename: str = "coverage.svg") -> Path:
        """Save coverage badge to file."""
        svg_content = self.generate_svg_badge(coverage_percentage)
        badge_path = self.output_dir / filename

        badge_path.write_text(svg_content, encoding="utf-8")
        return badge_path

    def generate_json_report(self, coverage_percentage: float, filename: str = "coverage.json") -> Path:
        """Generate JSON report with coverage data."""
        import time

        report_data = {
            "coverage_percentage": coverage_percentage,
            "timestamp": time.time(),
            "color": self.determine_badge_color(coverage_percentage),
            "status": "passed" if coverage_percentage >= 80 else "failed",
            "threshold": 80,
        }

        json_path = self.output_dir / filename
        json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        return json_path

    def run(self, coverage_source: str = "auto", coverage_percentage: Optional[float] = None) -> bool:
        """Main execution method."""
        print("🏷️  PRP-1061 Coverage Badge Generator")
        print("=" * 50)

        # Get coverage percentage
        if coverage_percentage is not None:
            print(f"📊 Using provided coverage: {coverage_percentage:.2f}%")
        elif coverage_source == "xml":
            coverage_percentage = self.get_coverage_from_xml(Path("coverage.xml"))
        elif coverage_source == "pytest":
            coverage_percentage = self.get_coverage_from_pytest()
        else:  # auto
            # Try XML first, then pytest
            coverage_percentage = self.get_coverage_from_xml(Path("coverage.xml"))
            if coverage_percentage is None:
                coverage_percentage = self.get_coverage_from_pytest()

        if coverage_percentage is None:
            print("❌ Could not determine coverage percentage")
            return False

        print(f"📊 Coverage: {coverage_percentage:.2f}%")

        # Generate badge
        try:
            badge_path = self.save_badge(coverage_percentage)
            print(f"✅ Coverage badge saved: {badge_path}")

            # Generate JSON report
            json_path = self.generate_json_report(coverage_percentage)
            print(f"✅ Coverage report saved: {json_path}")

            # Show badge color
            color = self.determine_badge_color(coverage_percentage)
            print(f"🎨 Badge color: {color}")

            return True

        except Exception as e:
            print(f"❌ Failed to generate badge: {e}")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate coverage badge for PRP-1061")
    parser.add_argument(
        "--source", choices=["auto", "xml", "pytest"], default="auto", help="Coverage data source (default: auto)"
    )
    parser.add_argument("--coverage", type=float, help="Specific coverage percentage to use")
    parser.add_argument("--output-dir", default="docs/badges", help="Output directory for badge files")
    parser.add_argument("--filename", default="coverage.svg", help="Output badge filename")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        print(f"Arguments: {vars(args)}")

    # Create generator
    generator = CoverageBadgeGenerator(output_dir=args.output_dir)

    # Generate badge
    success = generator.run(coverage_source=args.source, coverage_percentage=args.coverage)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
