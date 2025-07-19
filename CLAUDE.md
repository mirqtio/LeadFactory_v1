🚨🚨🚨 CRITICAL: Multi-Agent PRP Orchestration System 🚨🚨🚨
ALL Project Requirement Plans (PRPs) are managed through a multi-agent orchestration system with Redis-based coordination.

🏗️ AGENT ARCHITECTURE (24x7 AI Operations):
- **Orchestrator**: Strategic oversight, backlog prioritization, quality enforcement
- **Project Managers (PMs)**: Feature development, owns PRP until handoff
- **Integration Agent**: Merge management, CI orchestration, conflict resolution
- **Validator**: Quality gates, standards enforcement, completion verification

📋 PRP STATES (Central Source of Truth: Redis + `.claude/prp_tracking/prp_status.yaml`):
- **new**: PRP drafted, quality unknown, awaiting assignment
- **validated**: PRP passed 6-gate review, ready for assignment
- **assigned**: PRP assigned to PM, development starting
- **development**: PM actively developing feature
- **validation**: PM finished, handed off to Validator for quality review
- **integration**: Validator approved, handed off to Integration Agent for CI
- **complete**: All requirements met, CI passed, Orchestrator verified

🔒 STATE TRANSITION RULES & AGENT AUTHORITY:
- **Orchestrator ONLY**: Assigns PRPs, changes priority, spawns subagents, marks complete after CI success
- **PM Authority**: new → assigned → development → validation (within assigned PRP)
- **Validator**: validation → integration (after quality gates pass) OR back to PM if rejected
- **Integration Agent**: integration → ready for Orchestrator (after CI passes)
- **NO backwards transitions** without Orchestrator override
- **MULTIPLE PRPs** can be in different phases simultaneously

🛠️ AGENT COMMANDS & REDIS COORDINATION:

**Redis Shared State** (All agents read/write):
```bash
# Core PRP tracking
redis-cli SET prp:P0-024:state "development"
redis-cli SET prp:P0-024:owner "pm-2"
redis-cli LPUSH integration:queue "P0-024"
redis-cli SET merge:lock "P0-024"

# Agent status
redis-cli SET agent:pm-1:current_prp "P0-025"
redis-cli SET agent:pm-1:status "coding"
```

**Traditional PRP Commands** (Orchestrator use):
- Status check: `python .claude/prp_tracking/cli_commands.py status [PRP_ID]`
- List PRPs: `python .claude/prp_tracking/cli_commands.py list --status=development`
- Assign PRP: `python .claude/prp_tracking/cli_commands.py assign P2-010 pm-1`

🎯 AGENT ROLES & RESPONSIBILITIES:

**🎛️ Orchestrator (Strategic Authority)**:
- **Backlog Management**: Prioritize PRP queue, assign to PMs
- **Quality Oversight**: Monitor Validator for standards drift
- **Bottleneck Detection**: Spawn additional agents when queues back up
- **Escalation Handling**: Resolve conflicts, handle timeouts
- **Subagent Spawning**: Create Architect/Security SMEs for complex PRPs
- **Integration Health**: Ensure Integration Agent isn't gaming system

**👨‍💻 Project Manager (Feature Development)**:
- **PRP Ownership**: Own assigned PRP from development → validation handoff
- **Feature Implementation**: Code, test, validate locally using `make quick-check`
- **Branch Management**: Work on `feat/<prp-id>-<slug>` branches
- **Handoff Protocol**: Push branch, set Redis state to "validation", move to next PRP
- **Quality Fixes**: Return for fixes if Validator rejects for quality issues
- **Evidence Collection**: Document implementation for Validator review

**✅ Validator (Quality Gates)**:
- **Quality Review**: Receive PRPs from PMs, verify ALL success criteria met
- **Evidence Validation**: Review PM documentation, test results, local validation
- **Standards Enforcement**: Ensure no corners cut, no "functionally complete" shortcuts
- **Quality Gates**: Run comprehensive validation including coverage, performance
- **Handoff Decision**: Pass to Integration Agent OR reject back to PM
- **Metrics Tracking**: Monitor completion quality, flag declining standards

**🔄 Integration Agent (Merge & CI Orchestration)**:
- **Merge Management**: Receive Validator-approved PRPs, acquire merge lock
- **Branch Integration**: Merge feature branches to main using fast-forward/rebase
- **CI Execution**: Run full CI suite - smoke tests, integration tests, deployment
- **CI Monitoring**: Monitor CI success/failure, handle simple fixes
- **Orchestrator Handoff**: Report CI results to Orchestrator for final completion
- **Queue Management**: Process integration queue, notify Orchestrator of backups

🚨 CRITICAL: Definition of "Complete" 🚨🚨🚨
A PRP is ONLY complete when Orchestrator confirms:
- **PM Evidence**: Feature implemented with passing `make quick-check`
- **Validator Approval**: All quality gates passed, standards met
- **Integration Success**: Merged to main with full CI passing
- **No Regressions**: Existing functionality unaffected
- **Standards Compliance**: Code quality, testing, documentation standards met
- **Deployment Verified**: Feature accessible in deployed environment

🔒 BRANCHING & MERGE STRATEGY:
- **Feature Branches**: `feat/<prp-id>-<description>` per PRP
- **Merge Serialization**: Redis `merge:lock` prevents concurrent merges
- **Fast-Forward Only**: Rebase-and-merge to keep clean history
- **Smoke CI Gate**: Integration Agent runs ≤5 min test suite before merge
- **Nightly Regression**: Full test suite runs nightly, auto-generates fix PRPs

📞 COMMUNICATION PROTOCOLS:

**Tmux Messaging** (Between agents):
```bash
# Orchestrator → PM assignment
/Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh pm-1:0 "Assigned P0-024. Review requirements and begin development."

# PM → Integration handoff
redis-cli SET prp:P0-024:state "integration"
redis-cli LPUSH integration:queue "P0-024"

# Integration → PM callback
/Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh pm-2:0 "P0-024 CI failed. Debug branch feat/p0-024-auth. Your expertise needed."

# Validator → Orchestrator escalation
/Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh orchestrator:0 "P0-024 rejected. PM cutting corners on test coverage."
```

**Redis Status Updates** (All agents monitor):
```bash
# Agent heartbeat (every 10 min)
redis-cli HSET agent:pm-1 status "coding" current_prp "P0-024" last_update "2025-01-17T10:30:00Z"

# Queue monitoring
redis-cli LLEN integration:queue  # Orchestrator monitors for backups
redis-cli GET merge:lock          # Check who owns merge lock

# Metrics tracking
redis-cli INCR metrics:prps_completed_today
redis-cli SET metrics:ci_success_rate "0.85"
```

⚡ ESCALATION & TIMEBOXING:

**Automatic Escalation Triggers**:
- **PM stalled**: Redis status unchanged >30 min → Orchestrator ping
- **Integration queue backup**: >5 PRPs waiting → Spawn second Integration Agent
- **CI failures**: Same PRP fails >3 times → Orchestrator intervention
- **Validator rejection**: PRP rejected >2 times → Orchestrator review
- **Merge lock held**: Same lock >60 min → Orchestrator override

**Orchestrator Scheduled Checks** (Every 10 minutes):

🚨 **CRITICAL ORCHESTRATOR PROTOCOL**: The Orchestrator MUST perform agent coordination checks every 10 minutes using the standard template from `/Users/charlieirwin/Tmux-Orchestrator/next_check_note.txt`

**Universal Status Format** (All agents use for coordination):
```
{Agent} {Symbol} {Task}({Progress}) | {Activity} | {Blockers} | ⏱️{Time} | ETA:{Estimate}
Example: PM-1 🔄 P0-022 (60%) | implementing bulk validation tests | ✅ no blockers | ⏱️05:30 | ETA:15m
```

**Status Symbols**: 📋 PENDING, 🔄 IN_PROGRESS, ⚠️ BLOCKED, ✅ COMPLETE, 🚨 URGENT, 🟢 READY, ❌ FAILED, 📊 ANALYZING

**IMPORTANT**: Agent status updates should be posted to Redis using the universal format, NOT in chat channels. Chat should be used for specific task coordination, not routine status broadcasts.

```bash
# Check agent health
for agent in pm-1 pm-2 pm-3 integration validator; do
  last_update=$(redis-cli HGET agent:$agent last_update)
  # Alert if >30 min stale
done

# Check queue health
queue_len=$(redis-cli LLEN integration:queue)
if [ $queue_len -gt 5 ]; then
  # Spawn additional Integration Agent
fi

# Check merge lock timeout
lock_age=$(redis-cli GET merge:lock:timestamp)
# Override if >60 min old
```

🧱 Code Structure & Modularity
Never create a file longer than 500 lines of code. If a file approaches this limit, refactor by splitting it into modules or helper files.
Organize code into clearly separated modules, grouped by feature or responsibility. For agents this looks like:
agent.py - Main agent definition and execution logic
tools.py - Tool functions used by the agent
prompts.py - System prompts
Use clear, consistent imports (prefer relative imports within packages).
Use clear, consistent imports (prefer relative imports within packages).
Use python_dotenv and load_env() for environment variables.
🧪 Testing & Reliability
Always create Pytest unit tests for new features (functions, classes, routes, etc).
After updating any logic, check whether existing unit tests need to be updated. If so, do it.
Tests should live in a /tests folder mirroring the main app structure.
Include at least:
1 test for expected use
1 edge case
1 failure case
✅ Task Completion
Before marking ANY task as complete:
1. Run PRP completion validator (`.claude/prompts/prp_completion_validator.md`) - MUST score 100/100
2. Run `make quick-check` - MUST pass (no exceptions)
3. Run `make pre-push` - MUST pass (no exceptions)  
4. Commit and push to GitHub - MUST use proper validation
5. All CI checks MUST be GREEN
6. If validation fails, create new high-priority todo: "CRITICAL: Fix validation for [task]"
7. NEVER mark a task complete if validation was bypassed

Mark completed tasks in TASK.md immediately after finishing them.
Add new sub-tasks or TODOs discovered during development to TASK.md under a "Discovered During Work" section.
📎 Style & Conventions
Use Python as the primary language.
Follow PEP8, use type hints, and format with black.
Use pydantic for data validation.
Use FastAPI for APIs and SQLAlchemy or SQLModel for ORM if applicable.
Write docstrings for every function using the Google style:
def example():
    """
    Brief summary.

    Args:
        param1 (type): Description.

    Returns:
        type: Description.
    """
📚 Documentation & Explainability
Update README.md when new features are added, dependencies change, or setup steps are modified.
Comment non-obvious code and ensure everything is understandable to a mid-level developer.
When writing complex logic, add an inline # Reason: comment explaining the why, not just the what.
🧠 AI Behavior Rules
Never assume missing context. Ask questions if uncertain.
Never hallucinate libraries or functions – only use known, verified Python packages.
Always confirm file paths and module names exist before referencing them in code or tests.
Never delete or overwrite existing code unless explicitly instructed to or if part of a task 
🚨 Security Warnings
- There is a GitHub token in .env
- Use the GitHub token in .env when checking CI logs on GitHub

🛠️ Development Tools
- **BPCI (Bulletproof CI)**: The unified CI/CD validation system that runs EXACTLY what GitHub CI runs
  - Located at `scripts/bpci.sh` - this is the single source of truth for CI validation
  - Uses Docker Compose to create the same test environment as GitHub Actions
  - Runs the complete test suite with PostgreSQL and stub server dependencies
  - Generates coverage reports and JUnit test results

🛡️ BULLETPROOF CI REQUIREMENTS (MANDATORY)
🚨 BEFORE EVERY COMMIT: Claude Code MUST run validation commands:
- FIRST: Run PRP completion validator (`.claude/prompts/prp_completion_validator.md`) on any completed PRPs
- For quick commits: `make quick-check` (30 seconds)  
- For significant changes: `make pre-push` (5-10 minutes)
- For complete CI simulation: `make bpci` (full Docker-based CI validation)

🚨 NEVER PUSH CODE WITHOUT LOCAL VALIDATION
- These commands catch issues locally instead of breaking CI
- BPCI runs the EXACT same Docker Compose setup as GitHub CI
- If `make bpci` passes locally, GitHub CI will pass

🚨 VALIDATION FAILURE = STOP ALL WORK IMMEDIATELY
- If `make quick-check` fails, fix issues before proceeding with ANY other work
- If `make pre-push` or `make bpci` fails, the push would break CI - fix first
- Validation failures are P0 CRITICAL issues that override all other priorities
- NEVER work around validation problems - fix the root cause
- Create highest priority todo: "CRITICAL: Fix validation failure - [specific error]"
- Debug and fix validation issues properly, don't bypass them
- Check Docker logs for failures: `docker compose -f docker-compose.test.yml logs`
- Only resume other work after validation passes completely

Available validation commands:
- `make quick-check` - Fast linting, formatting, basic unit tests
- `make bpci` - Full Bulletproof CI validation using Docker (mirrors GitHub CI exactly)
- `make pre-push` - Alias for `make bpci` for pre-push validation
- `make format` - Auto-fix code formatting (black + isort)
- `make lint` - Check code quality with flake8
- `make docker-test` - Run tests in Docker without full BPCI setup

🤖 Multi-Agent Workflow Integration

**SuperClaude Framework Workflow (ALL Agents)**:
- Use SuperClaude enhanced commands and intelligent personas
- Leverage MCP servers for specialized capabilities
- Apply appropriate flags for complexity and validation
- Coordinate through Redis state management

**Agent-Specific Workflows**:

**PM Agent Workflow**:
1. Receive PRP assignment via Redis and Tmux notification
2. Execute `/analyze --focus requirements` to understand scope
3. Implement using `/implement` with appropriate personas
4. Validate locally with `make quick-check` (MANDATORY)
5. Update Redis evidence and handoff to Validator
6. Available for callback if Validator rejects for quality issues

**Validator Workflow**:
1. Receive handoff from PM via Redis validation queue
2. Execute `/analyze --focus quality --persona-qa` comprehensive review
3. Execute `/analyze --focus security --persona-security` validation
4. Review all PM evidence and test results
5. Run PRP completion validator (MUST score 100/100)
6. Pass to Integration Agent OR reject back to PM via Redis

**Integration Agent Workflow**:
1. Monitor Redis integration queue for Validator-approved PRPs
2. Acquire merge lock and execute `/git` workflow commands
3. Run full CI suite - smoke tests, integration tests, deployment
4. Handle simple failures, escalate complex issues to PM
5. Report CI success/failure to Orchestrator for final completion
6. Release merge lock and process next queue item

**Orchestrator Workflow**:
1. Monitor Redis agent health and queue status every 10 minutes
2. Assign validated PRPs to available PMs
3. Handle escalations using `/analyze --focus architecture --persona-architect`
4. Spawn additional agents when bottlenecks detected
5. Track system metrics and performance optimization

**CRITICAL Validation Rules (ALL Agents)**:
- ALWAYS validate code before committing using bulletproof CI system
- NEVER use `--no-verify` or bypass validation under any circumstances
- When validation fails, debugging becomes highest priority work item
- Escalate through Redis coordination system, never work around validation
- Use SuperClaude `/troubleshoot` commands for systematic debugging
- Treat validation issues as system bugs requiring fixes, not obstacles to avoid

**Redis Coordination Protocol**:
- Check Redis state before all major operations
- Update Redis with progress, evidence, and status changes
- Respect locks and queue coordination
- Escalate conflicts through proper Redis channels
- Monitor system health and bottleneck indicators

# Multi-Agent System Important Instruction Reminders

**Multi-Agent Coordination Principles**:
- Follow assigned agent role and responsibilities
- Coordinate through Redis state management system
- Use SuperClaude enhanced commands and intelligent personas
- Escalate appropriately through defined channels
- Maintain evidence and transparency for quality gates

**Core Operational Rules**:
- Do what has been asked within agent authority; nothing more, nothing less
- NEVER create files unless absolutely necessary for achieving assigned PRP goals
- ALWAYS prefer editing existing files to creating new ones
- NEVER proactively create documentation files (*.md) or README files unless explicitly part of PRP requirements
- Update Redis coordination state before and after major operations
- Respect merge locks, queue coordination, and agent boundaries

**SuperClaude Integration Requirements**:
- Use appropriate enhanced commands for task complexity
- Apply intelligent personas based on domain and agent role
- Leverage MCP servers for specialized capabilities
- Provide evidence and metrics for quality validation
- Follow escalation procedures for complex issues or conflicts

**Redis MCP Integration Note**: This multi-agent system requires Redis MCP server for coordination. The Redis shared state schema and agent coordination patterns are designed to work with Redis MCP for seamless state management and inter-agent communication.

- Do not ever create a work around or mock data or a sample without explicit permission.
- Follow multi-agent coordination protocols and Redis state management.
- Use SuperClaude framework integration for enhanced AI capabilities.
- Maintain agent role boundaries and escalation procedures.

# Orchestrator Learning System

📚 **Learning & Process Improvement Framework**:
- **Learning File**: `.claude/orchestrator_learnings.md` - Comprehensive session insights and process optimizations
- **Structure**: Process Improvement Suggestions (top) → Ongoing Learnings (bottom)
- **Agent Learning**: Each agent maintains their own learning files for domain expertise
- **Review Cycle**: Regular learning capture during 10-minute orchestrator checks
- **Improvement Integration**: Process suggestions evaluated and implemented continuously

**Learning Capture Requirements**:
- Document session patterns, crisis resolutions, and coordination successes
- Track agent-specific performance insights and optimization opportunities
- Maintain process improvement suggestions by agent role (PM, Validator, Integration)
- Update operational protocols based on real-world session experience
- Ask agents regularly for process improvement suggestions and learning contributions

**Process Evolution Principles**:
- Continuous improvement through systematic learning capture
- Evidence-based process optimization using session data
- Cross-agent pattern recognition and knowledge sharing
- Operational excellence through iterative refinement
- Strategic decision support through historical insight analysis

# Tmux Communication Notes
- **IMPORTANT**: When sending a prompt to another tmux window the Enter key must be sent as a second command.