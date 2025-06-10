#!/bin/bash
# PostgreSQL Backup Script - Task 091
# Automated daily backup with compression and retention

set -e

# Configuration from environment variables
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-leadfactory}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/postgresql}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Generate backup filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/leadfactory_$TIMESTAMP.sql.gz"

echo "Starting PostgreSQL backup at $(date)"
echo "Database: $PGDATABASE at $PGHOST:$PGPORT"
echo "Backup file: $BACKUP_FILE"

# Create compressed backup
pg_dump \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --username="$PGUSER" \
    --no-password \
    --verbose \
    --format=custom \
    --compress=9 \
    --file="${BACKUP_FILE%.gz}" \
    "$PGDATABASE"

# Compress the backup
gzip "${BACKUP_FILE%.gz}"

echo "Backup completed: $BACKUP_FILE"
echo "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"

# Cleanup old backups (keep last N days)
find "$BACKUP_DIR" -name "leadfactory_*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "Old backups cleaned up (retention: $RETENTION_DAYS days)"

# Optional: Upload to S3 if configured
if [ -n "$BACKUP_S3_BUCKET" ]; then
    echo "Uploading backup to S3: $BACKUP_S3_BUCKET"
    aws s3 cp "$BACKUP_FILE" "s3://$BACKUP_S3_BUCKET/database-backups/"
    echo "S3 upload completed"
fi

echo "Backup process finished at $(date)"