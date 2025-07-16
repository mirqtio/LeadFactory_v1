#!/usr/bin/env python3
"""
Analyze Known Test Issues

This script analyzes the test codebase for common patterns that lead to flaky tests.
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple


class TestIssueAnalyzer:
    """Analyzes test files for common flaky test patterns."""

    def __init__(self, test_root: str = "tests/"):
        self.test_root = test_root
        self.issues = {
            "hardcoded_ports": [],
            "time_sleep": [],
            "missing_cleanup": [],
            "async_issues": [],
            "external_dependencies": [],
            "race_conditions": [],
            "resource_conflicts": [],
            "xfail_tests": [],
            "skip_tests": [],
            "no_timeout": [],
        }

    def analyze_all_tests(self) -> Dict:
        """Analyze all test files for issues."""
        test_files = self._find_test_files()

        print(f"Analyzing {len(test_files)} test files...")

        for test_file in test_files:
            self._analyze_file(test_file)

        return self._generate_report()

    def _find_test_files(self) -> List[Path]:
        """Find all test files."""
        test_files = []

        for root, dirs, files in os.walk(self.test_root):
            for file in files:
                if file.startswith("test_") and file.endswith(".py"):
                    test_files.append(Path(root) / file)

        return test_files

    def _analyze_file(self, file_path: Path):
        """Analyze a single test file for issues."""
        try:
            with open(file_path, "r") as f:
                content = f.read()

            # Analyze content
            self._check_hardcoded_ports(file_path, content)
            self._check_time_sleep(file_path, content)
            self._check_missing_cleanup(file_path, content)
            self._check_async_issues(file_path, content)
            self._check_external_dependencies(file_path, content)
            self._check_race_conditions(file_path, content)
            self._check_xfail_skip(file_path, content)
            self._check_missing_timeout(file_path, content)

            # Parse AST for deeper analysis
            try:
                tree = ast.parse(content)
                self._analyze_ast(file_path, tree)
            except SyntaxError:
                pass

        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")

    def _check_hardcoded_ports(self, file_path: Path, content: str):
        """Check for hardcoded ports."""
        port_patterns = [
            r"port\s*=\s*(\d{4,5})",
            r':(\d{4,5})["\s/]',
            r"localhost:(\d{4,5})",
            r"127\.0\.0\.1:(\d{4,5})",
            r"0\.0\.0\.0:(\d{4,5})",
        ]

        for pattern in port_patterns:
            for match in re.finditer(pattern, content):
                port = match.group(1)
                line_no = content[: match.start()].count("\n") + 1
                self.issues["hardcoded_ports"].append(
                    {"file": str(file_path), "line": line_no, "port": port, "context": match.group(0)}
                )

    def _check_time_sleep(self, file_path: Path, content: str):
        """Check for time.sleep usage."""
        sleep_pattern = r"time\.sleep\s*\([^)]+\)"

        for match in re.finditer(sleep_pattern, content):
            line_no = content[: match.start()].count("\n") + 1
            self.issues["time_sleep"].append({"file": str(file_path), "line": line_no, "code": match.group(0)})

    def _check_missing_cleanup(self, file_path: Path, content: str):
        """Check for missing cleanup patterns."""
        # Look for setup without teardown
        has_setup = bool(re.search(r"def setup|@pytest\.fixture|def setUp", content))
        has_teardown = bool(re.search(r"def teardown|yield|def tearDown|finally:|\.close\(\)", content))

        if has_setup and not has_teardown:
            self.issues["missing_cleanup"].append({"file": str(file_path), "issue": "Setup without teardown"})

        # Check for resource creation without cleanup
        resource_patterns = [
            (r"threading\.Thread", "thread"),
            (r"asyncio\.create_task", "task"),
            (r"open\([^)]+\)", "file"),
            (r"connect\(", "connection"),
            (r"Pool\(", "pool"),
        ]

        for pattern, resource_type in resource_patterns:
            if re.search(pattern, content) and not re.search(r"(close|join|cancel|shutdown)", content):
                self.issues["missing_cleanup"].append(
                    {"file": str(file_path), "issue": f"{resource_type} created without cleanup", "pattern": pattern}
                )

    def _check_async_issues(self, file_path: Path, content: str):
        """Check for async/await issues."""
        # Mix of sync and async
        has_async = bool(re.search(r"async def|@pytest\.mark\.asyncio|asyncio\.run", content))
        has_sync_tests = bool(re.search(r"def test_(?!.*async)", content))

        if has_async and has_sync_tests:
            self.issues["async_issues"].append({"file": str(file_path), "issue": "Mixed sync and async tests"})

        # Asyncio.run in async context
        if re.search(r"async def.*asyncio\.run", content, re.DOTALL):
            self.issues["async_issues"].append(
                {"file": str(file_path), "issue": "asyncio.run() called in async function"}
            )

        # Missing pytest.mark.asyncio
        async_test_pattern = r"async def (test_[^(]+)"
        for match in re.finditer(async_test_pattern, content):
            test_name = match.group(1)
            # Check if the test has the asyncio marker
            test_start = match.start()
            preceding_lines = content[:test_start].split("\n")[-5:]  # Check last 5 lines
            if not any("@pytest.mark.asyncio" in line for line in preceding_lines):
                line_no = content[: match.start()].count("\n") + 1
                self.issues["async_issues"].append(
                    {
                        "file": str(file_path),
                        "line": line_no,
                        "issue": f"Async test '{test_name}' missing @pytest.mark.asyncio",
                    }
                )

    def _check_external_dependencies(self, file_path: Path, content: str):
        """Check for external dependencies."""
        external_patterns = [
            (r"requests\.(get|post|put|delete)", "HTTP request"),
            (r"httpx\.(get|post|put|delete)", "HTTP request"),
            (r"boto3\.client", "AWS service"),
            (r"psycopg2\.connect", "PostgreSQL connection"),
            (r"redis\.Redis", "Redis connection"),
            (r"os\.environ\[", "Environment variable"),
            (r"os\.getenv\(", "Environment variable"),
        ]

        for pattern, dep_type in external_patterns:
            for match in re.finditer(pattern, content):
                line_no = content[: match.start()].count("\n") + 1

                # Check if it's mocked
                function_context = content[max(0, match.start() - 500) : match.end() + 500]
                if not re.search(r"(mock|patch|monkeypatch|stub)", function_context, re.I):
                    self.issues["external_dependencies"].append(
                        {"file": str(file_path), "line": line_no, "type": dep_type, "code": match.group(0)}
                    )

    def _check_race_conditions(self, file_path: Path, content: str):
        """Check for potential race conditions."""
        race_patterns = [
            (r"threading\.Thread.*\.start\(\)", "Multiple threads"),
            (r"multiprocessing\.Process", "Multiple processes"),
            (r"concurrent\.futures", "Concurrent execution"),
            (r"asyncio\.gather", "Concurrent async tasks"),
        ]

        for pattern, issue_type in race_patterns:
            if re.search(pattern, content):
                # Check for synchronization
                if not re.search(r"(Lock|Semaphore|Event|join|wait|barrier)", content):
                    self.issues["race_conditions"].append(
                        {"file": str(file_path), "issue": f"{issue_type} without proper synchronization"}
                    )

    def _check_xfail_skip(self, file_path: Path, content: str):
        """Check for xfail and skip decorators."""
        patterns = [
            (r'@pytest\.mark\.xfail.*reason="([^"]+)"', "xfail"),
            (r'@pytest\.mark\.skip.*reason="([^"]+)"', "skip"),
            (r'pytest\.xfail\("([^"]+)"\)', "xfail"),
            (r'pytest\.skip\("([^"]+)"\)', "skip"),
        ]

        for pattern, test_type in patterns:
            for match in re.finditer(pattern, content):
                reason = match.group(1) if match.lastindex > 0 else "No reason given"
                line_no = content[: match.start()].count("\n") + 1

                if test_type == "xfail":
                    self.issues["xfail_tests"].append({"file": str(file_path), "line": line_no, "reason": reason})
                else:
                    self.issues["skip_tests"].append({"file": str(file_path), "line": line_no, "reason": reason})

    def _check_missing_timeout(self, file_path: Path, content: str):
        """Check for tests that might need timeouts."""
        timeout_needed_patterns = [
            r"while\s+True:",
            r"while\s+[^:]+:\s*(?!break)",
            r"requests\.",
            r"httpx\.",
            r"subprocess\.",
            r"asyncio\.wait",
            r"\.join\(\)",
        ]

        has_timeout_risk = any(re.search(pattern, content) for pattern in timeout_needed_patterns)
        has_timeout = bool(re.search(r"@pytest\.mark\.timeout|timeout=", content))

        if has_timeout_risk and not has_timeout:
            self.issues["no_timeout"].append(
                {"file": str(file_path), "issue": "Test with blocking operations but no timeout"}
            )

    def _analyze_ast(self, file_path: Path, tree: ast.AST):
        """Perform AST-based analysis."""
        # This could be extended for more sophisticated analysis
        pass

    def _generate_report(self) -> Dict:
        """Generate analysis report."""
        report = {
            "summary": {
                "total_issues": sum(len(issues) for issues in self.issues.values()),
                "files_analyzed": len(
                    set(issue.get("file", "") for issue_list in self.issues.values() for issue in issue_list)
                ),
            },
            "issues": self.issues,
            "priorities": self._prioritize_issues(),
        }

        return report

    def _prioritize_issues(self) -> List[Dict]:
        """Prioritize issues for fixing."""
        priorities = []

        # High priority: Issues that directly cause flakiness
        high_priority_types = ["hardcoded_ports", "race_conditions", "missing_cleanup"]
        for issue_type in high_priority_types:
            if self.issues[issue_type]:
                priorities.append(
                    {
                        "priority": "HIGH",
                        "type": issue_type,
                        "count": len(self.issues[issue_type]),
                        "reason": "Directly causes test flakiness",
                    }
                )

        # Medium priority: Issues that can cause flakiness
        medium_priority_types = ["time_sleep", "async_issues", "external_dependencies"]
        for issue_type in medium_priority_types:
            if self.issues[issue_type]:
                priorities.append(
                    {
                        "priority": "MEDIUM",
                        "type": issue_type,
                        "count": len(self.issues[issue_type]),
                        "reason": "Can cause intermittent failures",
                    }
                )

        # Low priority: Issues that might need attention
        low_priority_types = ["xfail_tests", "skip_tests", "no_timeout"]
        for issue_type in low_priority_types:
            if self.issues[issue_type]:
                priorities.append(
                    {
                        "priority": "LOW",
                        "type": issue_type,
                        "count": len(self.issues[issue_type]),
                        "reason": "Should be reviewed and fixed",
                    }
                )

        return sorted(priorities, key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x["priority"]])


def main():
    """Main entry point."""
    import json

    analyzer = TestIssueAnalyzer()
    report = analyzer.analyze_all_tests()

    # Print summary
    print(f"\n📊 Analysis Complete")
    print(f"Total issues found: {report['summary']['total_issues']}")
    print(f"Files with issues: {report['summary']['files_analyzed']}")

    # Print priorities
    print("\n🎯 Issue Priorities:")
    for priority in report["priorities"]:
        print(f"\n{priority['priority']} Priority: {priority['type'].replace('_', ' ').title()}")
        print(f"  Count: {priority['count']}")
        print(f"  Reason: {priority['reason']}")

    # Generate detailed report
    with open("test_issues_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\n📄 Detailed report saved to test_issues_report.json")

    # Generate markdown report
    generate_markdown_report(report)


def generate_markdown_report(report: Dict):
    """Generate a markdown report of test issues."""
    lines = []
    lines.append("# Test Issues Analysis Report")
    lines.append(f"\n## Summary")
    lines.append(f"- Total issues: {report['summary']['total_issues']}")
    lines.append(f"- Files with issues: {report['summary']['files_analyzed']}")

    # Issue details by priority
    for priority_level in ["HIGH", "MEDIUM", "LOW"]:
        priority_items = [p for p in report["priorities"] if p["priority"] == priority_level]
        if priority_items:
            lines.append(f"\n## {priority_level} Priority Issues")

            for item in priority_items:
                issue_type = item["type"]
                issues = report["issues"][issue_type]

                if issues:
                    lines.append(f"\n### {issue_type.replace('_', ' ').title()} ({len(issues)} issues)")

                    # Group by file
                    by_file = {}
                    for issue in issues[:10]:  # Show first 10
                        file_path = issue.get("file", "Unknown")
                        if file_path not in by_file:
                            by_file[file_path] = []
                        by_file[file_path].append(issue)

                    for file_path, file_issues in by_file.items():
                        lines.append(f"\n**{file_path}**")
                        for issue in file_issues:
                            if "line" in issue:
                                lines.append(
                                    f"- Line {issue['line']}: {issue.get('issue', issue.get('code', issue.get('context', 'Issue found')))}"
                                )
                            else:
                                lines.append(f"- {issue.get('issue', 'Issue found')}")

                    if len(issues) > 10:
                        lines.append(f"\n*... and {len(issues) - 10} more issues*")

    # Recommendations
    lines.append("\n## Recommendations for Fixing")
    lines.append("\n1. **Fix hardcoded ports**: Use dynamic port allocation or fixtures")
    lines.append("2. **Remove time.sleep()**: Use proper wait conditions or mocks")
    lines.append("3. **Add cleanup**: Ensure all resources are properly cleaned up")
    lines.append("4. **Fix async tests**: Use pytest-asyncio consistently")
    lines.append("5. **Mock external dependencies**: Don't rely on external services")
    lines.append("6. **Add timeouts**: Prevent tests from hanging indefinitely")

    with open("test_issues_analysis.md", "w") as f:
        f.write("\n".join(lines))

    print("📄 Markdown report saved to test_issues_analysis.md")


if __name__ == "__main__":
    main()
