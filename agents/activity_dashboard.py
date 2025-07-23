#!/usr/bin/env python3
"""
Enhanced Activity Dashboard - Shows real-time agent activity and progress
"""
import redis
import json
import time
import os
from datetime import datetime, timedelta
from collections import defaultdict

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

def get_activity_logs(r, since_minutes=5):
    """Get recent activity from Redis logs"""
    activities = []
    
    # Check for activity logs in Redis
    activity_keys = r.keys("activity:*")
    log_keys = r.keys("log:*")
    
    # Get recent activities
    cutoff = datetime.now() - timedelta(minutes=since_minutes)
    
    for key in activity_keys + log_keys:
        try:
            data = r.get(key)
            if data:
                activity = json.loads(data.decode())
                timestamp = datetime.fromisoformat(activity.get('timestamp', '1970-01-01'))
                if timestamp > cutoff:
                    activities.append(activity)
        except:
            pass
    
    return sorted(activities, key=lambda x: x.get('timestamp', ''))

def check_agent_heartbeats(agents):
    """Check if agents are actually alive based on heartbeat timestamps"""
    now = datetime.now()
    agent_health = {}
    
    for agent_id, data in agents.items():
        last_update = data.get('last_update', 'never')
        if last_update == 'never':
            agent_health[agent_id] = 'unknown'
        else:
            try:
                last_time = datetime.fromisoformat(last_update)
                diff = (now - last_time).total_seconds()
                if diff < 60:  # Active within last minute
                    agent_health[agent_id] = 'active'
                elif diff < 300:  # Within 5 minutes
                    agent_health[agent_id] = 'idle'
                else:
                    agent_health[agent_id] = 'stale'
            except:
                agent_health[agent_id] = 'error'
    
    return agent_health

def format_activity_feed(activities, max_items=10):
    """Format recent activity as a scrolling feed"""
    if not activities:
        return ["No recent activity (last 5 minutes)", "System may be idle or not logging properly"]
    
    lines = ["🔄 RECENT ACTIVITY (last 5 minutes):", "─" * 50]
    
    for activity in activities[-max_items:]:
        timestamp = activity.get('timestamp', 'unknown')
        agent = activity.get('agent', 'system')
        action = activity.get('action', 'unknown')
        details = activity.get('details', '')
        
        # Format timestamp
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime('%H:%M:%S')
        except:
            time_str = 'unknown'
        
        lines.append(f"{time_str} | {agent:12} | {action:15} | {details}")
    
    return lines

def check_prp_progress(r, prp_id):
    """Check detailed progress for a specific PRP"""
    prp_data = r.hgetall(f"prp:{prp_id}")
    if not prp_data:
        return None
    
    progress = {}
    for key, value in prp_data.items():
        progress[key.decode()] = value.decode()
    
    # Check for progress indicators
    indicators = {}
    if 'pm_started_at' in progress:
        indicators['PM Started'] = progress['pm_started_at']
    if 'validation_started_at' in progress:
        indicators['Validation Started'] = progress['validation_started_at']
    if 'integration_started_at' in progress:
        indicators['Integration Started'] = progress['integration_started_at']
    
    return indicators

def render_activity_dashboard():
    """Render dashboard focused on activity and progress"""
    r = redis.from_url("redis://localhost:6379/0")
    
    # Get basic status
    queues = {
        "new_queue": r.llen("new_queue"),
        "dev_queue": r.llen("dev_queue"), 
        "validation_queue": r.llen("validation_queue"),
        "integration_queue": r.llen("integration_queue")
    }
    
    # Get agents
    agents = {}
    agent_keys = r.keys("agent:*")
    for key in agent_keys:
        agent_data = r.hgetall(key)
        if agent_data:
            agent_id = key.decode().split(":")[-1]
            agents[agent_id] = {k.decode(): v.decode() for k, v in agent_data.items()}
    
    # Get PRPs
    prps = {}
    prp_keys = r.keys("prp:*")
    for key in prp_keys:
        prp_data = r.hgetall(key)
        if prp_data:
            prp_id = key.decode().split(":")[-1]
            prps[prp_id] = {k.decode(): v.decode() for k, v in prp_data.items()}
    
    # Get activity
    activities = get_activity_logs(r)
    agent_health = check_agent_heartbeats(agents)
    
    clear_screen()
    
    print("🔄 MULTI-AGENT ACTIVITY DASHBOARD")
    print("═" * 80)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Quick pipeline status
    print("📊 PIPELINE STATUS:")
    total_items = sum(queues.values())
    if total_items == 0:
        print("  🟢 All queues empty - system idle or complete")
    else:
        print(f"  📋 {queues['new_queue']} new → 💻 {queues['dev_queue']} dev → 🔍 {queues['validation_queue']} validation → 🚀 {queues['integration_queue']} integration")
    print()
    
    # Agent health with real status
    print("🤖 AGENT HEALTH:")
    print("─" * 50)
    for agent_id, health in agent_health.items():
        agent_data = agents.get(agent_id, {})
        current_prp = agent_data.get('current_prp', 'none')
        status = agent_data.get('status', 'unknown')
        
        health_icon = {
            'active': '🟢',
            'idle': '🟡',
            'stale': '🔴',
            'unknown': '❓',
            'error': '💥'
        }.get(health, '❓')
        
        print(f"  {health_icon} {agent_id:15} : {health:8} | {status:8} | PRP: {current_prp}")
    print()
    
    # PRP Progress Details
    print("📄 PRP PROGRESS:")
    print("─" * 50)
    for prp_id, data in prps.items():
        state = data.get('state', 'unknown')
        owner = data.get('owner', 'unassigned')
        
        # Get detailed progress
        progress_indicators = check_prp_progress(r, prp_id)
        
        state_icon = {
            'new': '📋',
            'assigned': '👤',
            'development': '💻',
            'validation': '🔍', 
            'integration': '🚀',
            'complete': '✅'
        }.get(state, '❓')
        
        print(f"  {state_icon} {prp_id:12} : {state:12} | {owner:12}")
        
        if progress_indicators:
            for step, timestamp in progress_indicators.items():
                print(f"    └─ {step}: {timestamp}")
    print()
    
    # Activity feed
    activity_lines = format_activity_feed(activities)
    for line in activity_lines:
        print(line)
    
    print()
    print("─" * 80)
    print("🔍 TROUBLESHOOTING:")
    if not activities:
        print("  ⚠️  No recent activity detected")
        print("  💡 Check if agents are running: ps aux | grep python.*agent")
        print("  💡 Check agent logs: tmux list-sessions")
    elif total_items > 0 and not any(h == 'active' for h in agent_health.values()):
        print("  ⚠️  Items in queue but no active agents")
        print("  💡 Agents may be stuck or not processing")
    else:
        print("  ✅ System appears to be functioning")
    
    print("Press Ctrl+C to exit | Refreshes every 3 seconds")

def main():
    """Main dashboard loop"""
    try:
        while True:
            render_activity_dashboard()
            time.sleep(3)
    except KeyboardInterrupt:
        clear_screen()
        print("Activity dashboard stopped.")
    except Exception as e:
        print(f"Dashboard error: {e}")

if __name__ == "__main__":
    main()