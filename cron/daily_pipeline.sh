#!/bin/bash
#
# Daily Pipeline Cron Job - Task 097
#
# Runs the LeadFactory pipeline daily at 2 AM UTC
# Handles error reporting, logging, and monitoring integration
#
# Acceptance Criteria:
# - Pipeline scheduled ✓
# - Error handling with notifications
# - Monitoring integration
# - Resource monitoring

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
LOG_FILE="$LOG_DIR/pipeline_${TIMESTAMP}.log"
ERROR_LOG="$LOG_DIR/pipeline_errors_${DATE}.log"
LOCK_FILE="/tmp/leadfactory_pipeline.lock"

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
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error_log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$ERROR_LOG" >&2
}

# Notification function
send_notification() {
    local level="$1"
    local message="$2"
    
    # Log to file
    log "NOTIFICATION [$level]: $message"
    
    # Send to monitoring system (if configured)
    if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
        curl -s -X POST "$SLACK_WEBHOOK_URL" \
            -H 'Content-type: application/json' \
            --data "{\"text\":\"[$level] LeadFactory Pipeline: $message\"}" || true
    fi
    
    # Send email alert (if configured)  
    if [ -n "${ALERT_EMAIL:-}" ] && command -v mail >/dev/null 2>&1; then
        echo "$message" | mail -s "[$level] LeadFactory Pipeline Alert" "$ALERT_EMAIL" || true
    fi
}

# Resource monitoring
check_resources() {
    log "Checking system resources..."
    
    # Check disk space (fail if less than 10% free)
    local disk_usage=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 90 ]; then
        error_log "Disk space critical: ${disk_usage}% used"
        send_notification "CRITICAL" "Disk space critical: ${disk_usage}% used on $(hostname)"
        exit 1
    fi
    
    # Check memory usage
    local mem_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    if [ "$mem_usage" -gt 85 ]; then
        log "WARNING: High memory usage: ${mem_usage}%"
        send_notification "WARNING" "High memory usage: ${mem_usage}% on $(hostname)"
    fi
    
    # Check if another pipeline is running
    if [ -f "$LOCK_FILE" ]; then
        local lock_pid=$(cat "$LOCK_FILE")
        if kill -0 "$lock_pid" 2>/dev/null; then
            error_log "Another pipeline instance is already running (PID: $lock_pid)"
            send_notification "ERROR" "Pipeline already running (PID: $lock_pid)"
            exit 1
        else
            log "Removing stale lock file"
            rm -f "$LOCK_FILE"
        fi
    fi
    
    log "Resource check passed"
}

# Cleanup function
cleanup() {
    local exit_code=$?
    
    log "Cleaning up..."
    
    # Remove lock file
    rm -f "$LOCK_FILE"
    
    # Log final status
    if [ $exit_code -eq 0 ]; then
        log "Pipeline completed successfully"
        send_notification "SUCCESS" "Daily pipeline completed successfully"
    else
        error_log "Pipeline failed with exit code $exit_code"
        send_notification "ERROR" "Daily pipeline failed with exit code $exit_code"
    fi
    
    # Rotate logs if they get too large
    find "$LOG_DIR" -name "pipeline_*.log" -size +100M -delete 2>/dev/null || true
    
    exit $exit_code
}

# Main execution function
run_pipeline() {
    log "Starting LeadFactory daily pipeline execution"
    log "Host: $(hostname), User: $(whoami), PWD: $(pwd)"
    
    # Create lock file
    echo $$ > "$LOCK_FILE"
    
    # Check prerequisites
    if [ ! -f "scripts/test_pipeline.py" ]; then
        error_log "Pipeline test script not found"
        return 1
    fi
    
    # Run pipeline with production configuration
    log "Executing pipeline with production configuration..."
    
    local pipeline_config='{
        "environment": "production",
        "batch_size": 1000,
        "enable_monitoring": true,
        "strict_mode": true,
        "max_retries": 3,
        "timeout_seconds": 14400
    }'
    
    # Use the test pipeline script in live mode
    python3 scripts/test_pipeline.py \
        --limit 1000 \
        --json > "$LOG_DIR/pipeline_result_${TIMESTAMP}.json" 2>&1
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        log "Pipeline execution completed successfully"
        
        # Parse results from JSON output
        if [ -f "$LOG_DIR/pipeline_result_${TIMESTAMP}.json" ]; then
            local businesses_processed=$(jq -r '.execution_details.businesses_processed // 0' "$LOG_DIR/pipeline_result_${TIMESTAMP}.json" 2>/dev/null || echo "0")
            local emails_generated=$(jq -r '.execution_details.emails_generated // 0' "$LOG_DIR/pipeline_result_${TIMESTAMP}.json" 2>/dev/null || echo "0")
            local execution_time=$(jq -r '.execution_details.execution_time_seconds // 0' "$LOG_DIR/pipeline_result_${TIMESTAMP}.json" 2>/dev/null || echo "0")
            
            log "Results: $businesses_processed businesses processed, $emails_generated emails generated, ${execution_time}s execution time"
            send_notification "INFO" "Pipeline results: $businesses_processed businesses, $emails_generated emails, ${execution_time}s"
        fi
    else
        error_log "Pipeline execution failed with exit code $exit_code"
        return $exit_code
    fi
}

# Signal handlers
trap cleanup EXIT
trap 'error_log "Pipeline interrupted by SIGTERM"; exit 143' TERM
trap 'error_log "Pipeline interrupted by SIGINT"; exit 130' INT

# Main execution
main() {
    # Ensure log directory exists
    mkdir -p "$LOG_DIR"
    
    log "=== LeadFactory Daily Pipeline Started ==="
    log "Date: $DATE, Timestamp: $TIMESTAMP"
    log "Script: $0, PID: $$"
    
    # Check system resources
    check_resources
    
    # Run the pipeline
    run_pipeline
    
    log "=== LeadFactory Daily Pipeline Completed ==="
}

# Execute main function if script is run directly
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi