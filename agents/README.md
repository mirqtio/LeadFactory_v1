# LeadFactory Agent System

A Python-based multi-agent system that processes PRPs (Pull Request Proposals) through development, validation, and integration stages using Claude API.

## Architecture

The system replaces tmux/Claude Code instances with Python workers that call Claude API directly:

```
┌─────────────────┐
│   Orchestrator  │ (Python coordinator)
│                 │
└────────┬────────┘
         │
┌────────┴────────┬─────────┬──────────┐
│                 │         │          │
▼                 ▼         ▼          ▼
PM Agents    Validator  Integration  Q&A Oracle
(Sonnet 4)   (Sonnet 4) (Sonnet 4)   (Opus 4)
│                 │         │          │
└─────────────────┴─────────┴──────────┘
                  │
                Redis
```

## Key Features

- **Stateless Workers**: Agents pull work from Redis queues
- **Evidence-Based Completion**: Agents output structured JSON evidence
- **Q&A System**: Complex questions routed to Opus 4 with full codebase context
- **Automatic Retries**: Failed PRPs are retried with context
- **Health Monitoring**: Orchestrator monitors and restarts failed agents

## Setup

1. **Install Redis**:
   ```bash
   # macOS
   brew install redis
   brew services start redis
   
   # Ubuntu
   sudo apt-get install redis
   sudo systemctl start redis
   ```

2. **Get Anthropic API Key**:
   - Sign up at https://console.anthropic.com
   - Generate an API key
   - Note: This is separate from Claude.ai subscriptions

3. **Configure Environment**:
   ```bash
   cd agents
   cp .env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   ```

4. **Install Dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Running the System

### Start the Agents
```bash
./start_agents.sh
```

### Reset Queues and Start Fresh
```bash
./start_agents.sh --reset
```

### Add a PRP to Process
```python
import redis
r = redis.from_url("redis://localhost:6379/0")

# Add PRP data
r.hset("prp:P0-001", {
    "id": "P0-001",
    "title": "Add user authentication",
    "content": "Implement JWT-based authentication...",
    "priority": "high"
})

# Queue for development
r.lpush("dev_queue", "P0-001")
```

## Agent Roles

### PM/Developer Agent
- Implements features based on PRP requirements
- Writes tests and ensures coverage
- Outputs evidence: `tests_passed`, `coverage_pct`, `implementation_complete`

### Validator Agent
- Reviews code quality and correctness
- Checks security and performance
- Can approve or reject with feedback

### Integration Agent
- Handles git operations and CI/CD
- Diagnoses and fixes CI failures
- Manages deployment

### Q&A Orchestrator
- Uses Opus 4 for complex questions
- Has full codebase context
- Helps agents with architectural decisions

## Evidence Format

Agents output evidence as JSON blocks:

```json
{"key": "tests_passed", "value": "true"}
{"key": "coverage_pct", "value": "85"}
{"key": "lint_passed", "value": "true"}
```

## Monitoring

Check system status:
```bash
redis-cli
> LLEN dev_queue        # Pending PRPs
> LLEN dev_queue:inflight  # Active PRPs
> HGETALL agent:pm-1    # Agent status
> GET metrics:latest    # System metrics
```

## Cost Estimation

With Sonnet 4 (~$3/MTok input, $15/MTok output):
- Average PRP: ~450k tokens total
- Cost per PRP: ~$5-10
- Daily cost (100 PRPs): ~$500-1000

Optimization available through:
- Prompt caching (90% savings on repeated context)
- Batch processing (50% discount)
- Smart routing (only complex questions to Opus 4)

## Testing

Run the test suite:
```bash
cd tests
python -m pytest test_agent_system.py -v
```

## Troubleshooting

### "Redis is not running"
Start Redis: `brew services start redis` or `sudo systemctl start redis`

### "ANTHROPIC_API_KEY not configured"
Add your API key to the .env file

### Agent crashes
Check logs - the orchestrator will automatically restart crashed agents

### High costs
- Switch to Haiku for simple tasks
- Enable prompt caching
- Reduce PM_AGENT_COUNT in .env

## Configuration

See `.env.example` for all configuration options:
- Model selection per role
- Agent counts
- Retry policies  
- Cost limits
- Monitoring intervals