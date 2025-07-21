#!/usr/bin/env python3
"""
PRP-1060 Simple Validation Script

Simplified validation script for PRP-1060 that avoids complex imports
and focuses on file-based validation.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


class PRP1060SimpleValidator:
    """Simplified PRP-1060 validation system."""

    def __init__(self):
        self.validation_results = {}
        self.score = 0
        self.max_score = 100
        self.project_root = Path(__file__).parent.parent

    def run_validation(self) -> Dict[str, Any]:
        """Run complete PRP-1060 validation."""
        print("🚀 Starting PRP-1060 Simple Validation")
        print("=" * 60)

        start_time = time.time()

        # Component validations
        validations = [
            ("Profile System", self.validate_profile_system),
            ("Container System", self.validate_container_system),
            ("Evidence System", self.validate_evidence_system),
            ("Deployment System", self.validate_deployment_system),
            ("Integration Files", self.validate_integration_files),
            ("GitHub Actions", self.validate_github_actions),
            ("Documentation", self.validate_documentation),
            ("Requirements", self.validate_requirements),
        ]

        for component_name, validator in validations:
            print(f"\n📋 Validating {component_name}...")
            try:
                result = validator()
                self.validation_results[component_name] = result
                self.score += result.get("score", 0)

                status = "✅ PASS" if result.get("passed", False) else "❌ FAIL"
                score = result.get("score", 0)
                max_score = result.get("max_score", 0)
                print(f"   {status} - {score}/{max_score} points")

                # Show details
                for detail in result.get("details", []):
                    print(f"     {detail}")

            except Exception as e:
                print(f"   ❌ ERROR - {str(e)}")
                self.validation_results[component_name] = {
                    "passed": False,
                    "score": 0,
                    "max_score": 12,
                    "error": str(e),
                }

        # Overall results
        duration = time.time() - start_time
        overall_passed = self.score >= 80  # 80% threshold

        final_results = {
            "overall_passed": overall_passed,
            "total_score": self.score,
            "max_score": self.max_score,
            "percentage": round((self.score / self.max_score) * 100, 2),
            "duration_seconds": round(duration, 2),
            "validation_results": self.validation_results,
            "prp_id": "PRP-1060",
            "validation_timestamp": time.time(),
        }

        self.print_summary(final_results)
        return final_results

    def validate_profile_system(self) -> Dict[str, Any]:
        """Validate SuperClaude profile system."""
        result = {"passed": False, "score": 0, "max_score": 15, "details": []}

        # Check profiles directory
        profiles_dir = self.project_root / "profiles"
        if profiles_dir.exists():
            result["details"].append("✅ profiles/ directory found")
            result["score"] += 2
        else:
            result["details"].append("❌ profiles/ directory not found")
            return result

        # Check ProfileLoader
        profile_init = profiles_dir / "__init__.py"
        if profile_init.exists():
            content = profile_init.read_text()
            if "class ProfileLoader" in content:
                result["details"].append("✅ ProfileLoader class found")
                result["score"] += 3
            else:
                result["details"].append("❌ ProfileLoader class not found")
        else:
            result["details"].append("❌ profiles/__init__.py not found")

        # Check acceptance.yaml
        acceptance_profile = profiles_dir / "acceptance.yaml"
        if acceptance_profile.exists():
            result["details"].append("✅ acceptance.yaml profile found")
            result["score"] += 3

            try:
                import yaml

                with open(acceptance_profile, "r") as f:
                    profile_data = yaml.safe_load(f)

                required_fields = ["name", "description", "command", "workflow"]
                for field in required_fields:
                    if field in profile_data:
                        result["details"].append(f"✅ Profile field '{field}' present")
                        result["score"] += 1
                    else:
                        result["details"].append(f"❌ Profile field '{field}' missing")

                # Check workflow steps
                if "workflow" in profile_data and "steps" in profile_data["workflow"]:
                    steps = profile_data["workflow"]["steps"]
                    step_names = [step.get("name") for step in steps if isinstance(step, dict)]

                    required_steps = ["setup", "test_execution", "evidence_validation"]
                    for step_name in required_steps:
                        if step_name in step_names:
                            result["details"].append(f"✅ Workflow step '{step_name}' found")
                            result["score"] += 1
                        else:
                            result["details"].append(f"❌ Workflow step '{step_name}' missing")

            except Exception as e:
                result["details"].append(f"❌ Error parsing acceptance.yaml: {e}")
        else:
            result["details"].append("❌ acceptance.yaml profile not found")

        result["passed"] = result["score"] >= 12  # 80% of max score
        return result

    def validate_container_system(self) -> Dict[str, Any]:
        """Validate container system components."""
        result = {"passed": False, "score": 0, "max_score": 15, "details": []}

        # Check containers directory
        containers_dir = self.project_root / "containers" / "acceptance"
        if containers_dir.exists():
            result["details"].append("✅ containers/acceptance/ directory found")
            result["score"] += 2
        else:
            result["details"].append("❌ containers/acceptance/ directory not found")
            return result

        # Check Dockerfile
        dockerfile = containers_dir / "Dockerfile"
        if dockerfile.exists():
            result["details"].append("✅ Dockerfile found")
            result["score"] += 3

            content = dockerfile.read_text()
            if "FROM python:" in content:
                result["details"].append("✅ Dockerfile uses Python base")
                result["score"] += 1
            if "USER acceptance" in content or "RUN useradd" in content:
                result["details"].append("✅ Dockerfile uses non-root user")
                result["score"] += 2
            if "WORKDIR /workspace" in content:
                result["details"].append("✅ Dockerfile sets workspace")
                result["score"] += 1
        else:
            result["details"].append("❌ Dockerfile not found")

        # Check acceptance_runner.py
        runner_file = containers_dir / "acceptance_runner.py"
        if runner_file.exists():
            result["details"].append("✅ acceptance_runner.py found")
            result["score"] += 3

            content = runner_file.read_text()
            if "class AcceptanceRunner" in content:
                result["details"].append("✅ AcceptanceRunner class found")
                result["score"] += 2
            if "run_full_workflow" in content:
                result["details"].append("✅ Workflow orchestration found")
                result["score"] += 1
        else:
            result["details"].append("❌ acceptance_runner.py not found")

        # Check requirements.txt
        requirements_file = containers_dir / "requirements.txt"
        if requirements_file.exists():
            result["details"].append("✅ Container requirements.txt found")
            result["score"] += 1
        else:
            result["details"].append("❌ Container requirements.txt not found")

        result["passed"] = result["score"] >= 12  # 80% of max score
        return result

    def validate_evidence_system(self) -> Dict[str, Any]:
        """Validate evidence collection and validation system."""
        result = {"passed": False, "score": 0, "max_score": 12, "details": []}

        # Check deployment directory
        deployment_dir = self.project_root / "deployment"
        if deployment_dir.exists():
            result["details"].append("✅ deployment/ directory found")
            result["score"] += 1
        else:
            result["details"].append("❌ deployment/ directory not found")
            return result

        # Check evidence_validator.py
        evidence_file = deployment_dir / "evidence_validator.py"
        if evidence_file.exists():
            result["details"].append("✅ evidence_validator.py found")
            result["score"] += 3

            content = evidence_file.read_text()
            if "class EvidenceValidator" in content:
                result["details"].append("✅ EvidenceValidator class found")
                result["score"] += 2
            if "collect_evidence" in content:
                result["details"].append("✅ Evidence collection method found")
                result["score"] += 1
            if "validate_acceptance_evidence" in content:
                result["details"].append("✅ Acceptance evidence validation found")
                result["score"] += 2
            if "validate_deployment_evidence" in content:
                result["details"].append("✅ Deployment evidence validation found")
                result["score"] += 2
            if "trigger_prp_promotion" in content:
                result["details"].append("✅ PRP promotion integration found")
                result["score"] += 1
        else:
            result["details"].append("❌ evidence_validator.py not found")

        result["passed"] = result["score"] >= 10  # 80% of max score
        return result

    def validate_deployment_system(self) -> Dict[str, Any]:
        """Validate deployment and health checking system."""
        result = {"passed": False, "score": 0, "max_score": 12, "details": []}

        deployment_dir = self.project_root / "deployment"

        # Check ssh_deployer.py
        ssh_file = deployment_dir / "ssh_deployer.py"
        if ssh_file.exists():
            result["details"].append("✅ ssh_deployer.py found")
            result["score"] += 3

            content = ssh_file.read_text()
            if "class SSHDeployer" in content:
                result["details"].append("✅ SSHDeployer class found")
                result["score"] += 2
            if "paramiko" in content:
                result["details"].append("✅ SSH client integration found")
                result["score"] += 1
        else:
            result["details"].append("❌ ssh_deployer.py not found")

        # Check health_checker.py
        health_file = deployment_dir / "health_checker.py"
        if health_file.exists():
            result["details"].append("✅ health_checker.py found")
            result["score"] += 3

            content = health_file.read_text()
            if "class HealthChecker" in content:
                result["details"].append("✅ HealthChecker class found")
                result["score"] += 2
            if "run_all_checks" in content:
                result["details"].append("✅ Comprehensive health checking found")
                result["score"] += 1
        else:
            result["details"].append("❌ health_checker.py not found")

        result["passed"] = result["score"] >= 10  # 80% of max score
        return result

    def validate_integration_files(self) -> Dict[str, Any]:
        """Validate integration files and core integration."""
        result = {"passed": False, "score": 0, "max_score": 15, "details": []}

        # Check acceptance_integration.py
        integration_file = self.project_root / "core" / "acceptance_integration.py"
        if integration_file.exists():
            result["details"].append("✅ acceptance_integration.py found")
            result["score"] += 4

            content = integration_file.read_text()
            if "class AcceptanceIntegrator" in content:
                result["details"].append("✅ AcceptanceIntegrator class found")
                result["score"] += 3
            if "extended_integration_validation" in content:
                result["details"].append("✅ Extended validation function found")
                result["score"] += 2
        else:
            result["details"].append("❌ acceptance_integration.py not found")

        # Check integration tests
        test_file = self.project_root / "tests" / "integration" / "test_acceptance_pipeline.py"
        if test_file.exists():
            result["details"].append("✅ Integration test suite found")
            result["score"] += 3

            content = test_file.read_text()
            if "TestEndToEndIntegration" in content:
                result["details"].append("✅ End-to-end tests found")
                result["score"] += 2
            if "TestPerformanceValidation" in content:
                result["details"].append("✅ Performance tests found")
                result["score"] += 1
        else:
            result["details"].append("❌ Integration test suite not found")

        result["passed"] = result["score"] >= 12  # 80% of max score
        return result

    def validate_github_actions(self) -> Dict[str, Any]:
        """Validate GitHub Actions workflow."""
        result = {"passed": False, "score": 0, "max_score": 10, "details": []}

        # Check GitHub Actions workflow
        workflow_file = self.project_root / ".github" / "workflows" / "build-acceptance-container.yml"
        if workflow_file.exists():
            result["details"].append("✅ GitHub Actions workflow found")
            result["score"] += 4

            content = workflow_file.read_text()
            if "ghcr.io" in content:
                result["details"].append("✅ GHCR registry configuration found")
                result["score"] += 2
            if "build-and-push" in content:
                result["details"].append("✅ Container build job found")
                result["score"] += 2
            if "trivy" in content:
                result["details"].append("✅ Security scanning found")
                result["score"] += 2
        else:
            result["details"].append("❌ GitHub Actions workflow not found")

        result["passed"] = result["score"] >= 8  # 80% of max score
        return result

    def validate_documentation(self) -> Dict[str, Any]:
        """Validate documentation completeness."""
        result = {"passed": False, "score": 0, "max_score": 10, "details": []}

        # Check for docstrings in main files
        files_to_check = [
            "core/acceptance_integration.py",
            "deployment/evidence_validator.py",
            "deployment/ssh_deployer.py",
            "deployment/health_checker.py",
            "containers/acceptance/acceptance_runner.py",
        ]

        documented_files = 0
        for file_path in files_to_check:
            full_path = self.project_root / file_path
            if full_path.exists():
                content = full_path.read_text()
                if '"""' in content and "class " in content:
                    result["details"].append(f"✅ {file_path} has docstrings")
                    documented_files += 1
                    result["score"] += 2
                else:
                    result["details"].append(f"⚠️ {file_path} needs better docstrings")
                    result["score"] += 1
            else:
                result["details"].append(f"❌ {file_path} not found")

        result["passed"] = result["score"] >= 8  # 80% of max score
        return result

    def validate_requirements(self) -> Dict[str, Any]:
        """Validate requirements and dependencies."""
        result = {"passed": False, "score": 0, "max_score": 11, "details": []}

        # Check main requirements.txt
        requirements_file = self.project_root / "requirements.txt"
        if requirements_file.exists():
            result["details"].append("✅ requirements.txt found")
            result["score"] += 2

            content = requirements_file.read_text()
            required_deps = ["paramiko", "docker", "redis", "pydantic", "httpx"]

            for dep in required_deps:
                if dep in content:
                    result["details"].append(f"✅ {dep} dependency found")
                    result["score"] += 1
                else:
                    result["details"].append(f"❌ {dep} dependency missing")
        else:
            result["details"].append("❌ requirements.txt not found")

        # Check container requirements
        container_reqs = self.project_root / "containers" / "acceptance" / "requirements.txt"
        if container_reqs.exists():
            result["details"].append("✅ Container requirements.txt found")
            result["score"] += 2
        else:
            result["details"].append("❌ Container requirements.txt not found")

        # Check if unit tests exist
        unit_test_file = self.project_root / "tests" / "unit" / "acceptance" / "test_acceptance_profile.py"
        if unit_test_file.exists():
            result["details"].append("✅ Unit tests found")
            result["score"] += 2
        else:
            result["details"].append("❌ Unit tests not found")

        result["passed"] = result["score"] >= 9  # 80% of max score
        return result

    def print_summary(self, results: Dict[str, Any]):
        """Print validation summary."""
        print("\n" + "=" * 60)
        print("📊 PRP-1060 VALIDATION SUMMARY")
        print("=" * 60)

        status = "✅ PASS" if results["overall_passed"] else "❌ FAIL"
        print(f"Overall Status: {status}")
        print(f"Score: {results['total_score']}/{results['max_score']} ({results['percentage']}%)")
        print(f"Duration: {results['duration_seconds']}s")

        print("\n📋 Component Scores:")
        for component, result in results["validation_results"].items():
            status = "✅" if result.get("passed", False) else "❌"
            score = result.get("score", 0)
            max_score = result.get("max_score", 0)
            print(f"  {status} {component}: {score}/{max_score}")

        print("\n🎯 Requirements Status:")
        print(f"  {'✅' if results['percentage'] >= 80 else '❌'} Minimum 80% score: {results['percentage']}%")
        print(f"  {'✅' if results['total_score'] >= 80 else '❌'} Feature completeness: {results['total_score']}/100")

        if not results["overall_passed"]:
            print("\n🔧 Action Items:")
            for component, result in results["validation_results"].items():
                if not result.get("passed", False):
                    print(f"  • Fix {component} ({result.get('score', 0)}/{result.get('max_score', 0)} points)")
        else:
            print("\n🎉 All requirements met! PRP-1060 is ready for deployment.")

        print("=" * 60)


def main():
    """Main validation entry point."""
    validator = PRP1060SimpleValidator()
    results = validator.run_validation()

    # Save results to file
    results_file = Path(__file__).parent.parent / "prp_1060_validation_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n💾 Results saved to: {results_file}")

    # Exit with appropriate code
    sys.exit(0 if results["overall_passed"] else 1)


if __name__ == "__main__":
    main()
