#!/usr/bin/env python3
"""
Quality Gate Script for PRP-1061 Coverage/Lint Bot
Orchestrates Ruff linting and coverage validation with Redis evidence collection
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import redis
from pydantic import BaseModel, ConfigDict


class QualityGateConfig(BaseModel):
    """Configuration for quality gate execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Redis configuration
    redis_url: str = "redis://localhost:6379"
    prp_id: Optional[str] = None

    # Quality thresholds
    coverage_threshold: int = 80
    ruff_strict_mode: bool = False

    # Performance targets
    max_execution_seconds: int = 120

    # Feature flags
    enable_ruff_enforcement: bool = False
    parallel_legacy_tools: bool = True
    quality_gate_strict_mode: bool = False


class QualityResults(BaseModel):
    """Results from quality gate execution."""

    # Overall status
    success: bool
    execution_time_seconds: float

    # Ruff results
    ruff_clean: bool
    ruff_errors: List[str] = []
    ruff_warnings: List[str] = []
    ruff_fixes_applied: int = 0

    # Coverage results
    coverage_percentage: float
    coverage_passed: bool
    coverage_report: str = ""
    missing_lines: Dict[str, List[int]] = {}

    # Evidence keys
    evidence_keys: Dict[str, str] = {}

    # PRP promotion readiness
    promotion_ready: bool = False


class QualityGate:
    """Main quality gate orchestrator with Redis evidence integration."""

    def __init__(self, config: QualityGateConfig):
        self.config = config
        self.redis_client = self._setup_redis()
        self.start_time = time.time()

    def _setup_redis(self) -> Optional[redis.Redis]:
        """Initialize Redis connection with fallback handling."""
        try:
            client = redis.from_url(self.config.redis_url, decode_responses=True)
            # Test connection
            client.ping()
            return client
        except Exception as e:
            print(f"⚠️  Redis unavailable: {e}")
            print("ℹ️  Continuing with local validation only")
            return None

    def run(self) -> QualityResults:
        """Execute complete quality gate workflow."""
        print("🚀 Starting PRP-1061 Quality Gate")
        print(f"📋 PRP ID: {self.config.prp_id or 'not specified'}")
        print(f"🎯 Coverage threshold: {self.config.coverage_threshold}%")
        print(f"⚡ Ruff enforcement: {'enabled' if self.config.enable_ruff_enforcement else 'disabled'}")
        print()

        results = QualityResults(
            success=False, execution_time_seconds=0.0, ruff_clean=False, coverage_percentage=0.0, coverage_passed=False
        )

        try:
            # Step 1: Run Ruff linting
            print("🔍 Step 1: Running Ruff linting...")
            ruff_success, ruff_data = self._run_ruff_linting()
            results.ruff_clean = ruff_success
            results.ruff_errors = ruff_data.get("errors", [])
            results.ruff_warnings = ruff_data.get("warnings", [])
            results.ruff_fixes_applied = ruff_data.get("fixes_applied", 0)

            # Step 2: Run coverage analysis
            print("📊 Step 2: Running coverage analysis...")
            coverage_success, coverage_data = self._run_coverage_analysis()
            results.coverage_passed = coverage_success
            results.coverage_percentage = coverage_data.get("percentage", 0.0)
            results.coverage_report = coverage_data.get("report", "")
            results.missing_lines = coverage_data.get("missing_lines", {})

            # Step 3: Collect evidence to Redis
            print("💾 Step 3: Writing evidence to Redis...")
            evidence_keys = self._write_evidence_to_redis(results)
            results.evidence_keys = evidence_keys

            # Step 4: Final validation
            results.success = self._validate_promotion_criteria(results)
            results.execution_time_seconds = time.time() - self.start_time

            # Step 5: Validate PRP promotion readiness
            if self.config.prp_id:
                print("🔬 Step 5: Validating PRP promotion readiness...")
                promotion_ready = self._validate_prp_promotion_readiness(results)
                results.promotion_ready = promotion_ready

            # Step 6: Generate coverage badge
            if results.coverage_passed:
                print("🏷️  Step 6: Generating coverage badge...")
                self._generate_coverage_badge(results.coverage_percentage)

            self._print_final_report(results)
            return results

        except Exception as e:
            print(f"❌ Quality gate failed with exception: {e}")
            results.execution_time_seconds = time.time() - self.start_time
            return results

    def _run_ruff_linting(self) -> Tuple[bool, Dict]:
        """Execute Ruff linting with zero-tolerance rule enforcement."""
        ruff_data = {"errors": [], "warnings": [], "fixes_applied": 0}

        try:
            # Run ruff check with auto-fix
            print("  🔧 Running ruff check --fix...")
            check_result = subprocess.run(
                ["ruff", "check", ".", "--fix", "--exit-non-zero-on-fix"], capture_output=True, text=True, timeout=60
            )

            if check_result.stdout:
                print(f"  📝 Ruff check output:\n{check_result.stdout}")

            # Run ruff format
            print("  🎨 Running ruff format...")
            format_result = subprocess.run(["ruff", "format", "."], capture_output=True, text=True, timeout=30)

            # Parse results for zero-tolerance rules
            zero_tolerance_violations = self._check_zero_tolerance_rules()

            if zero_tolerance_violations:
                ruff_data["errors"] = zero_tolerance_violations
                print(f"  ❌ Zero-tolerance violations found: {len(zero_tolerance_violations)}")
                for error in zero_tolerance_violations[:5]:  # Show first 5
                    print(f"    • {error}")
                if len(zero_tolerance_violations) > 5:
                    print(f"    ... and {len(zero_tolerance_violations) - 5} more")
                return False, ruff_data

            # Check if Ruff enforcement is enabled
            if self.config.enable_ruff_enforcement and check_result.returncode != 0:
                ruff_data["errors"].append(f"Ruff check failed with exit code {check_result.returncode}")
                return False, ruff_data

            print("  ✅ Ruff linting completed successfully")
            return True, ruff_data

        except subprocess.TimeoutExpired:
            ruff_data["errors"].append("Ruff execution timed out")
            return False, ruff_data
        except FileNotFoundError:
            ruff_data["errors"].append("Ruff not found - ensure it's installed")
            return False, ruff_data
        except Exception as e:
            ruff_data["errors"].append(f"Ruff execution failed: {e}")
            return False, ruff_data

    def _check_zero_tolerance_rules(self) -> List[str]:
        """Check for zero-tolerance rule violations using ruff check."""
        violations = []

        try:
            # Run ruff check for specific zero-tolerance rules
            zero_tolerance_rules = ["E501", "F401"]  # Line length, unused imports

            for rule in zero_tolerance_rules:
                result = subprocess.run(
                    ["ruff", "check", ".", f"--select={rule}", "--no-fix"], capture_output=True, text=True, timeout=30
                )

                if result.returncode != 0 and result.stdout:
                    # Parse violations from output
                    for line in result.stdout.split("\n"):
                        if rule in line and line.strip():
                            violations.append(line.strip())

            return violations

        except Exception as e:
            return [f"Failed to check zero-tolerance rules: {e}"]

    def _run_coverage_analysis(self) -> Tuple[bool, Dict]:
        """Execute pytest with coverage analysis and threshold enforcement."""
        coverage_data = {"percentage": 0.0, "report": "", "missing_lines": {}}

        try:
            print("  🧪 Running pytest with coverage...")

            # Run pytest with coverage
            pytest_cmd = [
                "pytest",
                "--cov=.",
                f"--cov-fail-under={self.config.coverage_threshold}",
                "--cov-report=term-missing",
                "--cov-report=xml:coverage.xml",
                "--tb=short",
                "-q",
            ]

            result = subprocess.run(pytest_cmd, capture_output=True, text=True, timeout=90)

            coverage_data["report"] = result.stdout

            # Parse coverage percentage from output
            coverage_percentage = self._parse_coverage_percentage(result.stdout)
            coverage_data["percentage"] = coverage_percentage

            # Check if coverage meets threshold
            if coverage_percentage >= self.config.coverage_threshold:
                print(f"  ✅ Coverage: {coverage_percentage}% (threshold: {self.config.coverage_threshold}%)")
                return True, coverage_data
            else:
                print(f"  ❌ Coverage: {coverage_percentage}% (below threshold: {self.config.coverage_threshold}%)")
                return False, coverage_data

        except subprocess.TimeoutExpired:
            coverage_data["report"] = "Coverage analysis timed out"
            return False, coverage_data
        except Exception as e:
            coverage_data["report"] = f"Coverage analysis failed: {e}"
            return False, coverage_data

    def _parse_coverage_percentage(self, coverage_output: str) -> float:
        """Parse coverage percentage from pytest-cov output."""
        try:
            # Look for "TOTAL" line with coverage percentage
            for line in coverage_output.split("\n"):
                if "TOTAL" in line and "%" in line:
                    # Extract percentage (format: "TOTAL    1234   123    89%")
                    parts = line.split()
                    for part in parts:
                        if part.endswith("%"):
                            return float(part.rstrip("%"))

            # Fallback: look for coverage XML file
            coverage_xml = Path("coverage.xml")
            if coverage_xml.exists():
                import xml.etree.ElementTree as ET

                tree = ET.parse(coverage_xml)
                root = tree.getroot()
                coverage_elem = root.find(".//coverage")
                if coverage_elem is not None:
                    line_rate = float(coverage_elem.get("line-rate", 0))
                    return round(line_rate * 100, 2)

            return 0.0

        except Exception as e:
            print(f"  ⚠️  Failed to parse coverage percentage: {e}")
            return 0.0

    def _write_evidence_to_redis(self, results: QualityResults) -> Dict[str, str]:
        """Write evidence keys to Redis for PRP promotion system."""
        evidence_keys = {}

        if not self.redis_client or not self.config.prp_id:
            print("  ⚠️  Skipping Redis evidence (no Redis client or PRP ID)")
            return evidence_keys

        try:
            prp_id = self.config.prp_id

            # Write lint_clean flag
            lint_key = f"prp:{prp_id}:lint_clean"
            lint_value = "true" if results.ruff_clean else "false"
            self.redis_client.set(lint_key, lint_value, ex=86400)  # 24h TTL
            evidence_keys["lint_clean"] = lint_key

            # Write coverage percentage
            coverage_key = f"prp:{prp_id}:coverage_pct"
            coverage_value = str(results.coverage_percentage)
            self.redis_client.set(coverage_key, coverage_value, ex=86400)  # 24h TTL
            evidence_keys["coverage_pct"] = coverage_key

            # Write quality report summary
            report_key = f"prp:{prp_id}:quality_report"
            report_data = {
                "timestamp": time.time(),
                "execution_time": results.execution_time_seconds,
                "ruff_clean": results.ruff_clean,
                "coverage_percentage": results.coverage_percentage,
                "success": results.success,
                "errors": results.ruff_errors[:10],  # Limit error count
            }
            self.redis_client.set(report_key, json.dumps(report_data), ex=86400)
            evidence_keys["quality_report"] = report_key

            print(f"  ✅ Evidence written to Redis:")
            print(f"    • {lint_key} = {lint_value}")
            print(f"    • {coverage_key} = {coverage_value}")
            print(f"    • {report_key} = <report_data>")

        except Exception as e:
            print(f"  ❌ Failed to write evidence to Redis: {e}")

        return evidence_keys

    def _validate_promotion_criteria(self, results: QualityResults) -> bool:
        """Validate if quality gate meets PRP promotion criteria."""
        print("🔍 Validating promotion criteria...")

        criteria = [
            ("Ruff linting clean", results.ruff_clean),
            ("Coverage threshold met", results.coverage_passed),
            ("Execution within time limit", results.execution_time_seconds <= self.config.max_execution_seconds),
        ]

        all_passed = True
        for criterion, passed in criteria:
            status = "✅" if passed else "❌"
            print(f"  {status} {criterion}")
            if not passed:
                all_passed = False

        return all_passed

    def _validate_prp_promotion_readiness(self, results: QualityResults) -> bool:
        """Validate PRP promotion readiness using PRP-1059 Lua script."""
        if not self.redis_client or not self.config.prp_id:
            print("  ⚠️  Skipping PRP promotion validation (no Redis client or PRP ID)")
            return False

        try:
            # Load promote.lua script
            script_path = Path("redis_scripts/promote.lua")
            if not script_path.exists():
                print(f"  ❌ Promote script not found at {script_path}")
                return False

            script_content = script_path.read_text()

            # Register the script with Redis
            script_sha = self.redis_client.script_load(script_content)

            # Define evidence keys for PRP-1061
            evidence_key = f"prp:{self.config.prp_id}"
            required_fields = ["lint_clean", "coverage_pct"]  # PRP-1061 evidence requirements

            # Call the Lua script to validate evidence
            result = self.redis_client.evalsha(
                script_sha,
                1,  # Number of KEYS
                evidence_key,  # KEYS[1]
                json.dumps(required_fields),  # ARGV[1]
                "strict",  # ARGV[2] - validation mode
            )

            is_valid = result[0] == 1
            missing_fields_json = result[1]

            if is_valid:
                print("  ✅ PRP promotion evidence validation passed")
                return True
            else:
                missing_fields = json.loads(missing_fields_json) if missing_fields_json != "{}" else []
                print(f"  ❌ PRP promotion evidence validation failed")
                print(f"    Missing fields: {missing_fields}")
                return False

        except Exception as e:
            print(f"  ❌ PRP promotion validation error: {e}")
            return False

    def _generate_coverage_badge(self, coverage_percentage: float):
        """Generate coverage badge using shields.io format."""
        try:
            # Create docs/badges directory if it doesn't exist
            badges_dir = Path("docs/badges")
            badges_dir.mkdir(parents=True, exist_ok=True)

            # Determine badge color based on coverage
            if coverage_percentage >= 90:
                color = "brightgreen"
            elif coverage_percentage >= 80:
                color = "green"
            elif coverage_percentage >= 70:
                color = "yellow"
            elif coverage_percentage >= 60:
                color = "orange"
            else:
                color = "red"

            # Generate simple SVG badge content
            badge_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="104" height="20">
<linearGradient id="b" x2="0" y2="100%">
<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
<stop offset="1" stop-opacity=".1"/>
</linearGradient>
<clipPath id="a">
<rect width="104" height="20" rx="3" fill="#fff"/>
</clipPath>
<g clip-path="url(#a)">
<path fill="#555" d="M0 0h63v20H0z"/>
<path fill="{color}" d="M63 0h41v20H63z"/>
<path fill="url(#b)" d="M0 0h104v20H0z"/>
</g>
<g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="110">
<text x="325" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="530">coverage</text>
<text x="325" y="140" transform="scale(.1)" textLength="530">coverage</text>
<text x="825" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="310">{coverage_percentage:.0f}%</text>
<text x="825" y="140" transform="scale(.1)" textLength="310">{coverage_percentage:.0f}%</text>
</g>
</svg>"""

            # Write badge to file
            badge_path = badges_dir / "coverage.svg"
            badge_path.write_text(badge_svg)
            print(f"  ✅ Coverage badge generated: {badge_path}")

        except Exception as e:
            print(f"  ⚠️  Failed to generate coverage badge: {e}")

    def _print_final_report(self, results: QualityResults):
        """Print final quality gate report."""
        print()
        print("=" * 60)
        print("🏁 QUALITY GATE FINAL REPORT")
        print("=" * 60)

        status_emoji = "✅" if results.success else "❌"
        print(f"{status_emoji} Overall Status: {'PASSED' if results.success else 'FAILED'}")
        print(f"⏱️  Execution Time: {results.execution_time_seconds:.1f}s")
        print()

        # Ruff Results
        print("🔍 RUFF LINTING:")
        ruff_status = "✅ CLEAN" if results.ruff_clean else "❌ VIOLATIONS"
        print(f"  Status: {ruff_status}")
        if results.ruff_errors:
            print(f"  Errors: {len(results.ruff_errors)}")
            for error in results.ruff_errors[:3]:  # Show first 3
                print(f"    • {error}")
        if results.ruff_fixes_applied > 0:
            print(f"  Fixes Applied: {results.ruff_fixes_applied}")

        print()

        # Coverage Results
        print("📊 COVERAGE ANALYSIS:")
        coverage_status = "✅ PASSED" if results.coverage_passed else "❌ FAILED"
        print(f"  Status: {coverage_status}")
        print(f"  Coverage: {results.coverage_percentage:.1f}% (threshold: {self.config.coverage_threshold}%)")

        print()

        # Evidence Keys
        if results.evidence_keys:
            print("💾 EVIDENCE COLLECTED:")
            for key_name, redis_key in results.evidence_keys.items():
                print(f"  {key_name}: {redis_key}")

        # PRP Promotion Status
        if hasattr(results, "promotion_ready"):
            print()
            print("🚀 PRP PROMOTION STATUS:")
            promotion_status = "✅ READY" if results.promotion_ready else "❌ NOT READY"
            print(f"  Status: {promotion_status}")
            if results.promotion_ready:
                print(f"  Integration: PRP-1059 Lua script validation passed")
                print(f"  Evidence: lint_clean=true, coverage_pct>={self.config.coverage_threshold}")

        print("=" * 60)


def load_config() -> QualityGateConfig:
    """Load configuration from environment variables."""
    return QualityGateConfig(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
        prp_id=os.getenv("PRP_ID"),
        coverage_threshold=int(os.getenv("COVERAGE_FAIL_UNDER", "80")),
        enable_ruff_enforcement=os.getenv("ENABLE_RUFF_ENFORCEMENT", "false").lower() == "true",
        parallel_legacy_tools=os.getenv("PARALLEL_LEGACY_TOOLS", "true").lower() == "true",
        quality_gate_strict_mode=os.getenv("QUALITY_GATE_STRICT_MODE", "false").lower() == "true",
        max_execution_seconds=int(os.getenv("QUALITY_GATE_TIMEOUT", "120")),
    )


def main():
    """Main entry point for quality gate execution."""
    parser = argparse.ArgumentParser(description="PRP-1061 Quality Gate")
    parser.add_argument("--prp-id", help="PRP ID for evidence tracking")
    parser.add_argument("--coverage-threshold", type=int, default=80, help="Coverage threshold percentage")
    parser.add_argument("--strict", action="store_true", help="Enable strict mode")
    parser.add_argument("--redis-url", help="Redis connection URL")
    parser.add_argument("--timeout", type=int, default=120, help="Maximum execution time in seconds")

    args = parser.parse_args()

    # Load base config and override with CLI args
    config = load_config()
    if args.prp_id:
        config.prp_id = args.prp_id
    if args.coverage_threshold:
        config.coverage_threshold = args.coverage_threshold
    if args.strict:
        config.quality_gate_strict_mode = True
        config.enable_ruff_enforcement = True
    if args.redis_url:
        config.redis_url = args.redis_url
    if args.timeout:
        config.max_execution_seconds = args.timeout

    # Execute quality gate
    quality_gate = QualityGate(config)
    results = quality_gate.run()

    # Exit with appropriate code
    sys.exit(0 if results.success else 1)


if __name__ == "__main__":
    main()
