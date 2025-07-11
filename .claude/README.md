# LeadFactory Context Engineering

This directory contains the context engineering infrastructure for the LeadFactory project, adapted from [context-engineering-intro](https://github.com/coleam00/context-engineering-intro).

## Overview

The system uses a recursive PRP (Project Requirements Plan) approach to systematically implement tasks defined in `INITIAL.md`. Tasks are executed in two waves:

- **Wave A**: Stabilize existing codebase (P0 priority tasks)
- **Wave B**: Add Phase 0.5 features (P1/P2 priority tasks)

## Directory Structure

```
.claude/
├── commands/           # Claude command definitions
├── PRPs/              # Generated PRP files
├── scripts/           # Automation scripts
├── templates/         # PRP templates
├── prp_progress.json  # Execution progress tracking
└── README.md          # This file
```

## Workflow

### 1. Generate PRPs from INITIAL.md

```bash
python .claude/scripts/recursive_prp_processor.py generate
```

This parses `INITIAL.md` and creates individual PRP files following the naming convention: `PRP-{priority}-{title-slug}.md`

### 2. Execute PRPs Recursively

```bash
python .claude/scripts/recursive_prp_processor.py execute
```

This will:
- Execute PRPs in dependency order
- Track progress in `prp_progress.json`
- Stop on failures
- Ensure Wave A completes before Wave B starts

### 3. Check Status

```bash
python .claude/scripts/recursive_prp_processor.py status
```

Shows current progress and which tasks are pending/completed/failed.

## PRP Naming Convention

PRPs follow this naming pattern:
- `PRP-P0-000-prerequisites-check.md`
- `PRP-P1-010-semrush-client-metrics.md`
- `PRP-P2-040-orchestration-budget-stop.md`

Where:
- `P0/P1/P2` = Priority level
- `000-999` = Task sequence number
- `title-slug` = Kebab-case title

## Key Files

### INITIAL.md
Master plan with all tasks, dependencies, and acceptance criteria.

### recursive_prp_processor.py
Python script that:
- Parses INITIAL.md
- Generates PRP files
- Manages execution order
- Tracks progress

### prp_progress.json
Tracks task status:
```json
{
  "P0-000": "completed",
  "P0-001": "in_progress",
  "P0-002": "pending"
}
```

## Claude Commands

- `generate-prp`: Create a single PRP with research
- `execute-prp`: Execute a single PRP
- `execute-prp-recursive`: Execute PRP and continue to next

## Rules

1. **Dependencies**: Tasks can only execute if dependencies are complete
2. **Wave Order**: All Wave A must complete before Wave B starts
3. **Failure Stops**: Any P0 failure stops execution
4. **CI Verification**: Each task must verify CI is green
5. **Progress Tracking**: All status updates saved to progress file

## Usage with Claude

1. First, have Claude generate all PRPs:
   ```
   Run: python .claude/scripts/recursive_prp_processor.py generate
   ```

2. Then start recursive execution:
   ```
   Execute the first PRP using execute-prp-recursive command
   ```

3. Claude will automatically continue through all tasks until complete or blocked.

## Troubleshooting

- **Dependencies not met**: Check `prp_progress.json` and complete required tasks
- **PRP not found**: Run generate command to create PRPs
- **Execution stopped**: Check for failed tasks in status output

## Important Notes

- Always follow CLAUDE.md rules during execution
- Each task must have passing tests before marking complete
- Use Docker for test verification to match CI environment
- Commit after each successful task completion