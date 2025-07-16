# Execute PRP with Completion Validation

Implement a feature using the PRP file with mandatory completion validation.

## PRP Files: $ARGUMENTS (space-separated PRP IDs like "P0-021 P0-022", defaults to all pending)

## Execution Process

1. **Parse Arguments & Check PRP Status**
   - If arguments provided: process only specified PRP IDs (e.g., "P2-010 P2-020")
   - If no arguments: get next validated PRP from tracking system
   - **MANDATORY**: Check PRP status using tracking system:
     ```bash
     python .claude/prp_tracking/cli_commands.py status P2-010
     ```
   - **CRITICAL**: PRP must be in 'validated' state to start execution
   - **CRITICAL**: No other PRPs can be 'in_progress' (only one at a time)

2. **Start PRP Execution**
   - **MANDATORY**: Transition PRP to 'in_progress' state:
     ```bash
     python .claude/prp_tracking/cli_commands.py start P2-010
     ```
   - If transition fails, STOP execution and report the issue

3. **For Each PRP (Sequential Execution):**

   ### A. **Load PRP**
   - Read the specified PRP file from .claude/PRPs/
   - Understand all context and requirements
   - Follow all instructions in the PRP and extend research if needed
   - Check dependencies are completed in .claude/prp_progress.json
   - Do web searches and codebase exploration as needed

   ### B. **ULTRATHINK**
   - Create comprehensive plan addressing ALL requirements
   - Break down complex tasks using TodoWrite tool
   - Identify implementation patterns from existing code
   - Plan for meeting every acceptance criterion

   ### C. **Execute Implementation**
   - Implement all code following PRP specifications
   - Follow CLAUDE.md rules and INITIAL.md security baseline
   - **MANDATORY**: Run `make quick-check` before every commit
   - **MANDATORY**: Run `make pre-push` before any push to GitHub
   - Fix failures and re-run until all pass

   ### D. **PRP Completion Validation (MANDATORY)**
   **CRITICAL: PRP is NOT complete until this passes with 100% score**
   
   Invoke the PRP Completion Validator with:
   - Original PRP document
   - All code changes made
   - Test results and coverage reports
   - CI passing evidence
   - Rollback procedure verification
   
   ```
   Task: PRP Completion Validation for {task_id}
   
   Use .claude/prompts/prp_completion_validator.md to validate this PRP implementation.
   
   Provide:
   1. Original PRP: .claude/PRPs/PRP-{task_id}-*.md
   2. Implementation evidence: code files, test results, documentation
   3. CI status and validation outputs
   
   Score across all dimensions:
   - Acceptance Criteria (30%)
   - Technical Implementation (25%) 
   - Test Coverage (20%)
   - Validation Framework (15%)
   - Documentation (10%)
   
   Return structured feedback with gaps and fixes needed.
   Only mark complete when score = 100/100.
   ```

   ### E. **Iterate Until Perfect**
   - If validation score < 100%, address ALL identified gaps
   - Fix specific issues provided in validation feedback
   - Re-run validation until achieving 100% score
   - DO NOT proceed to next PRP until current one scores 100%

   ### F. **Complete Current PRP**
   - **MANDATORY**: Commit all changes first
   - **MANDATORY**: Verify GitHub CI passes for the commit
   - **MANDATORY**: Complete PRP using tracking system:
     ```bash
     python .claude/prp_tracking/cli_commands.py complete P2-010
     ```
   - This automatically validates BPCI pass + GitHub CI success
   - Update legacy .claude/prp_progress.json for backwards compatibility

3. **Final Report**
   - List all PRPs processed and their final status
   - Report any failures or incomplete implementations
   - Provide summary of validation scores achieved

## Success Criteria (Per PRP)
- All acceptance criteria fully implemented
- PRP Completion Validation score: 100/100
- All tests passing in CI
- No regression in existing functionality
- Rollback procedure tested and documented

## Failure Handling
- If PRP completion validation fails, do NOT proceed to next PRP
- Address all gaps identified by validator
- Iterate implementation → validation until 100% achieved
- If unable to achieve 100% after multiple attempts, escalate with specific blockers

Note: This process ensures every PRP meets the quality standards defined in INITIAL.md before being marked complete.