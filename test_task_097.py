#!/usr/bin/env python3
"""
Simple test for Task 097 - Setup daily cron jobs
"""

import os
import sys
import subprocess
from pathlib import Path

def test_cron_scripts():
    """Test that the cron scripts exist and are executable"""
    print("Testing Task 097: Setup daily cron jobs")
    
    project_root = Path(__file__).parent
    cron_dir = project_root / "cron"
    
    # Required files
    required_files = [
        "daily_pipeline.sh",
        "cleanup.sh", 
        "backup.sh",
        "crontab.example",
        "logrotate.conf"
    ]
    
    # Test file existence
    for filename in required_files:
        file_path = cron_dir / filename
        assert file_path.exists(), f"Missing file: {file_path}"
        print(f"✅ Found: {filename}")
    
    # Test script executability
    script_files = ["daily_pipeline.sh", "cleanup.sh", "backup.sh"]
    for script in script_files:
        script_path = cron_dir / script
        assert os.access(script_path, os.X_OK), f"Script not executable: {script}"
        print(f"✅ Executable: {script}")
    
    # Test script syntax
    for script in script_files:
        script_path = cron_dir / script
        result = subprocess.run(["bash", "-n", str(script_path)], 
                              capture_output=True, text=True)
        assert result.returncode == 0, f"Syntax error in {script}: {result.stderr}"
        print(f"✅ Syntax OK: {script}")
    
    # Test crontab format
    crontab_path = cron_dir / "crontab.example"
    with open(crontab_path, 'r') as f:
        content = f.read()
        
    # Check for required cron job patterns
    required_patterns = [
        "0 1 * * *",  # Backup at 1 AM
        "0 2 * * *",  # Pipeline at 2 AM  
        "0 3 * * *",  # Cleanup at 3 AM
        "daily_pipeline.sh",
        "cleanup.sh",
        "backup.sh"
    ]
    
    for pattern in required_patterns:
        assert pattern in content, f"Missing pattern in crontab: {pattern}"
        print(f"✅ Crontab contains: {pattern}")
    
    # Test logrotate configuration
    logrotate_path = cron_dir / "logrotate.conf"
    with open(logrotate_path, 'r') as f:
        logrotate_content = f.read()
    
    logrotate_patterns = [
        "daily",
        "rotate",
        "compress",
        "/opt/leadfactory/logs/*.log"
    ]
    
    for pattern in logrotate_patterns:
        assert pattern in logrotate_content, f"Missing pattern in logrotate: {pattern}"
        print(f"✅ Logrotate contains: {pattern}")
    
    print("\n✅ All acceptance criteria met:")
    print("   - Pipeline scheduled ✓ (Daily at 2 AM UTC)")
    print("   - Cleanup configured ✓ (Daily at 3 AM UTC)")  
    print("   - Backups automated ✓ (Daily at 1 AM UTC)")
    print("   - Logs rotated ✓ (Via logrotate configuration)")
    
    return True

if __name__ == "__main__":
    try:
        result = test_cron_scripts()
        print("🎉 Task 097 test passed!" if result else "❌ Task 097 test failed!")
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"❌ Task 097 test failed: {e}")
        sys.exit(1)