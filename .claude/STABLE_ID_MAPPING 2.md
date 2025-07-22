# PRP Stable ID Mapping - LeadFactory Implementation

**Generated**: 2025-07-20  
**Strategy**: Separate ticket identity from priority using stable IDs + flexible priority prefixes  
**Total PRPs**: 57 (55 active after deprecating 2 duplicates)

## Architecture Overview

**Stable ID Format**: `PRP-NNNN` (PRP-1001 through PRP-1057)  
**Priority Prefix**: `P0/P1/P2/P3` based on MoSCoW framework  
**Benefits**: 
- Stable identity across priority changes
- Flexible priority management
- Clear separation of concerns
- Historical tracking preservation

## Complete Stable ID Mapping

### COMPLETED PRPs (32 total - 56% completion rate)

#### P0 Must-Have Completed (20 PRPs)
| Stable ID | Priority | Current ID | Title | Evidence |
|-----------|----------|------------|--------|----------|
| PRP-1001 | P0 | P0-001 | Fix D4 Coordinator | Merge/cache logic operational |
| PRP-1002 | P0 | P0-002 | Wire Prefect Full Pipeline | End-to-end orchestration |
| PRP-1003 | P0 | P0-003 | Dockerize CI | Docker test environment |
| PRP-1004 | P0 | P0-004 | Database Migrations Current | Schema aligned |
| PRP-1005 | P0 | P0-005 | Environment & Stub Wiring | Test/prod separation |
| PRP-1006 | P0 | P0-006 | Green KEEP Test Suite | Core tests passing |
| PRP-1007 | P0 | P0-007 | Health Endpoint | Production monitoring |
| PRP-1008 | P0 | P0-008 | Test Infrastructure Cleanup | Test discovery fixed |
| PRP-1009 | P0 | P0-009 | Remove Yelp Remnants | Yelp provider removed |
| PRP-1010 | P0 | P0-010 | Fix Missing Dependencies | Environments aligned |
| PRP-1011 | P0 | P0-011 | Deploy to VPS | Automated deployment |
| PRP-1012 | P0 | P0-012 | Postgres on VPS Container | Database container |
| PRP-1013 | P0 | P0-016 | Test Suite Stabilization | 88 tests passing |
| PRP-1014 | P0 | P0-020 | Design System Token Extraction | W3C compliant tokens |
| PRP-1015 | P0 | P0-021 | Lead Explorer | Full CRUD API + audit |
| PRP-1016 | P0 | P0-022 | Batch Report Runner | WebSocket progress + cost |
| PRP-1017 | P0 | P0-023 | Lineage Panel | API + DB + tests |
| PRP-1018 | P0 | P0-024 | Template Studio | GitHub integration + Monaco |
| PRP-1019 | P0 | P0-025 | Scoring Playground | Sheets integration + deltas |
| PRP-1020 | P0 | P0-026 | Governance | RBAC + audit trails |

#### P1 Should-Have Completed (8 PRPs)
| Stable ID | Priority | Current ID | Title | Evidence |
|-----------|----------|------------|--------|----------|
| PRP-1021 | P1 | P1-010 | SEMrush Client & Metrics | 6 key metrics implemented |
| PRP-1022 | P1 | P1-020 | Lighthouse headless audit | Browser-based testing |
| PRP-1023 | P1 | P1-030 | Visual Rubric analyzer | 1-9 scale scoring |
| PRP-1024 | P1 | P1-040 | LLM Heuristic audit | GPT-4 content analysis |
| PRP-1025 | P1 | P1-050 | Gateway cost ledger | External API cost tracking |
| PRP-1026 | P1 | P1-060 | Cost guardrails | Runaway cost prevention |
| PRP-1027 | P1 | P1-070 | DataAxle Client | Business data enrichment |
| PRP-1028 | P1 | P1-080 | Bucket enrichment flow | Industry segment processing |

#### P2 Could-Have Completed (3 PRPs)
| Stable ID | Priority | Current ID | Title | Evidence |
|-----------|----------|------------|--------|----------|
| PRP-1029 | P2 | P2-000 | Account Management Module | Account system operational |
| PRP-1030 | P2 | P2-010 | Unit Economics Views | Analytics API + DB views |
| PRP-1031 | P2 | P2-020 | Unit Economics PDF Section | Cost insights + visualizations |

#### P3 Won't-Have-Now Completed (1 PRP)
| Stable ID | Priority | Current ID | Title | Evidence |
|-----------|----------|------------|--------|----------|
| PRP-1032 | P3 | P3-003 | Fix Lead Explorer Audit Trail | Session listeners + SHA-256 |

### REMAINING PRPs (25 total - 44% to complete)

#### P0 Must-Have Remaining (8 PRPs)
| Stable ID | Priority | Current ID | Title | Status | Business Rationale |
|-----------|----------|------------|--------|--------|-------------------|
| PRP-1033 | P0 | P0-000 | Prerequisites Check | validated | Foundation dependency validation |
| PRP-1034 | P0 | P0-013 | CI/CD Pipeline Stabilization | validated | Deployment reliability critical |
| PRP-1035 | P0 | P0-014 | Test Suite Re-Enablement | validated | Quality assurance foundation |
| PRP-1036 | P0 | P0-015 | Test Coverage Enhancement to 80% | validated | Production readiness requirement |
| PRP-1037 | P0 | P0-027 | Global Navigation Shell | validated | Core UI framework for all components |
| PRP-1038 | P0 | P0-028 | Design-System UI Foundations | new | Design system foundation required |
| PRP-1039 | P0 | P3-001 | Fix RBAC for All API Endpoints | in_progress | **CRITICAL SECURITY VULNERABILITY** |
| PRP-1040 | P0 | P3-007 | Fix CI Docker Test Execution | validated | Blocking development workflow |

#### P1 Should-Have Remaining (6 PRPs)
| Stable ID | Priority | Current ID | Title | Status | Business Rationale |
|-----------|----------|------------|--------|--------|-------------------|
| PRP-1041 | P1 | P2-030 | Email Personalization V2 | in_progress | Key revenue driver, LLM-powered |
| PRP-1042 | P1 | P0-029 | Lead Explorer UI | new | Essential user interface (Wave D) |
| PRP-1043 | P1 | P0-030 | Lineage Panel UI | new | Important operational transparency |
| PRP-1044 | P1 | P0-031 | Batch Report Runner UI | new | Critical operational tool (Wave D) |
| PRP-1045 | P1 | P3-002 | Complete Lineage Integration | validated | System transparency and debugging |
| PRP-1046 | P1 | P3-005 | Complete Test Coverage | validated | Production confidence requirement |

#### P2 Could-Have Remaining (7 PRPs)
| Stable ID | Priority | Current ID | Title | Status | Business Rationale |
|-----------|----------|------------|--------|--------|-------------------|
| PRP-1047 | P2 | P2-040 | Dynamic Report Designer | validated | Advanced functionality enhancement |
| PRP-1048 | P2 | P2-050 | Report Performance Tuning | validated | Performance optimization |
| PRP-1049 | P2 | P2-060 | Full Text Search | validated | User experience enhancement |
| PRP-1050 | P2 | P2-080 | Advanced Filters | validated | Enhanced search capabilities |
| PRP-1051 | P2 | P2-090 | Lead Tracking | validated | Additional functionality |
| PRP-1052 | P2 | P0-032 | Template Studio Polish | new | Existing feature enhancement |
| PRP-1053 | P2 | P0-033 | Scoring Playground Integration | new | Integration improvement |

#### P3 Won't-Have-Now Remaining (4 PRPs)
| Stable ID | Priority | Current ID | Title | Status | Business Rationale |
|-----------|----------|------------|--------|--------|-------------------|
| PRP-1054 | P3 | P0-034 | Governance Console Polish | new | UI polish, lower priority |
| PRP-1055 | P3 | P3-006 | Replace Mock Integrations | validated | Technical debt cleanup |
| PRP-1056 | P3 | P2-070 | Lead Explorer UI | validated | **DUPLICATE** → Deprecate (superseded by PRP-1042) |
| PRP-1057 | P3 | P3-004 | Create Batch Runner UI | validated | **DUPLICATE** → Deprecate (superseded by PRP-1044) |

## Priority Distribution Analysis

| Priority | Count | Percentage | MoSCoW Alignment |
|----------|-------|------------|------------------|
| **P0 Must-Have** | 28 | 49% | ✅ Critical infrastructure + core functionality |
| **P1 Should-Have** | 14 | 25% | ✅ High-value features + essential UI |
| **P2 Could-Have** | 10 | 18% | ✅ Valuable enhancements + optimizations |
| **P3 Won't-Have-Now** | 5 | 9% | ✅ Polish + technical debt + duplicates |

**Total Active PRPs**: 55 (after deprecating 2 duplicates)

## Duplicate Deprecation Strategy

### PRPs to Deprecate
1. **PRP-1056 (P2-070)**: Lead Explorer UI → Superseded by PRP-1042 (P0-029)
2. **PRP-1057 (P3-004)**: Create Batch Runner UI → Superseded by PRP-1044 (P0-031)

**Rationale**: Wave D UI Consolidation (P0-028 through P0-034) represents the current UI strategy, making these older PRPs redundant.

## Implementation Benefits

### Before (Current System)
- Priority tied to ID (P0-001, P1-010, etc.)
- Priority changes require ID changes
- Difficult to track historical changes
- Priority distribution unclear

### After (Stable ID System)
- Stable identity (PRP-1001) separate from priority (P0)
- Priority changes don't affect ID
- Clear historical tracking
- Evidence-based MoSCoW distribution

## Migration Strategy

**Phase 1**: Generate mapping (✅ Complete)  
**Phase 2**: Update tracking systems  
**Phase 3**: Update documentation  
**Phase 4**: Implement new naming convention  

**Timeline**: 2 hours total execution

## References

- **Source Document**: `.claude/prp_tracking/prp_status.yaml`
- **Completion Evidence**: `COMPLETED.md`
- **Ground Truth Analysis**: `GROUND_TRUTH_ANALYSIS.md`
- **MoSCoW Framework**: Must/Should/Could/Won't Have prioritization

---

This mapping provides stable identities while enabling flexible priority management based on evolving business needs and technical requirements.