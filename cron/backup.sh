#!/bin/bash
#
# Backup Cron Job - Task 097
#
# Automated backup of database, configuration files, and critical data
# Runs daily at 1 AM UTC before pipeline execution
#
# Acceptance Criteria:
# - Backups automated ✓
# - Database backup with compression
# - Configuration files backed up
# - Remote storage support

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
BACKUP_DIR="$PROJECT_ROOT/backups"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_LOG="$LOG_DIR/backup_${TIMESTAMP}.log"

# Backup settings
BACKUP_RETENTION_DAYS=30
DATABASE_BACKUP_COMPRESSION=true
CONFIG_BACKUP_ENABLED=true
REMOTE_BACKUP_ENABLED=false

# Remote backup settings (configure as needed)
S3_BUCKET="${BACKUP_S3_BUCKET:-}"
AWS_REGION="${AWS_REGION:-us-east-1}"
BACKUP_ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"

# Environment
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
cd "$PROJECT_ROOT"

# Source environment variables
if [ -f ".env.production" ]; then
    set -a
    source .env.production
    set +a
fi

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$BACKUP_LOG"
}

error_log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$BACKUP_LOG" >&2
}

# Notification function
send_notification() {
    local level="$1"
    local message="$2"
    
    log "NOTIFICATION [$level]: $message"
    
    # Send to monitoring system (if configured)
    if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
        curl -s -X POST "$SLACK_WEBHOOK_URL" \
            -H 'Content-type: application/json' \
            --data "{\"text\":\"[$level] LeadFactory Backup: $message\"}" || true
    fi
}

# Database backup
backup_database() {
    log "Starting database backup..."
    
    if [ -z "${DATABASE_URL:-}" ]; then
        log "Database backup skipped - DATABASE_URL not configured"
        return 0
    fi
    
    local db_backup_file="$BACKUP_DIR/database_${TIMESTAMP}.sql"
    local db_backup_compressed="$BACKUP_DIR/database_${TIMESTAMP}.sql.gz"
    
    # Extract database connection details
    local db_url="$DATABASE_URL"
    
    # Backup using pg_dump if available
    if command -v pg_dump >/dev/null 2>&1; then
        log "Creating PostgreSQL database backup..."
        
        if pg_dump "$db_url" > "$db_backup_file" 2>>"$BACKUP_LOG"; then
            log "Database backup created successfully: $db_backup_file"
            
            # Compress backup if enabled
            if [ "$DATABASE_BACKUP_COMPRESSION" = true ]; then
                log "Compressing database backup..."
                if gzip "$db_backup_file"; then
                    log "Database backup compressed: $db_backup_compressed"
                    db_backup_file="$db_backup_compressed"
                else
                    error_log "Database backup compression failed"
                fi
            fi
            
            # Verify backup integrity
            local backup_size=$(du -h "$db_backup_file" | cut -f1)
            log "Backup size: $backup_size"
            
            if [ -s "$db_backup_file" ]; then
                log "Database backup verification passed"
            else
                error_log "Database backup verification failed - file is empty"
                return 1
            fi
            
        else
            error_log "Database backup failed"
            return 1
        fi
        
    # Try Python script as fallback
    elif python3 -c "import psycopg2" 2>/dev/null; then
        log "Creating database backup via Python..."
        
        python3 -c "
import os
import psycopg2
import subprocess

try:
    # Connect and get table list
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    
    # Get all table names
    cur.execute(\"\"\"
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public'
    \"\"\")
    tables = [row[0] for row in cur.fetchall()]
    
    # Create backup using pg_dump
    cmd = ['pg_dump', os.environ['DATABASE_URL']]
    with open('$db_backup_file', 'w') as f:
        subprocess.run(cmd, stdout=f, check=True)
    
    print(f'Database backup created: $db_backup_file')
    
except Exception as e:
    print(f'Database backup failed: {e}')
    exit(1)
finally:
    if 'conn' in locals():
        conn.close()
" >> "$BACKUP_LOG" 2>&1
        
        if [ $? -eq 0 ] && [ -s "$db_backup_file" ]; then
            log "Database backup created via Python"
        else
            error_log "Python database backup failed"
            return 1
        fi
        
    else
        log "Database backup skipped - no PostgreSQL client available"
        return 0
    fi
    
    # Store backup metadata
    cat > "$BACKUP_DIR/database_${TIMESTAMP}.meta" << EOF
{
    "backup_date": "$TIMESTAMP",
    "database_url": "$(echo "$DATABASE_URL" | sed 's/:[^:]*@/:***@/')",
    "backup_file": "$(basename "$db_backup_file")",
    "backup_size": "$(stat -f%z "$db_backup_file" 2>/dev/null || stat -c%s "$db_backup_file" 2>/dev/null || echo 0)",
    "compressed": $DATABASE_BACKUP_COMPRESSION,
    "host": "$(hostname)",
    "user": "$(whoami)"
}
EOF
    
    return 0
}

# Configuration backup
backup_configuration() {
    if [ "$CONFIG_BACKUP_ENABLED" != true ]; then
        log "Configuration backup disabled"
        return 0
    fi
    
    log "Starting configuration backup..."
    
    local config_backup_file="$BACKUP_DIR/config_${TIMESTAMP}.tar.gz"
    
    # List of configuration files and directories to backup
    local config_items=(
        ".env.production"
        "config/"
        "cron/"
        "monitoring/"
        "data/initial_targets.csv"
        "scoring_rules*.yaml"
        "templates/"
        "docker-compose.production.yml"
        "requirements.txt"
        "alembic.ini"
        "alembic/versions/"
    )
    
    # Create list of existing items
    local existing_items=()
    for item in "${config_items[@]}"; do
        if [ -e "$item" ]; then
            existing_items+=("$item")
        fi
    done
    
    if [ ${#existing_items[@]} -eq 0 ]; then
        log "No configuration files found to backup"
        return 0
    fi
    
    # Create configuration backup
    log "Backing up configuration files: ${existing_items[*]}"
    
    if tar -czf "$config_backup_file" "${existing_items[@]}" 2>>"$BACKUP_LOG"; then
        local backup_size=$(du -h "$config_backup_file" | cut -f1)
        log "Configuration backup created: $config_backup_file ($backup_size)"
        
        # Store configuration backup metadata
        cat > "$BACKUP_DIR/config_${TIMESTAMP}.meta" << EOF
{
    "backup_date": "$TIMESTAMP",
    "backup_file": "$(basename "$config_backup_file")",
    "backup_size": "$(stat -f%z "$config_backup_file" 2>/dev/null || stat -c%s "$config_backup_file" 2>/dev/null || echo 0)",
    "items_backed_up": $(printf '%s\n' "${existing_items[@]}" | jq -R . | jq -s .),
    "host": "$(hostname)",
    "user": "$(whoami)"
}
EOF
        
    else
        error_log "Configuration backup failed"
        return 1
    fi
    
    return 0
}

# Application data backup
backup_application_data() {
    log "Starting application data backup..."
    
    local data_backup_file="$BACKUP_DIR/data_${TIMESTAMP}.tar.gz"
    
    # List of data directories to backup
    local data_items=(
        "logs/"
        "tmp/"
    )
    
    # Only include existing directories
    local existing_data=()
    for item in "${data_items[@]}"; do
        if [ -d "$item" ] && [ "$(find "$item" -type f | wc -l)" -gt 0 ]; then
            existing_data+=("$item")
        fi
    done
    
    if [ ${#existing_data[@]} -eq 0 ]; then
        log "No application data found to backup"
        return 0
    fi
    
    # Create data backup (excluding large log files)
    log "Backing up recent application data..."
    
    if tar -czf "$data_backup_file" \
        --exclude="*.log.gz" \
        --exclude="logs/*.log" \
        "${existing_data[@]}" 2>>"$BACKUP_LOG"; then
        
        local backup_size=$(du -h "$data_backup_file" | cut -f1)
        log "Application data backup created: $data_backup_file ($backup_size)"
    else
        error_log "Application data backup failed"
        return 1
    fi
    
    return 0
}

# Remote backup upload
upload_to_remote() {
    if [ "$REMOTE_BACKUP_ENABLED" != true ] || [ -z "$S3_BUCKET" ]; then
        log "Remote backup disabled or not configured"
        return 0
    fi
    
    log "Starting remote backup upload..."
    
    # Check if AWS CLI is available
    if ! command -v aws >/dev/null 2>&1; then
        error_log "AWS CLI not available for remote backup"
        return 1
    fi
    
    # Upload each backup file to S3
    local upload_success=true
    
    for backup_file in "$BACKUP_DIR"/*_${TIMESTAMP}.*; do
        if [ -f "$backup_file" ]; then
            local filename=$(basename "$backup_file")
            local s3_path="s3://$S3_BUCKET/leadfactory/backups/$DATE/$filename"
            
            log "Uploading $filename to S3..."
            
            if aws s3 cp "$backup_file" "$s3_path" \
                --region "$AWS_REGION" \
                --storage-class STANDARD_IA \
                2>>"$BACKUP_LOG"; then
                log "Successfully uploaded $filename to S3"
            else
                error_log "Failed to upload $filename to S3"
                upload_success=false
            fi
        fi
    done
    
    if [ "$upload_success" = true ]; then
        log "Remote backup upload completed successfully"
        send_notification "INFO" "Backups uploaded to S3: $S3_BUCKET/leadfactory/backups/$DATE/"
    else
        error_log "Remote backup upload had errors"
        send_notification "WARNING" "Some backups failed to upload to S3"
        return 1
    fi
    
    return 0
}

# Backup verification
verify_backups() {
    log "Verifying backup integrity..."
    
    local verification_success=true
    local total_backup_size=0
    
    # Verify each backup file
    for backup_file in "$BACKUP_DIR"/*_${TIMESTAMP}.*; do
        if [ -f "$backup_file" ] && [[ "$backup_file" != *.meta ]]; then
            local filename=$(basename "$backup_file")
            local file_size=$(stat -f%z "$backup_file" 2>/dev/null || stat -c%s "$backup_file" 2>/dev/null || echo 0)
            total_backup_size=$((total_backup_size + file_size))
            
            if [ "$file_size" -gt 0 ]; then
                log "✓ $filename: $((file_size / 1024))KB"
            else
                error_log "✗ $filename: Empty file"
                verification_success=false
            fi
            
            # Test file integrity for compressed files
            if [[ "$backup_file" == *.gz ]]; then
                if ! gzip -t "$backup_file" 2>/dev/null; then
                    error_log "✗ $filename: Compression integrity check failed"
                    verification_success=false
                fi
            fi
        fi
    done
    
    log "Total backup size: $((total_backup_size / 1024 / 1024))MB"
    
    if [ "$verification_success" = true ]; then
        log "All backups verified successfully"
    else
        error_log "Backup verification failed"
        return 1
    fi
    
    return 0
}

# Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up old backups (retention: $BACKUP_RETENTION_DAYS days)..."
    
    local old_backups=$(find "$BACKUP_DIR" -name "*_20*" -type f -mtime +$BACKUP_RETENTION_DAYS 2>/dev/null | wc -l)
    
    if [ "$old_backups" -gt 0 ]; then
        local space_freed=$(find "$BACKUP_DIR" -name "*_20*" -type f -mtime +$BACKUP_RETENTION_DAYS -exec du -c {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")
        find "$BACKUP_DIR" -name "*_20*" -type f -mtime +$BACKUP_RETENTION_DAYS -delete 2>/dev/null || true
        log "Removed $old_backups old backup files (${space_freed}KB freed)"
    else
        log "No old backups to clean up"
    fi
}

# Generate backup report
generate_backup_report() {
    local backup_duration=$(($(date +%s) - start_time))
    local backup_files=$(find "$BACKUP_DIR" -name "*_${TIMESTAMP}.*" -type f | wc -l)
    
    log "=== Backup Summary ==="
    log "Duration: ${backup_duration} seconds"
    log "Files created: $backup_files"
    log "Backup directory: $BACKUP_DIR"
    log "Date: $DATE"
    log "Host: $(hostname)"
    log "User: $(whoami)"
    
    # Create summary report
    cat > "$BACKUP_DIR/backup_report_${TIMESTAMP}.json" << EOF
{
    "backup_date": "$TIMESTAMP",
    "duration_seconds": $backup_duration,
    "files_created": $backup_files,
    "backup_directory": "$BACKUP_DIR",
    "host": "$(hostname)",
    "user": "$(whoami)",
    "database_backed_up": $([ -f "$BACKUP_DIR/database_${TIMESTAMP}.sql"* ] && echo "true" || echo "false"),
    "config_backed_up": $([ -f "$BACKUP_DIR/config_${TIMESTAMP}.tar.gz" ] && echo "true" || echo "false"),
    "remote_upload": $REMOTE_BACKUP_ENABLED,
    "retention_days": $BACKUP_RETENTION_DAYS
}
EOF
}

# Main execution
main() {
    local start_time=$(date +%s)
    
    # Ensure directories exist
    mkdir -p "$LOG_DIR" "$BACKUP_DIR"
    
    log "=== LeadFactory Backup Started ==="
    log "Date: $DATE, Timestamp: $TIMESTAMP"
    log "Script: $0, PID: $$"
    log "Backup directory: $BACKUP_DIR"
    
    # Check disk space before backup
    local available_space=$(df "$BACKUP_DIR" | awk 'NR==2 {print $4}')
    local available_gb=$((available_space / 1024 / 1024))
    log "Available disk space: ${available_gb}GB"
    
    if [ "$available_gb" -lt 1 ]; then
        error_log "Insufficient disk space for backup (${available_gb}GB available)"
        send_notification "ERROR" "Backup failed: insufficient disk space (${available_gb}GB)"
        exit 1
    fi
    
    # Execute backup operations
    local backup_success=true
    
    if ! backup_database; then
        backup_success=false
    fi
    
    if ! backup_configuration; then
        backup_success=false
    fi
    
    if ! backup_application_data; then
        backup_success=false
    fi
    
    if ! verify_backups; then
        backup_success=false
    fi
    
    # Upload to remote storage
    upload_to_remote
    
    # Cleanup old backups
    cleanup_old_backups
    
    # Generate report
    generate_backup_report
    
    if [ "$backup_success" = true ]; then
        log "=== LeadFactory Backup Completed Successfully ==="
        send_notification "SUCCESS" "Backup completed successfully on $(hostname)"
    else
        error_log "=== LeadFactory Backup Completed with Errors ==="
        send_notification "ERROR" "Backup completed with errors on $(hostname)"
        exit 1
    fi
}

# Signal handlers
trap 'error_log "Backup interrupted"; exit 1' INT TERM

# Execute main function if script is run directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi