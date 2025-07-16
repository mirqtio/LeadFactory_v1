# PRP Tracking System Installation Guide

## Overview
This guide will help you install and configure the PRP (Project Requirement Plan) tracking system with Claude Code hooks.

## Prerequisites
- Python 3.11+
- Git repository
- Claude Code installed
- GitHub token (optional, for CI validation)

## Installation Steps

### 1. Verify Installation
The PRP tracking system should already be installed in your repository. Verify by checking:

```bash
ls -la .claude/prp_tracking/
```

You should see:
- `prp_status.yaml` - Central source of truth
- `prp_state_manager.py` - Core state management
- `cli_commands.py` - CLI interface
- `github_integration.py` - GitHub CI validation
- `hooks/` - Claude Code hooks

### 2. Configure Claude Code Settings
The system uses Claude Code hooks. Settings are in `.claude/settings.json`:

```json
{
  "hooks": {
    "userPromptSubmit": {
      "command": "python .claude/prp_tracking/hooks/user_prompt_hook.py",
      "description": "Intercepts PRP status change requests and validates them"
    }
  }
}
```

### 3. Environment Setup (Optional)
For GitHub CI validation, set your GitHub token:

```bash
export GITHUB_TOKEN=your_token_here
```

### 4. Test Installation
Test the system:

```bash
# Check overall status
python .claude/prp_tracking/cli_commands.py status

# Check next PRP
python .claude/prp_tracking/cli_commands.py next

# Check specific PRP
python .claude/prp_tracking/cli_commands.py status P2-010
```

## Usage

### Basic Commands

```bash
# Show all PRPs status
python .claude/prp_tracking/cli_commands.py status

# Show specific PRP
python .claude/prp_tracking/cli_commands.py status P2-010

# List PRPs by status
python .claude/prp_tracking/cli_commands.py list --status=validated

# Get next PRP ready for work
python .claude/prp_tracking/cli_commands.py next

# Start work on a PRP
python .claude/prp_tracking/cli_commands.py start P2-010

# Complete a PRP (requires CI validation)
python .claude/prp_tracking/cli_commands.py complete P2-010
```

### Claude Code Integration

The system integrates with Claude Code through hooks:

1. **User Prompt Hook**: Intercepts requests like "start P2-010" and validates them
2. **Pre-commit Hook**: Prevents invalid commits (planned feature)

### State Management

PRPs have 4 states:
- **new**: Draft PRP, not ready for execution
- **validated**: Ready for execution after 6-gate review
- **in_progress**: Currently being implemented
- **complete**: Fully implemented and validated

### Workflow

1. **Start a PRP**: `python .claude/prp_tracking/cli_commands.py start P2-010`
2. **Work on implementation**: Code, test, validate locally
3. **Complete PRP**: `python .claude/prp_tracking/cli_commands.py complete P2-010`
4. **System validates**: BPCI pass, GitHub CI success, requirements met

## Troubleshooting

### Common Issues

1. **"PRP not found"**: Check PRP ID spelling and case sensitivity
2. **"Invalid transition"**: Check current status and allowed transitions
3. **"BPCI validation failed"**: Run `make quick-check` to see issues
4. **"GitHub CI failed"**: Check GitHub Actions for failing tests

### Debug Commands

```bash
# Check PRP state manager directly
python .claude/prp_tracking/prp_state_manager.py status P2-010

# Check GitHub integration
python .claude/prp_tracking/github_integration.py status abc123

# Test user prompt hook
python .claude/prp_tracking/hooks/user_prompt_hook.py "start P2-010"
```

### System Recovery

If the system gets into an inconsistent state:

1. **Check status file**: `.claude/prp_tracking/prp_status.yaml`
2. **Verify git state**: `git status`
3. **Run validation**: `make quick-check`
4. **Check GitHub CI**: Recent workflow runs

## Configuration

### Custom Settings

Edit `.claude/prp_tracking/prp_status.yaml` to:
- Add new PRPs
- Update PRP titles
- Add notes or metadata

**⚠️ Warning**: Only modify through CLI commands or risk validation errors.

### Hook Configuration

Hooks are configured in `.claude/settings.json`. You can:
- Enable/disable hooks
- Modify hook commands
- Add custom validation

## Integration with Development Workflow

### With Git

The system integrates with your git workflow:
- Pre-commit hooks validate PRP transitions
- Commit messages can trigger PRP state changes
- GitHub CI validation ensures quality

### With BPCI

The system requires BPCI validation:
- `make quick-check` must pass
- `make pre-push` must pass
- All CI checks must be green

### With Claude Code

The system enhances Claude Code:
- Automatic PRP status management
- Validation before state changes
- Clear workflow enforcement

## Support

For issues:
1. Check this documentation
2. Review system logs
3. Validate your environment
4. Test with simple commands first

The system is designed to be fail-safe - if hooks fail, development continues normally.