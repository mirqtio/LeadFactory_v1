  # CLAUDE.md - Mandatory Rules (NEVER DEVIATE)

  ## CRITICAL WORKFLOW RULES
  1. **After every auto-compact**: IMMEDIATELY review @planning/README.md before doing ANY other work
  2. **Never work around requirements** - If blocked, ask for clarification, don't improvise
  3. **Follow the plan precisely** - Use taskmaster_plan.json as the single source of truth
  4. **Task completion definition**: A task is ONLY complete when ALL of these are met:
     - ✅ All tests pass in Docker environment 
     - ✅ Code merged into main branch
     - ✅ CI shows "conclusion": "success" (not "in_progress" or "failure")
     - ✅ Task marked "completed" in @planning/task_status.json
  5. **Test integrity**: Do not make tests fail gracefully when the point is to detect failures

  ## MANDATORY TASK WORKFLOW (NEVER SKIP STEPS)
  1. **Start**: Run `python3 planning/get_next_task.py` to get next task
  2. **Begin**: Mark task as "in_progress" in task_status.json  
  3. **Implement**: Follow acceptance criteria exactly from taskmaster_plan.json
  4. **Test**: Run tests locally, then in Docker - both MUST pass
  5. **Commit**: Create descriptive git commit and push to main
  6. **Verify CI**: Wait for CI status to be "success" (use GitHub API to confirm)
  7. **Complete**: Mark task "completed" in task_status.json
  8. **CONTINUE**: Immediately run get_next_task.py and start next task
  9. **NEVER STOP**: Repeat until all 100 tasks are complete

  ## BLOCKING CONDITIONS (MUST CHECK BEFORE PROCEEDING)
  - [ ] @planning/README.md has been reviewed (if after auto-compact)
  - [ ] Current task dependencies are satisfied
  - [ ] Previous task is fully complete per rule #4
  - [ ] CI status is "success" for latest commit
  - [ ] Next task ID retrieved from get_next_task.py

  ## COMPLIANCE VERIFICATION COMMANDS
  ```bash
  # Check CI status for latest commit
  curl -s -H "Accept: application/vnd.github.v3+json" \
    https://api.github.com/repos/mirqtio/LeadFactory_v1/actions/runs | \
    jq '.workflow_runs[0] | {name, status, conclusion, head_sha}'

  # Get next task
  python3 planning/get_next_task.py

  # Run Docker tests
  docker build -t test-app . && docker run --rm test-app python3 -m pytest [test_path] -v

  FAILURE RECOVERY

  If any step fails:
  1. DO NOT PROCEED to next task
  2. FIX THE ISSUE completely
  3. RE-RUN ALL STEPS from the beginning
  4. VERIFY COMPLIANCE before continuing

  CONTINUOUS EXECUTION MANDATE

  - NEVER STOP after completing one task
  - IMMEDIATELY CONTINUE to next task after completion
  - WORK THROUGH ALL 100 TASKS systematically
  - ASK FOR PERMISSION only if genuinely blocked
  - DEFAULT TO CONTINUING work on next available task

  ERROR HANDLING

  - NO WORKAROUNDS - Fix root causes
  - NO SHORTCUTS - Follow every step
  - NO ASSUMPTIONS - Verify everything
  - ASK QUESTIONS only when truly blocked

  ## Key Improvements in This Version:

  1. **Explicit Workflow Steps**: Clear numbered steps that must be followed in order
  2. **Blocking Conditions**: Checklist format that forces verification
  3. **Continuous Execution Mandate**: Makes it impossible to stop after one task
  4. **Specific Commands**: Exact commands to verify compliance
  5. **Failure Recovery Process**: Clear instructions for when things go wrong
  6. **CI Verification**: Specific API calls to confirm CI status
  7. **No Ambiguity**: Every rule is explicit and actionable