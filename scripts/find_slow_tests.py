#!/usr/bin/env python3
"""
Find slow tests by running pytest on each test directory separately.
This avoids timeout issues with large test suites.
"""

import subprocess
import sys
import re
from pathlib import Path
from typing import List, Tuple, Dict
import argparse


def find_test_directories() -> List[Path]:
    """Find all test directories containing Python test files."""
    test_root = Path(__file__).parent.parent / "tests"
    test_dirs = []
    
    # Find all directories with test files
    for test_file in test_root.rglob("test_*.py"):
        test_dir = test_file.parent
        if test_dir not in test_dirs:
            test_dirs.append(test_dir)
    
    return sorted(test_dirs)


def profile_directory(test_dir: Path, num_durations: int = 20) -> List[Tuple[str, float]]:
    """Profile a single test directory and return slow tests."""
    print(f"\nProfiling {test_dir.relative_to(test_dir.parent.parent)}...")
    
    cmd = [
        sys.executable, "-m", "pytest",
        str(test_dir),
        f"--durations={num_durations}",
        "--tb=no",
        "-v",
        "--no-header",
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout per directory
            cwd=Path(__file__).parent.parent
        )
        
        # Parse durations from output
        durations = []
        duration_pattern = r'(\d+\.\d+)s call\s+(.+?)(?:\s|$)'
        
        for match in re.finditer(duration_pattern, result.stdout):
            duration = float(match.group(1))
            test_path = match.group(2).strip()
            durations.append((test_path, duration))
        
        return durations
        
    except subprocess.TimeoutExpired:
        print(f"  Timeout profiling {test_dir}")
        return []
    except Exception as e:
        print(f"  Error profiling {test_dir}: {e}")
        return []


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Find slow tests across the codebase")
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        help="Time threshold in seconds for marking tests as slow (default: 1.0)"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of slowest tests to show per directory (default: 20)"
    )
    args = parser.parse_args()
    
    # Find test directories
    test_dirs = find_test_directories()
    print(f"Found {len(test_dirs)} test directories to profile")
    
    # Collect all slow tests
    all_slow_tests: Dict[str, List[Tuple[str, float]]] = {}
    
    for test_dir in test_dirs:
        durations = profile_directory(test_dir, args.top)
        
        # Filter by threshold
        slow_tests = [(test, dur) for test, dur in durations if dur >= args.threshold]
        
        if slow_tests:
            all_slow_tests[str(test_dir)] = slow_tests
    
    # Generate report
    print(f"\n{'='*80}")
    print(f"SLOW TEST SUMMARY (threshold: {args.threshold}s)")
    print(f"{'='*80}\n")
    
    if not all_slow_tests:
        print("No slow tests found!")
        return 0
    
    total_slow = sum(len(tests) for tests in all_slow_tests.values())
    print(f"Total slow tests found: {total_slow}")
    print(f"Affected directories: {len(all_slow_tests)}\n")
    
    # Sort by total time in slow tests
    dir_times = {}
    for dir_path, tests in all_slow_tests.items():
        dir_times[dir_path] = sum(dur for _, dur in tests)
    
    sorted_dirs = sorted(dir_times.items(), key=lambda x: x[1], reverse=True)
    
    # Print top slow tests
    print("\nTop 20 Slowest Tests Overall:")
    print("-" * 80)
    
    all_tests = []
    for dir_path, tests in all_slow_tests.items():
        for test, dur in tests:
            all_tests.append((test, dur))
    
    all_tests.sort(key=lambda x: x[1], reverse=True)
    
    for i, (test, dur) in enumerate(all_tests[:20], 1):
        print(f"{i:2}. {dur:6.2f}s  {test}")
    
    # Files to update
    print(f"\n{'='*80}")
    print("FILES REQUIRING @pytest.mark.slow")
    print(f"{'='*80}\n")
    
    files_to_update = set()
    for tests in all_slow_tests.values():
        for test, _ in tests:
            if "::" in test:
                file_path = test.split("::")[0]
                files_to_update.add(file_path)
    
    for file_path in sorted(files_to_update):
        print(f"  {file_path}")
    
    print(f"\nTotal files to update: {len(files_to_update)}")
    
    # Save results
    output_file = Path(__file__).parent / "slow_tests_found.txt"
    with open(output_file, "w") as f:
        f.write(f"Slow Tests Report (threshold: {args.threshold}s)\n")
        f.write("=" * 80 + "\n\n")
        
        for test, dur in all_tests:
            if dur >= args.threshold:
                f.write(f"{dur:6.2f}s  {test}\n")
    
    print(f"\nDetailed results saved to: {output_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())