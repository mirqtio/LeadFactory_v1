#!/usr/bin/env python3
"""
Wait for stub server to be ready
"""
import os
import sys
import time

import requests


def wait_for_stub_server(url=None, max_retries=30, delay=1):
    """Wait for stub server to be ready"""
    if url is None:
        # Use environment variable or default based on CI environment
        stub_base_url = os.environ.get("STUB_BASE_URL", "http://localhost:5010")
        url = f"{stub_base_url}/health"

    print(f"Waiting for stub server at {url}...")

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ Stub server is ready after {attempt + 1} attempts")
                return True
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1}/{max_retries}: {e}")

        if attempt < max_retries - 1:
            time.sleep(delay)

    print("❌ Stub server failed to start")
    return False


if __name__ == "__main__":
    if not wait_for_stub_server():
        sys.exit(1)
