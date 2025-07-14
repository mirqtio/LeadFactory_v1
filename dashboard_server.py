#!/usr/bin/env python3
"""
Simple dashboard server for AI CTO status updates.
Serves the dashboard on http://localhost:8501 (or next available port)
"""

import http.server
import socket
import socketserver
import webbrowser
from pathlib import Path


def find_free_port(start_port=8501):
    """Find the next available port starting from start_port."""
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", port))
                return port
        except OSError:
            continue
    raise RuntimeError("No free ports found")


def start_dashboard_server():
    """Start the dashboard server."""
    dashboard_dir = Path(__file__).parent

    # Change to dashboard directory
    import os

    os.chdir(dashboard_dir)

    # Find available port
    port = find_free_port()

    # Create server
    handler = http.server.SimpleHTTPRequestHandler

    class QuietHTTPServer(socketserver.TCPServer):
        def log_message(self, format, *args):
            pass  # Suppress log messages

    with QuietHTTPServer(("localhost", port), handler) as httpd:
        dashboard_url = f"http://localhost:{port}/ai_cto_dashboard.html"
        print(f"🤖 AI CTO Dashboard running at: {dashboard_url}")
        print(f"📊 Dashboard will auto-refresh every 30 seconds")
        print(f"🔄 Press Ctrl+C to stop server")

        # Open browser automatically
        try:
            webbrowser.open(dashboard_url)
        except:
            print(f"⚠️  Could not auto-open browser. Please visit: {dashboard_url}")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print(f"\n✅ Dashboard server stopped")


if __name__ == "__main__":
    start_dashboard_server()
