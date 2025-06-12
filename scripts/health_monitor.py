#!/usr/bin/env python3
"""Production health monitoring script"""
import requests
import smtplib
from email.mime.text import MIMEText
import os
import time

HEALTH_ENDPOINTS = [
    "http://leadfactory-api:8000/health",
    "http://leadfactory-api:8000/api/v1/targeting/health",
    "http://leadfactory-api:8000/api/v1/analytics/health",
    "http://leadfactory-api:8000/metrics"
]

ALERT_EMAIL = os.getenv("ALERT_EMAIL", "ops@leadfactory.com")

def check_health():
    """Check all health endpoints"""
    failures = []
    
    for endpoint in HEALTH_ENDPOINTS:
        try:
            response = requests.get(endpoint, timeout=10)
            if response.status_code != 200:
                failures.append(f"{endpoint}: HTTP {response.status_code}")
        except Exception as e:
            failures.append(f"{endpoint}: {str(e)}")
    
    if failures:
        send_alert("\n".join(failures))
    
    return len(failures) == 0

def send_alert(message):
    """Send email alert"""
    msg = MIMEText(f"Health check failures:\n\n{message}")
    msg['Subject'] = 'LeadFactory Health Check Alert'
    msg['From'] = 'alerts@leadfactory.com'
    msg['To'] = ALERT_EMAIL
    
    # Send email via SMTP
    # Configure with your SMTP server
    print(f"ALERT: {message}")

if __name__ == "__main__":
    while True:
        if not check_health():
            print("Health check failed!")
        time.sleep(300)  # Check every 5 minutes
