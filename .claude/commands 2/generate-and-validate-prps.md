# Generate and Validate PRPs

Review INITIAL.md and identify all PRPs that are not marked as complete in .claude/prp_progress.json. For each incomplete task, generate high-quality PRPs using an automated validation loop that regenerates based on feedback until validation passes.

## Usage
Arguments: $ARGUMENTS (optional task IDs like "P0-021 P0-022", defaults to all pending)

## Process Overview

1. **Read INITIAL.md** to extract all task definitions
2. **Check .claude/prp_progress.json** to identify which tasks need PRPs (not marked as "completed")
3. **Filter by arguments** if provided (e.g., only process P0-021 if specified)
4. **Run validation loops** for each task (NOT just spawn subagents)
5. **Generate Super PRP** after all individual PRPs pass validation

## Research Task for Context Gathering

### Research Agent (Run BEFORE PRP Generation)
For each task, spawn a research Task subagent to gather authoritative context:

```
Task: Research context for {task_id} - {title}
1. Read the prompt from .claude/prompts/research_context.md
2. Replace placeholders: {task_id}, {title}, {dependencies}, {goal}
3. Focus research on the TECHNICAL ASPECTS of the task:
   - For "Lead Explorer": Research FastAPI CRUD patterns, SQLAlchemy models, Pydantic schemas
   - For "CI Test Re-enablement": Research pytest markers, pytest-xdist, GitHub Actions optimization
   - For "Template Studio": Research Jinja2 templating, Monaco editor integration, GitHub API
   - NOT generic terms like "PRP", "Claude", "product requirements"
4. Search for:
   - Official documentation (highest priority)
   - Recent GitHub issues/PRs discussing the topic
   - Technical blog posts from recognized authorities
   - Recent discussions (HackerNews, Reddit, YouTube tutorials)
   - Best practices and common pitfalls
5. Synthesize findings into a research context document
6. Save to .claude/research_cache/research_{task_id}.txt
7. Return key insights and relevant URLs
```

## Six-Gate Validation Conveyor Implementation

### IMPORTANT: Each Task Must Run Complete Six-Gate Validation
For each task that needs a PRP, spawn a Task subagent that runs the ENTIRE six-gate validation conveyor:

```
Task: Complete Six-Gate validation for {task_id} - {title}

INITIAL RESEARCH (first time only):
0. RESEARCH CONTEXT:
   - Read .claude/prompts/research_context.md
   - Search for authoritative sources and recent discussions
   - Save findings to .claude/research_cache/research_{task_id}.txt
   - Include research context in PRP generation

SIX-GATE VALIDATION CONVEYOR (repeat up to 3 times):
1. REGENERATE (or generate if first attempt):
   - Read .claude/prompts/regenerate_prp.md (or generate_prp.md for first attempt)
   - Include research context from .claude/research_cache/research_{task_id}.txt
   - If regenerating, include ALL feedback from failed gates:
     * {schema_issues}: Structure and format violations
     * {policy_issues}: DO NOT IMPLEMENT violations and architecture conflicts
     * {lint_issues}: Code style, security, and pattern violations
     * {research_issues}: Missing authoritative sources and outdated practices
     * {critic_issues}: Quality and completeness issues
     * {judge_feedback}: Dimension scores and improvement areas
     * {ui_issues}: Design token, accessibility, and pattern violations (if UI task)
   - Generate/regenerate the PRP addressing all feedback
   - Save to .claude/PRPs/PRP-{task_id}-{title-slug}.md

2. SCHEMA VALIDATION (Gate 1):
   - Read .claude/prompts/schema_validation.md
   - Validate PRP structure, format, and required sections
   - Check task ID format, mandatory fields, content structure
   - If FAIL: Go back to step 1 with schema errors
   - If PASS: Continue to Gate 2

3. POLICY VALIDATION (Gate 2):
   - Read .claude/prompts/policy_validation.md
   - Check against DO NOT IMPLEMENT list from CURRENT_STATE.md
   - Verify technology stack compliance and feature flag respect
   - If FAIL: Go back to step 1 with policy violations
   - If PASS: Continue to Gate 3

4. LINT VALIDATION (Gate 3):
   - Read .claude/prompts/lint_validation.md
   - Check code examples for style, security, and architectural patterns
   - Validate configuration syntax and best practices
   - If FAIL: Go back to step 1 with lint issues
   - If PASS: Continue to Gate 4

5. RESEARCH VALIDATION (Gate 4):
   - Read .claude/prompts/research_validator.md
   - Verify authoritative sources and technical accuracy
   - Check for outdated practices or missing developments
   - If FAIL: Go back to step 1 with research gaps
   - If PASS: Continue to Gate 5

6. CRITIC REVIEW (Gate 5):
   - Read .claude/prompts/critic_review.md
   - Review for clarity, completeness, feasibility, consistency
   - If FAIL (any HIGH issues): Go back to step 1 with feedback
   - If PASS: Continue to Gate 6

7. JUDGE SCORING (Gate 6):
   - Read .claude/prompts/judge_scoring.md
   - Score on 6 dimensions (including Missing-Checks Validation)
   - If FAIL (average <4.0 OR any dimension <3): Go back to step 1
   - If PASS: Continue to optional UI gate

8. UI & ACCESSIBILITY VALIDATION (Optional Gate - UI tasks only):
   - Read .claude/prompts/ui_validation_gates.md
   - Check design token compliance, accessibility (WCAG), component patterns
   - If FAIL: Go back to step 1 with UI issues
   - If PASS: Mark complete and exit

Continue loop until all gates pass OR 3 attempts exhausted.
Return final status with attempt count, gate failures, and scores.
```

### Key Points:
- **DO NOT** just spawn separate tasks for each gate
- **DO** run the complete Six-Gate conveyor within each Task subagent
- **ALWAYS** pass feedback from ALL failed gates back to regeneration
- **TRACK** the number of attempts and stop at 3 (align with Gold-Standard workflow)
- **GATES** must pass in sequence - failure at any gate triggers regeneration
- **UI GATE** only runs for UI-related tasks (auto-detect based on task content)

## Six-Gate Validation Criteria

### Gate 1: Schema Validation
- **PASS**: 100% valid structure, all required sections present, correct format
- **FAIL**: Missing sections, invalid task ID format, malformed headers

### Gate 2: Policy Validation  
- **PASS**: No violations of DO NOT IMPLEMENT list, compliant with CURRENT_STATE.md
- **FAIL**: References deprecated features, violates architecture decisions

### Gate 3: Lint Validation
- **PASS**: Zero critical issues, ≤2 high issues in code/config examples
- **FAIL**: Security vulnerabilities, syntax errors, major pattern violations

### Gate 4: Research Validation
- **PASS**: Research score ≥ 70, no CRITICAL issues, authoritative sources used
- **FAIL**: Outdated practices, unverified claims, or missing research

### Gate 5: CRITIC Review
- **PASS**: Zero HIGH severity issues across all quality dimensions
- **FAIL**: Any HIGH severity issue (placeholders, missing code, vague requirements)

### Gate 6: Judge Scoring
- **PASS**: Average ≥4.0 AND all dimensions ≥3 (including Missing-Checks)
- **FAIL**: Average <4.0 OR any dimension <3

### Optional Gate: UI & Accessibility (UI tasks only)
- **PASS**: No serious violations in design tokens, WCAG, component patterns
- **FAIL**: Hardcoded colors/spacing, accessibility violations, pattern deviations

## Supplementary Safeguards (Parallel Execution)

### These safeguards run in parallel with gate validation but don't block PRP generation:

#### 1. Local Pre-commit Bundle
- **Check**: Pre-commit hook configuration in PRP
- **Requirements**: ruff, mypy, pytest -m "not e2e" 
- **Purpose**: Prevent CI discovering issues that should be caught locally

#### 2. Security Guard
- **Check**: Security scanning requirements specified
- **Requirements**: Dependabot summaries, Trivy CVE scan, critical vuln blocking
- **Purpose**: Catch vulnerable dependencies early

#### 3. Performance Guard  
- **Check**: Performance regression prevention measures
- **Requirements**: Baseline benchmarks, budget gates, regression failure conditions
- **Purpose**: Prevent silent performance degradation

#### 4. Migration Sanity
- **Check**: Database migration safety procedures (DB tasks only)
- **Requirements**: Disposable Postgres test, upgrade→downgrade cycle
- **Purpose**: Ensure reversible database changes

#### 5. Style-token Lint
- **Check**: Design system enforcement (UI tasks only)  
- **Requirements**: Lint for hardcoded values, token compliance verification
- **Purpose**: Maintain design consistency

#### 6. Branch Protection & CI Requirements
- **Check**: GitHub repository protection configuration
- **Requirements**: Required status checks, review requirements, automated workflows
- **Purpose**: Enforce quality gates in repository workflow

## Super PRP Generation

### After All PRPs Pass Validation
Once all individual PRPs have passed validation:

1. **Clean up existing Super PRPs**:
   - Remove any existing Super PRP files (e.g., `PRPs/SUPER_PRP_*.md`)
   - Maintain only the latest version

2. **Generate new Super PRP**:
   ```
   Task: Generate Super PRP
   1. Read all validated PRPs from .claude/PRPs/PRP-*.md
   2. Create a consolidated document with:
      - Executive summary of all tasks
      - Table of contents with links
      - All individual PRPs in order (P0, P1, P2)
      - Cross-task dependencies mapped
      - Overall implementation roadmap
   3. Save to .claude/PRPs/SUPER_PRP_VALIDATED.md
   4. Include generation timestamp and validation scores
   ```

3. **Super PRP Structure**:
   ```markdown
   # Super PRP - All Validated Tasks
   Generated: [timestamp]
   Total Tasks: [count]
   Average Judge Score: [score]

   ## Executive Summary
   [Brief overview of all tasks]

   ## Table of Contents
   - [P0-014 - Strategic CI Test Re-enablement](#p0-014)
   - [P0-021 - Lead Explorer](#p0-021)
   ...

   ## Implementation Roadmap
   [Dependency graph and suggested order]

   ---

   # P0-014 - Strategic CI Test Re-enablement
   [Full PRP content]

   ---

   # P0-021 - Lead Explorer
   [Full PRP content]
   ```

## PRP Approval & Gold-Standard Stamping

### After Six-Gate Validation Success
Once a PRP clears all gates:
1. **Stamp as "Gold-Standard"** with validation metadata
2. **Queue for execution** with approved status
3. **Generate lineage hash** for audit trail
4. **Persist with approval timestamp** for governance

### Approval Metadata
```json
{
  "task_id": "P0-021",
  "status": "GOLD_STANDARD_APPROVED", 
  "validation_scores": {
    "schema": "PASS",
    "policy": "PASS", 
    "lint": "PASS",
    "research": 85,
    "critic": "PASS",
    "judge": 4.2,
    "ui_accessibility": "PASS"
  },
  "attempts": 2,
  "lineage_hash": "sha256:abc123...",
  "approved_at": "2025-01-15T10:30:00Z",
  "supplementary_checks": ["pre_commit", "security", "performance"]
}
```

## Automated Execution Integration

### Post-Approval Workflow
```
Gold PRP → Task Planner → Implementation Tasks → Commit Hooks → CI Gates → Release
```

### Integration Points
1. **Task Planner**: Break approved PRP into granular implementation tasks
2. **Developer/Agent Work**: Every commit runs local test/lint/security bundle
3. **GitHub Actions**: Reproduce all gates + full test suite + visual snapshots
4. **Automated Retry**: On CI failure, log-triage agent generates patch (max 3 attempts)
5. **Release Gate**: Build artifacts → security scan → staging deploy → smoke tests

## Continuous Lineage & Audit

### For Every Generated PRP
- **Triplet ID**: `{task_id}|{pipeline_run_id}|{template_version_id}` + build SHA
- **Raw Inputs**: Compressed and retained (≤2MB) for download
- **Gate History**: All validation attempts and feedback stored
- **Lineage Records**: Queryable via Lineage Panel UI (no edits allowed)

### Audit Trail
```json
{
  "prp_lineage": {
    "task_id": "P0-021",
    "pipeline_run": "run_20250115_103000",
    "template_version": "v2.1.0",
    "build_sha": "commit_abc123",
    "inputs_compressed": "path/to/inputs.gz",
    "gate_attempts": [
      {"attempt": 1, "failed_gates": ["schema", "policy"], "feedback": "..."},
      {"attempt": 2, "failed_gates": [], "status": "APPROVED"}
    ],
    "created_at": "2025-01-15T10:30:00Z"
  }
}
```

## Final Summary
After all tasks complete, report:
- Successfully generated PRPs (list with Gold-Standard stamps and scores)
- Failed PRPs after max attempts (list with final gate failures)
- Number of regeneration cycles per PRP
- Overall quality metrics (average gate passage rates and Judge scores)
- Super PRP generation status
- Lineage hashes for audit trail
- Supplementary safeguard compliance status

## File Locations
- Task definitions: `INITIAL.md`
- Progress tracking: `.claude/prp_progress.json`
- Prompt templates: `.claude/prompts/`
- Individual PRPs: `.claude/PRPs/PRP-{task_id}-{title-slug}.md`
- Super PRP: `.claude/PRPs/SUPER_PRP_VALIDATED.md`