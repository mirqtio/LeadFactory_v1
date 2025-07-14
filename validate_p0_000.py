#!/usr/bin/env python3
"""
Validation script for P0-000 Prerequisites Check.

This script validates the P0-000 implementation and ensures all requirements
are met according to the PRP specification.
"""

import json
import sys
from pathlib import Path

from core.prerequisites import validate_all_prerequisites, print_results


def main():
    """Main validation function."""
    print("🚀 P0-000 Prerequisites Check Validation")
    print("=" * 50)
    
    # Run prerequisites validation
    result = validate_all_prerequisites()
    
    # Print results
    print_results(result)
    
    # Validate specific PRP requirements
    print("\n📋 PRP P0-000 Acceptance Criteria Validation:")
    print("=" * 50)
    
    # Check that basic requirements are met
    required_checks = [
        "Python Version",
        "Docker Version", 
        "Docker Compose Version",
        "Database Connectivity",
        "Environment Variables",
        "Python Dependencies",
        "Pytest Collection",
        "CI Toolchain"
    ]
    
    check_names = [check.name for check in result.checks]
    missing_checks = [req for req in required_checks if req not in check_names]
    
    if missing_checks:
        print(f"❌ Missing required checks: {', '.join(missing_checks)}")
        return False
    
    print("✅ All required checks present")
    
    # Check pytest collection specifically
    pytest_check = next((c for c in result.checks if c.name == "Pytest Collection"), None)
    if pytest_check and pytest_check.passed:
        print("✅ Pytest collection succeeds without errors")
    else:
        print("❌ Pytest collection failed")
        return False
    
    # Check that we have comprehensive test coverage
    if result.total_checks >= 8:
        print(f"✅ Comprehensive validation ({result.total_checks} checks)")
    else:
        print(f"❌ Insufficient validation coverage ({result.total_checks} checks)")
        return False
    
    # Check environment info is populated
    if result.environment_info:
        print("✅ Environment information populated")
    else:
        print("❌ Environment information missing")
        return False
    
    # Overall validation
    if result.passed:
        print("\n🎉 P0-000 Prerequisites Check - VALIDATION PASSED")
        print("All acceptance criteria met!")
        return True
    else:
        print(f"\n❌ P0-000 Prerequisites Check - VALIDATION FAILED")
        print(f"Failed checks: {result.failed_checks}")
        print(f"Warning checks: {result.warning_checks}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)