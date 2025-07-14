#!/usr/bin/env python3
"""
Six-Gate PRP Validation Script
"""
import json
import re
import sys
from pathlib import Path


def gate1_structure_validation(content):
    """Gate 1: Structure Validation"""
    print("=== GATE 1: Structure Validation ===")

    required_sections = [
        "## Task ID:",
        "## Wave:",
        "## Business Logic",
        "## Overview",
        "## Dependencies",
        "## Outcome-Focused Acceptance Criteria",
        "## Integration Points",
        "## Tests to Pass",
        "## Implementation Guide",
        "## Validation Commands",
        "## Rollback Strategy",
        "## Success Criteria",
        "## Critical Context",
    ]

    missing_sections = []
    for section in required_sections:
        if section not in content:
            missing_sections.append(section)

    if missing_sections:
        print("FAILED: Missing required sections:")
        for section in missing_sections:
            print(f"  - {section}")
        return False

    print("PASSED: All required sections present")

    # Check formatting
    lines = content.split("\n")
    issues = []

    # Check for proper markdown headers
    header_pattern = re.compile(r"^#{1,6} .+")
    for i, line in enumerate(lines):
        if line.startswith("#") and not header_pattern.match(line):
            issues.append(f"Line {i+1}: Invalid header format: {line}")

    # Check for code blocks
    code_block_count = content.count("```")
    if code_block_count % 2 != 0:
        issues.append("Unclosed code block detected")

    if issues:
        print("\nFormatting issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False

    print("Formatting validation passed")
    return True


def gate2_dependency_check(content, task_id):
    """Gate 2: Dependency Check"""
    print("\n=== GATE 2: Dependency Check ===")

    # Extract dependencies from PRP
    dep_match = re.search(r"## Dependencies\n- (P0-\d+)", content)
    if not dep_match:
        print("No dependencies found in PRP")
        return True

    dependency = dep_match.group(1)
    print(f"Found dependency: {dependency}")

    # Check progress file
    progress_file = Path(".claude/prp_progress.json")
    if not progress_file.exists():
        print("ERROR: Progress file not found")
        return False

    with open(progress_file, "r") as f:
        progress = json.load(f)

    if dependency in progress and progress[dependency]["status"] == "completed":
        print(f"PASSED: Dependency {dependency} is completed")
        return True
    else:
        print(f"FAILED: Dependency {dependency} is not completed")
        return False


def gate3_acceptance_criteria(content):
    """Gate 3: Acceptance Criteria Validation"""
    print("\n=== GATE 3: Acceptance Criteria Validation ===")

    # Extract acceptance criteria section
    criteria_match = re.search(r"## Outcome-Focused Acceptance Criteria\n(.*?)(?=\n##)", content, re.DOTALL)
    if not criteria_match:
        print("FAILED: Could not extract acceptance criteria")
        return False

    criteria_text = criteria_match.group(1)

    # Check for specific criteria
    criteria_checks = {
        "test collection": "Collect phase shows correct counts" in criteria_text,
        "slow tests": "`pytest -m slow` runs 0 tests in CI" in criteria_text,
        "import errors": "import errors in ignored files eliminated" in criteria_text,
        "xfail marking": "Phase 0.5 tests auto-marked as xfail" in criteria_text,
        "collection time": "Test collection time <5 seconds" in criteria_text,
        "coverage requirement": "test coverage ≥ 80%" in criteria_text,
    }

    failed = []
    for check, result in criteria_checks.items():
        if not result:
            failed.append(check)
        else:
            print(f"✓ {check}")

    if failed:
        print("\nFAILED: Missing acceptance criteria:")
        for f in failed:
            print(f"  - {f}")
        return False

    print("\nPASSED: All acceptance criteria defined")
    return True


def gate4_test_coverage(content):
    """Gate 4: Test Coverage Requirements"""
    print("\n=== GATE 4: Test Coverage Requirements ===")

    # Extract Tests to Pass section
    tests_match = re.search(r"## Tests to Pass\n(.*?)(?=\n##)", content, re.DOTALL)
    if not tests_match:
        print("FAILED: No 'Tests to Pass' section found")
        return False

    tests_text = tests_match.group(1)

    # Check for specific test requirements
    test_checks = {
        "pytest collect": "`pytest --collect-only`" in tests_text,
        "CI time": "CI runs in <10 minutes" in tests_text,
        "slow marker": '`pytest -m "slow"' in tests_text,
        "coverage maintained": "coverage ≥ 80%" in content,
    }

    failed = []
    for check, result in test_checks.items():
        if not result:
            failed.append(check)
        else:
            print(f"✓ {check}")

    if failed:
        print("\nFAILED: Missing test requirements:")
        for f in failed:
            print(f"  - {f}")
        return False

    print("\nPASSED: All test requirements specified")
    return True


def gate5_implementation_clarity(content):
    """Gate 5: Implementation Clarity"""
    print("\n=== GATE 5: Implementation Clarity ===")

    # Extract implementation guide
    impl_match = re.search(r"## Implementation Guide\n(.*?)(?=\n##)", content, re.DOTALL)
    if not impl_match:
        print("FAILED: No implementation guide found")
        return False

    impl_text = impl_match.group(1)

    # Check for required implementation steps
    impl_checks = {
        "dependency verification": "Verify Dependencies" in impl_text or "Check .claude/prp_progress.json" in impl_text,
        "environment setup": "Set Up Environment" in impl_text or "Python version" in impl_text,
        "implementation steps": "Implementation" in impl_text and ("conftest.py" in content or "pytest.ini" in content),
        "testing steps": "Testing" in impl_text or "Run all tests" in impl_text,
        "validation steps": "Validation" in impl_text or "validation command" in impl_text,
    }

    failed = []
    for check, result in impl_checks.items():
        if not result:
            failed.append(check)
        else:
            print(f"✓ {check}")

    # Check integration points
    if "## Integration Points" in content:
        int_match = re.search(r"## Integration Points\n(.*?)(?=\n##|\n\*\*)", content, re.DOTALL)
        if int_match and ("conftest.py" in int_match.group(1) or "pytest.ini" in int_match.group(1)):
            print("✓ Integration points specified")
        else:
            failed.append("integration points not properly specified")

    if failed:
        print("\nFAILED: Missing implementation details:")
        for f in failed:
            print(f"  - {f}")
        return False

    print("\nPASSED: Implementation guide is clear")
    return True


def gate6_ci_integration(content):
    """Gate 6: CI/CD Integration"""
    print("\n=== GATE 6: CI/CD Integration ===")

    ci_checks = {
        "validation commands": "## Validation Commands" in content,
        "rollback strategy": "## Rollback Strategy" in content,
        "success criteria": "## Success Criteria" in content and "CI green after push" in content,
        "test infrastructure": "conftest.py" in content or "pytest.ini" in content,
        "ci workflow": "CI workflow files" in content or "CI runs in <10 minutes" in content,
    }

    failed = []
    for check, result in ci_checks.items():
        if not result:
            failed.append(check)
        else:
            print(f"✓ {check}")

    # Check for validation script reference
    if "validate_wave_a.sh" in content:
        print("✓ Wave A validation script referenced")
    else:
        failed.append("No wave validation script reference")

    if failed:
        print("\nFAILED: Missing CI/CD requirements:")
        for f in failed:
            print(f"  - {f}")
        return False

    print("\nPASSED: CI/CD integration properly defined")
    return True


def main():
    task_id = "P0-008"
    prp_file = f".claude/PRPs/PRP-{task_id}-test-infrastructure-cleanup.md"

    if not Path(prp_file).exists():
        print(f"ERROR: PRP file not found: {prp_file}")
        return 1

    with open(prp_file, "r") as f:
        content = f.read()

    print(f"Validating PRP for task {task_id}")
    print("=" * 50)

    # Run all gates
    gates = [
        ("Gate 1: Structure", gate1_structure_validation(content)),
        ("Gate 2: Dependencies", gate2_dependency_check(content, task_id)),
        ("Gate 3: Acceptance Criteria", gate3_acceptance_criteria(content)),
        ("Gate 4: Test Coverage", gate4_test_coverage(content)),
        ("Gate 5: Implementation Clarity", gate5_implementation_clarity(content)),
        ("Gate 6: CI/CD Integration", gate6_ci_integration(content)),
    ]

    print("\n" + "=" * 50)
    print("VALIDATION SUMMARY")
    print("=" * 50)

    all_passed = True
    for gate_name, passed in gates:
        status = "PASSED" if passed else "FAILED"
        print(f"{gate_name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("✓ ALL GATES PASSED - PRP is valid")
        return 0
    else:
        print("✗ VALIDATION FAILED - PRP needs revision")
        return 1


if __name__ == "__main__":
    sys.exit(main())
