# Generate and Validate PRPs

Review INITIAL.md and identify all PRPs that need generation based on the new stable ID system v2.0. For each PRP with status "new" or "failed_validation", generate high-quality PRPs using an automated validation loop that regenerates based on feedback until validation passes.

## Usage
Arguments: $ARGUMENTS (optional stable IDs like "PRP-1058 PRP-1059", defaults to all pending)

## Process Overview

1. **Read INITIAL.md** to extract all PRP definitions using stable ID system v2.0
2. **Identify PRPs needing generation** based on status in INITIAL.md:
   - Status "new": Never had a PRP generated
   - Status "failed_validation": Previous PRP failed validation and needs regeneration
   - Status "validated": Skip - PRP already validated
   - Status "in_progress": Skip - PRP implementation in progress  
   - Status "complete": Skip - PRP fully implemented
3. **Check .claude/PRPs/** to see which PRPs already exist (using stable IDs)
4. **Load previous validation feedback** from PRP_VALIDATION_REPORT.md if it exists
5. **Filter by arguments** if provided (e.g., only process PRP-1058 if specified)
6. **Run validation loops** for each PRP (NOT just spawn subagents)
7. **Update INITIAL.md status** after each PRP validation:
   - Success: Update status from "new" → "validated"
   - Failure: Update status to "failed_validation" with failure reason
8. **Generate Super PRP** after all individual PRPs pass validation

### Handling New PRPs
For PRPs found in INITIAL.md with status "new":
- Generate detailed PRPs using stable ID format
- Include them in validation queue
- Example: PRP-1058, PRP-1059, PRP-1060, PRP-1061 recently added for queue infrastructure

## Research Task for Context Gathering

### Research Agent (Run BEFORE PRP Generation)
For each PRP, spawn a research Task subagent to gather authoritative context:

```
Task: Research context for {stable_id} - {title}
1. Read the prompt from .claude/prompts/research_context.md
2. Replace placeholders: {stable_id}, {title}, {dependencies}, {goal}
3. Focus research on the TECHNICAL ASPECTS of the PRP:
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
6. Save to .claude/research_cache/research_{stable_id}.txt
7. Return key insights and relevant URLs
```

## Previous Validation Feedback Integration

### For PRPs with Failed Validation
If a PRP has status "failed_validation" in INITIAL.md:
1. **Load validation report** from PRP_VALIDATION_REPORT.md
2. **Extract specific gaps** for this stable ID
3. **Pass ALL gaps as initial feedback** to the regeneration prompt
4. **Start at regeneration step** (not fresh generation)

Example feedback to include:
```yaml
Previous validation gaps for {stable_id}:
- Missing property-based test for cache key collisions
- Test coverage at 72.07% (below 80% threshold)
- No dedicated unit tests for merge_enrichment_data
- Documentation not updated
- Performance test missing
```

## Six-Gate Validation Conveyor Implementation

### IMPORTANT: Each PRP Must Run Complete Six-Gate Validation
For each PRP that needs generation, spawn a Task subagent that runs the ENTIRE six-gate validation conveyor:

```
Task: Complete Six-Gate validation for {stable_id} - {title}

INITIAL RESEARCH (first time only):
0. RESEARCH CONTEXT:
   - Read .claude/prompts/research_context.md
   - Search for authoritative sources and recent discussions
   - Save findings to .claude/research_cache/research_{stable_id}.txt
   - Include research context in PRP generation

SIX-GATE VALIDATION CONVEYOR (repeat up to 3 times):
1. REGENERATE (or generate if first attempt):
   - Read .claude/prompts/regenerate_prp.md (or generate_prp.md for first attempt)
   - Include research context from .claude/research_cache/research_{stable_id}.txt
   - If PRP has "failed_validation" status, INCLUDE PREVIOUS VALIDATION GAPS:
     * Load specific gaps from PRP_VALIDATION_REPORT.md for this stable_id
     * Pass ALL previous gaps as {previous_validation_gaps}
   - If regenerating, include ALL feedback from failed gates:
     * {schema_issues}: Structure and format violations
     * {policy_issues}: DO NOT IMPLEMENT violations and architecture conflicts
     * {lint_issues}: Code style, security, and pattern violations
     * {research_issues}: Missing authoritative sources and outdated practices
     * {critic_issues}: Quality and completeness issues
     * {judge_feedback}: Dimension scores and improvement areas
     * {ui_issues}: Design token, accessibility, and pattern violations (if UI task)
     * {previous_validation_gaps}: Gaps from PRP_VALIDATION_REPORT.md (if exists)
   - Generate/regenerate the PRP addressing all feedback
   - Save to .claude/PRPs/PRP-{stable_id}-{title-slug}.md

2. SCHEMA VALIDATION (Gate 1):
   - Read .claude/prompts/schema_validation.md
   - Validate PRP structure, format, and required sections
   - Check stable ID format, mandatory fields, content structure
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
- **FAIL**: Missing sections, invalid stable ID format, malformed headers

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

### Optional Gate: UI & Accessibility (UI PRPs only)
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
- **Check**: Design system enforcement (UI PRPs only)  
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
   1. Read all validated PRPs from .claude/PRPs/PRP-*.md using stable IDs
   2. Create a consolidated document with:
      - Executive summary of all PRPs
      - Table of contents with stable ID links
      - All individual PRPs in priority order (P0, P1, P2, P3)
      - Cross-PRP dependencies mapped using stable IDs
      - Overall implementation roadmap
   3. Save to .claude/PRPs/SUPER_PRP_VALIDATED.md
   4. Include generation timestamp and validation scores
   ```

3. **Super PRP Structure**:
   ```markdown
   # Super PRP - All Validated PRPs (Stable ID System v2.0)
   Generated: [timestamp]
   Total PRPs: [count]
   Average Judge Score: [score]

   ## Executive Summary
   [Brief overview of all PRPs]

   ## Table of Contents
   - [PRP-1035 - Test Suite Re-Enablement](#prp-1035)
   - [PRP-1042 - Lead Explorer UI](#prp-1042)
   - [PRP-1058 - Redis Queue Broker](#prp-1058)
   ...

   ## Implementation Roadmap
   [Dependency graph and suggested order using stable IDs]

   ---

   # PRP-1035 - Test Suite Re-Enablement and Coverage Plan
   [Full PRP content]

   ---

   # PRP-1042 - Lead Explorer UI
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
  "stable_id": "PRP-1042",
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
- **Triplet ID**: `{stable_id}|{pipeline_run_id}|{template_version_id}` + build SHA
- **Raw Inputs**: Compressed and retained (≤2MB) for download
- **Gate History**: All validation attempts and feedback stored
- **Lineage Records**: Queryable via Lineage Panel UI (no edits allowed)

### Audit Trail
```json
{
  "prp_lineage": {
    "stable_id": "PRP-1042",
    "pipeline_run": "run_20250721_103000",
    "template_version": "v2.1.0",
    "build_sha": "commit_abc123",
    "inputs_compressed": "path/to/inputs.gz",
    "gate_attempts": [
      {"attempt": 1, "failed_gates": ["schema", "policy"], "feedback": "..."},
      {"attempt": 2, "failed_gates": [], "status": "APPROVED"}
    ],
    "created_at": "2025-07-21T10:30:00Z"
  }
}
```

## Final Summary
After all PRPs complete, report:
- Successfully generated PRPs (list with Gold-Standard stamps and scores)
- Failed PRPs after max attempts (list with final gate failures)
- Number of regeneration cycles per PRP
- Overall quality metrics (average gate passage rates and Judge scores)
- Super PRP generation status
- Lineage hashes for audit trail
- Supplementary safeguard compliance status

## File Locations
- PRP definitions: `INITIAL.md` (stable ID system v2.0)
- Prompt templates: `.claude/prompts/`
- Individual PRPs: `.claude/PRPs/PRP-{stable_id}-{title-slug}.md`
- Super PRP: `.claude/PRPs/SUPER_PRP_VALIDATED.md`
- Previous validation report: `PRP_VALIDATION_REPORT.md`
- Research cache: `.claude/research_cache/research_{stable_id}.txt`