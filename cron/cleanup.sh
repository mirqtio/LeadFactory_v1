#!/bin/bash
#
# Cleanup Cron Job - Task 097  
#
# Automated cleanup of old logs, temporary files, and database records
# Runs daily at 3 AM UTC to clean up after pipeline execution
#
# Acceptance Criteria:
# - Cleanup configured ✓
# - Old logs removed
# - Temporary files cleaned
# - Database maintenance

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
TEMP_DIR="$PROJECT_ROOT/tmp"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
CLEANUP_LOG="$LOG_DIR/cleanup_${TIMESTAMP}.log"

# Retention periods (in days)
LOG_RETENTION_DAYS=30
TEMP_FILE_RETENTION_DAYS=7
METRICS_RETENTION_DAYS=90
ERROR_LOG_RETENTION_DAYS=90

# Database cleanup settings
DB_CLEANUP_BATCH_SIZE=1000
OLD_EMAIL_RETENTION_DAYS=180
OLD_ASSESSMENT_RETENTION_DAYS=90

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
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$CLEANUP_LOG"
}

error_log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$CLEANUP_LOG" >&2
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
            --data "{\"text\":\"[$level] LeadFactory Cleanup: $message\"}" || true
    fi
}

# File system cleanup
cleanup_filesystem() {
    log "Starting filesystem cleanup..."
    local files_removed=0
    local space_freed=0
    
    # Create temp directory if it doesn't exist
    mkdir -p "$TEMP_DIR"
    
    # Clean up old log files
    log "Cleaning up log files older than $LOG_RETENTION_DAYS days..."
    if [ -d "$LOG_DIR" ]; then
        local old_logs=$(find "$LOG_DIR" -name "*.log" -type f -mtime +$LOG_RETENTION_DAYS 2>/dev/null | wc -l)
        if [ "$old_logs" -gt 0 ]; then
            local log_space=$(find "$LOG_DIR" -name "*.log" -type f -mtime +$LOG_RETENTION_DAYS -exec du -c {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")
            find "$LOG_DIR" -name "*.log" -type f -mtime +$LOG_RETENTION_DAYS -delete 2>/dev/null || true
            files_removed=$((files_removed + old_logs))
            space_freed=$((space_freed + log_space))
            log "Removed $old_logs old log files (${log_space}KB freed)"
        fi
    fi
    
    # Clean up temporary files
    log "Cleaning up temporary files older than $TEMP_FILE_RETENTION_DAYS days..."
    if [ -d "$TEMP_DIR" ]; then
        local temp_files=$(find "$TEMP_DIR" -type f -mtime +$TEMP_FILE_RETENTION_DAYS 2>/dev/null | wc -l)
        if [ "$temp_files" -gt 0 ]; then
            local temp_space=$(find "$TEMP_DIR" -type f -mtime +$TEMP_FILE_RETENTION_DAYS -exec du -c {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")
            find "$TEMP_DIR" -type f -mtime +$TEMP_FILE_RETENTION_DAYS -delete 2>/dev/null || true
            files_removed=$((files_removed + temp_files))
            space_freed=$((space_freed + temp_space))
            log "Removed $temp_files temporary files (${temp_space}KB freed)"
        fi
    fi
    
    # Clean up old Python cache files
    log "Cleaning up Python cache files..."
    local cache_files=$(find "$PROJECT_ROOT" -name "__pycache__" -type d 2>/dev/null | wc -l)
    if [ "$cache_files" -gt 0 ]; then
        find "$PROJECT_ROOT" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        log "Removed $cache_files Python cache directories"
    fi
    
    # Clean up old JSON result files
    log "Cleaning up old pipeline result files..."
    local result_files=$(find "$LOG_DIR" -name "pipeline_result_*.json" -type f -mtime +$LOG_RETENTION_DAYS 2>/dev/null | wc -l)
    if [ "$result_files" -gt 0 ]; then
        local result_space=$(find "$LOG_DIR" -name "pipeline_result_*.json" -type f -mtime +$LOG_RETENTION_DAYS -exec du -c {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo "0")
        find "$LOG_DIR" -name "pipeline_result_*.json" -type f -mtime +$LOG_RETENTION_DAYS -delete 2>/dev/null || true
        files_removed=$((files_removed + result_files))
        space_freed=$((space_freed + result_space))
        log "Removed $result_files old result files (${result_space}KB freed)"
    fi
    
    log "Filesystem cleanup completed: $files_removed files removed, ${space_freed}KB freed"
    
    if [ $files_removed -gt 100 ] || [ $space_freed -gt 100000 ]; then
        send_notification "INFO" "Cleanup completed: $files_removed files removed, $((space_freed/1024))MB freed"
    fi
}

# Database cleanup
cleanup_database() {
    log "Starting database cleanup..."
    
    # Create cleanup SQL script
    local cleanup_sql="$TEMP_DIR/cleanup_${TIMESTAMP}.sql"
    cat > "$cleanup_sql" << EOF
-- Database cleanup script
-- Remove old email records
DELETE FROM emails 
WHERE created_at < NOW() - INTERVAL '$OLD_EMAIL_RETENTION_DAYS days'
  AND status IN ('delivered', 'bounced', 'complained', 'unsubscribed')
LIMIT $DB_CLEANUP_BATCH_SIZE;

-- Remove old assessment results
DELETE FROM assessment_results 
WHERE created_at < NOW() - INTERVAL '$OLD_ASSESSMENT_RETENTION_DAYS days'
LIMIT $DB_CLEANUP_BATCH_SIZE;

-- Remove old gateway usage records  
DELETE FROM gateway_usage
WHERE created_at < NOW() - INTERVAL '$METRICS_RETENTION_DAYS days'
LIMIT $DB_CLEANUP_BATCH_SIZE;

-- Clean up orphaned business records (no recent activity)
DELETE FROM businesses b
WHERE NOT EXISTS (
    SELECT 1 FROM emails e WHERE e.business_id = b.id AND e.created_at > NOW() - INTERVAL '90 days'
)
AND NOT EXISTS (
    SELECT 1 FROM assessment_results ar WHERE ar.business_id = b.id AND ar.created_at > NOW() - INTERVAL '90 days'  
)
AND b.created_at < NOW() - INTERVAL '180 days'
LIMIT $DB_CLEANUP_BATCH_SIZE;

-- Update table statistics
ANALYZE emails;
ANALYZE businesses;
ANALYZE assessment_results;
ANALYZE gateway_usage;

-- Report cleanup statistics
SELECT 'emails' as table_name, COUNT(*) as remaining_records FROM emails
UNION ALL
SELECT 'businesses' as table_name, COUNT(*) as remaining_records FROM businesses  
UNION ALL
SELECT 'assessment_results' as table_name, COUNT(*) as remaining_records FROM assessment_results
UNION ALL
SELECT 'gateway_usage' as table_name, COUNT(*) as remaining_records FROM gateway_usage;
EOF

    # Execute database cleanup if database is configured
    if [ -n "${DATABASE_URL:-}" ]; then
        log "Executing database cleanup..."
        
        # Try PostgreSQL first
        if command -v psql >/dev/null 2>&1; then
            if psql "$DATABASE_URL" -f "$cleanup_sql" >> "$CLEANUP_LOG" 2>&1; then
                log "Database cleanup completed successfully"
            else
                error_log "Database cleanup failed"
            fi
        # Try Python script as fallback
        elif python3 -c "import psycopg2" 2>/dev/null; then
            python3 -c "
import os
import psycopg2
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    with open('$cleanup_sql', 'r') as f:
        cur.execute(f.read())
    conn.commit()
    print('Database cleanup completed via Python')
except Exception as e:
    print(f'Database cleanup failed: {e}')
finally:
    if 'conn' in locals():
        conn.close()
" >> "$CLEANUP_LOG" 2>&1
        else
            log "Database cleanup skipped - no PostgreSQL client available"
        fi
    else
        log "Database cleanup skipped - DATABASE_URL not configured"
    fi
    
    # Clean up SQL script
    rm -f "$cleanup_sql"
}

# System maintenance
system_maintenance() {
    log "Starting system maintenance..."
    
    # Check and report disk usage
    local disk_usage=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $5}' | sed 's/%//')
    log "Current disk usage: ${disk_usage}%"
    
    if [ "$disk_usage" -gt 80 ]; then
        send_notification "WARNING" "High disk usage: ${disk_usage}% on $(hostname)"
    fi
    
    # Check for large files that might need attention
    log "Checking for large files (>100MB)..."
    local large_files=$(find "$PROJECT_ROOT" -type f -size +100M 2>/dev/null | head -5)
    if [ -n "$large_files" ]; then
        log "Large files found:"
        echo "$large_files" | while read -r file; do
            local size=$(du -h "$file" | cut -f1)
            log "  $file ($size)"
        done
    fi
    
    # Memory usage check
    local mem_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    log "Current memory usage: ${mem_usage}%"
    
    # Log rotation check
    if command -v logrotate >/dev/null 2>&1 && [ -f "/etc/logrotate.d/leadfactory" ]; then
        log "Running logrotate..."
        logrotate -f /etc/logrotate.d/leadfactory 2>/dev/null || log "Logrotate not configured or failed"
    fi
    
    log "System maintenance completed"
}

# Performance optimization
optimize_performance() {
    log "Starting performance optimization..."
    
    # Vacuum database if PostgreSQL is available
    if [ -n "${DATABASE_URL:-}" ] && command -v psql >/dev/null 2>&1; then
        log "Running database vacuum..."
        psql "$DATABASE_URL" -c "VACUUM ANALYZE;" >> "$CLEANUP_LOG" 2>&1 || log "Database vacuum failed"
    fi
    
    # Clear system page cache if running as root
    if [ "$(id -u)" -eq 0 ]; then
        log "Clearing system page cache..."
        sync && echo 1 > /proc/sys/vm/drop_caches 2>/dev/null || log "Cache clear failed (non-root)"
    fi
    
    log "Performance optimization completed"
}

# Generate cleanup report
generate_report() {
    local total_files_removed=0
    local total_space_freed=0
    local cleanup_duration=$(($(date +%s) - start_time))
    
    log "=== Cleanup Summary ==="
    log "Duration: ${cleanup_duration} seconds"
    log "Files removed: $total_files_removed"
    log "Space freed: $((total_space_freed/1024))MB"
    log "Host: $(hostname)"
    log "User: $(whoami)"
    
    # Archive the cleanup log
    if [ -f "$CLEANUP_LOG" ]; then
        gzip "$CLEANUP_LOG" 2>/dev/null || true
    fi
}

# Main execution
main() {
    local start_time=$(date +%s)
    
    # Ensure log directory exists
    mkdir -p "$LOG_DIR"
    
    log "=== LeadFactory Cleanup Started ==="
    log "Date: $DATE, Timestamp: $TIMESTAMP"
    log "Script: $0, PID: $$"
    
    # Run cleanup operations
    cleanup_filesystem
    cleanup_database
    system_maintenance
    optimize_performance
    
    # Generate final report
    generate_report
    
    log "=== LeadFactory Cleanup Completed ==="
}

# Signal handlers
trap 'error_log "Cleanup interrupted"; exit 1' INT TERM

# Execute main function if script is run directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi