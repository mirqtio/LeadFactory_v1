#!/usr/bin/env python3
"""
CI Job Optimizer - Analyzes test distribution and recommends optimal job splitting

This script analyzes the test suite structure and provides recommendations for
splitting tests into separate CI jobs for better parallelization and faster feedback.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


@dataclass
class TestInfo:
    """Information about a test file"""

    path: str
    markers: set[str] = field(default_factory=set)
    module_domain: str = ""
    estimated_runtime: float = 0.0
    line_count: int = 0
    test_count: int = 0


@dataclass
class JobConfig:
    """Configuration for a CI job"""

    name: str
    description: str
    pytest_command: str
    included_markers: list[str] = field(default_factory=list)
    excluded_markers: list[str] = field(default_factory=list)
    test_patterns: list[str] = field(default_factory=list)
    estimated_runtime: float = 0.0
    test_count: int = 0
    parallel_workers: int = 4


class CIJobOptimizer:
    """Analyzes test distribution and recommends optimal CI job configuration"""

    def __init__(self, test_root: str = "tests"):
        self.test_root = Path(test_root)
        self.test_files: list[TestInfo] = []
        self.marker_stats: dict[str, int] = defaultdict(int)
        self.domain_stats: dict[str, int] = defaultdict(int)

    def analyze_tests(self):
        """Scan and analyze all test files"""
        print("🔍 Analyzing test distribution...")

        for test_file in self.test_root.rglob("test_*.py"):
            if "__pycache__" in str(test_file):
                continue

            info = self._analyze_test_file(test_file)
            self.test_files.append(info)

            # Update statistics
            for marker in info.markers:
                self.marker_stats[marker] += 1
            if info.module_domain:
                self.domain_stats[info.module_domain] += 1

        print(f"✅ Analyzed {len(self.test_files)} test files")

    def _analyze_test_file(self, file_path: Path) -> TestInfo:
        """Analyze a single test file"""
        info = TestInfo(path=str(file_path))

        # Extract domain from path (e.g., d0_gateway, d1_targeting)
        path_parts = file_path.parts
        for part in path_parts:
            if re.match(r"d\d+_\w+", part):
                info.module_domain = part
                break

        # Read file content
        try:
            content = file_path.read_text()
            info.line_count = len(content.splitlines())

            # Extract markers
            marker_pattern = r"@pytest\.mark\.(\w+)"
            markers = re.findall(marker_pattern, content)
            info.markers = set(markers)

            # Count test functions
            test_pattern = r"def test_\w+"
            info.test_count = len(re.findall(test_pattern, content))

            # Estimate runtime based on markers and complexity
            info.estimated_runtime = self._estimate_runtime(info)

        except Exception as e:
            print(f"⚠️  Error analyzing {file_path}: {e}")

        return info

    def _estimate_runtime(self, info: TestInfo) -> float:
        """Estimate test runtime in seconds"""
        base_time = 0.1 * info.test_count  # Base 0.1s per test

        # Adjust based on markers
        if "slow" in info.markers:
            base_time *= 5
        if "integration" in info.markers:
            base_time *= 3
        if "smoke" in info.markers:
            base_time *= 0.5
        if "critical" in info.markers:
            base_time *= 0.8

        # Adjust based on file size
        if info.line_count > 500:
            base_time *= 1.5

        return base_time

    def generate_job_configs(self) -> list[JobConfig]:
        """Generate recommended CI job configurations"""
        jobs = []

        # Job 1: Critical/Smoke Tests - Fast Feedback
        jobs.append(
            JobConfig(
                name="fast-feedback",
                description="Critical and smoke tests for immediate feedback",
                pytest_command="python -m pytest -v -m 'critical or smoke' --tb=short -n 4",
                included_markers=["critical", "smoke"],
                excluded_markers=["slow", "integration"],
                parallel_workers=4,
            )
        )

        # Job 2: Unit Tests - Core Logic
        jobs.append(
            JobConfig(
                name="unit-tests",
                description="All unit tests excluding integration and slow tests",
                pytest_command="python -m pytest -v -m 'unit or (not integration and not slow and not e2e)' --tb=short -n auto",
                included_markers=["unit"],
                excluded_markers=["integration", "slow", "e2e"],
                parallel_workers=8,
            )
        )

        # Job 3: Integration Tests - Database/API
        jobs.append(
            JobConfig(
                name="integration-tests",
                description="Integration tests with database and external services",
                pytest_command="python -m pytest -v -m 'integration' --tb=short -n 2",
                included_markers=["integration"],
                excluded_markers=["e2e"],
                parallel_workers=2,
            )
        )

        # Job 4: Domain-Specific Tests (Parallel)
        # Split by domain for better parallelization
        domain_jobs = self._generate_domain_jobs()
        jobs.extend(domain_jobs)

        # Job 5: Full Test Suite - Complete Validation
        jobs.append(
            JobConfig(
                name="full-test-suite",
                description="Complete test suite validation",
                pytest_command="python -m pytest -v -m 'not slow and not phase_future' --tb=short --cov=. --cov-report=xml -n auto",
                excluded_markers=["slow", "phase_future"],
                parallel_workers=4,
            )
        )

        # Calculate estimated runtimes
        self._calculate_job_runtimes(jobs)

        return jobs

    def _generate_domain_jobs(self) -> list[JobConfig]:
        """Generate domain-specific test jobs"""
        domain_jobs = []

        # Group domains into logical batches
        domain_groups = {
            "data-pipeline": ["d0_gateway", "d1_targeting", "d2_sourcing", "d3_assessment", "d4_enrichment"],
            "business-logic": ["d5_scoring", "d6_reports", "d7_storefront", "d8_personalization"],
            "delivery-orchestration": ["d9_delivery", "d10_analytics", "d11_orchestration"],
        }

        for group_name, domains in domain_groups.items():
            test_paths = " ".join([f"tests/unit/{d}" for d in domains if f"tests/unit/{d}" in str(self.test_root)])
            if test_paths:
                domain_jobs.append(
                    JobConfig(
                        name=f"domain-{group_name}",
                        description=f"Domain-specific tests for {group_name}",
                        pytest_command=f"python -m pytest -v {test_paths} -m 'not slow' --tb=short -n 4",
                        test_patterns=domains,
                        excluded_markers=["slow"],
                        parallel_workers=4,
                    )
                )

        return domain_jobs

    def _calculate_job_runtimes(self, jobs: list[JobConfig]):
        """Calculate estimated runtime for each job"""
        for job in jobs:
            total_runtime = 0
            test_count = 0

            for test_info in self.test_files:
                # Check if test matches job criteria
                if self._test_matches_job(test_info, job):
                    total_runtime += test_info.estimated_runtime
                    test_count += test_info.test_count

            # Adjust for parallelization
            job.estimated_runtime = total_runtime / job.parallel_workers
            job.test_count = test_count

    def _test_matches_job(self, test: TestInfo, job: JobConfig) -> bool:
        """Check if a test file matches job criteria"""
        # Check included markers
        if job.included_markers:
            if not any(marker in test.markers for marker in job.included_markers):
                return False

        # Check excluded markers
        if job.excluded_markers:
            if any(marker in test.markers for marker in job.excluded_markers):
                return False

        # Check test patterns
        if job.test_patterns:
            if not any(pattern in test.path for pattern in job.test_patterns):
                return False

        return True

    def print_analysis(self):
        """Print analysis results"""
        print("\n📊 Test Distribution Analysis")
        print("=" * 50)

        print(f"\nTotal test files: {len(self.test_files)}")
        print(f"Total test count: {sum(t.test_count for t in self.test_files)}")

        print("\n🏷️  Marker Distribution:")
        for marker, count in sorted(self.marker_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  {marker:20} {count:4} files")

        print("\n📦 Domain Distribution:")
        for domain, count in sorted(self.domain_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  {domain:20} {count:4} files")

    def print_job_recommendations(self, jobs: list[JobConfig]):
        """Print job configuration recommendations"""
        print("\n🚀 Recommended CI Job Configuration")
        print("=" * 50)

        for i, job in enumerate(jobs, 1):
            print(f"\n{i}. {job.name}")
            print(f"   Description: {job.description}")
            print(f"   Command: {job.pytest_command}")
            print(f"   Estimated Runtime: {job.estimated_runtime:.1f}s")
            print(f"   Test Count: ~{job.test_count} tests")
            print(f"   Parallel Workers: {job.parallel_workers}")

    def generate_github_actions_yaml(self, jobs: list[JobConfig]) -> str:
        """Generate GitHub Actions job definitions"""
        yaml_content = """
# Optimized CI Job Structure
# Generated by ci_job_optimizer.py

jobs:
"""

        for job in jobs:
            job_id = job.name.replace("-", "_")
            yaml_content += f"""
  {job_id}:
    name: {job.description}
    runs-on: ubuntu-latest
    timeout-minutes: {max(10, int(job.estimated_runtime / 60) + 5)}
    
    steps:
    - name: Run {job.name} tests
      run: |
        {job.pytest_command}
"""

        return yaml_content

    def generate_makefile_targets(self, jobs: list[JobConfig]) -> str:
        """Generate Makefile targets for local testing"""
        makefile_content = """
# CI Job Test Targets
# Generated by ci_job_optimizer.py

"""

        for job in jobs:
            target_name = job.name.replace("-", "_")
            makefile_content += f"""
.PHONY: test-{target_name}
test-{target_name}:  ## Run {job.description}
\t@echo "🧪 Running {job.name} tests..."
\t{job.pytest_command}

"""

        return makefile_content


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Analyze test distribution and optimize CI jobs")
    parser.add_argument("--test-root", default="tests", help="Root directory for tests")
    parser.add_argument("--output-yaml", action="store_true", help="Output GitHub Actions YAML")
    parser.add_argument("--output-makefile", action="store_true", help="Output Makefile targets")
    parser.add_argument("--json", action="store_true", help="Output analysis as JSON")

    args = parser.parse_args()

    optimizer = CIJobOptimizer(args.test_root)
    optimizer.analyze_tests()

    if args.json:
        # Output JSON analysis
        analysis = {
            "total_files": len(optimizer.test_files),
            "total_tests": sum(t.test_count for t in optimizer.test_files),
            "marker_stats": dict(optimizer.marker_stats),
            "domain_stats": dict(optimizer.domain_stats),
        }
        print(json.dumps(analysis, indent=2))
    else:
        optimizer.print_analysis()

        jobs = optimizer.generate_job_configs()
        optimizer.print_job_recommendations(jobs)

        if args.output_yaml:
            print("\n📄 GitHub Actions YAML:")
            print(optimizer.generate_github_actions_yaml(jobs))

        if args.output_makefile:
            print("\n📄 Makefile Targets:")
            print(optimizer.generate_makefile_targets(jobs))

        print("\n💡 Benefits of Job Separation:")
        print("  ✅ Faster feedback on critical tests (< 1 minute)")
        print("  ✅ Parallel execution reduces total CI time")
        print("  ✅ Easier to identify and debug failures")
        print("  ✅ Can retry individual job types")
        print("  ✅ Better resource utilization")


if __name__ == "__main__":
    main()
