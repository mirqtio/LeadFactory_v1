# Execute PRP (Recursive Mode)

Execute a PRP file with automatic continuation to the next PRP after successful completion.

## PRP File: $ARGUMENTS

## Critical Context Included in Every PRP

Each PRP now automatically includes:
- **CLAUDE.md**: Project-wide coding standards and rules
- **CURRENT_STATE.md**: What NOT to implement (deprecated features, removed providers)
- **REFERENCE_MAP.md**: Specific examples and references for the task

**IMPORTANT**: Always follow CURRENT_STATE.md when there's any conflict with older documentation. The DO NOT IMPLEMENT section is critical.

## Execution Process

1. **Load PRP**
   - Read the specified PRP file (includes CLAUDE.md and CURRENT_STATE.md)
   - Understand all context and requirements
   - Pay special attention to the DO NOT IMPLEMENT section
   - Follow all instructions in the PRP and extend the research if needed
   - Ensure you have all needed context to implement the PRP fully
   - Do more web searches and codebase exploration as needed

2. **Check Dependencies**
   - Verify all dependent tasks are completed (check .claude/prp_progress.json)
   - If dependencies not met, report and stop

3. **ULTRATHINK**
   - Think hard before you execute the plan. Create a comprehensive plan addressing all requirements.
   - Break down complex tasks into smaller, manageable steps using your todos tools.
   - Use the TodoWrite tool to create and track your implementation plan.
   - Identify implementation patterns from existing code to follow.

4. **Execute the plan**
   - Execute the PRP
   - Implement all the code
   - Follow CLAUDE.md rules strictly

5. **Validate**
   - Run each validation command from the PRP
   - Fix any failures
   - Re-run until all pass
   - Verify CI is green after pushing

6. **Complete**
   - Ensure all checklist items done
   - Run final validation suite
   - Update .claude/prp_progress.json with completion status
   - Commit changes with descriptive message referencing the PRP

7. **Continue Recursively**
   - After successful completion, automatically run:
     ```bash
     python .claude/scripts/recursive_prp_processor.py execute
     ```
   - This will find and execute the next PRP in sequence
   - Continue until all PRPs are complete or a failure occurs

## Failure Handling
- If a task fails, update progress.json with "failed" status
- Stop recursive execution
- Report the failure clearly
- Do NOT continue to next PRP on failure

## Success Criteria
- All tests in the PRP pass
- All acceptance criteria met
- CI shows green after push
- Progress tracked in .claude/prp_progress.json
- Automatic continuation to next PRP

Note: This recursive execution follows the Wave A → Wave B sequence defined in INITIAL.md