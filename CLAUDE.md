🚨🚨🚨 CRITICAL: Definition of "Complete" 🚨🚨🚨
A task is ONLY complete when:
- Code is implemented and validated
- Pushed to GitHub main branch  
- ALL CI checks pass GREEN (not just some)
- This includes Test Suite, Docker Build, Linting, Deploy to VPS - EVERYTHING
- If CI was green before and isn't now, the changes broke it and must be fixed
- NEVER mark a task as complete if ANY CI check is failing
- "Deploy to VPS passing" does NOT mean the task is complete if Test Suite is failing

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
- There is a local CI/CD bootstrap you can use.

🛡️ BULLETPROOF CI REQUIREMENTS (MANDATORY)
🚨 BEFORE EVERY COMMIT: Claude Code MUST run validation commands:
- For quick commits: `make quick-check` (30 seconds)  
- For significant changes: `make pre-push` (5-10 minutes)
- For complete CI simulation: `make ci-local` (full pipeline)

🚨 NEVER PUSH CODE WITHOUT LOCAL VALIDATION
- These commands catch issues locally instead of breaking CI
- They mirror GitHub CI exactly - if local passes, CI will pass
- Prevents the chronic CI failure cycle that wastes time

🚨 VALIDATION FAILURE = STOP WORK
- If `make quick-check` fails, fix issues before proceeding
- If `make pre-push` fails, the push would break CI - fix first
- Use this system to debug current CI issues faster

Available validation commands:
- `make quick-check` - Fast linting, formatting, basic tests
- `make pre-push` - Complete pre-push validation (mirrors CI exactly)  
- `make ci-local` - Full GitHub CI simulation
- `make format` - Auto-fix code formatting
- `make lint` - Check code quality

🤖 Agent Workflow
- Use Task Subagents when possible.
- ALWAYS validate code before committing using bulletproof CI system.