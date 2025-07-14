#!/usr/bin/env python3
"""
Fix test infrastructure issues identified during CI/CD testing
"""

import os
import subprocess
import sys


def run_command(cmd, description):
    """Run a command and report results"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Success")
        if result.stdout:
            print(result.stdout)
    else:
        print(f"❌ Failed with code {result.returncode}")
        if result.stderr:
            print("Error output:")
            print(result.stderr)
    
    return result.returncode == 0


def main():
    """Main test infrastructure fixes"""
    
    print("🚀 Starting test infrastructure fixes...")
    
    # 1. Set test environment variables
    os.environ["ENVIRONMENT"] = "test"
    os.environ["USE_STUBS"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///tmp/test.db"
    os.environ["SECRET_KEY"] = "test-secret-key"
    os.environ["CI"] = "true"
    
    # 2. Create necessary directories
    run_command("mkdir -p tmp coverage test-results", "Creating test directories")
    
    # 3. Check Python version
    run_command("python --version", "Checking Python version")
    
    # 4. Install test dependencies if needed
    run_command("pip install -r requirements.txt -r requirements-dev.txt", "Installing dependencies")
    
    # 5. Run basic import test
    test_imports = """
import os
os.environ['ENVIRONMENT'] = 'test'
os.environ['USE_STUBS'] = 'true'

# Test critical imports
try:
    from core.config import get_settings
    from database.base import Base
    from database.models import Business, Lead
    from stubs.server import app
    print('✅ All critical imports successful')
except Exception as e:
    print(f'❌ Import error: {e}')
    exit(1)
"""
    
    with open("test_imports.py", "w") as f:
        f.write(test_imports)
    
    run_command("python test_imports.py", "Testing critical imports")
    os.remove("test_imports.py")
    
    # 6. Run minimal test suite
    print("\n🧪 Running minimal test suite...")
    
    tests = [
        ("Smoke tests", "python -m pytest tests/test_ci_smoke.py -xvs"),
        ("Core unit tests", "python -m pytest tests/unit/test_core.py -xvs"),
        ("Model tests", "python -m pytest tests/unit/test_unit_models.py -xvs"),
        ("Stub server tests", "python -m pytest tests/integration/test_stub_server.py -xvs"),
    ]
    
    all_passed = True
    for test_name, test_cmd in tests:
        if not run_command(test_cmd, f"Running {test_name}"):
            all_passed = False
    
    # 7. Test Docker build
    print("\n🐳 Testing Docker build...")
    
    if run_command("docker --version", "Checking Docker"):
        run_command("docker build -f Dockerfile.test -t leadfactory-test .", "Building test Docker image")
    
    # 8. Summary
    print("\n" + "="*60)
    print("📊 Test Infrastructure Check Summary")
    print("="*60)
    
    if all_passed:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())