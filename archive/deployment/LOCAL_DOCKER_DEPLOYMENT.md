# LeadFactory Local Docker Deployment Guide

## 🚀 Quick Start for Local Docker

Since you're running locally with Docker, many production concerns (SSL, domain, monitoring) are simplified or unnecessary.

## 📋 Pre-Deployment Checklist

### 1. ✅ Environment Configuration (Already Done)
Your `.env` file is ready with your API keys. Just need a few updates:

```bash
# 1. Generate a secure SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Update in .env:
SECRET_KEY=<paste-generated-key-here>

# 3. Keep test Stripe keys for local testing (no need for live keys)
# Your current test keys are fine for local development

# 4. Update URLs to localhost
STRIPE_SUCCESS_URL=http://localhost:8000/purchase/success?session_id={CHECKOUT_SESSION_ID}
STRIPE_CANCEL_URL=http://localhost:8000/purchase/cancel
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### 2. 🗄️ PostgreSQL Database (Docker)

No need to install PostgreSQL locally! Docker Compose will handle it:

```yaml
# Already in docker-compose.yml
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: leadfactory
      POSTGRES_PASSWORD: leadfactory_dev_password  # Change for security
      POSTGRES_DB: leadfactory
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
```

Update your `.env`:
```bash
# For Docker networking, use service name 'db' as host
DATABASE_URL=postgresql://leadfactory:leadfactory_dev_password@db:5432/leadfactory
```

### 3. 🔐 Redis Configuration

Redis is also handled by Docker Compose:

```yaml
# Already in docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass redis_dev_password  # Change password
    ports:
      - "6379:6379"
```

Update your `.env`:
```bash
REDIS_URL=redis://:redis_dev_password@redis:6379/0
CELERY_BROKER_URL=redis://:redis_dev_password@redis:6379/1
CELERY_RESULT_BACKEND=redis://:redis_dev_password@redis:6379/2
```

### 4. 🏗️ Build and Deploy

```bash
# 1. Make sure Docker Desktop is running

# 2. Build all services
docker-compose build

# 3. Start the database first
docker-compose up -d db redis

# 4. Wait a moment for DB to initialize, then run migrations
docker-compose run --rm web alembic upgrade head

# 5. Start all services
docker-compose up -d

# 6. Check logs
docker-compose logs -f
```

### 5. 🔍 Verify Deployment

```bash
# Check all services are running
docker-compose ps

# Test API health
curl http://localhost:8000/health

# View logs
docker-compose logs web
docker-compose logs db
docker-compose logs redis

# Access the application
open http://localhost:8000/docs  # FastAPI documentation
```

## 📝 Local Development URLs

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Database**: localhost:5432 (if you need direct access)
- **Redis**: localhost:6379

## 🛠️ Common Docker Commands

```bash
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# Stop and remove volumes (careful - deletes data!)
docker-compose down -v

# Rebuild after code changes
docker-compose build web
docker-compose up -d web

# Run tests
docker-compose run --rm web pytest

# Access container shell
docker-compose exec web bash

# View real-time logs
docker-compose logs -f web

# Run a one-off command
docker-compose run --rm web python scripts/verify_integrations.py
```

## 🔧 Local Configuration Adjustments

### Update docker-compose.yml for local development:

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development  # or 'local'
      - DEBUG=True  # Enable for development
    env_file:
      - .env
    depends_on:
      - db
      - redis
    volumes:
      - ./:/app  # Mount code for hot reload
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: leadfactory
      POSTGRES_PASSWORD: leadfactory_dev_password
      POSTGRES_DB: leadfactory
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass redis_dev_password
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

## 🚦 Testing Your Deployment

### 1. Create a test campaign:
```bash
docker-compose run --rm web python scripts/launch_campaign.py \
  --name "Test Campaign" \
  --vertical "restaurant" \
  --location "San Francisco, CA" \
  --radius 5
```

### 2. Test email sending (using MailHog for local testing):
```yaml
# Add to docker-compose.yml for local email testing
services:
  mailhog:
    image: mailhog/mailhog
    ports:
      - "1025:1025"  # SMTP
      - "8025:8025"  # Web UI
```

Then update `.env` for local testing:
```bash
# For local testing with MailHog
SENDGRID_API_KEY=dummy_key_for_local
EMAIL_BACKEND=smtp
SMTP_HOST=mailhog
SMTP_PORT=1025
```

Access MailHog UI at http://localhost:8025 to see sent emails.

### 3. Test Stripe webhooks locally:
```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login to Stripe
stripe login

# Forward webhooks to your local instance
stripe listen --forward-to http://localhost:8000/webhooks/stripe
```

## 🐛 Troubleshooting

### Database connection issues:
```bash
# Check if database is running
docker-compose ps db

# Check database logs
docker-compose logs db

# Connect to database directly
docker-compose exec db psql -U leadfactory -d leadfactory
```

### Port conflicts:
```bash
# If port 8000 is in use
lsof -i :8000  # Find what's using it
# Change port in docker-compose.yml and .env
```

### Permission issues:
```bash
# If you get permission errors
docker-compose run --rm web chown -R $(id -u):$(id -g) .
```

## 🎯 Next Steps for Local Testing

1. **Run the test suite**:
   ```bash
   docker-compose run --rm web pytest -v
   ```

2. **Create sample data**:
   ```bash
   docker-compose run --rm web python scripts/seed_campaigns.py
   ```

3. **Monitor performance**:
   ```bash
   # Simple metrics endpoint
   curl http://localhost:8000/metrics
   ```

4. **Test the full pipeline**:
   ```bash
   docker-compose run --rm web python scripts/test_pipeline.py
   ```

## 🚀 Moving to Production Later

When you're ready to deploy to a real server:
1. Update `.env` with production values
2. Switch to `docker-compose.production.yml`
3. Set up SSL certificates
4. Configure a proper domain
5. Enable monitoring stack
6. Use managed databases (RDS, Cloud SQL, etc.)

For now, enjoy testing locally with Docker! 🎉