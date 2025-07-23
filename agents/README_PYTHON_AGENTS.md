# Python-Based Agent System

This is a new Python-based implementation of the multi-agent PRP orchestration system that replaces the tmux/Claude Code approach with direct API calls.

## Architecture

The system consists of stateless worker agents that:
- Pull work from Redis queues
- Process PRPs through Claude API calls
- Extract evidence from responses
- Automatically promote PRPs to next stage
- Handle Q&A with Opus 4 for complex questions

## Key Components

### Core Classes
- `AgentWorker`: Base class with queue processing, evidence extraction, Q&A handling
- `PMAgent`: Developer agent that implements features
- `ValidatorAgent`: Reviews and validates code
- `IntegrationAgent`: Handles CI/CD and deployment
- `QAOrchestrator`: Answers complex questions using Opus 4
- `Orchestrator`: Manages all agents with health monitoring

### Evidence System
Agents communicate completion through JSON evidence blocks:
```json
{"key": "tests_passed", "value": "true"}
{"key": "coverage_pct", "value": "100"}
{"key": "lint_passed", "value": "true"}
{"key": "implementation_complete", "value": "true"}
```

### Queue Flow
1. PM agents: `pm_queue` → `validator_queue`  
2. Validator agents: `validator_queue` → `integration_queue` (or back to `pm_queue` if failed)
3. Integration agents: `integration_queue` → PRP marked complete

**Note**: The original system uses `validation_queue` but due to conflicts with running agents, this implementation uses `validator_queue` instead.

## Testing

The system has been tested with real Claude API calls:
- Evidence extraction works correctly with Claude's response format
- Queue promotion logic functions properly
- Conversation history is preserved in Redis

### Running Tests

```bash
# Simple API test
python agents/test_simple_real.py

# PM workflow test
python agents/test_pm_simple.py

# Full workflow test (requires no conflicting agents running)
python agents/test_full_workflow.py
```

## Configuration

Set your Anthropic API key in the parent `.env` file:
```
ANTHROPIC_API_KEY=your-key-here
```

## Cost Optimization

- PM/Validator/Integration agents use Sonnet 4 ($3/$15 per 1M tokens)
- Q&A Orchestrator uses Opus 4 ($15/$75 per 1M tokens) 
- Average PRP costs estimated at $0.10-0.30 depending on complexity

## Starting the System

```bash
python agents/orchestrator.py
```

This will start all agents and begin processing PRPs from Redis queues.