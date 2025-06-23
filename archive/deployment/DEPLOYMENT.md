# LeadFactory Production Deployment Guide

## Pre-Deployment Checklist

### 1. Environment Setup
- [ ] Copy `.env.example` to `.env`
- [ ] Fill in all production API keys
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure PostgreSQL database URL
- [ ] Set strong `SECRET_KEY`

### 2. API Keys Required
- [ ] YELP_API_KEY - Get from https://www.yelp.com/developers
- [ ] GOOGLE_API_KEY - Get from Google Cloud Console
- [ ] PAGESPEED_API_KEY - Enable PageSpeed Insights API
- [ ] OPENAI_API_KEY - Get from https://platform.openai.com
- [ ] SENDGRID_API_KEY - Get from SendGrid dashboard
- [ ] STRIPE_SECRET_KEY - Get from Stripe dashboard (use live keys)
- [ ] STRIPE_WEBHOOK_SECRET - Configure webhook endpoint in Stripe

### 3. Database Setup
```bash
# Create production database
createdb leadfactory_production

# Run migrations
alembic upgrade head

# Verify database
python scripts/db_setup.py --verify
```

### 4. Security Configuration
- [ ] Configure HTTPS (SSL certificates)
- [ ] Set up reverse proxy (nginx/caddy)
- [ ] Configure firewall rules
- [ ] Enable rate limiting
- [ ] Set CORS origins to production domain only

### 5. Monitoring Setup
- [ ] Deploy Prometheus
- [ ] Import Grafana dashboards
- [ ] Configure alerts
- [ ] Set up log aggregation
- [ ] Configure Sentry for error tracking

### 6. Deployment Steps

#### Using Docker Compose:
```bash
# Build production images
docker-compose -f docker-compose.production.yml build

# Start services
docker-compose -f docker-compose.production.yml up -d

# Check logs
docker-compose -f docker-compose.production.yml logs -f
```

#### Manual Deployment:
```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start application
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 7. Post-Deployment Verification
```bash
# Check health endpoint
curl https://yourdomain.com/health

# Run system check
python scripts/system_check.py

# Verify integrations
python scripts/verify_integrations.py --production

# Monitor logs
tail -f logs/leadfactory.log
```

### 8. Backup Configuration
```bash
# Set up daily database backups
crontab -e
# Add: 0 2 * * * /path/to/scripts/db_backup.sh

# Test backup restoration
python scripts/db_backup.sh --test-restore
```

## Production Environment Variables

See `.env.example` for all required variables. Critical ones:

- `ENVIRONMENT=production`
- `DEBUG=False`
- `DATABASE_URL=postgresql://user:pass@host:5432/leadfactory`
- `REDIS_URL=redis://redis:6379/0`
- `SECRET_KEY=<generate-strong-key>`

## Security Best Practices

1. **API Keys**: Never commit `.env` file. Use secrets management.
2. **Database**: Use PostgreSQL with SSL. Regular backups.
3. **Redis**: Configure password. Bind to localhost only.
4. **HTTPS**: Always use SSL/TLS in production.
5. **Headers**: Configure security headers (HSTS, CSP, etc.)
6. **Updates**: Keep dependencies updated. Monitor CVEs.

## Troubleshooting

See `docs/troubleshooting.md` for common issues and solutions.

## Support

For deployment issues:
1. Check logs: `docker-compose logs`
2. Run diagnostics: `python scripts/health_check.py`
3. Review monitoring dashboards
