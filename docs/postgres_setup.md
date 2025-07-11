# PostgreSQL Container Setup for VPS

## Overview

This guide covers the PostgreSQL container setup as part of the LeadFactory production deployment (P0-012).

## Container Configuration

PostgreSQL runs as a service in `docker-compose.prod.yml` with the following configuration:

```yaml
db:
  image: postgres:15-alpine
  container_name: leadfactory_db
  restart: always
  environment:
    - POSTGRES_USER=leadfactory
    - POSTGRES_PASSWORD=${DB_PASSWORD}
    - POSTGRES_DB=leadfactory
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U leadfactory"]
    interval: 10s
    timeout: 5s
    retries: 5
```

## Initial Setup

1. **Set database password in environment**:
   ```bash
   # On VPS, create .env file in /srv/leadfactory
   echo "DB_PASSWORD=$(openssl rand -base64 32)" >> /srv/leadfactory/.env
   ```

2. **Start PostgreSQL container**:
   ```bash
   cd /srv/leadfactory
   docker compose -f docker-compose.prod.yml up -d db
   ```

3. **Verify container is running**:
   ```bash
   docker compose ps db
   # Should show "healthy" status
   ```

4. **Run database migrations**:
   ```bash
   # Execute migrations in web container
   docker compose -f docker-compose.prod.yml run --rm web alembic upgrade head
   ```

## Database Management

### Connect to PostgreSQL

```bash
# Interactive psql session
docker compose -f docker-compose.prod.yml exec db psql -U leadfactory

# Run single query
docker compose -f docker-compose.prod.yml exec db psql -U leadfactory -c "SELECT version();"
```

### Backup Database

```bash
# Create backup directory
mkdir -p /srv/leadfactory/backups

# Backup database
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U leadfactory leadfactory | gzip > /srv/leadfactory/backups/leadfactory_$(date +%Y%m%d_%H%M%S).sql.gz

# List backups
ls -lh /srv/leadfactory/backups/
```

### Restore Database

```bash
# Restore from backup
gunzip -c /srv/leadfactory/backups/leadfactory_20250111_120000.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U leadfactory leadfactory
```

### Automated Backups

Create a cron job for daily backups:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /srv/leadfactory && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U leadfactory leadfactory | gzip > /srv/leadfactory/backups/leadfactory_$(date +\%Y\%m\%d).sql.gz && find /srv/leadfactory/backups -name "*.sql.gz" -mtime +7 -delete
```

## Performance Tuning

### PostgreSQL Configuration

Create custom PostgreSQL configuration:

```bash
# Create config directory
mkdir -p /srv/leadfactory/postgres/conf.d

# Create custom config
cat > /srv/leadfactory/postgres/conf.d/custom.conf << EOF
# Connection settings
max_connections = 100

# Memory settings (adjust based on VPS RAM)
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB

# Query planning
random_page_cost = 1.1
effective_io_concurrency = 200

# Logging
log_min_duration_statement = 1000
log_line_prefix = '%t [%p]: [%l-1] db=%d,user=%u '
EOF
```

Update docker-compose.prod.yml to use custom config:

```yaml
db:
  # ... other settings ...
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./postgres/conf.d:/etc/postgresql/conf.d:ro
  command: postgres -c 'config_file=/etc/postgresql/postgresql.conf' -c 'include_dir=/etc/postgresql/conf.d'
```

### Monitor Performance

```bash
# Check database size
docker compose -f docker-compose.prod.yml exec db psql -U leadfactory -c "SELECT pg_database_size('leadfactory')/1024/1024 as size_mb;"

# Active connections
docker compose -f docker-compose.prod.yml exec db psql -U leadfactory -c "SELECT count(*) FROM pg_stat_activity;"

# Long running queries
docker compose -f docker-compose.prod.yml exec db psql -U leadfactory -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';"
```

## Health Checks

The PostgreSQL container includes health checks that:
- Run `pg_isready` every 10 seconds
- Mark container as unhealthy after 5 failed attempts
- Integrate with Docker's health monitoring

Monitor health status:

```bash
# Check health status
docker inspect leadfactory_db --format='{{.State.Health.Status}}'

# View health check logs
docker inspect leadfactory_db --format='{{range .State.Health.Log}}{{.Output}}{{end}}'
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs db --tail 50

# Common issues:
# - Invalid DB_PASSWORD in .env
# - Disk space full
# - Port 5432 already in use
```

### Connection refused

```bash
# Verify container is running
docker compose ps db

# Check if PostgreSQL is listening
docker compose -f docker-compose.prod.yml exec db netstat -tlnp | grep 5432

# Test connection from web container
docker compose -f docker-compose.prod.yml exec web python -c "
import psycopg2
conn = psycopg2.connect('postgresql://leadfactory:password@db:5432/leadfactory')
print('Connected successfully!')
"
```

### Disk space issues

```bash
# Check volume size
docker system df -v | grep postgres_data

# Clean up old WAL files
docker compose -f docker-compose.prod.yml exec db psql -U leadfactory -c "CHECKPOINT;"

# Vacuum database
docker compose -f docker-compose.prod.yml exec db vacuumdb -U leadfactory -d leadfactory -f -z
```

## Security Best Practices

1. **Network isolation**: PostgreSQL is only accessible within Docker network
2. **Strong passwords**: Use generated passwords, never hardcode
3. **Regular updates**: Keep postgres:15-alpine image updated
4. **Backup encryption**: Encrypt backup files at rest
5. **Connection limits**: Set appropriate max_connections
6. **SSL/TLS**: Enable for external connections (if needed)

## Verification Checklist

- [ ] PostgreSQL container running with "healthy" status
- [ ] Database accessible from web container
- [ ] Migrations applied successfully
- [ ] Backup script tested and working
- [ ] Health checks passing
- [ ] No errors in PostgreSQL logs
- [ ] Automated backups scheduled
- [ ] Performance metrics baseline established