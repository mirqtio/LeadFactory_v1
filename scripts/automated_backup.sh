#!/bin/bash
# Automated backup script for production

BACKUP_DIR=/backups/$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Database backup
PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h postgres -U leadfactory leadfactory | gzip > $BACKUP_DIR/database.sql.gz

# Application files backup
tar -czf $BACKUP_DIR/app_files.tar.gz /app/uploads /app/logs

# Keep only last 7 days of backups
find /backups -type d -mtime +7 -exec rm -rf {} \;

echo "Backup completed: $BACKUP_DIR"
