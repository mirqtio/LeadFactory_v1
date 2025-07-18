#!/usr/bin/env python3
"""
Redis-backed Dashboard Updater
Generates dynamic dashboard content from Redis state and PRP data
Following GPT o3's recommendation for Redis-backed dashboard
"""

import json
import sys
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Add current directory to path
sys.path.insert(0, '.')

try:
    from redis_cli import sync_redis, prp_redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    sync_redis = None

# Import PRP management
sys.path.insert(0, '.claude/prp_tracking')
try:
    from prp_state_manager import PRPStateManager, PRPStatus
    from redis_enhanced_state_manager import get_redis_state_manager
except ImportError as e:
    print(f"Warning: Could not import PRP managers: {e}")
    PRPStateManager = None


class RedisDashboardUpdater:
    """
    Updates dashboard with real-time data from Redis and PRP system
    """

    def __init__(self):
        self.redis_available = REDIS_AVAILABLE and sync_redis is not None
        
        if PRPStateManager:
            try:
                self.prp_manager = get_redis_state_manager()
            except Exception:
                self.prp_manager = PRPStateManager()
        else:
            self.prp_manager = None

    def get_redis_metrics(self) -> Dict:
        """Get Redis coordination metrics"""
        if not self.redis_available:
            return {
                "redis_status": "unavailable",
                "merge_lock_owner": None,
                "agent_count": 0,
                "events_count": 0
            }

        try:
            # Get merge lock status
            merge_lock_owner = sync_redis.get("prp:merge:lock")
            
            # Get agent status count
            agent_keys = sync_redis.get("agent_count") or 0
            
            # Get recent events count
            events_count = sync_redis.get("events_count") or 0
            
            return {
                "redis_status": "healthy",
                "merge_lock_owner": merge_lock_owner,
                "agent_count": agent_keys,
                "events_count": events_count,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            return {
                "redis_status": "error",
                "error": str(e),
                "merge_lock_owner": None,
                "agent_count": 0,
                "events_count": 0
            }

    def get_prp_metrics(self) -> Dict:
        """Get PRP status metrics"""
        if not self.prp_manager:
            return {
                "total_prps": 0,
                "completion_rate": 0,
                "status_breakdown": {},
                "current_prp": None
            }

        try:
            stats = self.prp_manager.get_stats()
            
            # Get current in-progress PRP
            in_progress_prps = self.prp_manager.get_in_progress_prps()
            current_prp = in_progress_prps[0] if in_progress_prps else None
            
            return {
                "total_prps": stats.get("total_prps", 0),
                "completion_rate": stats.get("completion_rate", 0),
                "status_breakdown": {
                    "new": stats.get("new", 0),
                    "validated": stats.get("validated", 0),
                    "in_progress": stats.get("in_progress", 0),
                    "complete": stats.get("complete", 0)
                },
                "current_prp": {
                    "id": current_prp.prp_id if current_prp else None,
                    "title": current_prp.title if current_prp else None,
                    "started_at": current_prp.started_at if current_prp else None
                } if current_prp else None
            }

        except Exception as e:
            return {
                "error": str(e),
                "total_prps": 0,
                "completion_rate": 0,
                "status_breakdown": {},
                "current_prp": None
            }

    def get_pm_status(self) -> List[Dict]:
        """Get PM agent status"""
        pm_agents = [
            {"id": "PM-1", "session": "PM-1:0", "domain": "Core/UI"},
            {"id": "PM-2", "session": "PM-2:0", "domain": "Business Logic"},
            {"id": "PM-3", "session": "PM-3:0", "domain": "Data/Infrastructure"}
        ]

        if not self.redis_available:
            for pm in pm_agents:
                pm.update({
                    "status": "unknown",
                    "current_prp": None,
                    "last_heartbeat": None
                })
            return pm_agents

        try:
            for pm in pm_agents:
                # Get agent status from Redis (would be populated by agents)
                agent_data = sync_redis.get(f"agent:{pm['id']}:status") or {}
                
                pm.update({
                    "status": agent_data.get("status", "unknown"),
                    "current_prp": agent_data.get("current_prp"),
                    "last_heartbeat": agent_data.get("updated_at"),
                    "active": agent_data.get("status") in ["coding", "testing", "debugging"]
                })

            return pm_agents

        except Exception as e:
            for pm in pm_agents:
                pm.update({
                    "status": "error",
                    "error": str(e),
                    "current_prp": None,
                    "last_heartbeat": None
                })
            return pm_agents

    def generate_dashboard_data(self) -> Dict:
        """Generate complete dashboard data"""
        timestamp = datetime.now(timezone.utc)
        
        return {
            "timestamp": timestamp.isoformat(),
            "formatted_timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "redis_metrics": self.get_redis_metrics(),
            "prp_metrics": self.get_prp_metrics(),
            "pm_status": self.get_pm_status(),
            "system_health": {
                "redis_available": self.redis_available,
                "prp_manager_available": self.prp_manager is not None,
                "overall_status": "healthy" if self.redis_available and self.prp_manager else "degraded"
            }
        }

    def update_dashboard_html(self, template_path: str, output_path: str) -> bool:
        """Update dashboard HTML with current data"""
        try:
            # Generate data
            data = self.generate_dashboard_data()
            
            # Read template
            with open(template_path, 'r') as f:
                template = f.read()

            # Replace data placeholders (simple template system)
            html_content = template.replace(
                "{{DASHBOARD_DATA}}", json.dumps(data, indent=2)
            ).replace(
                "{{TIMESTAMP}}", data["formatted_timestamp"]
            ).replace(
                "{{REDIS_STATUS}}", data["redis_metrics"]["redis_status"]
            ).replace(
                "{{TOTAL_PRPS}}", str(data["prp_metrics"]["total_prps"])
            ).replace(
                "{{COMPLETION_RATE}}", f"{data['prp_metrics']['completion_rate']:.1%}"
            ).replace(
                "{{CURRENT_PRP}}", 
                data["prp_metrics"]["current_prp"]["id"] if data["prp_metrics"]["current_prp"] else "None"
            ).replace(
                "{{SYSTEM_STATUS}}", data["system_health"]["overall_status"]
            )

            # Write updated HTML
            with open(output_path, 'w') as f:
                f.write(html_content)

            return True

        except Exception as e:
            print(f"Error updating dashboard: {e}")
            return False

    def generate_json_data(self, output_path: str) -> bool:
        """Generate JSON data file for dashboard consumption"""
        try:
            data = self.generate_dashboard_data()
            
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            return True

        except Exception as e:
            print(f"Error generating JSON data: {e}")
            return False


def main():
    """CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: python redis_dashboard_updater.py <command> [args]")
        print("Commands:")
        print("  data                           - Show dashboard data")
        print("  json <output_file>            - Generate JSON data file")
        print("  update <template> <output>    - Update HTML dashboard")
        return

    updater = RedisDashboardUpdater()
    command = sys.argv[1]

    if command == "data":
        data = updater.generate_dashboard_data()
        print(json.dumps(data, indent=2))

    elif command == "json":
        if len(sys.argv) < 3:
            print("Usage: json <output_file>")
            return
        
        output_file = sys.argv[2]
        success = updater.generate_json_data(output_file)
        print(f"{'✅' if success else '❌'} JSON data {'generated' if success else 'failed'}: {output_file}")

    elif command == "update":
        if len(sys.argv) < 4:
            print("Usage: update <template_file> <output_file>")
            return
        
        template_file = sys.argv[2]
        output_file = sys.argv[3]
        success = updater.update_dashboard_html(template_file, output_file)
        print(f"{'✅' if success else '❌'} Dashboard {'updated' if success else 'failed'}: {output_file}")

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()