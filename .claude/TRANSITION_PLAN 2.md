# 2-Hour PRP Naming Strategy Transition Plan

**Generated**: 2025-07-20  
**Strategy**: Implement stable ID + flexible priority architecture  
**Total Effort**: 2 hours  
**Immediate Benefits**: Stable tracking, flexible priority management, duplicate elimination

## Executive Summary

**Objective**: Transition from priority-tied IDs (P0-001) to stable IDs with flexible priorities (PRP-1001 + P0)

**Key Changes**:
- 57 PRPs → 55 active PRPs (deprecate 2 duplicates)
- Stable IDs: PRP-1001 through PRP-1057
- MoSCoW priorities: P0 (49%) | P1 (25%) | P2 (18%) | P3 (9%)
- Evidence-based priority distribution

**Risk Level**: LOW (tracking system changes only, no code impact)

## Phase 1: Preparation (15 minutes)

### 1.1 Backup Current State
```bash
# Create backup of current tracking systems
cp .claude/prp_tracking/prp_status.yaml .claude/prp_tracking/prp_status.yaml.backup
cp COMPLETED.md COMPLETED.md.backup
cp INITIAL.md INITIAL.md.backup

# Create Redis backup
redis-cli --scan --pattern "prp:*" | xargs redis-cli del > /tmp/redis_prp_backup.txt
```

### 1.2 Validate Mapping Completeness
```bash
# Verify stable mapping covers all PRPs
echo "Validating mapping completeness..."
grep -c "PRP-" .claude/STABLE_ID_MAPPING.md  # Should be 57
grep -c "P[0-3]-" .claude/prp_tracking/prp_status.yaml  # Should be 57
```

### 1.3 Create Migration Scripts
**Location**: `.claude/migration/`
- `migrate_yaml.py` - Update prp_status.yaml
- `migrate_redis.py` - Update Redis keys
- `migrate_docs.py` - Update documentation
- `validate_migration.py` - Verify migration success

**Deliverable**: ✅ Ready to execute migration

## Phase 2: System Migration (75 minutes)

### 2.1 Update PRP Tracking YAML (20 minutes)

**File**: `.claude/prp_tracking/prp_status.yaml`

**Changes Required**:
1. Add `stable_id` field to each PRP entry
2. Add `corrected_priority` field
3. Update metadata with new schema version
4. Mark duplicates as deprecated

**Script**: `migrate_yaml.py`
```python
# Key transformations:
# P0-001 → stable_id: PRP-1001, corrected_priority: P0
# P2-070 → deprecated: true, superseded_by: PRP-1042
# P3-004 → deprecated: true, superseded_by: PRP-1044

# Update stats section with corrected priority distribution
```

**Validation**:
- All 57 PRPs have stable_id
- Priority distribution: 28 P0, 14 P1, 10 P2, 5 P3
- 2 PRPs marked as deprecated

### 2.2 Update Redis Coordination System (15 minutes)

**Changes Required**:
1. Add stable ID keys: `prp:stable:PRP-1001`
2. Maintain backward compatibility: `prp:P0-001` → `prp:stable:PRP-1001`
3. Update priority-based queries
4. Add deprecation markers

**Script**: `migrate_redis.py`
```python
# Key mapping strategy:
# OLD: prp:P0-001:status = "complete"
# NEW: prp:stable:PRP-1001:status = "complete"
#      prp:stable:PRP-1001:priority = "P0"
#      prp:stable:PRP-1001:legacy_id = "P0-001"

# Maintain backward compatibility for 1 week
```

### 2.3 Update Documentation (25 minutes)

**Files to Update**:
1. `COMPLETED.md` - Add stable IDs, reorganize by priority
2. `INITIAL.md` - Update with new priority structure
3. `GROUND_TRUTH_ANALYSIS.md` - Add stable ID references
4. `.claude/PRPs/*.md` - Add stable ID headers

**Key Changes**:
- All PRP references include both stable ID and priority
- Priority-based organization with clear rationale
- Deprecated PRPs clearly marked
- Cross-references updated

### 2.4 Deprecate Duplicate PRPs (15 minutes)

**PRPs to Deprecate**:
1. **P2-070 (PRP-1056)**: Lead Explorer UI
   - Mark as deprecated
   - Reference superseding PRP-1042 (P0-029)
   - Maintain file with deprecation notice

2. **P3-004 (PRP-1057)**: Create Batch Runner UI
   - Mark as deprecated  
   - Reference superseding PRP-1044 (P0-031)
   - Maintain file with deprecation notice

**Process**:
- Add deprecation headers to PRP files
- Update tracking systems
- Create redirect documentation

**Deliverable**: ✅ All systems updated with stable IDs

## Phase 3: Validation & Testing (25 minutes)

### 3.1 Mapping Validation (10 minutes)
```bash
# Run validation script
python .claude/migration/validate_migration.py

# Key validations:
# - All 57 PRPs have stable IDs
# - No missing mappings
# - Priority distribution correct
# - Backward compatibility maintained
# - Deprecation properly marked
```

### 3.2 System Integration Testing (10 minutes)
```bash
# Test Redis queries with new structure
redis-cli get "prp:stable:PRP-1001:status"  # Should return "complete"
redis-cli get "prp:stable:PRP-1039:priority"  # Should return "P0"

# Test YAML access
python -c "import yaml; data = yaml.safe_load(open('.claude/prp_tracking/prp_status.yaml')); print(data['prp_tracking']['P3-001']['stable_id'])"  # Should return PRP-1039

# Test documentation references
grep -c "PRP-" COMPLETED.md  # Should be >32
```

### 3.3 Priority Distribution Verification (5 minutes)
```bash
# Verify MoSCoW distribution
python -c "
import yaml
data = yaml.safe_load(open('.claude/prp_tracking/prp_status.yaml'))
priorities = {}
for prp in data['prp_tracking'].values():
    if not prp.get('deprecated', False):
        priority = prp.get('corrected_priority', 'unknown')
        priorities[priority] = priorities.get(priority, 0) + 1
print('Priority Distribution:', priorities)
# Expected: {'P0': 28, 'P1': 14, 'P2': 10, 'P3': 3}  # 55 active PRPs
"
```

**Deliverable**: ✅ Migration validated and working

## Phase 4: Documentation & Handoff (5 minutes)

### 4.1 Create Migration Summary
**File**: `.claude/MIGRATION_COMPLETE.md`

**Contents**:
- Migration timestamp
- Changes summary
- Validation results  
- Rollback procedure
- New usage patterns

### 4.2 Update Usage Instructions

**New Patterns**:
```yaml
# Reference PRPs by stable ID:
stable_id: PRP-1001
current_priority: P0
legacy_id: P0-001

# Query by priority:
GET /prps?priority=P0&status=complete

# Query by stable ID:
GET /prps/PRP-1001
```

**Deliverable**: ✅ Complete documentation

## Risk Mitigation

### Low Risk Items
- ✅ **Tracking system changes only** (no code modifications)
- ✅ **Backward compatibility maintained** (1-week transition period)
- ✅ **Complete backups created** before migration
- ✅ **Validation scripts ready** for immediate verification

### Rollback Strategy (if needed)
```bash
# Complete rollback (5 minutes)
cp .claude/prp_tracking/prp_status.yaml.backup .claude/prp_tracking/prp_status.yaml
cp COMPLETED.md.backup COMPLETED.md  
cp INITIAL.md.backup INITIAL.md
redis-cli flushall  # Reset Redis (acceptable for development)
```

### Success Criteria
- [ ] All 57 PRPs have stable IDs
- [ ] Priority distribution: 28 P0, 14 P1, 10 P2, 5 P3 (55 active)
- [ ] 2 duplicates properly deprecated
- [ ] Backward compatibility functional
- [ ] Documentation updated and consistent
- [ ] Redis coordination system working
- [ ] Validation scripts pass 100%

## Timeline Breakdown

| Phase | Duration | Activity | Deliverable |
|-------|----------|----------|-------------|
| **Phase 1** | 15 min | Preparation & Backup | ✅ Ready to migrate |
| **Phase 2** | 75 min | System Migration | ✅ All systems updated |
| **Phase 3** | 25 min | Validation & Testing | ✅ Migration validated |
| **Phase 4** | 5 min | Documentation & Handoff | ✅ Complete documentation |
| **Total** | **120 min** | **Complete Transition** | **✅ Stable ID system active** |

## Immediate Benefits Post-Migration

1. **Stable Identity**: PRPs keep same ID regardless of priority changes
2. **Flexible Priority**: Evidence-based MoSCoW distribution
3. **Duplicate Elimination**: 57 → 55 active PRPs (cleaner tracking)
4. **Better Organization**: Priority-based grouping with business rationale
5. **Historical Tracking**: Clear audit trail of priority changes
6. **Reduced Confusion**: Separate identity from priority management

## Long-term Benefits

1. **Scalable Architecture**: Easy to add new PRPs without ID conflicts
2. **Priority Evolution**: Priorities can change based on business needs
3. **Clear Governance**: MoSCoW framework provides decision criteria
4. **Improved Planning**: Better visibility into work distribution
5. **Stakeholder Communication**: Clear priority explanations

---

**Migration Ready**: All preparation complete, execution can begin immediately.  
**Risk Level**: LOW - No code changes, full rollback capability maintained.  
**Success Probability**: HIGH - Well-defined process with comprehensive validation.