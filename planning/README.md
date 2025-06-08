# LeadFactory Planning & Task Management

This directory contains tools and documentation for managing the LeadFactory MVP development process.

## Overview

The LeadFactory project uses TaskMaster for tracking development progress across 100 tasks spanning 15 phases. This planning directory provides tools to:

- Track task completion status
- Get the next task to work on
- View progress metrics
- Integrate with TaskMaster

## Files

### `get_next_task.py`
Python script to identify the next task to work on based on dependencies and current progress.

```bash
python planning/get_next_task.py
```

### `task_status.json`
JSON file tracking the current status of all tasks. Updated automatically as tasks are completed.

### `taskmaster_plan.json`
The master task plan with all 100 tasks, dependencies, and acceptance criteria.

## Task Workflow

1. **Get Next Task**: Run `get_next_task.py` to identify what to work on
2. **Mark In Progress**: Update task status to "in_progress" 
3. **Implement**: Complete the task following acceptance criteria
4. **Test**: Run all tests including Docker tests if required
5. **Mark Complete**: Update task status to "completed"
6. **Commit**: Create a git commit with task reference

## Task Status

Tasks can have the following statuses:
- `pending`: Not yet started, may have unmet dependencies
- `ready`: All dependencies met, ready to start
- `in_progress`: Currently being worked on
- `completed`: Finished and tested
- `blocked`: Cannot proceed due to external factors

## Progress Tracking

Current progress is tracked in multiple ways:

1. **task_status.json**: Machine-readable status for all tasks
2. **TaskMaster Integration**: Updates todo list automatically
3. **Git Commits**: Each task completion creates a commit
4. **Metrics**: Prometheus tracks implementation metrics

## TaskMaster Integration

TaskMaster is integrated to provide:
- Visual progress tracking
- Task dependencies management
- Time estimation vs actual
- Automatic status updates

To use TaskMaster:
1. Tasks are automatically synced from `taskmaster_plan.json`
2. Status updates in `task_status.json` reflect in TaskMaster
3. Use TaskMaster UI for visual progress tracking

## Development Guidelines

When working on tasks:

1. **Check Dependencies**: Ensure all dependent tasks are complete
2. **Follow Acceptance Criteria**: Each task has specific criteria in the plan
3. **Write Tests**: All code must have tests per the PRD
4. **Run Docker Tests**: If specified, tests must pass in Docker
5. **Update Documentation**: Keep docs current with implementation

## Phases Overview

The 100 tasks are organized into 15 phases:

1. **Foundation Setup** (Tasks 1-10): Core infrastructure
2. **D0 Gateway** (Tasks 11-20): External API integration
3. **D1 Targeting** (Tasks 21-25): Business search
4. **D2 Enrichment** (Tasks 26-30): Data enhancement
5. **D3 Assessment** (Tasks 31-35): Website analysis
6. **D4 Engagement** (Tasks 36-40): Email outreach
7. **D5 Delivery** (Tasks 41-45): Report generation
8. **D6 Payment** (Tasks 46-50): Stripe integration
9. **D7 Storefront** (Tasks 51-55): Purchase flow
10. **D8 Pipeline** (Tasks 56-65): Orchestration
11. **D9 Attribution** (Tasks 66-70): Tracking
12. **D10 Experiment** (Tasks 71-75): A/B testing
13. **D11 Operations** (Tasks 76-80): Admin tools
14. **Testing** (Tasks 81-89): Comprehensive testing
15. **Deployment** (Tasks 90-100): Production launch

## Quick Commands

```bash
# Get next task to work on
python planning/get_next_task.py

# Check overall progress
python planning/get_next_task.py --progress

# Update task status
python planning/get_next_task.py --update TASK_ID STATUS

# Verify all dependencies
python planning/get_next_task.py --verify

# Generate progress report
python planning/get_next_task.py --report
```

## Best Practices

1. **One Task at a Time**: Focus on completing one task before starting another
2. **Test Continuously**: Run tests after each significant change
3. **Commit Often**: Make atomic commits for each task
4. **Document Changes**: Update relevant documentation
5. **Track Time**: Note actual time vs estimates for future planning

## Troubleshooting

If you encounter issues:

1. **Dependency Conflicts**: Check `get_next_task.py --verify`
2. **Test Failures**: Ensure Docker services are running
3. **Status Sync Issues**: Manually update `task_status.json`
4. **TaskMaster Sync**: Check network connectivity

## Contributing

When contributing to planning tools:

1. Test scripts thoroughly
2. Maintain backwards compatibility
3. Update this README
4. Add error handling
5. Include logging for debugging