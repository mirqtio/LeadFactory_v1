# Redis MCP Server Setup for Claude Desktop

## Required MCP Configuration

Add this to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "redis": {
      "command": "node",
      "args": ["/path/to/redis-mcp-server/dist/index.js"],
      "env": {
        "REDIS_URL": "redis://localhost:6379/0"
      }
    }
  }
}
```

## Alternative: Use Existing Redis Infrastructure

Since we have a working Redis setup with Python helpers, the MCP server may not be strictly necessary. The current implementation provides:

1. **Redis CLI Tools**: Direct Redis access via Python
2. **Sync/Async Interfaces**: Both blocking and non-blocking Redis operations
3. **State Management**: PRP and agent coordination through Redis
4. **Dashboard Integration**: Real-time data from Redis

## Current Redis Access Methods

- **From Python**: `from redis_cli import sync_redis, prp_redis`
- **From CLI**: `REDIS_URL=redis://localhost:6379/0 python script.py`
- **From Docker**: Redis container accessible at `localhost:6379`

## Testing Redis Connection

```bash
# Test direct Redis access
redis-cli ping

# Test Python helper
python -c "from redis_cli import sync_redis; print(sync_redis.get('test'))"

# Test PRP coordination
python .claude/prp_tracking/cli_commands.py redis-status
```