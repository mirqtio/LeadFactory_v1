# LeadFactory Production Deployment Instructions

## ✅ Step 1: Environment Configuration (COMPLETED)
I've created your `.env` file with your existing API keys. You still need to:

1. **Generate a secure SECRET_KEY**:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Replace `prod-secret-key-CHANGE-THIS-TO-RANDOM-STRING` with the output.

2. **Update Stripe to LIVE keys**:
   - Go to https://dashboard.stripe.com/apikeys
   - Copy your live keys (starting with `pk_live_` and `sk_live_`)
   - Replace the test keys in `.env`

3. **Update domain URLs**:
   - Replace `yourdomain.com` with your actual domain throughout `.env`

---

## 📊 Step 2: PostgreSQL Database Setup

### Option A: Local PostgreSQL
```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
```

```sql
-- In PostgreSQL prompt:
CREATE USER leadfactory WITH PASSWORD 'your-secure-password';
CREATE DATABASE leadfactory_production OWNER leadfactory;
GRANT ALL PRIVILEGES ON DATABASE leadfactory_production TO leadfactory;
\q
```

### Option B: Cloud PostgreSQL (Recommended)

#### AWS RDS:
1. Go to AWS RDS Console
2. Create database → PostgreSQL
3. Choose `db.t3.micro` for testing, `db.t3.small` for production
4. Set master username: `leadfactory`
5. Set a strong password
6. Enable automated backups
7. Copy the endpoint URL

#### DigitalOcean Managed Database:
1. Create a Database Cluster → PostgreSQL
2. Choose $15/month plan minimum
3. Select your region
4. Copy connection string

#### Update .env:
```bash
# Format: postgresql://username:password@host:port/database
DATABASE_URL=postgresql://leadfactory:your-password@your-host:5432/leadfactory_production?sslmode=require
```

### Run Migrations:
```bash
# Install alembic if needed
pip install alembic

# Run migrations
alembic upgrade head

# Verify
python scripts/db_setup.py --verify
```

---

## 🔒 Step 3: SSL Certificate Setup

### Option A: Let's Encrypt (Free)
```bash
# Install Certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal (add to crontab)
0 0 * * * /usr/bin/certbot renew --quiet
```

### Option B: Cloudflare (Recommended)
1. Add your domain to Cloudflare
2. Update nameservers at your registrar
3. Enable "Full (strict)" SSL mode
4. Enable "Always Use HTTPS"
5. Configure Origin Certificate:
   ```bash
   # Download origin certificate from Cloudflare
   # Save as /etc/ssl/certs/origin-cert.pem
   # Save key as /etc/ssl/private/origin-key.pem
   ```

### Option C: AWS Certificate Manager (for AWS deployments)
1. Request certificate in ACM
2. Validate via DNS
3. Attach to Load Balancer

---

## 🌐 Step 4: Domain and DNS Configuration

### Basic DNS Records:
```
Type    Name    Value                   TTL
A       @       your.server.ip.address  300
A       www     your.server.ip.address  300
CNAME   api     yourdomain.com          300
```

### For Load Balancer/CDN:
```
Type    Name    Value                           TTL
CNAME   @       your-lb.region.elb.amazonaws.com   300
CNAME   www     your-lb.region.elb.amazonaws.com   300
```

### Email Records (for SendGrid):
```
Type    Name              Value                         Priority
CNAME   em1234            u1234567.wl123.sendgrid.net   -
CNAME   s1._domainkey     s1.domainkey.u1234567.wl123.sendgrid.net   -
CNAME   s2._domainkey     s2.domainkey.u1234567.wl123.sendgrid.net   -
```

---

## 📈 Step 5: Monitoring Stack Setup

### Prometheus + Grafana (Docker)

1. **Create monitoring stack**:
```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=your-secure-password
      - GF_USERS_ALLOW_SIGN_UP=false

  alertmanager:
    image: prom/alertmanager:latest
    volumes:
      - ./monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml
    ports:
      - "9093:9093"

volumes:
  prometheus_data:
  grafana_data:
```

2. **Deploy monitoring**:
```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

3. **Configure Grafana**:
   - Access http://your-server:3000
   - Login: admin / your-secure-password
   - Add Prometheus data source: http://prometheus:9090
   - Import dashboards from `grafana/dashboards/`

### Sentry Error Tracking

1. **Create Sentry account** at https://sentry.io
2. **Create new project** → Python → FastAPI
3. **Copy DSN** and update `.env`:
   ```
   SENTRY_DSN=https://your-key@o123456.ingest.sentry.io/123456
   ```

### Uptime Monitoring

#### Option A: UptimeRobot (Free)
1. Sign up at https://uptimerobot.com
2. Add monitor → HTTP(s)
3. URL: https://yourdomain.com/health
4. Check interval: 5 minutes

#### Option B: Pingdom
1. Add uptime check
2. Configure alerts
3. Set up status page

---

## 🚀 Step 6: Deployment Commands

### Using Docker (Recommended):

```bash
# 1. Build production image
docker build -t leadfactory:production .

# 2. Run database migrations
docker run --rm \
  --env-file .env \
  leadfactory:production \
  alembic upgrade head

# 3. Deploy with Docker Compose
docker-compose -f docker-compose.production.yml up -d

# 4. Check logs
docker-compose -f docker-compose.production.yml logs -f

# 5. Scale if needed
docker-compose -f docker-compose.production.yml up -d --scale web=3
```

### Using Systemd (Traditional):

```bash
# 1. Create application user
sudo useradd -m -s /bin/bash leadfactory

# 2. Set up application directory
sudo mkdir -p /opt/leadfactory
sudo chown leadfactory:leadfactory /opt/leadfactory

# 3. Clone and setup as leadfactory user
sudo -u leadfactory bash
cd /opt/leadfactory
git clone https://github.com/yourusername/leadfactory.git .
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Copy systemd service
sudo cp leadfactory.service /etc/systemd/system/

# 5. Start service
sudo systemctl daemon-reload
sudo systemctl enable leadfactory
sudo systemctl start leadfactory

# 6. Configure nginx
sudo cp nginx.conf /etc/nginx/sites-available/leadfactory
sudo ln -s /etc/nginx/sites-available/leadfactory /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🔍 Post-Deployment Verification

### 1. Health Checks
```bash
# API health
curl https://yourdomain.com/health

# Database connectivity
curl https://yourdomain.com/health/db

# Redis connectivity  
curl https://yourdomain.com/health/redis
```

### 2. Test Critical Paths
```bash
# Test Stripe webhook
stripe listen --forward-to https://yourdomain.com/webhooks/stripe

# Send test email
curl -X POST https://yourdomain.com/api/v1/test-email \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

### 3. Monitor Logs
```bash
# Application logs
docker-compose -f docker-compose.production.yml logs -f web

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# System logs
journalctl -u leadfactory -f
```

### 4. Performance Baseline
- Note initial response times
- Check memory usage
- Monitor CPU utilization
- Verify database connection pooling

---

## 🔄 Rollback Plan

If issues arise:

1. **Quick rollback**:
   ```bash
   # Docker
   docker-compose -f docker-compose.production.yml down
   docker run -d --name leadfactory leadfactory:previous-version
   
   # Systemd
   systemctl stop leadfactory
   git checkout previous-tag
   systemctl start leadfactory
   ```

2. **Database rollback**:
   ```bash
   alembic downgrade -1
   ```

3. **DNS failover**:
   - Have backup server ready
   - Update DNS to point to backup
   - Or use Cloudflare page rules for maintenance mode

---

## 📞 Emergency Contacts

Fill in your team contacts:
- DevOps Lead: ___________
- Database Admin: ___________  
- On-call Engineer: ___________
- Escalation: ___________

---

## 🎯 First Week Checklist

- [ ] Monitor error rates closely
- [ ] Check email delivery rates
- [ ] Verify payment processing
- [ ] Review performance metrics
- [ ] Test backup restoration
- [ ] Document any issues
- [ ] Plan first optimization sprint

Good luck with your deployment! 🚀