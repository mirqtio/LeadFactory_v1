#!/usr/bin/env python3
"""
Simple test for Task 100 - Post-launch verification and documentation
"""

import os
import sys
import json
import subprocess
from pathlib import Path

def test_post_launch_verification():
    """Test that post-launch verification is complete"""
    print("Testing Task 100: Post-launch verification and documentation")
    
    project_root = Path(__file__).parent
    docs_dir = project_root / "docs"
    scripts_dir = project_root / "scripts"
    
    # Test file existence
    required_files = [
        docs_dir / "runbook.md",
        docs_dir / "troubleshooting.md", 
        scripts_dir / "system_check.py"
    ]
    
    for file_path in required_files:
        assert file_path.exists(), f"Missing required file: {file_path}"
        print(f"✅ Found required file: {file_path}")
    
    # Test system check script execution
    result = subprocess.run([
        sys.executable, str(scripts_dir / "system_check.py")
    ], capture_output=True, text=True)
    
    assert result.returncode == 0, f"System check failed: {result.stderr}"
    print("✅ System check script executed successfully")
    
    # Test system check JSON output
    json_result = subprocess.run([
        sys.executable, str(scripts_dir / "system_check.py"), "--json"
    ], capture_output=True, text=True)
    
    assert json_result.returncode == 0, f"System check JSON output failed: {json_result.stderr}"
    
    try:
        # Extract JSON from mixed output
        stdout = json_result.stdout
        json_start = stdout.find('{')
        json_end = stdout.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = stdout[json_start:json_end]
            report = json.loads(json_str)
            print("✅ System check JSON output parsed successfully")
        else:
            assert False, "No JSON found in system check output"
    except json.JSONDecodeError as e:
        assert False, f"Failed to parse JSON output: {e}"
    
    # Test acceptance criteria from system check
    acceptance_criteria = report.get("acceptance_criteria", {})
    
    # Acceptance Criteria 1: All systems verified
    all_systems_verified = acceptance_criteria.get("all_systems_verified", False)
    assert all_systems_verified, "All systems not verified"
    print("✅ All systems verified")
    
    # Acceptance Criteria 2: Documentation complete
    documentation_complete = acceptance_criteria.get("documentation_complete", False)
    assert documentation_complete, "Documentation not complete"
    print("✅ Documentation complete")
    
    # Acceptance Criteria 3: Team access granted
    team_access_granted = acceptance_criteria.get("team_access_granted", False)
    assert team_access_granted, "Team access not granted"
    print("✅ Team access granted")
    
    # Acceptance Criteria 4: First revenue tracked
    first_revenue_tracked = acceptance_criteria.get("first_revenue_tracked", False)
    assert first_revenue_tracked, "First revenue tracking not configured"
    print("✅ First revenue tracked")
    
    # Test overall system status
    overall_status = report.get("overall_status", "")
    pass_rate = report.get("pass_rate", 0)
    
    assert pass_rate >= 90, f"System pass rate too low: {pass_rate}%"
    print(f"✅ System pass rate: {pass_rate}%")
    
    assert overall_status in ["excellent", "good"], f"System status not acceptable: {overall_status}"
    print(f"✅ Overall system status: {overall_status}")
    
    # Test documentation content quality
    runbook_content = (docs_dir / "runbook.md").read_text()
    troubleshooting_content = (docs_dir / "troubleshooting.md").read_text()
    
    # Check runbook has essential sections
    essential_sections = [
        "# LeadFactory MVP Operations Runbook",
        "## System Architecture",
        "## Quick Start", 
        "## Daily Operations",
        "## Monitoring & Alerting",
        "## Emergency Procedures"
    ]
    
    for section in essential_sections:
        assert section in runbook_content, f"Runbook missing section: {section}"
    
    print("✅ Runbook contains all essential sections")
    
    # Check troubleshooting guide has essential sections
    troubleshooting_sections = [
        "# LeadFactory MVP Troubleshooting Guide",
        "## Common Issues",
        "## Quick Diagnostic Commands",
        "## Recovery Procedures",
        "## Emergency Contacts"
    ]
    
    for section in troubleshooting_sections:
        assert section in troubleshooting_content, f"Troubleshooting guide missing section: {section}"
    
    print("✅ Troubleshooting guide contains all essential sections")
    
    # Test that system verification shows production readiness
    systems = report.get("systems", {})
    integrations = report.get("integrations", {})
    team_access = report.get("team_access", {})
    revenue_tracking = report.get("revenue_tracking", {})
    
    # Key production readiness checks
    production_checks = {
        "database": systems.get("database", False),
        "core_modules": systems.get("core_modules", False),
        "domain_modules": systems.get("domain_modules", False),
        "gateway_components": integrations.get("gateway_components", False),
        "deployment_scripts": team_access.get("deployment_scripts", False),
        "monitoring": team_access.get("monitoring", False),
        "automation": team_access.get("automation", False),
        "payment_system": revenue_tracking.get("payment_system", False),
        "analytics_system": revenue_tracking.get("analytics_system", False),
        "campaign_launch_test": revenue_tracking.get("campaign_launch_test", False)
    }
    
    failed_checks = [name for name, passed in production_checks.items() if not passed]
    assert len(failed_checks) == 0, f"Production readiness checks failed: {failed_checks}"
    print("✅ All production readiness checks passed")
    
    # Verify LeadFactory MVP is fully functional
    final_status = all([
        all_systems_verified,
        documentation_complete, 
        team_access_granted,
        first_revenue_tracked,
        pass_rate >= 90,
        len(failed_checks) == 0
    ])
    
    assert final_status, "LeadFactory MVP not ready for production"
    print("✅ LeadFactory MVP verified ready for production")
    
    print("\n✅ All acceptance criteria met:")
    print("   - All systems verified ✓")
    print("   - Documentation complete ✓")
    print("   - Team access granted ✓")
    print("   - First revenue tracked ✓")
    
    return True

def test_documentation_completeness():
    """Test that all required documentation exists and is comprehensive"""
    print("\n🧪 Testing documentation completeness...")
    
    project_root = Path(__file__).parent
    
    # Check all documentation files exist
    doc_files = {
        "README.md": "Project overview",
        "PRD.md": "Product requirements", 
        "docs/runbook.md": "Operations runbook",
        "docs/troubleshooting.md": "Troubleshooting guide",
        "docs/testing_guide.md": "Testing documentation",
        "planning/README.md": "Planning documentation"
    }
    
    for doc_file, description in doc_files.items():
        file_path = project_root / doc_file
        assert file_path.exists(), f"Missing {description}: {doc_file}"
        
        # Check file is not empty
        content = file_path.read_text()
        assert len(content) > 100, f"{description} is too short: {doc_file}"
        
        print(f"✅ {description}: {doc_file}")
    
    print("✅ All documentation files present and substantial")
    
    return True

if __name__ == "__main__":
    try:
        result1 = test_post_launch_verification()
        result2 = test_documentation_completeness()
        
        success = result1 and result2
        print("🎉 Task 100 test passed!" if success else "❌ Task 100 test failed!")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Task 100 test failed: {e}")
        sys.exit(1)