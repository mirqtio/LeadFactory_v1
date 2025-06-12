#!/bin/bash
# Production Readiness Script
# Phase 4 - Security hardening and production setup

set -e

echo "=== Phase 4: Production Readiness ==="

# 1. Security Hardening
echo "1. Security Hardening..."

# Generate secure secrets if not present
if [ -z "$SECRET_KEY" ]; then
    export SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
    echo "Generated new SECRET_KEY"
fi

# Ensure production environment settings
cat > .env.production.secure <<EOF
# Production Environment Settings
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=WARNING

# Security
SECRET_KEY=${SECRET_KEY}
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=strict
CORS_ALLOWED_ORIGINS=https://leadfactory.com

# Database
DATABASE_URL=${DATABASE_URL:-postgresql://leadfactory:secure_password@postgres:5432/leadfactory}

# Rate Limiting
RATE_LIMIT_ENABLED=True
RATE_LIMIT_DEFAULT=100/hour

# Feature Flags
ENABLE_WEBHOOKS=True
ENABLE_ANALYTICS=True
ENABLE_EXPERIMENTS=True
USE_STUBS=False
EOF

# 2. Database Security
echo "2. Database Security..."

# Create production database user with limited permissions
cat > scripts/secure_database.sql <<EOF
-- Revoke all permissions and grant only necessary ones
REVOKE ALL ON SCHEMA public FROM leadfactory;
GRANT USAGE ON SCHEMA public TO leadfactory;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO leadfactory;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO leadfactory;

-- Enable row level security on sensitive tables
ALTER TABLE businesses ENABLE ROW LEVEL SECURITY;
ALTER TABLE emails ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchases ENABLE ROW LEVEL SECURITY;

-- Create audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    action VARCHAR(100),
    table_name VARCHAR(100),
    record_id VARCHAR(255),
    old_values JSONB,
    new_values JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
EOF

# 3. Monitoring Setup
echo "3. Monitoring Setup..."

# Create monitoring configuration
cat > monitoring/production.yml <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files:
  - 'alerts.yaml'

scrape_configs:
  - job_name: 'leadfactory'
    static_configs:
      - targets: ['leadfactory-api:8000']
    metrics_path: '/metrics'
    
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
      
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
EOF

# 4. Backup Configuration
echo "4. Backup Configuration..."

# Create backup script
cat > scripts/automated_backup.sh <<'BACKUP'
#!/bin/bash
# Automated backup script for production

BACKUP_DIR=/backups/$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Database backup
PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h postgres -U leadfactory leadfactory | gzip > $BACKUP_DIR/database.sql.gz

# Application files backup
tar -czf $BACKUP_DIR/app_files.tar.gz /app/uploads /app/logs

# Keep only last 7 days of backups
find /backups -type d -mtime +7 -exec rm -rf {} \;

echo "Backup completed: $BACKUP_DIR"
BACKUP

chmod +x scripts/automated_backup.sh

# 5. Health Monitoring
echo "5. Health Monitoring..."

# Create comprehensive health check script
cat > scripts/health_monitor.py <<'HEALTH'
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
HEALTH

chmod +x scripts/health_monitor.py

# 6. SSL/TLS Configuration
echo "6. SSL/TLS Configuration..."

# Create nginx SSL configuration
cat > nginx/ssl.conf <<EOF
server {
    listen 443 ssl http2;
    server_name leadfactory.com;

    ssl_certificate /etc/letsencrypt/live/leadfactory.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/leadfactory.com/privkey.pem;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    location / {
        proxy_pass http://leadfactory-api:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}

server {
    listen 80;
    server_name leadfactory.com;
    return 301 https://\$server_name\$request_uri;
}
EOF

# 7. Performance Optimization
echo "7. Performance Optimization..."

# Create production gunicorn configuration
cat > gunicorn.conf.py <<EOF
import multiprocessing

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2

# Logging
accesslog = "/app/logs/access.log"
errorlog = "/app/logs/error.log"
loglevel = "warning"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'leadfactory'

# Server mechanics
daemon = False
pidfile = '/var/run/leadfactory.pid'
user = 'leadfactory'
group = 'leadfactory'
tmp_upload_dir = '/tmp'

# SSL/TLS
keyfile = None
certfile = None
EOF

# 8. Create production docker-compose override
echo "8. Production Docker Compose Override..."

cat > docker-compose.production.override.yml <<EOF
version: '3.8'

services:
  leadfactory-api:
    restart: always
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "10"
    
  postgres:
    restart: always
    volumes:
      - postgres_backup:/backups
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
    
  redis:
    restart: always
    command: redis-server --requirepass \${REDIS_PASSWORD} --maxmemory 512mb --maxmemory-policy allkeys-lru
    
  nginx:
    restart: always
    volumes:
      - ./nginx/ssl.conf:/etc/nginx/conf.d/ssl.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    ports:
      - "443:443"
    
  prometheus:
    restart: always
    volumes:
      - ./monitoring/production.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    
  grafana:
    restart: always
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=\${GRAFANA_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false

volumes:
  postgres_backup:
  prometheus_data:
EOF

echo "=== Phase 4 Complete ==="
echo "Production readiness configurations created:"
echo "- Security hardening configurations"
echo "- Database security setup"
echo "- Monitoring and alerting"
echo "- Automated backups"
echo "- SSL/TLS configuration"
echo "- Performance optimizations"
echo ""
echo "Next steps:"
echo "1. Review and customize configurations"
echo "2. Set up SSL certificates with Let's Encrypt"
echo "3. Configure SMTP for email alerts"
echo "4. Set up external monitoring services"
echo "5. Perform security audit"