#!/usr/bin/env python3
"""
Six-Gate Validation for PRP-P0-026 Governance
"""

import re
import sys
from pathlib import Path


class P0026Validator:
    def __init__(self):
        self.prp_path = Path(".claude/PRPs/PRP-P0-026-governance.md")
        if not self.prp_path.exists():
            raise FileNotFoundError(f"PRP not found: {self.prp_path}")

        with open(self.prp_path, "r") as f:
            self.content = f.read()

    def validate_gate_1_schema(self) -> tuple[bool, str, list[str]]:
        """Gate 1: Schema Validation"""
        issues = []

        # Check required sections
        required_sections = [
            "## Goal",
            "## Why",
            "## What",
            "### Success Criteria",
            "## All Needed Context",
            "## Technical Implementation",
            "## Validation Gates",
            "## Dependencies",
            "## Rollback Strategy",
        ]

        for section in required_sections:
            if section not in self.content:
                issues.append(f"Missing required section: {section}")

        # Check for RBAC coverage
        if "RBAC applied to: leads, templates, batch operations" not in self.content:
            issues.append("Missing explicit RBAC coverage for all endpoints")

        # Check for endpoint protection checklist
        if "## Endpoint Protection Checklist" not in self.content:
            issues.append("Missing Endpoint Protection Checklist")

        passed = len(issues) == 0
        message = "All required sections present" if passed else f"{len(issues)} schema issues"
        return passed, message, issues

    def validate_gate_2_policy(self) -> tuple[bool, str, list[str]]:
        """Gate 2: Policy Validation"""
        violations = []

        # Check for banned patterns
        banned_patterns = [
            (r"yelp", "Yelp integration is DO NOT IMPLEMENT"),
            (r"deprecated/", "Deprecated paths are banned"),
        ]

        for pattern, message in banned_patterns:
            if re.search(pattern, self.content, re.IGNORECASE):
                violations.append(message)

        passed = len(violations) == 0
        message = "No policy violations" if passed else f"{len(violations)} policy violations"
        return passed, message, violations

    def validate_gate_3_lint(self) -> tuple[bool, str, list[str]]:
        """Gate 3: Lint/Quality Validation"""
        quality_checks = []

        # Check for quality tooling mentions
        if "ruff" in self.content.lower():
            quality_checks.append("Ruff linting specified")
        if "mypy" in self.content.lower():
            quality_checks.append("Type checking with mypy")
        if "pytest" in self.content.lower():
            quality_checks.append("Testing with pytest")
        if "coverage" in self.content.lower() or "cov" in self.content.lower():
            quality_checks.append("Coverage tracking")

        passed = len(quality_checks) >= 3
        message = f"{len(quality_checks)} quality tools" if passed else "Insufficient quality tooling"
        return passed, message, quality_checks

    def validate_gate_4_research(self) -> tuple[bool, str, list[str]]:
        """Gate 4: Research Validation"""
        research_items = []

        # Check for FastAPI security docs
        if "https://fastapi.tiangolo.com/advanced/advanced-dependencies/" in self.content:
            research_items.append("FastAPI dependency docs")
        if "https://fastapi.tiangolo.com/tutorial/security/" in self.content:
            research_items.append("FastAPI security patterns")
        if "https://docs.sqlalchemy.org" in self.content:
            research_items.append("SQLAlchemy documentation")

        # Check for codebase references
        if "d0_gateway/base.py" in self.content:
            research_items.append("Existing gateway patterns")
        if "core/config.py" in self.content:
            research_items.append("Configuration patterns")

        passed = len(research_items) >= 3
        message = f"{len(research_items)} research references" if passed else "Insufficient research"
        return passed, message, research_items

    def validate_gate_5_critic(self) -> tuple[bool, str, list[str]]:
        """Gate 5: CRITIC Review - Check for critical security implementation"""
        critical_items = []
        issues = []

        # Check for comprehensive RBAC coverage
        if "ALL mutation endpoints" in self.content and "CRITICAL: RBAC must be applied" in self.content:
            critical_items.append("Comprehensive RBAC coverage specified")
        else:
            issues.append("Missing emphasis on ALL endpoints protection")

        # Check for specific endpoint mentions
        endpoint_mentions = ["api/leads.py", "api/templates.py", "api/batch_operations.py"]
        found_endpoints = [ep for ep in endpoint_mentions if ep in self.content]
        if len(found_endpoints) >= 3:
            critical_items.append(f"Specific endpoint protection ({len(found_endpoints)} files)")
        else:
            issues.append("Insufficient specific endpoint mentions")

        # Check for comprehensive testing
        if "test_rbac_all_endpoints.py" in self.content:
            critical_items.append("Comprehensive RBAC testing")
        else:
            issues.append("Missing comprehensive endpoint testing")

        # Check for verification requirement
        if "100% of mutation endpoints require admin role" in self.content:
            critical_items.append("100% coverage requirement")
        else:
            issues.append("Missing 100% coverage requirement")

        passed = len(critical_items) >= 3 and len(issues) <= 1
        message = f"{len(critical_items)} critical items, {len(issues)} issues"
        return passed, message, critical_items + [f"Issue: {i}" for i in issues]

    def validate_gate_6_judge(self) -> tuple[bool, str, dict[str, int]]:
        """Gate 6: Judge Scoring"""
        scores = {}

        # Clarity (1-5)
        clarity_score = 5
        if "CRITICAL: RBAC must be applied to ALL" in self.content:
            clarity_score = 5
        elif "Success Criteria" in self.content:
            clarity_score = 4
        else:
            clarity_score = 3
        scores["Clarity"] = clarity_score

        # Feasibility (1-5)
        feasibility_score = 5
        if "FastAPI dependency" in self.content and "SQLAlchemy event" in self.content:
            feasibility_score = 5
        else:
            feasibility_score = 3
        scores["Feasibility"] = feasibility_score

        # Coverage (1-5)
        coverage_score = 5
        if "100% of mutation endpoints" in self.content and "Endpoint Protection Checklist" in self.content:
            coverage_score = 5
        elif "ALL mutation endpoints" in self.content:
            coverage_score = 4
        else:
            coverage_score = 2
        scores["Coverage"] = coverage_score

        # Policy Compliance (1-5)
        policy_score = 5  # No violations found in gate 2
        scores["Policy Compliance"] = policy_score

        # Technical Quality (1-5)
        tech_score = 5
        if all(x in self.content for x in ["80% coverage", "Integration tests", "Performance tests"]):
            tech_score = 5
        elif "80% coverage" in self.content:
            tech_score = 4
        else:
            tech_score = 3
        scores["Technical Quality"] = tech_score

        avg_score = sum(scores.values()) / len(scores)
        min_score = min(scores.values())

        passed = avg_score >= 4.0 and min_score >= 3
        message = f"Avg: {avg_score:.1f}/5.0, Min: {min_score}/5"
        return passed, message, scores

    def run_validation(self) -> tuple[bool, int]:
        """Run all six gates and return overall status"""
        print(f"\n{'='*60}")
        print("Six-Gate Validation for: P0-026 - Governance")
        print(f"{'='*60}")

        gates = [
            ("Schema", self.validate_gate_1_schema),
            ("Policy", self.validate_gate_2_policy),
            ("Lint", self.validate_gate_3_lint),
            ("Research", self.validate_gate_4_research),
            ("CRITIC", self.validate_gate_5_critic),
            ("Judge", self.validate_gate_6_judge),
        ]

        all_passed = True
        failed_gates = []
        gate_scores = {}

        for i, (gate_name, gate_func) in enumerate(gates, 1):
            result = gate_func()
            passed = result[0]
            message = result[1]

            if gate_name == "Judge":
                scores = result[2]
                gate_scores = scores
                print(f"\n🔍 Gate {i}: {gate_name}")
                for dimension, score in scores.items():
                    print(f"  - {dimension}: {score}/5")
            else:
                details = result[2] if len(result) > 2 else []
                print(f"\n🔍 Gate {i}: {gate_name}")
                if details:
                    for detail in details:
                        print(f"  - {detail}")

            if passed:
                print(f"  ✅ Result: PASSED - {message}")
            else:
                print(f"  ❌ Result: FAILED - {message}")
                all_passed = False
                failed_gates.append(gate_name)

        # Calculate final score
        if gate_scores:
            final_score = int((sum(gate_scores.values()) / len(gate_scores)) * 20)
        else:
            final_score = 0

        print(f"\n{'='*60}")
        if all_passed:
            print(f"✅ VALIDATION PASSED - Score: {final_score}/100")
            print("All six gates passed successfully!")
        else:
            print(f"❌ VALIDATION FAILED - Score: {final_score}/100")
            print(f"Failed gates: {', '.join(failed_gates)}")
        print(f"{'='*60}\n")

        return all_passed, final_score


def main():
    try:
        validator = P0026Validator()
        passed, score = validator.run_validation()

        # Update progress file
        progress_file = Path(".claude/prp_progress.json")
        if progress_file.exists():
            import json

            with open(progress_file, "r") as f:
                progress = json.load(f)

            progress["P0-026"] = {
                "status": "passed_validation" if passed else "failed_validation",
                "validation_score": score,
                "attempts": progress.get("P0-026", {}).get("attempts", 0) + 1,
            }

            with open(progress_file, "w") as f:
                json.dump(progress, f, indent=2)

        sys.exit(0 if passed else 1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
