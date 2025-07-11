# Database Backup Strategy

## Overview

This document outlines the backup strategy for the PostgreSQL database running in a Docker container on the VPS.

## Backup Components

### 1. Named Volume Persistence

The PostgreSQL data is stored in a named Docker volume `postgres_data` which persists across container restarts:

```yaml
volumes:
  postgres_data:
    driver: local
```

### 2. Daily Automated Backups

Create a cron job on the VPS for daily backups:

```bash
# Add to crontab (crontab -e)
0 2 * * * /srv/leadfactory/scripts/backup_database.sh
```

### 3. Backup Script

Create `/srv/leadfactory/scripts/backup_database.sh`:

```bash
#!/bin/bash
# Database backup script for LeadFactory

set -e

# Configuration
BACKUP_DIR="/srv/leadfactory/backups"
CONTAINER_NAME="leadfactory_db"
DB_NAME="leadfactory"
DB_USER="leadfactory"
RETENTION_DAYS=7

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/leadfactory_${TIMESTAMP}.sql.gz"

# Perform backup
echo "Starting database backup..."
docker exec -t $CONTAINER_NAME pg_dump -U $DB_USER $DB_NAME | gzip > "$BACKUP_FILE"

# Verify backup
if [ -f "$BACKUP_FILE" ]; then
    SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    echo "Backup completed: $BACKUP_FILE (Size: $SIZE)"
else
    echo "ERROR: Backup failed!"
    exit 1
fi

# Remove old backups
echo "Removing backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "leadfactory_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# List current backups
echo "Current backups:"
ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -5
```

### 4. Manual Backup Commands

For immediate backups:

```bash
# Quick backup
docker exec leadfactory_db pg_dump -U leadfactory leadfactory | gzip > leadfactory_$(date +%Y%m%d).sql.gz

# Backup with custom format (faster restore)
docker exec leadfactory_db pg_dump -U leadfactory -Fc leadfactory > leadfactory_$(date +%Y%m%d).dump
```

### 5. Restore Procedures

#### From gzipped SQL backup:
```bash
# Stop application to prevent writes
docker compose -f docker-compose.prod.yml stop web

# Restore database
gunzip -c /srv/leadfactory/backups/leadfactory_20250711.sql.gz | \
  docker exec -i leadfactory_db psql -U leadfactory leadfactory

# Restart application
docker compose -f docker-compose.prod.yml start web
```

#### From custom format backup:
```bash
docker exec -i leadfactory_db pg_restore -U leadfactory -d leadfactory < leadfactory_20250711.dump
```

### 6. Volume Backup (Full System)

For complete disaster recovery, backup the entire Docker volume:

```bash
# Stop containers
docker compose -f docker-compose.prod.yml down

# Backup volume
docker run --rm -v leadfactory_postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres_volume_$(date +%Y%m%d).tar.gz -C /data .

# Restart containers
docker compose -f docker-compose.prod.yml up -d
```

### 7. Remote Backup Storage

For production, consider:

1. **S3 Storage**: Upload backups to AWS S3 or compatible storage
2. **Remote Server**: rsync backups to a separate backup server
3. **Managed Backup**: Use VPS provider's backup service

Example S3 upload (requires AWS CLI):
```bash
aws s3 cp "$BACKUP_FILE" s3://your-backup-bucket/leadfactory/
```

## Backup Verification

### Weekly Verification Process

1. List recent backups:
   ```bash
   ls -lh /srv/leadfactory/backups/*.sql.gz | tail -10
   ```

2. Test restore to temporary database:
   ```bash
   docker exec leadfactory_db createdb -U leadfactory test_restore
   gunzip -c /srv/leadfactory/backups/latest.sql.gz | \
     docker exec -i leadfactory_db psql -U leadfactory test_restore
   docker exec leadfactory_db dropdb -U leadfactory test_restore
   ```

## Recovery Time Objectives

- **RPO (Recovery Point Objective)**: 24 hours (daily backups)
- **RTO (Recovery Time Objective)**: 1 hour
- **Backup Retention**: 7 days local, 30 days remote

## Monitoring

Add backup monitoring to ensure backups are running:

```bash
# Check last backup age
LAST_BACKUP=$(ls -t /srv/leadfactory/backups/*.sql.gz 2>/dev/null | head -1)
if [ -z "$LAST_BACKUP" ]; then
    echo "WARNING: No backups found!"
elif [ $(find "$LAST_BACKUP" -mtime +1 | wc -l) -gt 0 ]; then
    echo "WARNING: Last backup is more than 24 hours old!"
fi
```

## Migration to Managed Database

When moving to Supabase or RDS (P2-050), use these backups to migrate data:

1. Create final backup from Docker PostgreSQL
2. Restore to managed service
3. Update DATABASE_URL in application
4. Verify data integrity
5. Keep Docker backup for 30 days as fallback