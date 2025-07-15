#!/usr/bin/env python3
"""
Debug script to test stub server startup and connectivity
Useful for troubleshooting CI issues
"""
import os
import subprocess
import sys
import threading
import time

import requests


def start_stub_server():
    """Start the stub server in a subprocess"""
    print("Starting stub server...")
    env = os.environ.copy()
    env["USE_STUBS"] = "true"
    env["ENVIRONMENT"] = "test"

    try:
        # Start uvicorn in subprocess
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "stubs.server:app", "--host", "127.0.0.1", "--port", "5010"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Give it time to start
        time.sleep(2)

        # Check if process is still running
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"Stub server failed to start!")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return None

        return process
    except Exception as e:
        print(f"Error starting stub server: {e}")
        return None


def test_stub_server():
    """Test stub server connectivity"""
    print("\nTesting stub server connectivity...")

    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            response = requests.get("http://localhost:5010/health", timeout=2)
            if response.status_code == 200:
                print(f"✅ Stub server is healthy! Response: {response.json()}")
                return True
        except requests.exceptions.ConnectionError:
            print(f"❌ Attempt {attempt + 1}/{max_attempts}: Connection refused")
        except Exception as e:
            print(f"❌ Attempt {attempt + 1}/{max_attempts}: {type(e).__name__}: {e}")

        time.sleep(1)

    return False


def check_port_availability():
    """Check if port 5010 is available"""
    import socket

    print("\nChecking port 5010 availability...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", 5010))
    sock.close()

    if result == 0:
        print("❌ Port 5010 is already in use!")
        # Try to find what's using it
        try:
            output = subprocess.check_output(["lsof", "-i", ":5010"], text=True)
            print(f"Process using port 5010:\n{output}")
        except:
            pass
        return False
    else:
        print("✅ Port 5010 is available")
        return True


def check_dependencies():
    """Check if all required dependencies are installed"""
    print("\nChecking dependencies...")

    required_modules = ["fastapi", "uvicorn", "pydantic", "requests"]

    missing = []
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module} is installed")
        except ImportError:
            print(f"❌ {module} is NOT installed")
            missing.append(module)

    return len(missing) == 0


def main():
    """Main debug routine"""
    print("=== Stub Server Debug Script ===")

    # Check environment
    print("\nEnvironment variables:")
    print(f"USE_STUBS: {os.environ.get('USE_STUBS', 'not set')}")
    print(f"ENVIRONMENT: {os.environ.get('ENVIRONMENT', 'not set')}")
    print(f"CI: {os.environ.get('CI', 'not set')}")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'not set')}")

    # Check dependencies
    if not check_dependencies():
        print("\n❌ Missing dependencies! Install them with: pip install -r requirements.txt")
        sys.exit(1)

    # Check port
    if not check_port_availability():
        print("\n❌ Port 5010 is not available!")
        sys.exit(1)

    # Start stub server
    process = start_stub_server()
    if not process:
        print("\n❌ Failed to start stub server!")
        sys.exit(1)

    try:
        # Test connectivity
        if test_stub_server():
            print("\n✅ Stub server is working correctly!")

            # Test a few endpoints
            print("\nTesting stub endpoints:")
            test_endpoints = [
                "/health",
                "/maps/api/place/findplacefromtext/json?input=test&inputtype=textquery&key=test",
                "/pagespeedonline/v5/runPagespeed?url=https://example.com",
            ]

            for endpoint in test_endpoints:
                try:
                    response = requests.get(f"http://localhost:5010{endpoint}", timeout=2)
                    print(f"✅ {endpoint}: {response.status_code}")
                except Exception as e:
                    print(f"❌ {endpoint}: {e}")
        else:
            print("\n❌ Stub server is not responding!")
            sys.exit(1)

    finally:
        # Clean up
        if process:
            print("\nStopping stub server...")
            process.terminate()
            process.wait(timeout=5)
            print("Stub server stopped")


if __name__ == "__main__":
    main()
