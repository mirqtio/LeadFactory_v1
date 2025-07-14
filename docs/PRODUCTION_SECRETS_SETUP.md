# Production Secrets Setup Guide

This guide helps you securely deploy production secrets to the VPS.

## Prerequisites

1. SSH access to the VPS (you mentioned you can SSH successfully)
2. All production API keys ready
3. The `leadfactory_deploy` SSH key

## Step 1: Create Local Production Environment File

1. Copy the template:
   ```bash
   cp .env.production.template .env.production
   ```

2. Edit `.env.production` and add your REAL production values:
   ```bash
   nano .env.production  # or use your preferred editor
   ```

3. **CRITICAL**: Generate a strong SECRET_KEY:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

4. Generate a strong database password:
   ```bash
   openssl rand -base64 32
   ```

## Step 2: Deploy Secrets to VPS

### Option A: Using the Deploy Script (Recommended)

1. Run the deployment script:
   ```bash
   ./scripts/deploy_secrets.sh
   ```

   This script will:
   - Backup existing secrets on the VPS
   - Upload your new .env.production file
   - Set proper permissions (600)
   - Restart the Docker containers
   - Run database migrations
   - Perform a health check

### Option B: Manual Deployment

If you prefer to do it manually:

1. Copy the secrets file to VPS:
   ```bash
   scp -i ~/.ssh/leadfactory_deploy -P 22 .env.production deploy@96.30.197.121:/tmp/.env.new
   ```

2. SSH into the VPS:
   ```bash
   ssh -i ~/.ssh/leadfactory_deploy -p 22 deploy@96.30.197.121
   ```

3. Move and secure the file:
   ```bash
   sudo mv /tmp/.env.new /srv/leadfactory/.env
   sudo chmod 600 /srv/leadfactory/.env
   sudo chown deploy:deploy /srv/leadfactory/.env
   ```

4. Restart the application:
   ```bash
   cd /srv/leadfactory
   docker compose -f docker-compose.prod.yml down
   docker compose -f docker-compose.prod.yml up -d
   ```

5. Run migrations:
   ```bash
   docker compose -f docker-compose.prod.yml run --rm -T web alembic upgrade head
   ```

## Step 3: Verify Deployment

1. Check container status:
   ```bash
   ssh -i ~/.ssh/leadfactory_deploy deploy@96.30.197.121 \
     'cd /srv/leadfactory && docker compose -f docker-compose.prod.yml ps'
   ```

2. Check application health:
   ```bash
   curl http://96.30.197.121:8000/health
   ```

3. View logs if needed:
   ```bash
   ssh -i ~/.ssh/leadfactory_deploy deploy@96.30.197.121 \
     'cd /srv/leadfactory && docker compose -f docker-compose.prod.yml logs --tail=50'
   ```

## Required Secrets Checklist

Make sure you have real values for ALL of these:

### Critical (App won't start without these):
- [ ] SECRET_KEY - Generated strong key
- [ ] DB_PASSWORD - Strong database password
- [ ] DATABASE_URL - Must match DB_PASSWORD

### External APIs (Features won't work without these):
- [ ] GOOGLE_API_KEY
- [ ] GOOGLE_PLACES_API_KEY
- [ ] GOOGLE_PAGESPEED_API_KEY
- [ ] STRIPE_SECRET_KEY
- [ ] STRIPE_PUBLISHABLE_KEY
- [ ] STRIPE_WEBHOOK_SECRET
- [ ] STRIPE_PRICE_ID
- [ ] SENDGRID_API_KEY
- [ ] OPENAI_API_KEY

### Optional but Recommended:
- [ ] DATA_AXLE_API_KEY
- [ ] SEMRUSH_API_KEY
- [ ] SCREENSHOTONE_KEY
- [ ] HUNTER_API_KEY
- [ ] DATADOG_API_KEY
- [ ] SENTRY_DSN

## Security Notes

1. **NEVER** commit `.env.production` to git
2. Keep a secure backup of your production secrets
3. Rotate secrets regularly
4. Use strong, unique passwords
5. Limit access to production secrets

## Troubleshooting

### Container won't start
- Check logs: `docker compose logs web`
- Verify all required env vars are set
- Check SECRET_KEY and DB_PASSWORD match in all places

### Database connection errors
- Ensure DATABASE_URL uses the same password as DB_PASSWORD
- Check postgres container is running
- Verify database was created

### API errors
- Double-check API keys are correct
- Some APIs may need account activation
- Check API rate limits

## Next Steps

After successful deployment:
1. Set up SSL/TLS (use Let's Encrypt)
2. Configure a domain name
3. Set up monitoring (Datadog/Sentry)
4. Configure backups
5. Set up log rotation