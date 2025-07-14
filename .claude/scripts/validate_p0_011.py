#!/usr/bin/env python3
"""Six-Gate Validation for PRP-P0-011 - Deploy to VPS."""

import json
import re
import sys
from pathlib import Path


class P0011Validator:
    """Validator for P0-011 PRP."""

    def __init__(self, prp_path: str):
        """Initialize validator with PRP path."""
        self.prp_path = Path(prp_path)
        if not self.prp_path.exists():
            raise FileNotFoundError(f"PRP not found: {prp_path}")

        with open(self.prp_path, "r") as f:
            self.content = f.read()

        # Extract basic info
        header_match = re.search(r"# PRP: (.+)", self.content)
        if header_match:
            self.title = header_match.group(1).strip()
        else:
            raise ValueError("Invalid PRP format - missing header")

    def validate_gate_1_schema(self) -> tuple[bool, str]:
        """Gate 1: Schema Validation."""
        print("\n🔍 Gate 1: Schema Validation")

        issues = []

        # Check required sections
        required_sections = [
            "## Task ID: P0-011",
            "## Wave: A",
            "## Business Logic (Why This Matters)",
            "## Overview",
            "## Dependencies",
            "## Outcome-Focused Acceptance Criteria",
            "## Integration Points",
            "## Tests to Pass",
            "## Implementation Guide",
            "## Validation Commands",
            "## Rollback Strategy",
            "## Success Criteria",
        ]

        for section in required_sections:
            if section not in self.content:
                issues.append(f"Missing required section: {section}")

        # Check for acceptance criteria checkboxes
        if "- [ ]" not in self.content:
            issues.append("No acceptance criteria checkboxes found")

        # Check for validation commands
        if "```bash" not in self.content:
            issues.append("No executable validation commands found")

        if issues:
            return False, f"Schema issues: {', '.join(issues)}"
        return True, "All required sections present"

    def validate_gate_2_dependencies(self) -> tuple[bool, str]:
        """Gate 2: Dependency Validation."""
        print("\n📋 Gate 2: Dependency Validation")

        # Check if P0-010 dependency is mentioned
        if "P0-010" not in self.content:
            return False, "Missing P0-010 dependency"

        # Check progress file for P0-010 status
        progress_path = Path(".claude/prp_progress.json")
        if not progress_path.exists():
            return False, "Progress file not found"

        try:
            with open(progress_path, "r") as f:
                progress = json.load(f)

            p0_010_status = progress.get("P0-010", {}).get("status", "unknown")
            if p0_010_status not in ["completed", "validated"]:
                return False, f"P0-010 dependency status: {p0_010_status} (need completed/validated)"
        except Exception:
            return False, "Could not read progress file"

        return True, "P0-010 dependency satisfied"

    def validate_gate_3_acceptance_criteria(self) -> tuple[bool, str]:
        """Gate 3: Acceptance Criteria Validation."""
        print("\n🔧 Gate 3: Acceptance Criteria Validation")

        # Check for deployment-specific criteria
        deployment_criteria = [
            "GHCR image pushed",
            "SSH key authentication",
            "Docker installed",
            "Container runs",
            "Nginx reverse proxy",
        ]

        found_criteria = []
        for criterion in deployment_criteria:
            if criterion.lower() in self.content.lower():
                found_criteria.append(criterion)

        if len(found_criteria) >= 4:
            return True, f"Found {len(found_criteria)}/5 deployment criteria: {', '.join(found_criteria)}"
        return False, f"Only found {len(found_criteria)}/5 deployment criteria: {', '.join(found_criteria)}"

    def validate_gate_4_test_coverage(self) -> tuple[bool, str]:
        """Gate 4: Test Coverage Requirements."""
        print("\n📚 Gate 4: Test Coverage Requirements")

        # Check for test requirements
        test_requirements = [
            "Deployment workflow runs without errors",
            "curl https://vps-ip/health",
            "test_health.py",
            "coverage ≥ 80%",
        ]

        found_tests = []
        for test in test_requirements:
            if test.lower() in self.content.lower():
                found_tests.append(test)

        if len(found_tests) >= 3:
            return True, f"Found {len(found_tests)}/4 test requirements: {', '.join(found_tests)}"
        return False, f"Only found {len(found_tests)}/4 test requirements: {', '.join(found_tests)}"

    def validate_gate_5_implementation_clarity(self) -> tuple[bool, str]:
        """Gate 5: Implementation Clarity."""
        print("\n🎭 Gate 5: Implementation Clarity")

        # Check for clear implementation steps
        implementation_indicators = [
            "Step 1: Verify Dependencies",
            "Step 2: Set Up Environment",
            "Step 3: Implementation",
            "Step 4: Testing",
            "Step 5: Validation",
            "GitHub Actions",
            "VPS deployment",
            "Docker container",
        ]

        found_indicators = []
        for indicator in implementation_indicators:
            if indicator.lower() in self.content.lower():
                found_indicators.append(indicator)

        if len(found_indicators) >= 6:
            return True, f"Clear implementation guide with {len(found_indicators)}/8 indicators"
        return False, f"Unclear implementation - only {len(found_indicators)}/8 indicators found"

    def validate_gate_6_ci_integration(self) -> tuple[bool, str]:
        """Gate 6: CI/CD Integration."""
        print("\n⚖️ Gate 6: CI/CD Integration")

        # Check for CI/CD integration elements
        ci_elements = [
            "deploy.yml",
            "GitHub Actions",
            "GHCR",
            "SSH",
            "Docker",
            "validate_wave_a.sh",
            "rollback",
            "health endpoint",
        ]

        found_elements = []
        for element in ci_elements:
            if element.lower() in self.content.lower():
                found_elements.append(element)

        if len(found_elements) >= 6:
            return True, f"Strong CI/CD integration with {len(found_elements)}/8 elements"
        return False, f"Weak CI/CD integration - only {len(found_elements)}/8 elements found"

    def run_validation(self) -> bool:
        """Run all six gates."""
        print(f"\n{'='*60}")
        print(f"Six-Gate Validation for: P0-011 - {self.title}")
        print(f"{'='*60}")

        gates = [
            ("Schema", self.validate_gate_1_schema),
            ("Dependencies", self.validate_gate_2_dependencies),
            ("Acceptance Criteria", self.validate_gate_3_acceptance_criteria),
            ("Test Coverage", self.validate_gate_4_test_coverage),
            ("Implementation Clarity", self.validate_gate_5_implementation_clarity),
            ("CI/CD Integration", self.validate_gate_6_ci_integration),
        ]

        all_passed = True
        results = []

        for gate_name, gate_func in gates:
            passed, message = gate_func()
            results.append((gate_name, passed, message))

            if passed:
                print(f"  ✅ Gate {gates.index((gate_name, gate_func)) + 1} ({gate_name}) PASSED")
                print(f"     {message}")
            else:
                print(f"  ❌ Gate {gates.index((gate_name, gate_func)) + 1} ({gate_name}) FAILED")
                print(f"     {message}")
                all_passed = False

        print(f"\n{'='*60}")
        if all_passed:
            print("🎉 All six validation gates PASSED!")
            print("\nValidation Summary:")
            for gate_name, passed, message in results:
                print(f"  • {gate_name}: ✅ {message}")
        else:
            print("❌ Validation FAILED!")
            print("\nValidation Summary:")
            for gate_name, passed, message in results:
                status = "✅" if passed else "❌"
                print(f"  • {gate_name}: {status} {message}")
        print(f"{'='*60}\n")

        return all_passed


def main():
    """Run the P0-011 validator."""
    prp_path = ".claude/PRPs/PRP-P0-011-deploy-to-vps.md"

    try:
        validator = P0011Validator(prp_path)
        success = validator.run_validation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
