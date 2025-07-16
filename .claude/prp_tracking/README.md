# PRP Tracking System

## Overview
Enforced state management system for Project Requirement Plans (PRPs) using Claude Code hooks.

## Architecture

### Core Components
1. **Central Source of Truth**: `prp_status.yaml` - Version controlled status tracking
2. **State Transition Engine**: `prp_state_manager.py` - Validates and enforces transitions
3. **Hooks Integration**: Pre-commit and user prompt hooks for enforcement
4. **GitHub Integration**: CI status verification before completion
5. **CLI Commands**: Management interface for PRP operations

### PRP States
- **new**: PRP drafted, quality unknown, no execution done
- **validated**: PRP passed 6-gate review, ready for execution
- **in_progress**: Execution started but not completed
- **complete**: All requirements met, BPCI + GitHub CI passed

### State Transition Rules
```
new → validated: Requires 6-gate validation completion
validated → in_progress: Requires explicit start command
in_progress → complete: Requires BPCI pass + GitHub CI success + feature validation
No backwards transitions without explicit override
```

### File Structure
```
.claude/prp_tracking/
├── README.md                    # This file
├── prp_status.yaml             # Central source of truth
├── prp_state_manager.py        # Core state management logic
├── hooks/
│   ├── pre_commit_hook.py      # Pre-commit validation
│   └── user_prompt_hook.py     # User request interception
├── github_integration.py       # CI status verification
└── cli_commands.py            # Management commands
```

### Integration Points
- **CLAUDE.md**: Updated to reference PRP tracking system
- **Git hooks**: Pre-commit validation
- **Claude hooks**: User prompt interception
- **GitHub API**: CI status verification
- **BPCI**: Local validation integration

## Usage Workflow

### Starting a PRP
```bash
claude-prp start P2-010
```

### Checking Status
```bash
claude-prp status P2-010
claude-prp list --status=in_progress
```

### Completing a PRP
```bash
claude-prp complete P2-010 --commit-hash=abc123
```

### Validation
All state changes are automatically validated through hooks before execution.