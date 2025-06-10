# LeadFactory MVP Troubleshooting Guide

## Overview

This guide provides step-by-step troubleshooting procedures for common issues in the LeadFactory MVP. Each section includes symptoms, root cause analysis, and resolution steps.

## Quick Diagnostic Commands

Before diving into specific issues, run these quick diagnostics:

```bash
# Overall system health
python scripts/system_check.py

# Service status
docker-compose ps

# Integration verification
python scripts/verify_integrations.py

# Health check
python scripts/health_check.py

# Recent errors
tail -100 logs/app.log | grep ERROR
```

## Common Issues

### 1. Pipeline Not Processing Businesses

#### Symptoms
- Zero businesses processed in daily run
- Pipeline status shows "failed" or "stalled"
- No new entries in business table

#### Diagnostic Steps
```bash
# Check pipeline logs
docker logs leadfactory_pipeline_1 --tail=50

# Check targeting quota
python -c "
from d1_targeting.quota_tracker import QuotaTracker
tracker = QuotaTracker()
print(tracker.get_available_quota())
"

# Verify Yelp API connectivity
python scripts/verify_integrations.py | grep -A5 "Yelp"
```

#### Common Root Causes

**A. Yelp API Rate Limit Exceeded**
```bash
# Check rate limit status
python -c "
from d0_gateway.rate_limiter import RateLimiter
limiter = RateLimiter()
print(limiter.get_status('yelp'))
"

# Solution: Wait for reset or increase limit
# Temporary fix: Reduce batch size
export YELP_BATCH_SIZE=50
```

**B. No Available Targeting Quotas**
```bash
# Check quota allocation
python -c "
from d1_targeting.models import Target
from database.session import get_database_session
session = get_database_session()
targets = session.query(Target).filter(Target.daily_quota > 0).all()
print(f'Active targets: {len(targets)}')
"

# Solution: Create new targets or reset quotas
python scripts/seed_campaigns.py --reset-quotas
```

**C. Database Connection Issues**
```bash
# Test database connectivity
python -c "
from database.session import get_database_session
try:
    session = get_database_session()
    session.execute('SELECT 1')
    print('Database OK')
except Exception as e:
    print(f'Database Error: {e}')
"

# Solution: Restart database or fix connection string
docker-compose restart postgres
```

### 2. Email Delivery Failures

#### Symptoms
- High bounce rate (>10%)
- Emails stuck in "pending" status
- SendGrid webhooks not processing

#### Diagnostic Steps
```bash
# Check email status distribution
python -c "
from d9_delivery.models import Email
from database.session import get_database_session
from sqlalchemy import func
session = get_database_session()
stats = session.query(Email.status, func.count()).group_by(Email.status).all()
for status, count in stats:
    print(f'{status}: {count}')
"

# Check SendGrid API status
curl -H 'Authorization: Bearer $SENDGRID_API_KEY' \
     https://api.sendgrid.com/v3/user/account

# Review webhook events
tail -50 logs/sendgrid_events.log
```

#### Common Root Causes

**A. Invalid Email Addresses**
```bash
# Find invalid emails
python -c "
from d9_delivery.models import Email
from database.session import get_database_session
session = get_database_session()
bounced = session.query(Email).filter(Email.status=='bounced').limit(10).all()
for email in bounced:
    print(f'Bounced: {email.to_address} - {email.bounce_reason}')
"

# Solution: Improve email validation
python scripts/validate_email_list.py --fix
```

**B. Spam Filter Issues**
```bash
# Check spam scores
python -c "
from d8_personalization.spam_checker import SpamChecker
checker = SpamChecker()
recent_emails = get_recent_emails(10)  # Get recent emails
for email in recent_emails:
    score = checker.check_spam_score(email.content)
    print(f'Email {email.id}: {score}')
"

# Solution: Adjust content generation
# Edit d8_personalization/spam_rules.json to fix common issues
```

**C. SendGrid Configuration Issues**
```bash
# Verify SendGrid settings
python -c "
from d9_delivery.sendgrid_client import SendGridClient
client = SendGridClient()
print(client.verify_configuration())
"

# Check API key permissions
curl -H 'Authorization: Bearer $SENDGRID_API_KEY' \
     https://api.sendgrid.com/v3/scopes
```

### 3. Assessment Generation Failures

#### Symptoms
- Businesses stuck in "assessment_pending" status
- PageSpeed API errors
- AI insights not generating

#### Diagnostic Steps
```bash
# Check assessment coordinator status
python -c "
from d3_assessment.coordinator import AssessmentCoordinator
coordinator = AssessmentCoordinator()
print(coordinator.get_status())
"

# Test PageSpeed API
python -c "
from d0_gateway.providers.pagespeed import PageSpeedClient
client = PageSpeedClient()
result = client.test_connection()
print(result)
"

# Check OpenAI API
python -c "
from d0_gateway.providers.openai import OpenAIClient
client = OpenAIClient()
result = client.test_connection()
print(result)
"
```

#### Common Root Causes

**A. PageSpeed API Rate Limits**
```bash
# Check PageSpeed quota usage
python -c "
from d0_gateway.rate_limiter import RateLimiter
limiter = RateLimiter()
print(limiter.get_usage('pagespeed'))
"

# Solution: Implement caching or reduce frequency
export PAGESPEED_CACHE_TTL=86400  # 24 hours
```

**B. Invalid Website URLs**
```bash
# Find problematic URLs
python -c "
from d3_assessment.models import AssessmentResult
from database.session import get_database_session
session = get_database_session()
failed = session.query(AssessmentResult).filter(
    AssessmentResult.status=='failed'
).limit(10).all()
for result in failed:
    print(f'Failed: {result.business.website} - {result.error_message}')
"

# Solution: Improve URL validation
python scripts/validate_websites.py --fix
```

**C. OpenAI API Issues**
```bash
# Check OpenAI usage and limits
python -c "
from d0_gateway.providers.openai import OpenAIClient
client = OpenAIClient()
usage = client.get_usage_stats()
print(f'Tokens used: {usage}')
"

# Solution: Optimize prompts or increase limits
# Edit d3_assessment/prompts.py to reduce token usage
```

### 4. Payment Processing Issues

#### Symptoms
- Stripe webhooks failing
- Purchases not completing
- Revenue tracking inaccurate

#### Diagnostic Steps
```bash
# Check Stripe webhook status
python -c "
from d7_storefront.webhook_handlers import StripeWebhookHandler
handler = StripeWebhookHandler()
print(handler.get_webhook_status())
"

# Review recent purchases
python -c "
from d7_storefront.models import Purchase
from database.session import get_database_session
session = get_database_session()
recent = session.query(Purchase).order_by(Purchase.created_at.desc()).limit(10).all()
for purchase in recent:
    print(f'{purchase.stripe_payment_id}: {purchase.status}')
"

# Test Stripe connectivity
python scripts/verify_integrations.py | grep -A5 "Stripe"
```

#### Common Root Causes

**A. Webhook Signature Verification Failing**
```bash
# Check webhook endpoint logs
grep "webhook" logs/app.log | tail -20

# Verify webhook secret
python -c "
import os
print('Webhook secret configured:', bool(os.getenv('STRIPE_WEBHOOK_SECRET')))
"

# Solution: Update webhook secret in Stripe dashboard
# Copy new secret to .env.production
```

**B. Payment Amount Calculation Errors**
```bash
# Check pricing configuration
python -c "
from d7_storefront.checkout import CheckoutManager
manager = CheckoutManager()
print(manager.get_pricing_config())
"

# Verify tax calculation
python -c "
from d7_storefront.checkout import calculate_total
print(calculate_total(base_amount=9900, tax_rate=0.08))  # $99 + tax
"
```

### 5. Database Performance Issues

#### Symptoms
- Slow query performance
- Database connection timeouts
- High CPU/memory usage

#### Diagnostic Steps
```bash
# Check database performance
psql -c "
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;
"

# Check active connections
psql -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# Monitor database size
psql -c "
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

#### Common Root Causes

**A. Missing or Inefficient Indexes**
```bash
# Analyze query plans
psql -c "EXPLAIN ANALYZE SELECT * FROM businesses WHERE score > 80;"

# Check index usage
python scripts/analyze_indexes.py

# Solution: Add appropriate indexes
psql -c "CREATE INDEX CONCURRENTLY idx_businesses_score ON businesses(score);"
```

**B. Database Maintenance Needed**
```bash
# Check table bloat
psql -c "
SELECT schemaname, tablename, 
       n_tup_ins, n_tup_upd, n_tup_del,
       last_vacuum, last_autovacuum, last_analyze
FROM pg_stat_user_tables;
"

# Solution: Run maintenance
psql -c "VACUUM ANALYZE;"
```

### 6. Memory and Resource Issues

#### Symptoms
- Out of memory errors
- Container restarts
- Slow response times

#### Diagnostic Steps
```bash
# Check container resource usage
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Check system resources
free -h
df -h

# Monitor process memory
ps aux --sort=-%mem | head -10
```

#### Common Root Causes

**A. Memory Leaks in Python Processes**
```bash
# Monitor Python memory usage
python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print(f'Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB')
"

# Solution: Restart containers periodically
docker-compose restart app
```

**B. Large Dataset Processing**
```bash
# Check batch sizes
grep "BATCH_SIZE" .env.production

# Reduce batch sizes temporarily
export ASSESSMENT_BATCH_SIZE=10
export EMAIL_BATCH_SIZE=50
```

### 7. External API Issues

#### Symptoms
- API rate limit errors
- Connection timeouts
- Authentication failures

#### Diagnostic Steps
```bash
# Test all integrations
python scripts/verify_integrations.py --verbose

# Check circuit breaker status
python -c "
from d0_gateway.circuit_breaker import CircuitBreaker
apis = ['yelp', 'pagespeed', 'openai', 'sendgrid', 'stripe']
for api in apis:
    cb = CircuitBreaker(api)
    print(f'{api}: {cb.state}')
"

# Review API usage
python -c "
from d0_gateway.metrics import get_api_metrics
print(get_api_metrics())
"
```

#### Common Root Causes

**A. API Key Issues**
```bash
# Verify API keys are set
python -c "
import os
keys = ['YELP_API_KEY', 'GOOGLE_API_KEY', 'OPENAI_API_KEY', 'SENDGRID_API_KEY', 'STRIPE_SECRET_KEY']
for key in keys:
    print(f'{key}: {\"SET\" if os.getenv(key) else \"MISSING\"}')
"

# Test individual API authentication
python -c "
from d0_gateway.providers.yelp import YelpClient
client = YelpClient()
print(client.test_authentication())
"
```

**B. Rate Limit Configuration**
```bash
# Check rate limit settings
python -c "
from core.config import Config
config = Config()
print('Rate limits:', config.RATE_LIMITS)
"

# Adjust rate limits if needed
# Edit core/config.py rate limit settings
```

## Monitoring and Alerts

### Setting Up Alerts

1. **Configure Prometheus alerts**:
   ```yaml
   # monitoring/alerts.yaml
   groups:
   - name: leadfactory
     rules:
     - alert: PipelineDown
       expr: pipeline_businesses_processed_total == 0
       for: 2h
       labels:
         severity: critical
   ```

2. **Set up notification channels**:
   ```bash
   # Configure Slack webhook
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."
   
   # Test alert
   python scripts/test_alert.py --type=pipeline_failure
   ```

### Log Analysis

1. **Error pattern analysis**:
   ```bash
   # Find common error patterns
   grep ERROR logs/app.log | cut -d' ' -f5- | sort | uniq -c | sort -nr
   
   # Database error analysis
   grep "DatabaseError" logs/app.log | tail -20
   
   # API error analysis
   grep "APIError" logs/app.log | cut -d' ' -f6 | sort | uniq -c
   ```

2. **Performance analysis**:
   ```bash
   # Response time analysis
   grep "response_time" logs/app.log | awk '{print $NF}' | sort -n | tail -20
   
   # Database query analysis
   grep "slow_query" logs/postgresql.log | tail -10
   ```

## Performance Tuning

### Database Optimization

1. **Query optimization**:
   ```sql
   -- Enable query logging
   ALTER SYSTEM SET log_min_duration_statement = 1000;
   
   -- Analyze slow queries
   SELECT query, calls, total_time, mean_time 
   FROM pg_stat_statements 
   WHERE mean_time > 100
   ORDER BY total_time DESC;
   ```

2. **Connection pooling**:
   ```python
   # Update database/session.py
   engine = create_engine(
       database_url,
       pool_size=20,
       max_overflow=30,
       pool_pre_ping=True
   )
   ```

### Application Optimization

1. **Caching strategy**:
   ```python
   # Increase cache TTL for stable data
   CACHE_TTL = {
       'business_data': 3600,      # 1 hour
       'assessment_results': 7200,  # 2 hours
       'scoring_rules': 86400       # 24 hours
   }
   ```

2. **Batch processing optimization**:
   ```bash
   # Optimize batch sizes based on available memory
   export ASSESSMENT_BATCH_SIZE=20
   export EMAIL_GENERATION_BATCH_SIZE=100
   export SCORING_BATCH_SIZE=500
   ```

## Recovery Procedures

### Database Recovery

1. **Point-in-time recovery**:
   ```bash
   # Stop application
   docker-compose stop app
   
   # Restore database
   python scripts/restore_database.py --timestamp="2023-12-01 14:30:00"
   
   # Verify data integrity
   python scripts/verify_data_integrity.py
   
   # Restart application
   docker-compose start app
   ```

2. **Partial data recovery**:
   ```bash
   # Recover specific table
   pg_restore -t businesses backup.sql
   
   # Verify recovery
   psql -c "SELECT COUNT(*) FROM businesses;"
   ```

### Application Recovery

1. **Rollback deployment**:
   ```bash
   # Identify last known good commit
   git log --oneline -10
   
   # Rollback
   git checkout <commit-hash>
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   
   # Verify health
   python scripts/health_check.py
   ```

2. **Service-specific recovery**:
   ```bash
   # Restart specific service
   docker-compose restart pipeline
   
   # Check service logs
   docker logs leadfactory_pipeline_1 --tail=50
   ```

## Escalation Procedures

### Level 1: Self-Service
- Check this troubleshooting guide
- Run diagnostic commands
- Review recent logs
- Apply common fixes

### Level 2: Team Support
- Create support ticket with:
  - Error symptoms
  - Diagnostic output
  - Steps already taken
  - Business impact

### Level 3: Vendor Support
- Contact external API providers
- Include API key and account details
- Provide error codes and timestamps

### Level 4: Emergency Response
- Critical system down
- Data corruption detected
- Security incident

## Prevention Best Practices

### Monitoring Setup
```bash
# Set up comprehensive monitoring
python scripts/setup_monitoring.py --alerts --dashboards --logging

# Configure automated backups
python scripts/setup_backups.py --schedule="0 4 * * *" --retention=30

# Enable health checks
python scripts/setup_health_checks.py --interval=60 --endpoints=all
```

### Maintenance Schedule
```bash
# Weekly maintenance
0 2 * * 0 /app/scripts/weekly_maintenance.sh

# Monthly optimization
0 3 1 * * /app/scripts/monthly_optimization.sh

# Quarterly review
0 4 1 */3 * /app/scripts/quarterly_review.sh
```

### Documentation
- Keep runbook updated
- Document configuration changes
- Maintain incident postmortems
- Update contact information

## Emergency Contacts

### Internal Team
- **On-call Engineer**: [Contact]
- **Database Administrator**: [Contact]
- **DevOps Lead**: [Contact]

### External Vendors
- **Yelp API Support**: [Contact]
- **SendGrid Support**: [Contact]
- **Stripe Support**: [Contact]
- **OpenAI Support**: [Contact]
- **Infrastructure Provider**: [Contact]

### Escalation Matrix
```
Severity 1 (Critical): < 15 minutes
Severity 2 (High): < 1 hour  
Severity 3 (Medium): < 4 hours
Severity 4 (Low): < 24 hours
```