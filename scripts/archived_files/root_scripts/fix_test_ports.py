#!/usr/bin/env python3
"""
Fix Hardcoded Ports in Tests

This script helps identify and suggest fixes for hardcoded ports in test files.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def find_hardcoded_ports(file_path: Path) -> list[tuple[int, str, str]]:
    """Find hardcoded ports in a file.

    Returns list of (line_number, original_text, suggested_fix)
    """
    with open(file_path) as f:
        content = f.read()
        lines = content.split("\n")

    issues = []
    port_patterns = [
        # Direct port assignments
        (r"port\s*=\s*(\d{4,5})", "port = get_free_port()"),
        # URLs with ports
        (r"localhost:(\d{4,5})", "localhost:{port}"),
        (r"127\.0\.0\.1:(\d{4,5})", "127.0.0.1:{port}"),
        (r"0\.0\.0\.0:(\d{4,5})", "0.0.0.0:{port}"),
        # HTTP URLs
        (r"http://localhost:(\d{4,5})", "http://localhost:{port}"),
    ]

    for i, line in enumerate(lines, 1):
        for pattern, suggestion in port_patterns:
            match = re.search(pattern, line)
            if match:
                port = match.group(1)
                # Skip common default ports that might be intentional
                if port not in ["80", "443", "22"]:
                    issues.append((i, line.strip(), suggestion))

    return issues


def suggest_fixture():
    """Return suggested pytest fixture for dynamic ports."""
    return '''
@pytest.fixture
def free_port():
    """Get a free port for testing."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture
def test_server(free_port):
    """Start a test server on a free port."""
    # Example server setup
    server = YourTestServer(port=free_port)
    server.start()
    yield server
    server.stop()
'''


def suggest_helper_function():
    """Return suggested helper function for getting free ports."""
    return '''
def get_free_port():
    """Get a free port that can be used for testing."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


# Alternative using contextlib
from contextlib import closing
import socket

def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]
'''


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Find and fix hardcoded ports in tests")
    parser.add_argument("path", nargs="?", default="tests/", help="Path to test file or directory")
    parser.add_argument("--show-fixtures", action="store_true", help="Show example fixtures for dynamic ports")

    args = parser.parse_args()

    if args.show_fixtures:
        print("# Suggested Pytest Fixtures for Dynamic Ports")
        print(suggest_fixture())
        print("\n# Helper Functions")
        print(suggest_helper_function())
        return

    path = Path(args.path)

    if path.is_file():
        files = [path]
    else:
        files = list(path.rglob("test_*.py"))

    total_issues = 0
    files_with_issues = 0

    print("Scanning for hardcoded ports...\n")

    for file_path in files:
        issues = find_hardcoded_ports(file_path)

        if issues:
            files_with_issues += 1
            total_issues += len(issues)

            print(f"📄 {file_path}")
            for line_no, original, suggestion in issues:
                print(f"  Line {line_no}: {original}")
                print(f"    → Suggestion: {suggestion}")
            print()

    print("\n📊 Summary:")
    print(f"  Files scanned: {len(files)}")
    print(f"  Files with issues: {files_with_issues}")
    print(f"  Total hardcoded ports: {total_issues}")

    if total_issues > 0:
        print(f"\n💡 To see example fixtures, run: {sys.argv[0]} --show-fixtures")


if __name__ == "__main__":
    main()
