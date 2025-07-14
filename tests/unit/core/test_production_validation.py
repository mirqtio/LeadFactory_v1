"""
Test production environment validation
Ensures production never runs with stubs
"""
import os
import subprocess
import sys


def test_production_rejects_stubs():
    """Test that production environment rejects USE_STUBS=true at startup"""
    # Create a Python script that tries to initialize settings with production + stubs
    test_script = """
import sys
from core.config import get_settings

try:
    # Force production environment with stubs
    import os
    os.environ["ENVIRONMENT"] = "production"
    os.environ["USE_STUBS"] = "true"
    
    # Clear cache to ensure environment changes are picked up
    get_settings.cache_clear()
    
    settings = get_settings()
    print("ERROR: Production accepted USE_STUBS=true")
    sys.exit(1)
except Exception as e:
    if "Production environment cannot run with USE_STUBS=true" in str(e):
        print("SUCCESS: Production rejected USE_STUBS=true")
        sys.exit(0)
    else:
        print(f"ERROR: Unexpected error: {e}")
        sys.exit(2)
"""

    # Run the script in a subprocess to test actual startup behavior
    result = subprocess.run(
        [sys.executable, "-c", test_script],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": os.getcwd()},
    )

    assert result.returncode == 0, f"Production validation failed: {result.stderr}"
    assert "SUCCESS" in result.stdout
