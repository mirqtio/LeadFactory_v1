#!/bin/bash
# Continuous monitoring and auto-unsticking system for tmux panes

LOGFILE="/tmp/continuous_monitor.log"
PANES=("orchestrator" "dev-1" "dev-2" "validator" "integrator")

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOGFILE"
}

check_and_unstick() {
    local pane=$1
    local output=$(tmux capture-pane -p -S -3 -t "leadstack:$pane")
    
    # Check for pasted text waiting for submission
    if echo "$output" | grep -q "\[Pasted text #.*lines\]"; then
        log "🚨 STUCK DETECTED: $pane has pasted text waiting - sending Enter"
        tmux send-keys -t "leadstack:$pane" "C-m"
        sleep 0.5
        return 1
    fi
    
    # Check for "Bypassing Permissions" (might need input)
    if echo "$output" | grep -q "Bypassing Permissions"; then
        log "⚠️  PERMISSION PROMPT: $pane may need user confirmation"
        return 1
    fi
    
    # Check if agent is stuck in thinking loop (same message >5 min)
    # This would need more sophisticated logic with state tracking
    
    return 0
}

monitor_system() {
    while true; do
        log "=== MONITORING CYCLE ==="
        
        # Check each pane
        for pane in "${PANES[@]}"; do
            if ! check_and_unstick "$pane"; then
                log "📋 Intervention applied to $pane"
            fi
        done
        
        # Check queue status
        dev_q=$(redis-cli LLEN dev_queue 2>/dev/null || echo "ERR")
        val_q=$(redis-cli LLEN validation_queue 2>/dev/null || echo "ERR")  
        int_q=$(redis-cli LLEN integration_queue 2>/dev/null || echo "ERR")
        orch_q=$(redis-cli LLEN orchestrator_queue 2>/dev/null || echo "ERR")
        
        log "📊 QUEUES: dev=$dev_q val=$val_q int=$int_q orch=$orch_q"
        
        # Check for backups
        if [[ "$dev_q" != "ERR" && "$dev_q" -gt 3 ]]; then
            log "🚨 DEV QUEUE BACKUP: $dev_q items - may need more dev agents"
        fi
        
        if [[ "$val_q" != "ERR" && "$val_q" -gt 2 ]]; then
            log "🚨 VALIDATION QUEUE BACKUP: $val_q items - validator may be stuck"
        fi
        
        # Brief status of each pane
        for pane in "${PANES[@]}"; do
            status_line=$(tmux capture-pane -p -S -1 -t "leadstack:$pane" | tail -1)
            log "🔍 $pane: $(echo "$status_line" | head -c 80)..."
        done
        
        log "=== CYCLE COMPLETE - SLEEPING 30s ==="
        sleep 30
    done
}

# Start monitoring
log "🚀 Starting continuous monitoring and auto-unsticking system"
log "📝 Monitoring panes: ${PANES[*]}"
log "🔧 Auto-unstick features: paste detection, permission prompts"

monitor_system