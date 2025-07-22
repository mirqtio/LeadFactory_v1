#!/bin/bash
# Setup Redis subscriptions for all agents
# Run this to enable agents to receive Redis messages

echo "🚀 Setting up Redis subscriptions for all agents..."

# Create Redis subscriber for each agent
agents=("pm1" "pm2" "pm3" "validator" "integration")
agent_names=("PM-1" "PM-2" "PM-3" "Validator" "Integration")

for i in "${!agents[@]}"; do
    agent_id="${agents[$i]}"
    agent_name="${agent_names[$i]}"
    
    echo "📡 Setting up Redis subscriber for $agent_name..."
    
    # Create subscriber process in background
    nohup redis-cli PSUBSCRIBE "agent:${agent_id}" "agent:broadcast" | while IFS= read -r line; do
        # Filter out Redis pub/sub control messages
        if [[ "$line" == *"{"* ]]; then
            timestamp=$(date '+%H:%M:%S')
            echo "[$timestamp] 📨 REDIS MESSAGE for $agent_name: $line"
            
            # Extract just the message content for display
            message=$(echo "$line" | jq -r '.message // empty' 2>/dev/null || echo "$line")
            if [[ -n "$message" && "$message" != "null" ]]; then
                echo "  💬 $message"
            fi
        fi
    done > "/tmp/redis_${agent_id}.log" 2>&1 &
    
    echo "  ✅ $agent_name subscriber started (PID: $!)"
    echo "  📄 Logs: /tmp/redis_${agent_id}.log"
done

echo ""
echo "🎯 Redis subscriptions active for all agents!"
echo "📨 Messages will appear in agent log files and can be integrated into Claude Code sessions"
echo ""
echo "📋 To monitor Redis messages:"
echo "  tail -f /tmp/redis_*.log"
echo ""
echo "🧪 To test messaging:"
echo "  python3 dual_message_system.py"
echo ""
echo "🔄 To stop all Redis subscribers:"
echo "  pkill -f 'redis-cli PSUBSCRIBE'"