#!/bin/bash
# Monitor Enterprise Shims Dashboard

echo "🏢 Enterprise Shim Monitoring Dashboard"
echo "======================================"
date
echo

echo "📊 Shim Processes:"
ps aux | grep -E "enterprise_shim|start_enterprise_shim" | grep -v grep | awk '{print "  " $2 " | " $11 " " $12 " " $13 " " $14}' || echo "  No shims running"
echo

echo "📝 Recent Activity (last 3 lines from each log):"
for log in /tmp/*shim*.log; do
    if [[ -f "$log" ]]; then
        echo "$(basename "$log"):"
        tail -n 3 "$log" | sed 's/^/  /'
        echo
    fi
done

echo "🔍 Queue Status:"
redis-cli LLEN orchestrator_queue 2>/dev/null | xargs -I {} echo "  orchestrator_queue: {} items"
redis-cli LLEN dev_queue 2>/dev/null | xargs -I {} echo "  dev_queue: {} items"  
redis-cli LLEN validation_queue 2>/dev/null | xargs -I {} echo "  validation_queue: {} items"
redis-cli LLEN integration_queue 2>/dev/null | xargs -I {} echo "  integration_queue: {} items"
echo

echo "💡 Commands:"
echo "  tail -f /tmp/orchestrator_shim.log  # Monitor orchestrator"
echo "  tail -f /tmp/dev1_shim.log         # Monitor dev agent 1"  
echo "  tail -f /tmp/validator_shim.log     # Monitor validator"
echo "  ./monitor_shims.sh                 # Refresh this dashboard"