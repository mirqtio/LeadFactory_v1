# Deployment Verification Guide

## Overview

This guide outlines the verification process for LeadFactory deployments to ensure all acceptance criteria are met.

## Acceptance Criteria Checklist

### P0-011: Deploy to VPS

- [ ] **GitHub Actions deploy job completes successfully**
  - Test workflow runs without errors
  - Docker image builds and pushes to GHCR
  - SSH deployment executes successfully

- [ ] **Container responds 200 on `/health`**
  - Health endpoint returns proper JSON structure
  - Database connectivity check passes
  - Response time < 100ms

- [ ] **Restart policy is `always`**
  - Container automatically restarts on failure
  - Survives VPS reboot

- [ ] **SSH key auth works**
  - No password prompts during deployment
  - Secure key-based authentication only

## Verification Steps

### 1. Pre-Deployment Verification

```bash
# Verify GitHub secrets are configured
gh secret list

# Expected secrets:
# - VPS_HOST
# - VPS_USER
# - SSH_PRIVATE_KEY
# - PRODUCTION_URL (optional)
```

### 2. Trigger Deployment

```bash
# Manual deployment
gh workflow run deploy.yml

# Or push to main branch for automatic deployment
git push origin main
```

### 3. Monitor Deployment Progress

```bash
# List recent workflow runs
gh run list --workflow=deploy.yml --limit 5

# Watch the latest run
gh run watch

# View detailed logs
gh run view --log
```

### 4. Verify Container Status

SSH into VPS and check:

```bash
# Check container is running
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | grep leadfactory

# Verify restart policy
docker inspect leadfactory | grep -A 5 RestartPolicy
# Should show: "Name": "always"

# Check container logs
docker logs leadfactory --tail 50

# Verify environment
docker exec leadfactory env | grep -E "ENVIRONMENT|USE_STUBS"
# Should show: ENVIRONMENT=production, USE_STUBS=false
```

### 5. Test Health Endpoint

```bash
# From VPS
curl -i http://localhost:8000/health

# Expected response:
# HTTP/1.1 200 OK
# {
#   "status": "ok",
#   "timestamp": "2025-01-11T...",
#   "version": "1.0.0",
#   "environment": "production",
#   "database": "connected"
# }

# Test response time
time curl http://localhost:8000/health
# Should be < 100ms
```

### 6. Run Remote Smoke Tests

```bash
# From local machine
export LEADFACTORY_URL=http://your-vps-ip:8000
pytest tests/smoke/test_remote_health.py -v

# Or via GitHub Actions (automatic after deployment)
# Check the post-deploy-smoke job in workflow
```

### 7. Verify Persistence

```bash
# On VPS, simulate container failure
docker kill leadfactory

# Wait a few seconds
sleep 5

# Verify container auto-restarted
docker ps | grep leadfactory

# Check uptime
docker ps --format "table {{.Names}}\t{{.Status}}" | grep leadfactory
```

### 8. Test VPS Reboot Persistence

```bash
# WARNING: This will reboot the VPS
sudo reboot

# After VPS comes back up (wait ~2 minutes)
ssh user@vps-host

# Check container started automatically
docker ps | grep leadfactory
```

## Common Issues and Solutions

### Issue: Deployment fails with "permission denied"

**Solution**: Ensure VPS user has Docker permissions
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Issue: Health check returns 503

**Solution**: Check database connectivity
```bash
# Verify env file exists
ls -la /opt/leadfactory/.env.production

# Test database connection
docker exec leadfactory python -c "
from sqlalchemy import create_engine
import os
engine = create_engine(os.getenv('DATABASE_URL'))
engine.connect()
print('Database connected!')
"
```

### Issue: Container keeps restarting

**Solution**: Check logs for startup errors
```bash
# View recent logs
docker logs leadfactory --tail 100

# Common issues:
# - Missing environment variables
# - Database connection errors
# - Port already in use
```

### Issue: GitHub Actions fails at SSH step

**Solution**: Verify SSH key format
```bash
# The SSH_PRIVATE_KEY secret should include:
# - -----BEGIN OPENSSH PRIVATE KEY-----
# - Key content (no extra spaces/newlines)
# - -----END OPENSSH PRIVATE KEY-----

# Test SSH connection manually
ssh -i ~/.ssh/deploy_key user@vps-host "echo 'SSH works!'"
```

## Post-Deployment Checklist

- [ ] Container is running with correct image tag
- [ ] Health endpoint returns 200 OK
- [ ] Database connectivity confirmed
- [ ] Logs show no critical errors
- [ ] Restart policy is "always"
- [ ] Container survives kill/restart
- [ ] Remote smoke tests pass
- [ ] No USE_STUBS=true in production
- [ ] Nginx (if used) forwards requests correctly

## Monitoring Commands

```bash
# Quick health check
curl -s http://localhost:8000/health | jq .

# Container resource usage
docker stats leadfactory --no-stream

# Recent logs
docker logs leadfactory --since 1h --tail 100

# Check disk usage
df -h /opt/leadfactory/logs

# Active connections
docker exec leadfactory netstat -an | grep ESTABLISHED
```

## Success Indicators

✅ Deployment workflow shows green checkmarks
✅ Container status shows "Up X minutes"
✅ Health endpoint returns {"status": "ok"}
✅ No errors in container logs
✅ Remote smoke tests pass
✅ Container auto-restarts on failure

## Next Steps

Once P0-011 is verified complete:
1. Mark P0-011 as completed in PRP progress
2. Proceed to P0-012: Postgres on VPS Container