# Remaining PRPs - LeadFactory Implementation (Stable ID System)

**Last Updated**: 2025-07-21  
**Remaining Work**: 27 active PRPs (49% to complete)  
**System Version**: Stable ID v2.0

This document contains all Project Requirement Plans (PRPs) that remain to be completed using the new stable ID system with MoSCoW-based priority classification.

## Priority Distribution Summary

| Priority | Count | Percentage | Description |
|----------|-------|------------|-------------|
| **P0 Must-Have** | 12 remaining | 44% of remaining | Critical infrastructure, security, UI framework |
| **P1 Should-Have** | 6 remaining | 22% of remaining | Essential UI interfaces + key features |
| **P2 Could-Have** | 7 remaining | 26% of remaining | Valuable enhancements + optimizations |
| **P3 Won't-Have-Now** | 2 remaining | 8% of remaining | Technical debt + lower priority items |

## P0 Must-Have Remaining (12 PRPs)

**Business Impact**: CRITICAL - These PRPs block subsequent development and production deployment

### Foundation & Infrastructure

#### 🔄 PRP-1033 (P0-000): Prerequisites Check
**Stable ID**: PRP-1033 | **Priority**: P0 | **Status**: validated  
**Legacy ID**: P0-000 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Foundation dependency validation required for all subsequent work  
**Blocking**: All other PRPs depend on validated prerequisites

#### 🔄 PRP-1034 (P0-013): CI/CD Pipeline Stabilization  
**Stable ID**: PRP-1034 | **Priority**: P0 | **Status**: validated  
**Legacy ID**: P0-013 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Deployment reliability critical for production readiness  
**Blocking**: Automated deployment and quality gates

#### 🔄 PRP-1035 (P0-014): Test Suite Re-Enablement and Coverage Plan
**Stable ID**: PRP-1035 | **Priority**: P0 | **Status**: validated  
**Legacy ID**: P0-014 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Quality assurance foundation for production confidence  
**Blocking**: Comprehensive testing strategy implementation

#### 🔄 PRP-1036 (P0-015): Test Coverage Enhancement to 80%
**Stable ID**: PRP-1036 | **Priority**: P0 | **Status**: validated  
**Legacy ID**: P0-015 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Production readiness requirement for enterprise deployment  
**Blocking**: Automated coverage enforcement and quality gates

### UI Framework Foundation

#### 🔄 PRP-1037 (P0-027): Global Navigation Shell
**Stable ID**: PRP-1037 | **Priority**: P0 | **Status**: validated  
**Legacy ID**: P0-027 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Core UI framework required for all component integration  
**Blocking**: All UI components depend on navigation shell

#### 🔄 PRP-1038 (P0-028): Design-System UI Foundations
**Stable ID**: PRP-1038 | **Priority**: P0 | **Status**: validated  
**Legacy ID**: P0-028 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Design system foundation enables consistent UI development  
**Blocking**: Wave D UI Consolidation - all component development

### Critical Security & Infrastructure

#### 🚨 PRP-1039 (P3-001): Fix RBAC for All API Endpoints
**Stable ID**: PRP-1039 | **Priority**: P0 | **Status**: in_progress  
**Legacy ID**: P3-001 | **Migrated**: 2025-07-20T21:08:12Z  
**⚠️ CRITICAL SECURITY VULNERABILITY** - Original P3 priority was incorrect  
**Business Rationale**: Security vulnerability blocks production deployment  
**Blocking**: All API endpoints must have proper authorization

#### 🔄 PRP-1040 (P3-007): Fix CI Docker Test Execution
**Stable ID**: PRP-1040 | **Priority**: P0 | **Status**: validated  
**Legacy ID**: P3-007 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Blocking development workflow - prevents reliable testing  
**Blocking**: Docker-based CI pipeline execution

#### 🔄 PRP-1058 (P0-100): Redis Queue Broker
**Stable ID**: PRP-1058 | **Priority**: P0 | **Status**: validated  
**Legacy ID**: P0-100 | **Migrated**: 2025-07-21T10:15:00Z  
**Business Rationale**: Replace tmux keystroke routing with reliable Redis list bus using BRPOPLPUSH to prevent PRP loss/duplication on crashes  
**Blocking**: Reliable queue infrastructure for all PRP processing workflows  
**Implementation**: 
- New Code: `infra/redis_queue.py` using AWS Agent-Squad pattern
- Queues: `dev_queue`, `validation_queue`, `integration_queue` plus `:inflight` mirrors
- Worker: Replace tmux send-keys with `redis-cli BRPOPLPUSH dev_queue dev_queue:inflight 0`
- Tests: Unit tests for enqueue/dequeue/requeue, integration crash simulation, 10K ops <500ms
- Evidence: PRP hash must contain queue_name, timestamp, retry_count
- Citations: [Redis BRPOPLPUSH docs](https://redis.io/commands/brpoplpush/), [Stack Overflow reliable queue pattern](https://stackoverflow.com/questions/tagged/redis+queue)

#### 🔄 PRP-1059 (P0-101): Lua Promotion Script
**Stable ID**: PRP-1059 | **Priority**: P0 | **Status**: validated  
**Legacy ID**: P0-101 | **Migrated**: 2025-07-21T10:15:00Z  
**Business Rationale**: Atomic Redis Lua referee for queue promotion with evidence validation  
**Dependencies**: PRP-1058 (Redis Queue Broker)  
**Blocking**: Reliable PRP state transitions with evidence enforcement  
**Implementation**:
- Script: `redis/promote.lua` with SHA cached at boot
- Evidence Schema: `cfg:evidence_schema` hash defining required keys per transition
- Worker Call: `redis-cli EVALSHA $PROMOTE_SHA 2 prp:$ID $CUR_QUEUE`
- Performance: ≤50µs per call @ 1K RPS
- Tests: Unit tests with register_script, PROMOTE_FAILED validation
- Citations: [Redis EVAL guide](https://redis.io/commands/eval/), [Lua atomicity guarantees](https://redis.io/docs/manual/programmability/)

#### 🔄 PRP-1060 (P0-102): Acceptance + Deploy Runner Persona
**Stable ID**: PRP-1060 | **Priority**: P0 | **Status**: validated  
**Legacy ID**: P0-102 | **Migrated**: 2025-07-21T10:15:00Z  
**Business Rationale**: Containerized end-to-end runner for branch merge, acceptance testing, and SSH deployment  
**Dependencies**: PRP-1059 (Lua Promotion Script)  
**Blocking**: Automated deployment pipeline with evidence validation  
**Implementation**:
- Profile: `profiles/acceptance.yaml` (invoked with `/acceptance`)
- Container: `ghcr.io/leadfactory/acceptance-runner:latest`
- SSH: Uses .env DEPLOY_HOST, DEPLOY_USER, DEPLOY_KEY_PATH
- VPS Script: `~/bin/deploy.sh` (docker pull, compose up, health-check)
- Evidence: Sets `acceptance_passed=true` and `deploy_ok=true`
- Performance: <3min for p95 PRP completion
- Citations: [GHCR documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry), [SSH forced-command](https://man.openbsd.org/sshd_config#command)

#### 🔄 PRP-1061 (P0-103): Coverage / Lint Bot
**Stable ID**: PRP-1061 | **Priority**: P0 | **Status**: validated  
**Legacy ID**: P0-103 | **Migrated**: 2025-07-21T10:15:00Z  
**Business Rationale**: Block low-quality changes at dev_queue with Ruff linting and 80%+ coverage enforcement  
**Dependencies**: PRP-1059 (Lua Promotion Script)  
**Blocking**: Quality gates for all development workflow  
**Implementation**:
- Profile: `profiles/lint.yaml` (invoked via `/refactor --mode=lint`)
- Linting: Ruff errors E501, F401, PD* with zero tolerance
- Coverage: pytest-cov with `--cov-fail-under 80`
- Evidence: Sets `lint_clean=true`, `coverage_pct` (integer)
- Artifacts: Generates `coverage_badge.svg`
- Tests: Unit tests for both lint and coverage enforcement
- Citations: [Ruff documentation](https://github.com/astral-sh/ruff), [pytest-cov docs](https://pytest-cov.readthedocs.io/)

## P1 Should-Have Remaining (6 PRPs)

**Business Impact**: HIGH VALUE - Essential user interfaces and key revenue features

### Revenue-Critical Features

#### 🔄 PRP-1041 (P2-030): Email Personalization V2
**Stable ID**: PRP-1041 | **Priority**: P1 | **Status**: in_progress  
**Legacy ID**: P2-030 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Key revenue driver - LLM-powered personalization increases conversion  
**Impact**: Direct revenue impact through improved email performance

### Essential User Interfaces (Wave D UI Consolidation)

#### 🔄 PRP-1042 (P0-029): Lead Explorer UI
**Stable ID**: PRP-1042 | **Priority**: P1 | **Status**: validated  
**Legacy ID**: P0-029 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Essential user interface for core lead management functionality  
**Dependencies**: PRP-1037 (Navigation Shell), PRP-1038 (Design System)  
**Supersedes**: PRP-1050 (P2-070 deprecated duplicate)

#### 🔄 PRP-1043 (P0-030): Lineage Panel UI
**Stable ID**: PRP-1043 | **Priority**: P1 | **Status**: validated  
**Legacy ID**: P0-030 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Important operational transparency for debugging and compliance  
**Dependencies**: PRP-1037 (Navigation Shell), PRP-1017 (Lineage Panel API)

#### 🔄 PRP-1044 (P0-031): Batch Report Runner UI
**Stable ID**: PRP-1044 | **Priority**: P1 | **Status**: validated  
**Legacy ID**: P0-031 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Critical operational tool for batch processing management  
**Dependencies**: PRP-1037 (Navigation Shell), PRP-1016 (Batch Runner API)  
**Supersedes**: PRP-1056 (P3-004 deprecated duplicate)

### System Integration

#### 🔄 PRP-1045 (P3-002): Complete Lineage Integration
**Stable ID**: PRP-1045 | **Priority**: P1 | **Status**: validated  
**Legacy ID**: P3-002 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Important for system transparency and debugging capabilities  
**Dependencies**: PRP-1017 (Lineage Panel)

#### 🔄 PRP-1046 (P3-005): Complete Test Coverage
**Stable ID**: PRP-1046 | **Priority**: P1 | **Status**: validated  
**Legacy ID**: P3-005 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Production confidence requirement for enterprise deployment  
**Dependencies**: PRP-1035 (Test Re-Enablement), PRP-1036 (80% Coverage)

## P2 Could-Have Remaining (7 PRPs)

**Business Impact**: VALUABLE - Enhancements that improve user experience and system performance

### Advanced Functionality

#### 🔄 PRP-1047 (P2-040): Dynamic Report Designer
**Stable ID**: PRP-1047 | **Priority**: P2 | **Status**: validated  
**Legacy ID**: P2-040 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Advanced functionality enhancement for report customization

#### 🔄 PRP-1048 (P2-050): Report Performance Tuning
**Stable ID**: PRP-1048 | **Priority**: P2 | **Status**: validated  
**Legacy ID**: P2-050 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Performance optimization for large-scale report generation

#### 🔄 PRP-1049 (P2-060): Full Text Search
**Stable ID**: PRP-1049 | **Priority**: P2 | **Status**: validated  
**Legacy ID**: P2-060 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: User experience enhancement for lead discovery

#### 🔄 PRP-1051 (P2-080): Advanced Filters
**Stable ID**: PRP-1051 | **Priority**: P2 | **Status**: validated  
**Legacy ID**: P2-080 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Enhanced search capabilities for lead segmentation

#### 🔄 PRP-1052 (P2-090): Lead Tracking
**Stable ID**: PRP-1052 | **Priority**: P2 | **Status**: validated  
**Legacy ID**: P2-090 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Additional functionality for lead lifecycle management

### UI Polish & Enhancement

#### 🔄 PRP-1053 (P0-032): Template Studio Polish
**Stable ID**: PRP-1053 | **Priority**: P2 | **Status**: validated  
**Legacy ID**: P0-032 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Enhancement to existing template management feature  
**Dependencies**: PRP-1018 (Template Studio)

#### 🔄 PRP-1054 (P0-033): Scoring Playground Integration
**Stable ID**: PRP-1054 | **Priority**: P2 | **Status**: validated  
**Legacy ID**: P0-033 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Integration improvement for scoring system workflow  
**Dependencies**: PRP-1019 (Scoring Playground)

## P3 Won't-Have-Now Remaining (2 active PRPs)

**Business Impact**: DEFERRED - Lower priority items that can be addressed in future phases

### Lower Priority Polish

#### 🔄 PRP-1055 (P0-034): Governance Console Polish
**Stable ID**: PRP-1055 | **Priority**: P3 | **Status**: validated  
**Legacy ID**: P0-034 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: UI polish with lower business impact  
**Dependencies**: PRP-1020 (Governance)

#### 🔄 PRP-1057 (P3-006): Replace Mock Integrations
**Stable ID**: PRP-1057 | **Priority**: P3 | **Status**: validated  
**Legacy ID**: P3-006 | **Migrated**: 2025-07-20T21:08:12Z  
**Business Rationale**: Technical debt cleanup - non-blocking for production

## Deprecated PRPs (2 duplicates)

### ❌ Superseded by Wave D UI Consolidation

#### ❌ PRP-1050 (P2-070): Lead Explorer UI **[DEPRECATED]**
**Stable ID**: PRP-1050 | **Priority**: P2 | **Status**: deprecated  
**Legacy ID**: P2-070 | **Superseded By**: PRP-1042 (P0-029)  
**Reason**: Superseded by Wave D UI Consolidation strategy

#### ❌ PRP-1056 (P3-004): Create Batch Runner UI **[DEPRECATED]**
**Stable ID**: PRP-1056 | **Priority**: P3 | **Status**: deprecated  
**Legacy ID**: P3-004 | **Superseded By**: PRP-1044 (P0-031)  
**Reason**: Superseded by Wave D UI Consolidation strategy

## Critical Path Analysis

### Immediate Blockers (Must Complete First)
1. **PRP-1039** - Fix RBAC (CRITICAL SECURITY) 🚨
2. **PRP-1033** - Prerequisites Check (Foundation)
3. **PRP-1034** - CI/CD Stabilization (Deployment)
4. **PRP-1040** - Fix CI Docker Tests (Development workflow)

### Queue Infrastructure Phase (Enables Reliable Workflows)
5. **PRP-1058** - Redis Queue Broker (Foundation)
6. **PRP-1059** - Lua Promotion Script (Evidence validation)
7. **PRP-1060** - Acceptance + Deploy Runner (Automated deployment)
8. **PRP-1061** - Coverage / Lint Bot (Quality gates)

### Foundation Phase (Enables Wave D)
9. **PRP-1035** - Test Suite Re-Enablement 
10. **PRP-1036** - Test Coverage 80%
11. **PRP-1037** - Global Navigation Shell
12. **PRP-1038** - Design System Foundations

### Feature Development Phase
13. **PRP-1041** - Email Personalization V2 (Revenue impact)
14. **PRP-1042-1044** - Essential UI Components
15. **PRP-1045-1046** - System Integration & Testing

### Enhancement Phase
16. **P2 PRPs** - Advanced functionality and optimizations
17. **P3 PRPs** - Polish and technical debt

## Dependencies Matrix

| PRP | Depends On | Enables |
|-----|------------|---------|
| PRP-1059 | PRP-1058 | Reliable queue promotion |
| PRP-1060 | PRP-1059 | Automated deployment pipeline |
| PRP-1061 | PRP-1059 | Quality gate enforcement |
| PRP-1037 | PRP-1038 | PRP-1042, PRP-1043, PRP-1044 |
| PRP-1038 | PRP-1033 | All Wave D UI components |
| PRP-1042 | PRP-1037, PRP-1015 | Complete lead management UI |
| PRP-1043 | PRP-1037, PRP-1017 | Operational transparency |
| PRP-1044 | PRP-1037, PRP-1016 | Batch processing UI |
| PRP-1045 | PRP-1017 | Enhanced system integration |
| PRP-1046 | PRP-1035, PRP-1036 | Production confidence |

## Success Metrics

### P0 Must-Have Completion Targets
- **Security**: All API endpoints protected (PRP-1039)
- **Foundation**: CI/CD pipeline stable with 80% test coverage
- **Queue Infrastructure**: Redis-based reliable PRP processing with evidence validation
- **Quality Gates**: Automated lint/coverage enforcement blocking low-quality changes
- **Deployment**: Containerized acceptance testing with SSH deployment automation
- **UI Framework**: Navigation shell and design system operational
- **Quality**: All P0 items pass automated validation

### P1 Should-Have Success Criteria
- **Revenue**: Email personalization improves conversion by >15%
- **User Experience**: All essential UI components operational
- **Integration**: Complete system transparency and monitoring

### P2-P3 Value Delivery
- **Performance**: Report generation optimized for enterprise scale
- **Usability**: Advanced search and filtering capabilities
- **Maintenance**: Technical debt reduced, mock integrations replaced

## Migration Benefits Applied

**New Advantages**:
- **Stable Identity**: PRPs maintain consistent tracking across priority changes
- **Flexible Priority**: Evidence-based MoSCoW classification corrects original priorities
- **Clear Governance**: Transparent business rationale for all priority decisions
- **Duplicate Elimination**: 57 → 55 active PRPs improves tracking accuracy

**Priority Corrections Made**:
- P3-001 → P0 (Critical security vulnerability)
- P3-007 → P0 (Blocking development workflow)
- P2-030 → P1 (Key revenue driver)
- P0-029-031 → P1 (Essential UI, not infrastructure)
- P0-032-033 → P2 (Polish, not foundation)
- P0-034 → P3 (Lower priority polish)

---

**Total Remaining**: 27 active PRPs (49% of total work)  
**Critical Path**: 12 P0 Must-Have items must complete before Wave D UI development  
**Next Priority**: PRP-1039 (Fix RBAC) - CRITICAL SECURITY issue blocking production