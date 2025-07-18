#!/bin/bash
"""
Redis Dashboard Auto-Updater
Continuously updates the Redis-backed dashboard every 30 seconds
"""

echo "🚀 Starting Redis Dashboard Auto-Updater..."
echo "Dashboard will update every 30 seconds"
echo "Press Ctrl+C to stop"

while true; do
    echo "$(date): Updating Redis dashboard..."
    
    # Update the dashboard
    python redis_dashboard_updater.py update dashboard_template.html orchestrator_dashboard_redis.html
    
    if [ $? -eq 0 ]; then
        echo "✅ Dashboard updated successfully"
    else
        echo "❌ Dashboard update failed"
    fi
    
    # Wait 30 seconds
    sleep 30
done