# Required CLAUDE.md Updates for Redis Integration

Add these sections to CLAUDE.md:

## 🔧 Redis Coordination System
- **Redis Helper**: Use `redis_cli.py` for all agent coordination
- **PRP State Sync**: Enhanced state manager with Redis + YAML backup
- **Merge Coordination**: Use `merge_coordinator.py` for serialized merges
- **Agent Status**: Update agent heartbeats via Redis

## 🔄 Redis-Enhanced PRP Commands
- **Redis Status**: `python .claude/prp_tracking/cli_commands.py redis-status`
- **Redis Sync**: `python .claude/prp_tracking/cli_commands.py redis-sync`
- **Merge Status**: `python .claude/prp_tracking/merge_coordinator.py status`
- **Merge Request**: `python .claude/prp_tracking/merge_coordinator.py request <prp_id>`

## 📊 Redis Dashboard
- **Live Dashboard**: `orchestrator_dashboard_redis.html` (30s auto-refresh)
- **JSON API**: `dashboard_data.json` for real-time data
- **Dashboard Updater**: `python redis_dashboard_updater.py data`

## ⚡ Smoke-Only CI Gates (Redis Integration Ready)
- **Merge Gate**: Ultra-Fast CI Pipeline (<3 minutes)
- **Reliability**: 100% passing, smoke tests only
- **Coordination**: Works with Redis merge locks
- **Velocity**: Enables 24+ PRPs/day target