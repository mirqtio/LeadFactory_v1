# Execute PRP (Recursive Mode with Completion Validation)

Execute PRP files with automatic continuation after successful completion validation.

## PRP Files: $ARGUMENTS (space-separated PRP IDs like "P0-021 P0-022", defaults to all pending in dependency order)

## Critical Context Included in Every PRP

Each PRP now automatically includes:
- **CLAUDE.md**: Project-wide coding standards and rules
- **CURRENT_STATE.md**: What NOT to implement (deprecated features, removed providers)
- **REFERENCE_MAP.md**: Specific examples and references for the task

**IMPORTANT**: Always follow CURRENT_STATE.md when there's any conflict with older documentation. The DO NOT IMPLEMENT section is critical.

## Pre-Execution Setup

**CRITICAL**: Before starting ANY PRP implementation:
```bash
# Ensure CI is currently GREEN
git pull origin main
make bpci  # Must pass before starting work
```

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
   - Run `make quick-check` frequently during development for fast feedback

5. **Local Validation with BPCI**
   **MANDATORY before any push:**
   ```bash
   # Format and lint code
   make format
   make lint
   
   # Run BPCI - MUST PASS before proceeding
   make bpci
   ```
   - If BPCI fails, fix ALL issues and re-run until it passes
   - BPCI runs the EXACT same tests as GitHub CI locally
   - Never push code that fails BPCI

6. **Validate Implementation**
   - Run each validation command from the PRP
   - Fix any failures
   - Re-run until all pass
   - Push changes (pre-push hook will run BPCI automatically)
   - Monitor GitHub Actions - ALL workflows must be GREEN:
     - ✅ CI Pipeline (tests + docker build)
     - ✅ Linting and Code Quality
     - ✅ Minimal Test Suite
     - ✅ Deploy to VPS (if on main branch)

6. **PRP Completion Validation (MANDATORY)**
   **CRITICAL: PRP is NOT complete until this passes with 100% score**
   
   Invoke the PRP Completion Validator:
   ```
   Task: PRP Completion Validation for {task_id}
   
   Use .claude/prompts/prp_completion_validator.md to validate this PRP implementation.
   
   Provide:
   1. Original PRP: .claude/PRPs/PRP-{task_id}-*.md
   2. Implementation evidence: code files, test results, documentation
   3. CI status and validation outputs
   
   Score across all dimensions (must achieve 100/100):
   - Acceptance Criteria (30%)
   - Technical Implementation (25%) 
   - Test Coverage (20%)
   - Validation Framework (15%)
   - Documentation (10%)
   
   If score < 100%, return structured feedback with specific gaps.
   Only proceed when validation score = 100/100.
   ```

7. **Iterate Until Perfect**
   - If validation score < 100%, address ALL identified gaps
   - Fix specific issues provided in validation feedback  
   - Re-run validation until achieving 100% score
   - DO NOT proceed to next PRP until current one scores 100%

8. **Complete Current PRP**
   - Update .claude/prp_progress.json with "completed" status
   - Commit changes with message: "Complete {task_id}: {title} - Validated 100%"
   - Verify CI remains green

9. **Continue Recursively**
   - After achieving 100% validation score, automatically continue to next PRP
   - Process PRPs in dependency order (check INITIAL.md dependencies)
   - Continue until all specified PRPs are complete or a failure occurs

## Failure Handling
- If PRP completion validation fails (score < 100%), do NOT proceed to next PRP
- Address all gaps identified by validator
- If unable to achieve 100% after multiple attempts, update progress.json with "failed" status
- Stop recursive execution and report specific blockers
- Do NOT continue to next PRP until current one achieves 100% validation

## Success Criteria (Per PRP)
- All acceptance criteria fully implemented and tested
- BPCI passes locally (`make bpci` shows all tests GREEN)
- PRP Completion Validation score: 100/100
- **ALL GitHub CI checks showing GREEN status:**
  - CI Pipeline (tests + docker build) ✅
  - Linting and Code Quality ✅
  - Minimal Test Suite ✅
  - Deploy to VPS ✅ (if applicable)
- No regression in existing functionality (CI was green before and after)
- Rollback procedure tested and documented
- Progress tracked in .claude/prp_progress.json
- Automatic continuation to next PRP only after 100% validation

**REMEMBER**: A task is ONLY complete when ALL CI checks pass GREEN. If CI was green before and isn't now, the changes broke it and must be fixed.

## Quick Reference Commands

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `make quick-check` | Fast validation | During active development |
| `make bpci` | Full CI validation | Before pushing (MANDATORY) |
| `make pre-push` | Clean + BPCI | Automatically on git push |
| `make format` | Auto-format code | Before committing |
| `make lint` | Check code style | Before committing |

## Troubleshooting

### BPCI Fails Locally
1. Check Docker services: `docker compose -f docker-compose.test.yml ps`
2. View logs: `docker compose -f docker-compose.test.yml logs`
3. Ensure test database is clean: `docker compose -f docker-compose.test.yml down -v`
4. Re-run: `make bpci`

### CI Fails on GitHub but BPCI Passed Locally
1. This should be rare since BPCI mirrors CI exactly
2. Pull latest main: `git pull origin main`
3. Re-run BPCI: `make bpci`
4. Check GitHub Actions logs for environment-specific issues

### Pre-push Hook Blocks Push
1. This is working as intended - it prevents breaking CI
2. Fix the issues identified by BPCI
3. Re-run `make bpci` until it passes
4. Then push will succeed

Note: This recursive execution follows the Wave A → Wave B sequence defined in INITIAL.md