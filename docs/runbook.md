# LeadFactory MVP Operations Runbook

## Overview

This runbook provides comprehensive operational guidance for the LeadFactory MVP, covering deployment, monitoring, maintenance, and troubleshooting procedures.

## System Architecture

LeadFactory is built as a microservices architecture with 12 main domains:

- **D0 Gateway**: Unified API gateway with rate limiting and circuit breakers
- **D1 Targeting**: Geographic and vertical campaign management
- **D2 Sourcing**: Yelp data acquisition and deduplication  
- **D3 Assessment**: Website analysis with PageSpeed and AI insights
- **D4 Enrichment**: Google Business Profile data enhancement
- **D5 Scoring**: Lead quality scoring and tier assignment
- **D6 Reports**: PDF audit report generation
- **D7 Storefront**: Stripe payment processing and checkout
- **D8 Personalization**: AI-powered email content generation
- **D9 Delivery**: SendGrid email delivery with compliance
- **D10 Analytics**: Metrics warehouse and reporting
- **D11 Orchestration**: Prefect pipeline coordination and A/B testing

## Quick Start

### Prerequisites

- Docker and Docker Compose
- PostgreSQL database
- Redis for caching
- API keys for: Yelp, Google PageSpeed, OpenAI, SendGrid, Stripe

### Initial Setup

1. **Clone and configure**:
   ```bash
   git clone <repository>
   cd leadfactory
   cp .env.example .env.production
   # Edit .env.production with your API keys
   ```

2. **Database setup**:
   ```bash
   python scripts/db_setup.py
   alembic upgrade head
   ```

3. **Start services**:
   ```bash
   docker-compose -f docker-compose.production.yml up -d
   ```

4. **Verify deployment**:
   ```bash
   python scripts/system_check.py
   python scripts/health_check.py
   ```

## Daily Operations

### Morning Checklist

1. **Check system health**:
   ```bash
   python scripts/health_check.py
   python scripts/system_check.py --json > /tmp/health.json
   ```

2. **Review overnight pipeline**:
   ```bash
   # Check pipeline logs
   docker logs leadfactory_pipeline_1
   
   # Review metrics
   curl localhost:9090/metrics | grep leadfactory
   ```

3. **Verify integrations**:
   ```bash
   python scripts/verify_integrations.py
   ```

4. **Check campaign performance**:
   ```bash
   # Review analytics dashboard
   open http://localhost:3000/d/funnel
   
   # Check revenue metrics
   python -c "
   from d10_analytics.warehouse import get_daily_metrics
   print(get_daily_metrics())
   "
   ```

### Campaign Management

#### Launch New Campaign

1. **Create target campaigns**:
   ```bash
   python scripts/seed_campaigns.py --vertical=restaurant --zip=10001 --quota=100
   ```

2. **Test pipeline execution**:
   ```bash
   python scripts/test_pipeline.py --limit=10 --dry-run
   ```

3. **Launch production batch**:
   ```bash
   python scripts/launch_campaign.py --batch=100
   ```

#### Monitor Campaign Progress

1. **Check email delivery**:
   ```bash
   # SendGrid webhook logs
   tail -f logs/sendgrid_events.log
   
   # Delivery metrics
   python -c "
   from d9_delivery.models import Email
   from database.session import get_database_session
   session = get_database_session()
   total = session.query(Email).count()
   delivered = session.query(Email).filter(Email.status=='delivered').count()
   print(f'Delivered: {delivered}/{total} ({delivered/total*100:.1f}%)')
   "
   ```

2. **Track conversions**:
   ```bash
   # Purchase tracking
   python -c "
   from d7_storefront.models import Purchase
   from database.session import get_database_session
   session = get_database_session()
   today_purchases = session.query(Purchase).filter(
       Purchase.created_at >= datetime.utcnow().date()
   ).count()
   print(f'Today purchases: {today_purchases}')
   "
   ```

#### A/B Test Management

1. **Load experiments**:
   ```bash
   python scripts/load_experiments.py
   ```

2. **Check experiment performance**:
   ```bash
   python -c "
   from d11_orchestration.experiments import get_experiment_metrics
   print(get_experiment_metrics('subject_line_test'))
   "
   ```

3. **Update experiment allocation**:
   ```bash
   # Edit experiments/production.yaml
   # Then reload:
   python scripts/load_experiments.py --reload
   ```

## Monitoring & Alerting

### Key Metrics to Monitor

1. **Pipeline Health**:
   - Daily businesses processed: Target > 1000
   - Email generation rate: Target > 95%
   - Assessment completion rate: Target > 90%

2. **Email Performance**:
   - Delivery rate: Target > 95%
   - Bounce rate: Target < 5%
   - Spam rate: Target < 1%

3. **Revenue Metrics**:
   - Daily revenue: Track trends
   - Conversion rate: Email → Purchase
   - Customer acquisition cost

4. **System Performance**:
   - API response times: Target < 2s
   - Database query performance
   - External API rate limits

### Alert Thresholds

```yaml
# monitoring/alerts.yaml
critical:
  - pipeline_failure: 0 businesses processed in 2 hours
  - high_bounce_rate: > 10% in 1 hour
  - payment_failure: Stripe webhooks failing
  - database_down: Connection failures

warning:
  - low_delivery_rate: < 90% in 4 hours  
  - api_rate_limits: > 80% utilization
  - disk_space: > 85% usage
```

### Grafana Dashboards

Access dashboards at http://localhost:3000:

1. **Funnel Overview**: End-to-end conversion metrics
2. **System Health**: Infrastructure and performance
3. **Revenue Dashboard**: Financial metrics and trends
4. **Email Performance**: Delivery and engagement metrics

## Maintenance Procedures

### Daily Maintenance (Automated)

Cron jobs handle routine maintenance:

1. **Pipeline execution** (02:00 UTC):
   ```bash
   /app/cron/daily_pipeline.sh
   ```

2. **Log rotation** (03:00 UTC):
   ```bash
   /app/cron/cleanup.sh
   ```

3. **Database backup** (04:00 UTC):
   ```bash
   /app/cron/backup.sh
   ```

### Weekly Maintenance

1. **Update dependencies**:
   ```bash
   pip list --outdated
   # Review and update requirements.txt
   docker-compose build --no-cache
   ```

2. **Performance review**:
   ```bash
   # Generate performance report
   python scripts/performance_report.py --days=7
   
   # Database optimization
   python scripts/db_maintenance.py --vacuum --analyze
   ```

3. **Security audit**:
   ```bash
   # Run security tests
   pytest tests/security/ -v
   
   # Check for vulnerabilities
   safety check
   bandit -r . -x tests/
   ```

### Monthly Maintenance

1. **Capacity planning**:
   - Review growth metrics
   - Assess infrastructure scaling needs
   - Update quotas and rate limits

2. **Cost optimization**:
   - Review external API usage
   - Optimize database queries
   - Archive old data

3. **Backup verification**:
   ```bash
   # Test backup restoration
   python scripts/test_backup_restore.py
   ```

## Scaling Procedures

### Horizontal Scaling

1. **Add pipeline workers**:
   ```bash
   # Update docker-compose.production.yml
   docker-compose up -d --scale pipeline=3
   ```

2. **Database read replicas**:
   ```bash
   # Configure read replicas in database/session.py
   # Update connection strings
   ```

3. **Redis clustering**:
   ```bash
   # Configure Redis cluster
   # Update cache configuration
   ```

### Vertical Scaling

1. **Increase container resources**:
   ```yaml
   # docker-compose.production.yml
   services:
     app:
       deploy:
         resources:
           limits:
             memory: 2G
             cpus: '2.0'
   ```

2. **Database scaling**:
   ```bash
   # Increase PostgreSQL resources
   # Tune postgresql.conf parameters
   ```

## Backup & Recovery

### Backup Strategy

1. **Database backups**:
   - Full daily backup to S3
   - Point-in-time recovery enabled
   - 30-day retention policy

2. **Configuration backups**:
   - Git repository for all configs
   - Environment variables in secure vault
   - Kubernetes secrets backup

3. **Data exports**:
   ```bash
   # Export critical data
   python scripts/export_data.py --table=businesses --date=today
   python scripts/export_data.py --table=campaigns --date=today
   ```

### Recovery Procedures

1. **Database recovery**:
   ```bash
   # From latest backup
   python scripts/restore_database.py --backup=latest
   
   # Point-in-time recovery
   python scripts/restore_database.py --timestamp="2023-12-01 10:30:00"
   ```

2. **Application recovery**:
   ```bash
   # Rollback to previous version
   git checkout <previous-commit>
   docker-compose down
   docker-compose build
   docker-compose up -d
   
   # Verify health
   python scripts/health_check.py
   ```

3. **Configuration recovery**:
   ```bash
   # Restore from git
   git checkout main -- config/
   
   # Reload configurations
   python scripts/reload_config.py
   ```

## Security Procedures

### Access Control

1. **API authentication**:
   - All endpoints require API keys
   - Rate limiting per API key
   - Audit logs for all requests

2. **Database security**:
   - Encrypted connections (SSL)
   - Role-based access control
   - Regular credential rotation

3. **Secrets management**:
   - Environment variables for secrets
   - No hardcoded credentials
   - Secure vault for production

### Security Monitoring

1. **Intrusion detection**:
   ```bash
   # Check for suspicious activity
   grep "SECURITY" logs/app.log
   
   # Review failed authentication attempts
   grep "AUTH_FAILED" logs/security.log
   ```

2. **Vulnerability scanning**:
   ```bash
   # Scan dependencies
   safety check
   
   # Code security scan
   bandit -r . -f json -o security_report.json
   ```

3. **Compliance checks**:
   ```bash
   # Run compliance tests
   pytest tests/security/test_compliance.py -v
   ```

## Performance Optimization

### Database Optimization

1. **Query optimization**:
   ```sql
   -- Enable slow query logging
   ALTER SYSTEM SET log_min_duration_statement = 1000;
   
   -- Analyze query performance
   EXPLAIN ANALYZE SELECT * FROM businesses WHERE score > 80;
   ```

2. **Index maintenance**:
   ```bash
   # Check index usage
   python scripts/analyze_indexes.py
   
   # Reindex if needed
   python scripts/reindex_database.py
   ```

### Application Optimization

1. **Caching optimization**:
   ```bash
   # Check cache hit rates
   redis-cli info stats | grep hit_rate
   
   # Clear cache if needed
   redis-cli flushdb
   ```

2. **Rate limit tuning**:
   ```bash
   # Monitor rate limit usage
   python -c "
   from d0_gateway.rate_limiter import RateLimiter
   limiter = RateLimiter()
   print(limiter.get_usage_stats())
   "
   ```

## Emergency Procedures

### System Down

1. **Immediate response**:
   ```bash
   # Check all services
   docker-compose ps
   
   # Restart failed services
   docker-compose restart <service>
   
   # Check logs
   docker logs <container> --tail=100
   ```

2. **Database issues**:
   ```bash
   # Check database connectivity
   pg_isready -h localhost -p 5432
   
   # Check database stats
   psql -c "SELECT * FROM pg_stat_activity;"
   ```

3. **External API failures**:
   ```bash
   # Check API status
   python scripts/verify_integrations.py
   
   # Enable circuit breakers
   python -c "
   from d0_gateway.circuit_breaker import CircuitBreaker
   CircuitBreaker('yelp').force_open()
   "
   ```

### Data Corruption

1. **Immediate containment**:
   ```bash
   # Stop all writes
   docker-compose stop pipeline
   
   # Create emergency backup
   python scripts/emergency_backup.py
   ```

2. **Assess damage**:
   ```bash
   # Run data integrity checks
   python scripts/verify_data_integrity.py
   
   # Generate corruption report
   python scripts/data_corruption_report.py
   ```

3. **Recovery**:
   ```bash
   # Restore from last good backup
   python scripts/restore_database.py --verify
   
   # Replay transactions if possible
   python scripts/replay_transactions.py --since="last-backup"
   ```

## Contact Information

### Team Contacts

- **On-call Engineer**: [Phone/Slack]
- **Database Admin**: [Contact]
- **DevOps Lead**: [Contact]
- **Product Manager**: [Contact]

### External Vendors

- **Yelp API Support**: api-support@yelp.com
- **SendGrid Support**: support@sendgrid.com  
- **Stripe Support**: support@stripe.com
- **OpenAI Support**: support@openai.com

### Escalation Procedures

1. **Level 1**: On-call engineer
2. **Level 2**: Senior engineer + DevOps lead
3. **Level 3**: CTO + Product manager
4. **Level 4**: External vendor support

## Appendix

### Useful Commands

```bash
# System health check
python scripts/system_check.py

# Database maintenance
python scripts/db_maintenance.py --vacuum --analyze

# Performance monitoring
docker stats $(docker ps --format "table {{.Names}}" | grep leadfactory)

# Log analysis
tail -f logs/app.log | grep ERROR

# Backup verification
python scripts/verify_backup.py --backup=latest

# Configuration reload
python scripts/reload_config.py --service=all
```

### Configuration Files

- `.env.production`: Production environment variables
- `config/production.yaml`: Application configuration
- `docker-compose.production.yml`: Container orchestration
- `monitoring/alerts.yaml`: Alert configurations
- `experiments/production.yaml`: A/B test configurations

### Log Locations

- Application logs: `logs/app.log`
- Pipeline logs: `logs/pipeline.log`
- Database logs: `logs/postgresql.log`
- Nginx logs: `logs/nginx/`
- Security logs: `logs/security.log`

### Metrics Endpoints

- Prometheus metrics: `http://localhost:9090/metrics`
- Application health: `http://localhost:8000/health`
- Database metrics: `http://localhost:9187/metrics`