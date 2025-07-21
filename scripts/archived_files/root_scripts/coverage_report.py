#!/usr/bin/env python3
"""
Test Coverage Report Generator - Task 089

Generates comprehensive test coverage reports for the LeadFactory system.
Integrates with CI and provides detailed analysis of critical paths.

Acceptance Criteria:
- Coverage > 80% ✓
- Critical paths 100% ✓
- Report generation ✓
- CI integration ✓
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import coverage


class CoverageReporter:
    """Generates comprehensive test coverage reports"""

    def __init__(self, source_dir: str = ".", min_coverage: float = 80.0):
        """
        Initialize coverage reporter

        Args:
            source_dir: Source directory to analyze
            min_coverage: Minimum coverage threshold
        """
        self.source_dir = Path(source_dir)
        self.min_coverage = min_coverage
        self.cov = coverage.Coverage(
            source=[str(self.source_dir)],
            omit=[
                "*/tests/*",
                "*/test_*.py",
                "*/.venv/*",
                "*/venv/*",
                "*/env/*",
                "*/site-packages/*",
                "setup.py",
                "*/migrations/*",
                "*/alembic/*",
                "stubs/*",
                "scripts/*",
            ],
        )

        # Critical paths that must have 100% coverage
        self.critical_paths = [
            "core/config.py",
            "core/exceptions.py",
            "database/models.py",
            "d0_gateway/base.py",
            "d0_gateway/circuit_breaker.py",
            "d0_gateway/rate_limiter.py",
            "d7_storefront/checkout.py",
            "d7_storefront/webhooks.py",
            "d9_delivery/compliance.py",
        ]

    def run_tests_with_coverage(self) -> bool:
        """Run tests with coverage collection"""
        print("🧪 Running tests with coverage collection...")

        try:
            # Start coverage
            self.cov.start()

            # Run pytest with coverage
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "--tb=short", "-v"],
                capture_output=True,
                text=True,
            )

            # Stop coverage
            self.cov.stop()
            self.cov.save()

            if result.returncode != 0:
                print(f"❌ Tests failed:\n{result.stdout}\n{result.stderr}")
                return False

            print("✅ Tests completed successfully")
            return True

        except Exception as e:
            print(f"❌ Error running tests: {e}")
            return False

    def analyze_coverage(self) -> dict[str, Any]:
        """Analyze coverage data and generate report"""
        print("📊 Analyzing coverage data...")

        try:
            # Load coverage data
            self.cov.load()

            # Get overall coverage percentage
            total_coverage = self.cov.report(show_missing=False, file=None)

            # Get detailed file coverage
            file_coverage = {}
            for filename in self.cov.get_data().measured_files():
                rel_path = os.path.relpath(filename, self.source_dir)

                # Skip non-source files
                if any(skip in rel_path for skip in ["site-packages", ".venv", "venv", "env"]):
                    continue

                analysis = self.cov.analysis2(filename)
                executed_lines = len(analysis[1])
                missing_lines = len(analysis[3])
                total_lines = executed_lines + missing_lines

                if total_lines > 0:
                    file_percent = (executed_lines / total_lines) * 100
                    file_coverage[rel_path] = {
                        "coverage": file_percent,
                        "executed_lines": executed_lines,
                        "missing_lines": missing_lines,
                        "total_lines": total_lines,
                        "missing_line_numbers": analysis[3],
                    }

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "total_coverage": total_coverage,
                "min_coverage": self.min_coverage,
                "files": file_coverage,
                "critical_paths": self._analyze_critical_paths(file_coverage),
                "summary": self._generate_summary(total_coverage, file_coverage),
            }

        except Exception as e:
            print(f"❌ Error analyzing coverage: {e}")
            return {}

    def _analyze_critical_paths(self, file_coverage: dict[str, Any]) -> dict[str, Any]:
        """Analyze coverage of critical paths"""
        critical_analysis = {}

        for critical_path in self.critical_paths:
            if critical_path in file_coverage:
                coverage_pct = file_coverage[critical_path]["coverage"]
                critical_analysis[critical_path] = {
                    "coverage": coverage_pct,
                    "meets_requirement": coverage_pct == 100.0,
                    "missing_lines": file_coverage[critical_path]["missing_line_numbers"],
                }
            else:
                critical_analysis[critical_path] = {
                    "coverage": 0.0,
                    "meets_requirement": False,
                    "missing_lines": [],
                    "note": "File not found or not measured",
                }

        return critical_analysis

    def _generate_summary(self, total_coverage: float, file_coverage: dict[str, Any]) -> dict[str, Any]:
        """Generate coverage summary statistics"""
        files_above_threshold = sum(1 for f in file_coverage.values() if f["coverage"] >= self.min_coverage)
        total_files = len(file_coverage)

        # Find files with lowest coverage
        lowest_coverage = sorted(
            [(path, data["coverage"]) for path, data in file_coverage.items()],
            key=lambda x: x[1],
        )[:5]

        # Find files with highest coverage
        highest_coverage = sorted(
            [(path, data["coverage"]) for path, data in file_coverage.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        return {
            "total_coverage": total_coverage,
            "meets_minimum": total_coverage >= self.min_coverage,
            "files_above_threshold": files_above_threshold,
            "total_files": total_files,
            "threshold_percentage": (files_above_threshold / total_files * 100) if total_files > 0 else 0,
            "lowest_coverage_files": lowest_coverage,
            "highest_coverage_files": highest_coverage,
        }

    def generate_html_report(self, output_dir: str = "htmlcov") -> str:
        """Generate HTML coverage report"""
        print(f"📄 Generating HTML report in {output_dir}/...")

        try:
            self.cov.html_report(directory=output_dir)
            return f"{output_dir}/index.html"
        except Exception as e:
            print(f"❌ Error generating HTML report: {e}")
            return ""

    def generate_xml_report(self, output_file: str = "coverage.xml") -> str:
        """Generate XML coverage report for CI integration"""
        print(f"📄 Generating XML report: {output_file}")

        try:
            self.cov.xml_report(outfile=output_file)
            return output_file
        except Exception as e:
            print(f"❌ Error generating XML report: {e}")
            return ""

    def print_detailed_report(self, analysis: dict[str, Any]):
        """Print detailed coverage report to console"""
        print("\n" + "=" * 80)
        print("🎯 LEADFACTORY TEST COVERAGE REPORT")
        print("=" * 80)

        summary = analysis["summary"]
        print(f"\n📊 OVERALL COVERAGE: {summary['total_coverage']:.1f}%")

        if summary["meets_minimum"]:
            print(f"✅ Meets minimum threshold ({self.min_coverage}%)")
        else:
            print(f"❌ Below minimum threshold ({self.min_coverage}%)")

        print(f"\n📁 FILES ANALYZED: {summary['total_files']}")
        print(f"✅ Above threshold: {summary['files_above_threshold']} ({summary['threshold_percentage']:.1f}%)")

        # Critical paths analysis
        print("\n🔥 CRITICAL PATHS ANALYSIS:")
        critical_paths = analysis["critical_paths"]
        all_critical_pass = True

        for path, data in critical_paths.items():
            status = "✅" if data["meets_requirement"] else "❌"
            print(f"{status} {path}: {data['coverage']:.1f}%")
            if not data["meets_requirement"]:
                all_critical_pass = False
                if data["missing_lines"]:
                    print(f"    Missing lines: {data['missing_lines']}")

        if all_critical_pass:
            print("✅ All critical paths have 100% coverage")
        else:
            print("❌ Some critical paths need attention")

        # Lowest coverage files
        print("\n📉 LOWEST COVERAGE FILES:")
        for path, coverage_pct in summary["lowest_coverage_files"]:
            status = "✅" if coverage_pct >= self.min_coverage else "❌"
            print(f"{status} {path}: {coverage_pct:.1f}%")

        # Highest coverage files
        print("\n📈 HIGHEST COVERAGE FILES:")
        for path, coverage_pct in summary["highest_coverage_files"][:3]:
            print(f"✅ {path}: {coverage_pct:.1f}%")

        print("\n" + "=" * 80)

    def save_json_report(self, analysis: dict[str, Any], output_file: str = "coverage_report.json"):
        """Save detailed analysis as JSON"""
        print(f"💾 Saving JSON report: {output_file}")

        try:
            with open(output_file, "w") as f:
                json.dump(analysis, f, indent=2)
            return output_file
        except Exception as e:
            print(f"❌ Error saving JSON report: {e}")
            return ""

    def check_ci_requirements(self, analysis: dict[str, Any]) -> bool:
        """Check if coverage meets CI requirements"""
        summary = analysis["summary"]
        critical_paths = analysis["critical_paths"]

        # Check overall coverage
        if summary["total_coverage"] < self.min_coverage:
            print(f"❌ Overall coverage {summary['total_coverage']:.1f}% below {self.min_coverage}%")
            return False

        # Check critical paths
        for path, data in critical_paths.items():
            if not data["meets_requirement"]:
                print(f"❌ Critical path {path} has {data['coverage']:.1f}% coverage (requires 100%)")
                return False

        print("✅ All CI coverage requirements met")
        return True


def main():
    """Main entry point for coverage reporting"""
    print("🚀 Starting LeadFactory Coverage Analysis")

    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="Generate test coverage reports")
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=80.0,
        help="Minimum coverage percentage (default: 80)",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running tests, analyze existing coverage",
    )
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    parser.add_argument("--xml", action="store_true", help="Generate XML report for CI")
    parser.add_argument("--json", action="store_true", help="Generate JSON report")
    parser.add_argument(
        "--ci-check",
        action="store_true",
        help="Check CI requirements and exit with status code",
    )

    args = parser.parse_args()

    # Initialize reporter
    reporter = CoverageReporter(min_coverage=args.min_coverage)

    # Run tests with coverage (unless skipped)
    if not args.skip_tests:
        if not reporter.run_tests_with_coverage():
            print("❌ Test execution failed")
            sys.exit(1)

    # Analyze coverage
    analysis = reporter.analyze_coverage()
    if not analysis:
        print("❌ Coverage analysis failed")
        sys.exit(1)

    # Generate reports
    reporter.print_detailed_report(analysis)

    if args.html:
        html_file = reporter.generate_html_report()
        if html_file:
            print(f"📄 HTML report: {html_file}")

    if args.xml:
        xml_file = reporter.generate_xml_report()
        if xml_file:
            print(f"📄 XML report: {xml_file}")

    if args.json:
        json_file = reporter.save_json_report(analysis)
        if json_file:
            print(f"📄 JSON report: {json_file}")

    # CI check
    if args.ci_check:
        if not reporter.check_ci_requirements(analysis):
            print("❌ CI coverage requirements not met")
            sys.exit(1)
        else:
            print("✅ CI coverage requirements satisfied")
            sys.exit(0)

    # Exit with error if coverage requirements not met
    if not reporter.check_ci_requirements(analysis):
        sys.exit(1)

    print("✅ Coverage analysis completed successfully")


if __name__ == "__main__":
    main()
