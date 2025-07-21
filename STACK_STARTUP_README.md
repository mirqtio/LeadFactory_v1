# LeadFactory Multi-Agent Stack Startup

## 🚀 One-Command Deployment

This system provides complete automation for the Redis-queue-based multi-agent orchestration stack.

### Quick Start

```bash
# Start the complete stack
./start_stack.sh

# Start without backlog ingest
./start_stack.sh --no-ingest
```

## 📋 Prerequisites

### Required Software
- `tmux` - Terminal multiplexer for session management
- `redis-cli` - Redis command-line interface
- `claude-code` - Claude AI CLI tool
- `python3` - For PRP ingest script

### Environment Configuration
Ensure your `.env` file contains:

```bash
# Required Variables
REDIS_URL=redis://localhost:6379/0
VPS_SSH_HOST=96.30.197.121
VPS_SSH_USER=deploy
VPS_SSH_KEY=/Users/yourname/.ssh/leadfactory_deploy
CLAUDE_ORCH_MODEL=claude-3-opus-20240229
CLAUDE_DEV_MODEL=claude-3-5-sonnet-20241022

# Optional Variables
GITHUB_TOKEN=your_github_token
GITHUB_REPO=your-org/your-repo
AGENT_COORDINATION_MODE=redis
```

### SSH Setup
1. Ensure SSH key exists and has correct permissions:
   ```bash
   chmod 600 ~/.ssh/leadfactory_deploy
   ```

2. Test SSH connection:
   ```bash
   ssh -i ~/.ssh/leadfactory_deploy deploy@96.30.197.121 "echo 'SSH OK'"
   ```

## 🏗️ System Architecture

### Agent Windows
- **orchestrator** - Opus model, strategic coordination
- **dev-1** - Sonnet model, development work
- **dev-2** - Sonnet model, parallel development
- **validator** - Sonnet model, quality assurance
- **integrator** - Sonnet model, deployment coordination
- **logs** - Real-time monitoring dashboard

### Redis Queues
- `dev_queue` - Development tasks
- `validation_queue` - Quality assurance tasks
- `integration_queue` - Deployment tasks
- `orchestrator_queue` - Strategic coordination
- `completion_queue` - Completed tasks

### Context Injection
Each agent receives three layers of context:
1. **Organizational Context** - From CLAUDE.md
2. **Project Context** - From PROJECT_CONTEXT.md or generated summary
3. **Role-Specific Context** - Persona and queue assignments

## 🔍 Monitoring & Control

### Tmux Session Management
```bash
# Attach to running session
tmux attach-session -t leadstack

# List all sessions
tmux list-sessions

# Switch between windows
Ctrl+b + 0-5  # Window numbers

# Kill session
tmux kill-session -t leadstack
```

### Queue Monitoring
The `logs` window provides real-time monitoring of:
- Queue depths and inflight counts
- Agent health status
- VPS connectivity
- System status from Redis

### Manual Queue Operations
```bash
# Check queue depth
redis-cli -u $REDIS_URL LLEN dev_queue

# Add manual task
redis-cli -u $REDIS_URL LPUSH dev_queue "task_id"

# View orchestrator status
redis-cli -u $REDIS_URL HGETALL orchestrator:status
```

## 📦 Backlog Ingestion

### Automatic Ingest
If `backlog_prps/` directory exists with `.md` files, they will be automatically parsed and queued.

### Manual Ingest
```bash
# Run ingest script directly
python3 scripts/prp_ingest.py backlog_prps/

# Skip ingest during startup
./start_stack.sh --no-ingest
```

### PRP File Format
Backlog PRP files should have front matter:

```markdown
---
id: P0-123
title: Example PRP
description: Description of the work
priority_stage: dev
---

# PRP Content
Detailed requirements...
```

## 🔧 Troubleshooting

### Common Issues

**"tmux not found"**
```bash
# macOS
brew install tmux

# Ubuntu/Debian
sudo apt-get install tmux
```

**"redis-cli not found"**
```bash
# macOS
brew install redis

# Ubuntu/Debian
sudo apt-get install redis-tools
```

**"SSH connection failed"**
- Check SSH key path and permissions
- Verify VPS hostname and user
- Test manual SSH connection

**"Redis connection failed"**
- Ensure Redis is running: `redis-server`
- Check REDIS_URL format
- Verify network connectivity

### Script Failures
The startup script includes comprehensive error handling with line numbers. Common fixes:

1. **Environment variables missing** - Check `.env` file
2. **SSH key permissions** - Run `chmod 600 ~/.ssh/leadfactory_deploy`
3. **Redis connectivity** - Start Redis server
4. **Tmux session conflicts** - Script will automatically clean up

### Recovery Commands
```bash
# Force cleanup and restart
tmux kill-session -t leadstack
./start_stack.sh

# Check agent status
tmux list-windows -t leadstack

# View specific agent
tmux attach-session -t leadstack -c orchestrator
```

## 🎯 Usage Patterns

### Development Workflow
1. Start stack: `./start_stack.sh`
2. Monitor in logs window
3. Agents automatically pull from queues
4. Results tracked in Redis

### Emergency Operations
- **Stop all agents**: `tmux kill-session -t leadstack`
- **Restart specific agent**: Kill window and let monitoring restart
- **Clear queues**: Use `redis-cli` to manually clear
- **SSH debug**: Use integrator window for manual SSH

### Performance Tuning
- Adjust agent capacity via environment
- Monitor queue depths in logs window
- Scale agents by adding more tmux windows
- Use Redis clustering for high throughput

## 📊 Success Indicators

### Healthy Stack
- All 6 tmux windows active
- Queue depths changing (not stuck)
- SSH connectivity green
- Redis responding
- Agents responding to context injection

### Expected Startup Time
- Total startup: 30-60 seconds
- Agent startup: 3-5 seconds each
- Context injection: 2-3 seconds per agent
- SSH validation: 5-10 seconds

## 🔐 Security Notes

- SSH keys are validated and permissions fixed automatically
- Redis connection uses secure URL format
- Agent context includes environment isolation
- VPS access is logged and monitored
- All operations are logged for audit

## 📈 Scaling & Production

### Multi-Environment Support
Configure different `.env` files:
- `.env.development`
- `.env.staging`  
- `.env.production`

### Load Balancing
- Multiple dev agents for parallel work
- Queue prioritization via Redis
- Agent capacity scaling
- Horizontal Redis scaling

### Monitoring Integration
- Prometheus metrics via Redis
- Log aggregation to ELK stack
- Alert integration via webhooks
- Health check endpoints

## 🆘 Emergency Contacts

For production issues:
1. Check logs window first
2. Verify VPS connectivity
3. Check Redis status
4. Review agent responsiveness
5. Escalate to team if needed