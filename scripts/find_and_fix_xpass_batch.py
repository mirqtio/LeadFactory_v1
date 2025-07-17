#!/usr/bin/env python3
"""
Find xpassed tests by running each file with xfail markers individually.
"""
import re
import subprocess
import sys
from pathlib import Path


def has_xfail_markers(file_path):
    """Check if file contains xfail markers."""
    with open(file_path, 'r') as f:
        return '@pytest.mark.xfail' in f.read()


def run_tests_in_file(file_path):
    """Run tests in a single file and check for xpassed tests."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(file_path),
        "-v",
        "-rX",  # Show xpassed
        "--tb=no",
        "--no-header",
        "-x",  # Stop on first failure
        "--timeout=30",  # Timeout per test
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr
        
        # Extract xpassed test names
        xpassed_tests = []
        for line in output.split("\n"):
            if "XPASS" in line:
                # Extract full test path
                match = re.search(r"(test_\w+(?:::\w+)?)\s+XPASS", line)
                if match:
                    xpassed_tests.append(match.group(1))
        
        # Also check summary line
        match = re.search(r"(\d+) xpassed", output)
        xpass_count = int(match.group(1)) if match else 0
        
        return xpassed_tests, xpass_count, output
    except subprocess.TimeoutExpired:
        return [], 0, "TIMEOUT"
    except Exception as e:
        return [], 0, str(e)


def remove_xfail_markers(file_path, test_names):
    """Remove xfail markers from specific tests."""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    modified = False
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this is an xfail line
        if '@pytest.mark.xfail' in line:
            # Look ahead for the test function
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith('def '):
                j += 1
            
            if j < len(lines):
                # Extract test name
                match = re.match(r'\s*def (test_\w+)', lines[j])
                if match:
                    test_name = match.group(1)
                    if any(test_name in t for t in test_names):
                        # Remove the xfail line
                        lines.pop(i)
                        modified = True
                        continue
        i += 1
    
    if modified:
        with open(file_path, 'w') as f:
            f.writelines(lines)
    
    return modified


def main():
    """Main function."""
    # Get all test files with xfail markers
    test_files = []
    for file_path in Path("tests").rglob("test_*.py"):
        if file_path.is_file() and has_xfail_markers(file_path):
            test_files.append(file_path)
    
    print(f"Found {len(test_files)} files with xfail markers")
    print("=" * 80)
    
    total_xpassed = 0
    fixed_files = []
    
    for idx, file_path in enumerate(sorted(test_files), 1):
        print(f"\n[{idx}/{len(test_files)}] Checking {file_path}...")
        
        xpassed_tests, xpass_count, output = run_tests_in_file(file_path)
        
        if output == "TIMEOUT":
            print("  ⏱️  TIMEOUT - skipping")
            continue
        
        if xpass_count > 0:
            print(f"  🔍 Found {xpass_count} xpassed tests")
            total_xpassed += xpass_count
            
            if xpassed_tests:
                print(f"  🔧 Fixing {len(xpassed_tests)} tests...")
                if remove_xfail_markers(file_path, xpassed_tests):
                    fixed_files.append((file_path, len(xpassed_tests)))
                    print("  ✅ Fixed!")
                else:
                    print("  ⚠️  Could not fix automatically")
            else:
                print("  ℹ️  Tests identified but names not extracted")
        else:
            print("  ✅ No xpassed tests")
    
    print("\n" + "=" * 80)
    print(f"SUMMARY: Found {total_xpassed} xpassed tests total")
    print(f"Fixed {len(fixed_files)} files:")
    for file_path, count in fixed_files:
        print(f"  - {file_path}: {count} tests")


if __name__ == "__main__":
    main()