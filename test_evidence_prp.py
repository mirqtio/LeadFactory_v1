#!/usr/bin/env python3
"""
Create a test PRP to validate EVIDENCE_COMPLETE footer protocol
"""

import json
import os
import subprocess
from datetime import datetime


def create_test_prp():
    """Create a test PRP in Redis for evidence protocol testing"""

    prp_id = "TEST-EVIDENCE-001"

    # Test PRP data
    test_prp = {
        "id": prp_id,
        "title": "Test EVIDENCE_COMPLETE Footer Protocol",
        "description": "Simple test to validate evidence footer detection and promotion",
        "priority_stage": "dev",
        "status": "queued",
        "retry_count": "0",
        "added_at": datetime.utcnow().isoformat(),
        "test_task": "Create a simple text file with content and validate it works",
        "acceptance_criteria": [
            "File created successfully",
            "Content matches expected",
            "Evidence footer provided with proper JSON",
        ],
        "estimated_effort": "5 minutes",
        "complexity": "simple",
    }

    # Get Redis URL from environment or use default
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    print(f"🧪 Creating test PRP: {prp_id}")

    # Store PRP data in Redis hash
    prp_key = f"prp:{prp_id}"
    for field, value in test_prp.items():
        if isinstance(value, list):
            value = json.dumps(value)

        result = subprocess.run(
            ["redis-cli", "-u", redis_url, "HSET", prp_key, field, str(value)], capture_output=True, text=True
        )

        if result.returncode != 0:
            print(f"❌ Failed to set {field}: {result.stderr}")
            return False

    # Queue the PRP for development
    queue_result = subprocess.run(
        ["redis-cli", "-u", redis_url, "LPUSH", "dev_queue", prp_id], capture_output=True, text=True
    )

    if queue_result.returncode != 0:
        print(f"❌ Failed to queue PRP: {queue_result.stderr}")
        return False

    print(f"✅ Test PRP {prp_id} created and queued to dev_queue")

    # Verify it's in the queue
    check_result = subprocess.run(["redis-cli", "-u", redis_url, "LLEN", "dev_queue"], capture_output=True, text=True)

    queue_length = check_result.stdout.strip()
    print(f"📊 Dev queue length: {queue_length}")

    return True


def check_prp_status(prp_id):
    """Check the current status and evidence of a PRP"""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    prp_key = f"prp:{prp_id}"

    # Get all PRP data
    result = subprocess.run(["redis-cli", "-u", redis_url, "HGETALL", prp_key], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Failed to get PRP data: {result.stderr}")
        return

    # Parse the key-value pairs
    lines = result.stdout.strip().split("\n")
    prp_data = {}
    for i in range(0, len(lines), 2):
        if i + 1 < len(lines):
            key = lines[i]
            value = lines[i + 1]
            prp_data[key] = value

    print(f"\n📋 PRP {prp_id} Status:")
    print("=" * 40)

    # Show key fields
    important_fields = ["status", "stage", "success", "agent_id", "completed_at"]
    for field in important_fields:
        if field in prp_data:
            print(f"{field}: {prp_data[field]}")

    # Show evidence keys
    evidence_keys = [k for k in prp_data.keys() if k in ["tests_passed", "lint_clean", "coverage_pct", "file_created"]]
    if evidence_keys:
        print(f"\nEvidence keys: {', '.join(evidence_keys)}")

    return prp_data


def main():
    """Main test runner"""
    print("🚀 EVIDENCE_COMPLETE Footer Protocol Test")
    print("=" * 50)

    # Create test PRP
    if not create_test_prp():
        return False

    print("\n📝 Test Instructions:")
    print("1. The test PRP has been queued to dev_queue")
    print("2. A dev agent should pick it up automatically")
    print("3. The agent should complete the simple task:")
    print("   - Create a text file with test content")
    print("   - Validate the file exists and has correct content")
    print("   - Use EVIDENCE_COMPLETE footer with proper JSON")
    print("4. The enterprise shim should detect the footer and promote the PRP")
    print("\n💡 Expected footer format:")
    print('EVIDENCE_COMPLETE {"stage":"dev","success":true,"keys":["file_created","content_validated"]}')

    print(f"\n🔍 Monitor the process:")
    print("- Watch tmux session: tmux attach-session -t leadstack")
    print("- Check logs: tail -f /tmp/dev1_shim.log")
    print("- Check PRP status: python3 test_evidence_prp.py status")

    return True


if __name__ == "__main__":
    if len(os.sys.argv) > 1 and os.sys.argv[1] == "status":
        check_prp_status("TEST-EVIDENCE-001")
    else:
        success = main()
        exit(0 if success else 1)
