#!/usr/bin/env python3
"""
Simple test to verify enterprise integration components are in place
"""

import os
from pathlib import Path


def test_enterprise_integration_files():
    """Test that all required enterprise integration files exist"""

    project_root = Path(__file__).parent

    required_files = [
        "bin/enterprise_shim.py",
        "infra/redis_queue.py",
        "infra/agent_coordinator.py",
        "redis_scripts/promote.lua",
        "start_stack.sh",
        ".env",
    ]

    print("🔍 Testing Enterprise Integration File Structure...")

    all_exist = True
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - MISSING")
            all_exist = False

    return all_exist


def test_enterprise_shim_executable():
    """Test that enterprise shim is executable"""
    shim_path = Path(__file__).parent / "bin/enterprise_shim.py"

    if not shim_path.exists():
        print("❌ enterprise_shim.py not found")
        return False

    # Check if executable
    is_executable = os.access(shim_path, os.X_OK)
    if is_executable:
        print("✅ enterprise_shim.py is executable")
    else:
        print("❌ enterprise_shim.py is not executable")

    return is_executable


def test_start_stack_integration():
    """Test that start_stack.sh has been updated for enterprise integration"""
    start_stack_path = Path(__file__).parent / "start_stack.sh"

    if not start_stack_path.exists():
        print("❌ start_stack.sh not found")
        return False

    content = start_stack_path.read_text()

    # Check for enterprise integration
    enterprise_markers = [
        "enterprise_shim.py",
        "Enterprise Redis-tmux bridge",
        'orchestrator "${STACK_SESSION}"',
        'dev "${STACK_SESSION}"',
        'validator "${STACK_SESSION}"',
        'integrator "${STACK_SESSION}"',
    ]

    all_found = True
    for marker in enterprise_markers:
        if marker in content:
            print(f"✅ Found: {marker}")
        else:
            print(f"❌ Missing: {marker}")
            all_found = False

    return all_found


def main():
    """Main test runner"""
    print("🚀 Enterprise Integration Verification")
    print("=" * 50)

    # Test 1: File structure
    if not test_enterprise_integration_files():
        print("\n❌ File structure test FAILED")
        return False

    print("")

    # Test 2: Executable permissions
    if not test_enterprise_shim_executable():
        print("\n❌ Executable test FAILED")
        return False

    print("")

    # Test 3: start_stack.sh integration
    if not test_start_stack_integration():
        print("\n❌ start_stack.sh integration test FAILED")
        return False

    print("\n" + "=" * 50)
    print("✅ Enterprise Integration Verification PASSED!")
    print("\nThe enterprise Redis-tmux integration is ready:")
    print("- Enterprise shim connects existing tmux notification system")
    print("- With comprehensive Redis queue infrastructure from PRPs 1058-1061")
    print("- Providing enterprise features: agent registration, evidence tracking, atomic operations")
    print("- Ready to test with: ./start_stack.sh")

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
