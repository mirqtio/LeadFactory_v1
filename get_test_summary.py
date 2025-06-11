#!/usr/bin/env python3
"""Get comprehensive test summary"""

import subprocess
import re

def run_tests(test_path):
    """Run tests and return output"""
    result = subprocess.run(
        ['python3', '-m', 'pytest', test_path, '-v', '--tb=no'],
        capture_output=True,
        text=True
    )
    return result.stdout

def parse_summary(output):
    """Parse pytest output for summary"""
    # Look for the summary line
    summary_match = re.search(r'(\d+) failed.*?(\d+) passed.*?(\d+) skipped.*?(\d+) error', output)
    if summary_match:
        return {
            'failed': int(summary_match.group(1)),
            'passed': int(summary_match.group(2)),
            'skipped': int(summary_match.group(3)),
            'error': int(summary_match.group(4))
        }
    
    # Try alternate patterns
    patterns = [
        (r'(\d+) passed, (\d+) skipped', {'passed': 1, 'skipped': 2}),
        (r'(\d+) passed, (\d+) failed', {'passed': 1, 'failed': 2}),
        (r'(\d+) failed, (\d+) passed, (\d+) skipped', {'failed': 1, 'passed': 2, 'skipped': 3}),
        (r'(\d+) failed, (\d+) passed', {'failed': 1, 'passed': 2}),
        (r'(\d+) passed', {'passed': 1}),
    ]
    
    for pattern, groups in patterns:
        match = re.search(pattern, output)
        if match:
            result = {'passed': 0, 'failed': 0, 'skipped': 0, 'error': 0}
            for key, group_num in groups.items():
                result[key] = int(match.group(group_num))
            return result
    
    return {'passed': 0, 'failed': 0, 'skipped': 0, 'error': 0}

print("Test Summary Report")
print("=" * 50)

# Test each category
categories = [
    ('Unit Tests', 'tests/unit/'),
    ('Integration Tests', 'tests/integration/'),
    ('E2E Tests', 'tests/e2e/'),
    ('Other Tests', 'tests/')
]

total_stats = {'passed': 0, 'failed': 0, 'skipped': 0, 'error': 0}

for name, path in categories[:3]:  # Skip 'Other' for now
    print(f"\n{name}:")
    output = run_tests(path)
    stats = parse_summary(output)
    
    print(f"  Passed: {stats['passed']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"  Errors: {stats['error']}")
    
    for key in total_stats:
        total_stats[key] += stats[key]

print("\n" + "=" * 50)
print("TOTAL:")
print(f"  Passed: {total_stats['passed']}")
print(f"  Failed: {total_stats['failed']}")
print(f"  Skipped: {total_stats['skipped']}")
print(f"  Errors: {total_stats['error']}")
print(f"  Total Tests: {sum(total_stats.values())}")
print(f"  Success Rate: {total_stats['passed'] / sum(total_stats.values()) * 100:.1f}%")