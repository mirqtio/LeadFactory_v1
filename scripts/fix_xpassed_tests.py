#!/usr/bin/env python3
"""
Script to find and fix xpassed tests by removing unnecessary xfail markers.
"""
import ast
import re
import subprocess
import sys
from pathlib import Path


def run_pytest_on_file(file_path):
    """Run pytest on a single file to check for xpassed tests."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(file_path),
        "-v",
        "-rX",  # Show xpassed tests
        "--tb=no",
        "--no-header",
        "-x",  # Stop on first failure
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
        
        # Extract xpassed test names
        xpassed_tests = []
        for line in output.split("\n"):
            if "XPASS" in line:
                # Extract test name
                match = re.search(r"(\w+::\w+(?:::\w+)?)\s+XPASS", line)
                if match:
                    test_name = match.group(1).split("::")[-1]
                    xpassed_tests.append(test_name)
        
        return xpassed_tests
    except subprocess.TimeoutExpired:
        print(f"  ⚠️  Timeout running tests in {file_path}")
        return []
    except Exception as e:
        print(f"  ❌ Error running tests in {file_path}: {e}")
        return []


def remove_xfail_from_test(file_path, test_name):
    """Remove xfail marker from a specific test."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Pattern to match the xfail decorator before the test
    patterns = [
        # @pytest.mark.xfail(reason="...")
        rf'@pytest\.mark\.xfail\([^)]*\)\s*\ndef {test_name}\(',
        # @pytest.mark.xfail
        rf'@pytest\.mark\.xfail\s*\ndef {test_name}\(',
        # Multiple decorators including xfail
        rf'(@[^\n]+\n)*@pytest\.mark\.xfail[^\n]*\n((?:@[^\n]+\n)*)def {test_name}\(',
    ]
    
    modified = False
    for pattern in patterns:
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            # Remove just the xfail line
            if match.group(0).count('@') > 1:
                # Multiple decorators - remove only xfail
                new_content = re.sub(
                    rf'@pytest\.mark\.xfail[^\n]*\n',
                    '',
                    content
                )
            else:
                # Only xfail decorator - remove it
                new_content = re.sub(
                    rf'@pytest\.mark\.xfail[^\n]*\n(\s*)def {test_name}\(',
                    rf'\1def {test_name}(',
                    content
                )
            
            if new_content != content:
                content = new_content
                modified = True
                break
    
    if modified:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False


def process_file(file_path):
    """Process a single file to fix xpassed tests."""
    print(f"\n📄 Processing {file_path}")
    
    # Check if file has xfail markers
    with open(file_path, 'r') as f:
        content = f.read()
    
    if '@pytest.mark.xfail' not in content:
        print("  ⏭️  No xfail markers found")
        return 0
    
    # Count xfail markers
    xfail_count = content.count('@pytest.mark.xfail')
    print(f"  📊 Found {xfail_count} xfail markers")
    
    # Run tests to find xpassed
    xpassed_tests = run_pytest_on_file(file_path)
    
    if not xpassed_tests:
        print("  ✅ No xpassed tests found")
        return 0
    
    print(f"  🔍 Found {len(xpassed_tests)} xpassed tests")
    
    # Fix each xpassed test
    fixed_count = 0
    for test_name in xpassed_tests:
        print(f"  🔧 Fixing {test_name}...", end="")
        if remove_xfail_from_test(file_path, test_name):
            print(" ✅")
            fixed_count += 1
        else:
            print(" ❌ Could not remove xfail")
    
    # Verify fixes
    if fixed_count > 0:
        print(f"  🧪 Verifying fixes...")
        new_xpassed = run_pytest_on_file(file_path)
        if len(new_xpassed) < len(xpassed_tests):
            print(f"  ✅ Successfully fixed {fixed_count} tests")
        else:
            print(f"  ⚠️  Some tests still showing as xpassed")
    
    return fixed_count


def main():
    """Main function."""
    # Get all test files with xfail markers
    files_with_xfail = []
    
    test_dir = Path("tests")
    for file_path in test_dir.rglob("test_*.py"):
        if file_path.is_file():
            with open(file_path, 'r') as f:
                if '@pytest.mark.xfail' in f.read():
                    files_with_xfail.append(file_path)
    
    print(f"Found {len(files_with_xfail)} files with xfail markers")
    
    total_fixed = 0
    for file_path in sorted(files_with_xfail):
        fixed = process_file(file_path)
        total_fixed += fixed
    
    print(f"\n{'='*80}")
    print(f"SUMMARY: Fixed {total_fixed} xpassed tests")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()