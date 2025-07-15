#!/usr/bin/env python3
"""
Network debugging script for Docker container networking issues
"""
import os
import socket
import subprocess
from urllib.parse import urlparse

import requests


def run_command(cmd, timeout=10):
    """Run a shell command and return the output"""
    try:
        result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def check_dns_resolution(hostname):
    """Check if hostname can be resolved"""
    try:
        ip = socket.gethostbyname(hostname)
        print(f"✅ DNS: {hostname} -> {ip}")
        return True, ip
    except socket.gaierror as e:
        print(f"❌ DNS: Failed to resolve {hostname} - {e}")
        return False, None


def check_port_connectivity(hostname, port):
    """Check if port is reachable"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((hostname, port))
        sock.close()
        if result == 0:
            print(f"✅ Port: {hostname}:{port} is reachable")
            return True
        else:
            print(f"❌ Port: {hostname}:{port} is not reachable (error {result})")
            return False
    except Exception as e:
        print(f"❌ Port: Error checking {hostname}:{port} - {e}")
        return False


def check_http_endpoint(url):
    """Check if HTTP endpoint is responsive"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f"✅ HTTP: {url} returned {response.status_code}")
            return True, response.json() if "json" in response.headers.get("content-type", "") else response.text[:200]
        else:
            print(f"❌ HTTP: {url} returned {response.status_code}")
            return False, response.text[:200]
    except requests.exceptions.ConnectionError as e:
        print(f"❌ HTTP: Connection error to {url} - {e}")
        return False, None
    except requests.exceptions.Timeout as e:
        print(f"❌ HTTP: Timeout connecting to {url} - {e}")
        return False, None
    except Exception as e:
        print(f"❌ HTTP: Error connecting to {url} - {e}")
        return False, None


def check_container_network():
    """Check container networking specifics"""
    print("\n=== Container Network Information ===")

    # Check if running in container
    if os.path.exists("/.dockerenv"):
        print("✅ Running inside Docker container")
    else:
        print("ℹ️  Not running inside Docker container")

    # Show network interfaces
    code, stdout, stderr = run_command("ip addr show")
    if code == 0:
        print(f"Network interfaces:\n{stdout}")
    else:
        print(f"Could not get network interfaces: {stderr}")

    # Show routing table
    code, stdout, stderr = run_command("ip route show")
    if code == 0:
        print(f"Routing table:\n{stdout}")
    else:
        print(f"Could not get routing table: {stderr}")

    # Show hostname
    try:
        hostname = socket.gethostname()
        print(f"Container hostname: {hostname}")
    except Exception as e:
        print(f"Could not get hostname: {e}")


def main():
    """Main debugging function"""
    print("=== Docker Network Debugging ===")

    # Environment info
    print("\n=== Environment Variables ===")
    relevant_vars = [
        "STUB_BASE_URL",
        "DATABASE_URL",
        "DOCKER_ENV",
        "CI",
        "GITHUB_ACTIONS",
        "STUB_SERVER_HOST",
        "STUB_SERVER_PORT",
        "USE_STUBS",
        "ENVIRONMENT",
    ]
    for var in relevant_vars:
        value = os.environ.get(var, "NOT_SET")
        print(f"{var}={value}")

    # Check container networking
    check_container_network()

    # Test stub server connectivity
    print("\n=== Stub Server Connectivity ===")
    stub_url = os.environ.get("STUB_BASE_URL", "http://stub-server:5010")
    parsed_url = urlparse(stub_url)
    hostname = parsed_url.hostname
    port = parsed_url.port or 80

    print(f"Testing connectivity to: {stub_url}")

    # DNS resolution
    dns_ok, ip = check_dns_resolution(hostname)

    # Port connectivity
    if dns_ok:
        port_ok = check_port_connectivity(hostname, port)
    else:
        port_ok = False

    # HTTP check
    if port_ok:
        http_ok, response = check_http_endpoint(f"{stub_url}/health")
        if http_ok and response:
            print(f"Health check response: {response}")

    # Test database connectivity
    print("\n=== Database Connectivity ===")
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        try:
            import psycopg2

            psycopg2.connect(db_url)
            print("✅ Database connection successful")
        except ImportError:
            print("ℹ️  psycopg2 not installed, skipping database test")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
    else:
        print("ℹ️  DATABASE_URL not set")

    # Alternative connectivity tests
    print("\n=== Alternative Connectivity Tests ===")

    # Try localhost
    localhost_url = "http://localhost:5010/health"
    print(f"Testing localhost: {localhost_url}")
    check_http_endpoint(localhost_url)

    # Try 127.0.0.1
    local_ip_url = "http://127.0.0.1:5010/health"
    print(f"Testing 127.0.0.1: {local_ip_url}")
    check_http_endpoint(local_ip_url)

    # Show listening ports
    print("\n=== Listening Ports ===")
    code, stdout, stderr = run_command("netstat -tlnp")
    if code == 0:
        lines = stdout.split("\n")
        port_lines = [line for line in lines if ":5010" in line or ":5432" in line]
        if port_lines:
            for line in port_lines:
                print(line)
        else:
            print("No relevant ports found listening")
    else:
        print(f"Could not get listening ports: {stderr}")

    print("\n=== End Network Debugging ===")


if __name__ == "__main__":
    main()
