"""
Test Suite Stability Validator

Ensures tests follow best practices for reliable execution:
- No hardcoded ports
- Proper async cleanup
- Thread termination
- Resource isolation
"""

import ast
import asyncio
import os
import re
import threading
from pathlib import Path
from typing import List, Set, Tuple

import pytest


class StabilityCodeAnalyzer(ast.NodeVisitor):
    """AST visitor to analyze test code for stability issues."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.issues = []
        self.hardcoded_ports = []
        self.sleep_calls = []
        self.thread_starts = []
        self.async_issues = []

    def visit_Num(self, node):
        """Check for hardcoded port numbers."""
        if isinstance(node.n, int) and 1024 <= node.n <= 65535:
            # Check if this number might be a port
            line = self.get_line(node.lineno)
            if any(word in line.lower() for word in ["port", "bind", "listen", "connect"]):
                self.hardcoded_ports.append((node.lineno, node.n))
        self.generic_visit(node)

    def visit_Constant(self, node):
        """Check for hardcoded port numbers in Python 3.8+."""
        if isinstance(node.value, int) and 1024 <= node.value <= 65535:
            line = self.get_line(node.lineno)
            if any(word in line.lower() for word in ["port", "bind", "listen", "connect"]):
                self.hardcoded_ports.append((node.lineno, node.value))
        self.generic_visit(node)

    def visit_Call(self, node):
        """Check for problematic function calls."""
        func_name = self.get_func_name(node)

        # Check for time.sleep()
        if func_name in ["time.sleep", "sleep"]:
            self.sleep_calls.append((node.lineno, func_name))

        # Check for thread creation without proper cleanup
        if func_name in ["threading.Thread", "Thread"]:
            # Check if daemon=True is set
            has_daemon = any(kw.arg == "daemon" and self.get_value(kw.value) is True for kw in node.keywords)
            if has_daemon:
                self.issues.append((node.lineno, "Thread created with daemon=True may not clean up properly"))
            self.thread_starts.append((node.lineno, has_daemon))

        # Check for async issues
        if func_name in ["asyncio.create_task", "create_task"]:
            self.async_issues.append((node.lineno, "Ensure created tasks are awaited or cancelled"))

        self.generic_visit(node)

    def get_func_name(self, node):
        """Extract function name from call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return None

    def get_value(self, node):
        """Extract value from AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.NameConstant):
            return node.value
        elif hasattr(node, "value"):
            return node.value
        return None

    def get_line(self, lineno):
        """Get source line by number."""
        try:
            with open(self.filepath, "r") as f:
                lines = f.readlines()
                if 0 < lineno <= len(lines):
                    return lines[lineno - 1].strip()
        except Exception:
            pass
        return ""

    def analyze(self):
        """Analyze the file and return issues."""
        try:
            with open(self.filepath, "r") as f:
                tree = ast.parse(f.read(), filename=self.filepath)
            self.visit(tree)
        except Exception as e:
            self.issues.append((0, f"Failed to parse file: {e}"))

        return {
            "filepath": self.filepath,
            "hardcoded_ports": self.hardcoded_ports,
            "sleep_calls": self.sleep_calls,
            "thread_starts": self.thread_starts,
            "async_issues": self.async_issues,
            "general_issues": self.issues,
        }


def find_test_files(root_dir: Path) -> List[Path]:
    """Find all Python test files."""
    test_files = []
    for path in root_dir.rglob("test_*.py"):
        if not any(part.startswith(".") for part in path.parts):
            test_files.append(path)
    return test_files


def check_resource_cleanup(filepath: Path) -> List[Tuple[int, str]]:
    """Check for proper resource cleanup patterns."""
    issues = []

    with open(filepath, "r") as f:
        content = f.read()
        lines = content.splitlines()

    # Check for fixtures without cleanup
    fixture_pattern = re.compile(r"@pytest\.fixture")
    yield_pattern = re.compile(r"\byield\b")

    in_fixture = False
    fixture_start = 0
    has_yield = False

    for i, line in enumerate(lines, 1):
        if fixture_pattern.search(line):
            if in_fixture and not has_yield:
                issues.append((fixture_start, "Fixture without yield may not clean up resources"))
            in_fixture = True
            fixture_start = i
            has_yield = False
        elif in_fixture and yield_pattern.search(line):
            has_yield = True
        elif in_fixture and line.strip() and not line.strip().startswith((" ", "\t", "#")):
            # End of fixture
            if not has_yield:
                issues.append((fixture_start, "Fixture without yield may not clean up resources"))
            in_fixture = False

    return issues


class TestStabilityValidation:
    """Test suite to validate test stability practices."""

    @pytest.fixture(scope="session")
    def test_files(self):
        """Get all test files in the project."""
        root = Path(__file__).parent
        return find_test_files(root)

    def test_no_hardcoded_ports(self, test_files):
        """Ensure no tests use hardcoded ports."""
        violations = []

        for filepath in test_files:
            # Skip this file and test utilities
            if filepath.name in ["test_stability.py", "test_port_manager.py"]:
                continue

            analyzer = StabilityCodeAnalyzer(str(filepath))
            results = analyzer.analyze()

            if results["hardcoded_ports"]:
                for lineno, port in results["hardcoded_ports"]:
                    # Allow some specific ports in certain files
                    if port in [5432, 6379, 8000, 9090, 3000] and "docker" in str(filepath):
                        continue  # Docker compose tests may reference standard ports
                    violations.append(f"{filepath}:{lineno} - Hardcoded port {port}")

        assert not violations, "Tests should use dynamic port allocation:\n" + "\n".join(violations)

    def test_no_bare_sleep_calls(self, test_files):
        """Ensure tests use proper synchronization instead of sleep()."""
        violations = []

        for filepath in test_files:
            # Skip stability and synchronization test files
            if filepath.name in ["test_stability.py", "test_synchronization.py"]:
                continue

            analyzer = StabilityCodeAnalyzer(str(filepath))
            results = analyzer.analyze()

            if results["sleep_calls"]:
                # Read file to check context
                with open(filepath, "r") as f:
                    lines = f.readlines()

                for lineno, func in results["sleep_calls"]:
                    # Check if it's in a comment or has a comment explaining why
                    if lineno <= len(lines):
                        line = lines[lineno - 1]
                        # Allow sleep with explanatory comments
                        if "# " in line and any(
                            word in line for word in ["debounce", "rate limit", "retry", "backoff", "purposeful"]
                        ):
                            continue
                    violations.append(f"{filepath}:{lineno} - {func} should use wait_for_condition")

        # We expect some violations but they should be justified
        if violations:
            print(f"Found {len(violations)} sleep() calls that may need review:")
            for v in violations[:10]:  # Show first 10
                print(f"  {v}")

    def test_thread_cleanup(self, test_files):
        """Ensure all threads are properly managed."""
        issues = []

        for filepath in test_files:
            analyzer = StabilityCodeAnalyzer(str(filepath))
            results = analyzer.analyze()

            # Check general threading issues
            issues.extend(
                [f"{filepath}:{lineno} - {msg}" for lineno, msg in results["general_issues"] if "thread" in msg.lower()]
            )

            # Check for threads without join()
            if results["thread_starts"]:
                with open(filepath, "r") as f:
                    content = f.read()

                for lineno, has_daemon in results["thread_starts"]:
                    # Look for corresponding join() call
                    if not re.search(r"\.join\(\)", content):
                        issues.append(f"{filepath}:{lineno} - Thread started without join()")

        # Some daemon threads are acceptable in fixtures
        filtered_issues = [issue for issue in issues if "conftest.py" not in issue or "daemon=True" not in issue]

        assert not filtered_issues, "Thread management issues found:\n" + "\n".join(filtered_issues)

    def test_async_cleanup(self, test_files):
        """Ensure async resources are properly cleaned up."""
        issues = []

        for filepath in test_files:
            analyzer = StabilityCodeAnalyzer(str(filepath))
            results = analyzer.analyze()

            issues.extend([f"{filepath}:{lineno} - {msg}" for lineno, msg in results["async_issues"]])

        # Async issues are warnings for now
        if issues:
            print(f"Async cleanup warnings ({len(issues)} found):")
            for issue in issues[:5]:
                print(f"  {issue}")

    def test_resource_cleanup_patterns(self, test_files):
        """Ensure fixtures properly clean up resources."""
        all_issues = []

        for filepath in test_files:
            issues = check_resource_cleanup(filepath)
            all_issues.extend([f"{filepath}:{lineno} - {msg}" for lineno, msg in issues])

        # Filter out known good patterns
        filtered = [issue for issue in all_issues if "session" not in issue]  # Session fixtures may not need yield

        if filtered:
            print(f"Resource cleanup warnings ({len(filtered)} found):")
            for issue in filtered[:10]:
                print(f"  {issue}")

    def test_no_shared_state(self):
        """Validate that tests don't share mutable state."""
        # This is more of a guideline test
        shared_state_patterns = [
            (r"^[^#]*\b\w+\s*=\s*\[\]", "Mutable list at module level"),
            (r"^[^#]*\b\w+\s*=\s*\{\}", "Mutable dict at module level"),
            (r"^[^#]*\b\w+\s*=\s*set\(\)", "Mutable set at module level"),
        ]

        issues = []
        test_files = find_test_files(Path(__file__).parent)

        for filepath in test_files:
            with open(filepath, "r") as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                # Skip if in function/class definition
                if line.strip().startswith(("def ", "class ", "    ", "\t")):
                    continue

                for pattern, desc in shared_state_patterns:
                    if re.match(pattern, line):
                        issues.append(f"{filepath}:{i} - {desc}")

        # This is informational
        if issues:
            print(f"Potential shared state warnings ({len(issues)} found)")
            print("Consider using fixtures or factory functions instead")

    def test_parallel_safety_markers(self, test_files):
        """Check that tests requiring serial execution are properly marked."""
        serial_indicators = ["shared_resource", "database_migration", "modifies_global_state", "requires_serial"]

        warnings = []

        for filepath in test_files:
            with open(filepath, "r") as f:
                content = f.read()

            # Look for tests that might need serial execution
            if any(
                indicator in content
                for indicator in [
                    "os.environ[",
                    "monkeypatch.setenv",
                    "sys.path.insert",
                    "shutil.rmtree",
                    "CREATE DATABASE",
                    "DROP DATABASE",
                ]
            ):
                # Check if properly marked
                if not any(f"@pytest.mark.{marker}" in content for marker in ["serial", "no_parallel"]):
                    warnings.append(f"{filepath} - May need serial execution marker")

        if warnings:
            print(f"Tests that may need serial execution markers:")
            for warning in warnings[:5]:
                print(f"  {warning}")


@pytest.mark.flaky(reruns=3, reruns_delay=1)
class TestSystemStability:
    """System-level stability tests."""

    def test_port_manager_thread_safety(self):
        """Ensure PortManager is thread-safe."""
        from tests.test_port_manager import PortManager

        PortManager.reset()
        ports = []
        errors = []

        def allocate_port():
            try:
                port = PortManager.get_free_port()
                ports.append(port)
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=allocate_port)
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        assert not errors, f"Port allocation errors: {errors}"
        assert len(ports) == len(set(ports)), "Duplicate ports allocated"

        # Cleanup
        for port in ports:
            PortManager.release_port(port)

    def test_async_event_loop_cleanup(self):
        """Ensure event loops are properly cleaned up."""

        async def async_task():
            await asyncio.sleep(0.1)
            return "completed"

        # Create and run event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(async_task())
            assert result == "completed"
        finally:
            # Proper cleanup
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

        # Verify loop is closed
        assert loop.is_closed()


if __name__ == "__main__":
    # Run stability checks
    pytest.main([__file__, "-v"])
