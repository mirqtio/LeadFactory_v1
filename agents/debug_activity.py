#!/usr/bin/env python3
"""
Debug: Is the multi-agent system actually working?
"""
import redis
import subprocess
import json
from datetime import datetime

def check_system_activity():
    print("🔍 DEBUGGING MULTI-AGENT SYSTEM ACTIVITY")
    print("=" * 60)
    
    # 1. Check if agent processes are actually running
    print("1️⃣ PROCESS CHECK:")
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        agent_processes = [line for line in result.stdout.split('\n') if 'python' in line and 'agent' in line]
        
        if agent_processes:
            print(f"  ✅ Found {len(agent_processes)} agent processes:")
            for proc in agent_processes:
                # Extract just the relevant part
                parts = proc.split()
                if len(parts) > 10:
                    cmd = ' '.join(parts[10:])[:60]
                    print(f"    - {cmd}")
        else:
            print("  ❌ No agent processes found!")
            return False
    except Exception as e:
        print(f"  ❌ Error checking processes: {e}")
        return False
    
    print()
    
    # 2. Check Redis connection and data
    print("2️⃣ REDIS CHECK:")
    try:
        r = redis.from_url("redis://localhost:6379/0")
        r.ping()
        print("  ✅ Redis connection working")
        
        # Check if there's any data
        all_keys = r.keys("*")
        print(f"  📊 Redis has {len(all_keys)} keys total")
        
        # Break down by type
        prp_keys = r.keys("prp:*")
        agent_keys = r.keys("agent:*")
        queue_keys = [k for k in all_keys if b'queue' in k]
        
        print(f"    - {len(prp_keys)} PRP records")
        print(f"    - {len(agent_keys)} agent records") 
        print(f"    - {len(queue_keys)} queue keys")
        
    except Exception as e:
        print(f"  ❌ Redis error: {e}")
        return False
    
    print()
    
    # 3. Check if agents are updating their status
    print("3️⃣ AGENT HEARTBEAT CHECK:")
    agent_keys = r.keys("agent:*")
    if not agent_keys:
        print("  ❌ No agent status records found")
        return False
    
    now = datetime.now()
    for key in agent_keys:
        agent_data = r.hgetall(key)
        if agent_data:
            agent_id = key.decode().split(":")[-1]
            last_update = agent_data.get(b'last_update', b'never').decode()
            status = agent_data.get(b'status', b'unknown').decode()
            
            if last_update == 'never':
                print(f"  ❌ {agent_id}: No heartbeat recorded")
            else:
                try:
                    last_time = datetime.fromisoformat(last_update)
                    diff = (now - last_time).total_seconds()
                    if diff < 60:
                        print(f"  ✅ {agent_id}: Active (last update {diff:.0f}s ago)")
                    else:
                        print(f"  ⚠️  {agent_id}: Stale (last update {diff:.0f}s ago)")
                except:
                    print(f"  ❌ {agent_id}: Invalid timestamp format")
    
    print()
    
    # 4. Check queue processing
    print("4️⃣ QUEUE PROCESSING CHECK:")
    queues = ["new_queue", "dev_queue", "validation_queue", "integration_queue"]
    
    for queue_name in queues:
        length = r.llen(queue_name)
        items = r.lrange(queue_name, 0, -1)
        items_list = [item.decode() for item in items]
        
        if length > 0:
            print(f"  📋 {queue_name}: {length} items - {items_list}")
        else:
            print(f"  ⚪ {queue_name}: empty")
    
    print()
    
    # 5. Check for stuck items
    print("5️⃣ STUCK ITEM CHECK:")
    
    # Check if PRP-1001 is moving
    prp_data = r.hgetall("prp:PRP-1001")
    if prp_data:
        state = prp_data.get(b'state', b'unknown').decode()
        owner = prp_data.get(b'owner', b'unassigned').decode()
        print(f"  📄 PRP-1001: state={state}, owner={owner}")
        
        if state == 'new' and owner == 'unassigned':
            print("  ⚠️  PRP-1001 hasn't been picked up yet")
            
            # Check if any agent should be processing it
            new_queue_items = r.lrange("new_queue", 0, -1)
            if b'PRP-1001' in new_queue_items:
                print("  📋 PRP-1001 is in new_queue waiting to be processed")
            else:
                print("  ❌ PRP-1001 not in new_queue - may be stuck")
    else:
        print("  ❌ PRP-1001 not found in Redis")
    
    print()
    
    # 6. Suggested actions
    print("6️⃣ RECOMMENDATIONS:")
    
    # Check if we have items but no activity
    total_queue_items = sum(r.llen(q) for q in queues)
    if total_queue_items > 0:
        print("  💡 Items in queue - agents should be processing")
        print("  💡 Check agent logs: tmux attach-session -t leadstack:dev-1")
        print("  💡 Force agent restart if needed")
    else:
        print("  💡 All queues empty - system may be idle")
    
    return True

if __name__ == "__main__":
    check_system_activity()