#!/usr/bin/env python3
"""
Run basic tests to verify production readiness without Prefect dependencies
"""
import subprocess
import sys
import time
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print('='*60)
    
    start_time = time.time()
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    duration = time.time() - start_time
    
    if result.returncode == 0:
        print(f"✅ PASSED ({duration:.2f}s)")
        if result.stdout:
            print(result.stdout)
        return True
    else:
        print(f"❌ FAILED ({duration:.2f}s)")
        if result.stderr:
            print("STDERR:", result.stderr)
        if result.stdout:
            print("STDOUT:", result.stdout)
        return False

def main():
    """Run basic test suite"""
    print("\n" + "="*60)
    print("LEADFACTORY BASIC TEST SUITE")
    print("="*60)
    
    tests = [
        # Core functionality
        ("docker run --rm leadfactory-test pytest -xvs tests/unit/test_core.py -k 'not integration'",
         "Core utilities and configuration"),
        
        # Database models
        ("docker run --rm leadfactory-test pytest -xvs tests/unit/test_unit_models.py",
         "Database models"),
        
        # Gateway (D0)
        ("docker run --rm leadfactory-test pytest -xvs tests/unit/d0_gateway/test_facade.py tests/unit/d0_gateway/test_factory.py",
         "Gateway facade and factory"),
        
        # Scoring (D5)
        ("docker run --rm leadfactory-test pytest -xvs tests/unit/d5_scoring/test_engine.py",
         "Scoring engine"),
        
        # Delivery (D9)
        ("docker run --rm leadfactory-test pytest -xvs tests/unit/d9_delivery/test_delivery_manager.py",
         "Email delivery"),
        
        # Phase 0.5 tests
        ("docker run --rm leadfactory-test pytest -xvs tests/unit/test_phase_05_simple.py",
         "Phase 0.5 implementation"),
        
        # Integration test (simple)
        ("docker run --rm leadfactory-test pytest -xvs tests/integration/test_stub_server.py",
         "Stub server integration"),
    ]
    
    results = []
    total_tests = len(tests)
    passed = 0
    
    for cmd, description in tests:
        success = run_command(cmd, description)
        results.append((description, success))
        if success:
            passed += 1
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for description, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} - {description}")
    
    print(f"\nTotal: {passed}/{total_tests} passed")
    
    if passed == total_tests:
        print("\n🎉 All basic tests PASSED! System is ready for deployment.")
        return 0
    else:
        print(f"\n❌ {total_tests - passed} tests FAILED. Please fix before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())