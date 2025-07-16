🚨🚨🚨 CRITICAL: PRP Status Management System 🚨🚨🚨
ALL Project Requirement Plans (PRPs) are managed through an enforced state tracking system.

📋 PRP STATES (Central Source of Truth: `.claude/prp_tracking/prp_status.yaml`):
- **new**: PRP drafted, quality unknown, no execution done
- **validated**: PRP passed 6-gate review, ready for execution  
- **in_progress**: Execution started but not completed
- **complete**: All requirements met, BPCI + GitHub CI passed

🔒 STATE TRANSITION RULES (Enforced by hooks):
- new → validated: Requires 6-gate validation completion
- validated → in_progress: Requires explicit start command
- in_progress → complete: Requires BPCI pass + GitHub CI success + feature validation
- NO backwards transitions without explicit override
- ONLY ONE PRP can be in_progress at a time

🛠️ PRP MANAGEMENT COMMANDS:
- Status check: `python .claude/prp_tracking/cli_commands.py status [PRP_ID]`
- Start PRP: `python .claude/prp_tracking/cli_commands.py start P2-010`
- Complete PRP: `python .claude/prp_tracking/cli_commands.py complete P2-010`
- List PRPs: `python .claude/prp_tracking/cli_commands.py list --status=in_progress`
- Next PRP: `python .claude/prp_tracking/cli_commands.py next`

🚨 CRITICAL: Definition of "Complete" 🚨🚨🚨
A PRP is ONLY complete when:
- Code is implemented and validated
- `make quick-check` passes locally (MANDATORY)
- `make pre-push` passes locally (MANDATORY)
- Pushed to GitHub main branch  
- ALL CI checks pass GREEN (not just some)
- This includes Test Suite, Docker Build, Linting, Deploy to VPS - EVERYTHING
- If CI was green before and isn't now, the changes broke it and must be fixed
- NEVER mark a task as complete if ANY CI check is failing
- NEVER use `--no-verify` or bypass validation
- "Deploy to VPS passing" does NOT mean the task is complete if Test Suite is failing
- PRP status transitions are enforced by hooks and cannot be bypassed

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

🤖 Agent Workflow
- Use Task Subagents when possible.
- ALWAYS validate code before committing using bulletproof CI system.
- NEVER use `--no-verify` or bypass validation under any circumstances.
- When validation fails, debugging validation becomes the highest priority work item.
- Treat validation issues as system bugs to be fixed, not obstacles to avoid.