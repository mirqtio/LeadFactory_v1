# LeadFactory Production Deployment Guide

## Prerequisites

- Docker & Docker Compose installed
- Domain name configured with DNS
- SSL certificate (Let's Encrypt recommended)
- PostgreSQL 15+ 
- Redis 7+
- 4GB+ RAM, 2+ CPU cores
- 50GB+ storage

## Deployment Steps

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create deployment user
sudo useradd -m -s /bin/bash leadfactory
sudo usermod -aG docker leadfactory
```

### 2. Clone Repository

```bash
sudo su - leadfactory
git clone https://github.com/yourorg/leadfactory.git
cd leadfactory
```

### 3. Configure Environment

```bash
# Copy production environment template
cp .env.production.secure .env.production

# Edit with your values
nano .env.production

# Required variables:
# - DATABASE_URL
# - SECRET_KEY
# - STRIPE_SECRET_KEY
# - SENDGRID_API_KEY
# - YELP_API_KEY
# - OPENAI_API_KEY
```

### 4. SSL Certificate Setup

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot certonly --standalone -d leadfactory.com -d www.leadfactory.com

# Auto-renewal
sudo systemctl enable certbot.timer
```

### 5. Database Initialization

```bash
# Start only database service
docker-compose -f docker-compose.production.yml up -d postgres

# Wait for database to be ready
sleep 10

# Run migrations
docker-compose -f docker-compose.production.yml run --rm leadfactory-api alembic upgrade head

# Load initial data (if needed)
docker-compose -f docker-compose.production.yml run --rm leadfactory-api python scripts/seed_campaigns.py
```

### 6. Start Services

```bash
# Build images
docker-compose -f docker-compose.production.yml build

# Start all services
docker-compose -f docker-compose.production.yml -f docker-compose.production.override.yml up -d

# Check status
docker-compose -f docker-compose.production.yml ps
```

### 7. Verify Deployment

```bash
# Check health endpoints
curl https://leadfactory.com/health
curl https://leadfactory.com/api/v1/targeting/health
curl https://leadfactory.com/metrics

# Check logs
docker-compose -f docker-compose.production.yml logs -f leadfactory-api

# Run smoke tests
docker-compose -f docker-compose.production.yml run --rm leadfactory-api python tests/smoke_prod/runner.py
```

### 8. Setup Monitoring

```bash
# Configure Datadog (if using)
docker run -d --name datadog-agent \
  -e DD_API_KEY=$DATADOG_API_KEY \
  -e DD_SITE="us5.datadoghq.com" \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /proc/:/host/proc/:ro \
  -v /sys/fs/cgroup/:/host/sys/fs/cgroup:ro \
  datadog/agent:latest

# Setup alerts
curl -X POST https://api.us5.datadoghq.com/api/v1/monitor \
  -H "DD-API-KEY: $DATADOG_API_KEY" \
  -H "DD-APPLICATION-KEY: $DATADOG_APP_KEY" \
  -d @monitoring/alerts.json
```

### 9. Configure Backups

```bash
# Add to crontab
crontab -e

# Add backup job (daily at 2 AM)
0 2 * * * /home/leadfactory/leadfactory/scripts/automated_backup.sh

# Test backup
./scripts/automated_backup.sh
```

### 10. Security Hardening

```bash
# Configure firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Fail2ban for SSH protection
sudo apt install fail2ban
sudo systemctl enable fail2ban

# Apply database security
docker-compose -f docker-compose.production.yml exec postgres psql -U leadfactory -f /scripts/secure_database.sql
```

## Post-Deployment Tasks

### 1. DNS Configuration
- A record: leadfactory.com → your-server-ip
- CNAME: www.leadfactory.com → leadfactory.com
- MX records for email

### 2. Email Configuration
- SPF record: `v=spf1 include:sendgrid.net ~all`
- DKIM: Configure in SendGrid
- DMARC: `v=DMARC1; p=quarantine; rua=mailto:dmarc@leadfactory.com`

### 3. Performance Testing
```bash
# Load test with locust
pip install locust
locust -f tests/performance/locustfile.py --host=https://leadfactory.com
```

### 4. Security Scan
```bash
# Run security scan
docker run --rm -v $(pwd):/src semgrep/semgrep --config=auto /src

# Container scan
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image leadfactory:production
```

## Rollback Procedure

If deployment fails:

```bash
# Stop new services
docker-compose -f docker-compose.production.yml down

# Restore database backup
gunzip < /backups/latest/database.sql.gz | docker exec -i leadfactory-postgres psql -U leadfactory

# Restart previous version
docker-compose -f docker-compose.production.yml up -d --force-recreate
```

## Maintenance

### Daily
- Check health endpoints
- Review error logs
- Monitor disk space

### Weekly
- Review performance metrics
- Check backup integrity
- Security updates

### Monthly
- Full system backup test
- Performance optimization review
- Security audit

## Troubleshooting

### Common Issues

1. **502 Bad Gateway**
   - Check if API container is running
   - Review nginx logs
   - Verify upstream configuration

2. **Database Connection Failed**
   - Check PostgreSQL container status
   - Verify DATABASE_URL
   - Check network connectivity

3. **High Memory Usage**
   - Review container limits
   - Check for memory leaks
   - Scale horizontally if needed

### Debug Commands

```bash
# Container logs
docker logs leadfactory-api --tail 100

# Database connection test
docker exec leadfactory-api python -c "from database.session import engine; print(engine.execute('SELECT 1').scalar())"

# API shell
docker exec -it leadfactory-api python

# Database shell
docker exec -it leadfactory-postgres psql -U leadfactory
```

## Support

- Technical Support: support@leadfactory.com
- Emergency: +1-XXX-XXX-XXXX
- Documentation: https://docs.leadfactory.com