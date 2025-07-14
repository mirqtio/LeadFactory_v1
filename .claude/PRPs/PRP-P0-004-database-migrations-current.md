# PRP: Database Migrations Current

## Task ID: P0-004
## Wave: A

## Business Logic (Why This Matters)
Schema drift breaks runtime and Alembic autogenerate. When database models and actual schema diverge, the application fails at runtime with SQLAlchemy errors. Alembic's autogenerate feature becomes unreliable, potentially generating harmful migrations that drop columns or tables. This leads to data loss in production and blocks deployment pipelines.

## Overview
Ensure database schema matches SQLAlchemy models by fixing model imports, creating comprehensive migration tests, and establishing a validation framework that prevents schema drift.

## Dependencies
- P0-003 (Dockerize CI) - Must complete successfully in the same CI run

**Note**: This task requires Docker containers from P0-003 to test migrations in an isolated environment.

## Outcome-Focused Acceptance Criteria
- [ ] `alembic upgrade head` runs cleanly without errors
- [ ] `alembic check` shows no pending changes (exit code 0)
- [ ] `alembic downgrade -1` successfully rolls back the latest migration
- [ ] All SQLAlchemy models are properly imported in alembic/env.py
- [ ] Migration test suite validates schema consistency
- [ ] CI pipeline includes migration validation step
- [ ] Overall test coverage ≥ 80% maintained

### Task-Specific Acceptance Criteria
- [ ] All model changes captured in migrations
- [ ] No duplicate migrations exist
- [ ] Migrations run in correct dependency order
- [ ] Rollback tested for each migration
- [ ] Foreign key constraints properly handled
- [ ] Index creation/deletion tracked
- [ ] Enum types handled correctly across databases

### Additional Requirements
- [ ] Update relevant documentation if schema changes
- [ ] No performance regression on migration execution
- [ ] Only modify files within specified integration points
- [ ] Add pre-commit hook for migration validation
- [ ] Include migration sanity testing framework

## Integration Points
- `alembic/env.py` - Fix model imports
- `alembic/versions/` - Migration files
- All model files matching pattern `*/models.py`
- `tests/unit/test_migrations.py` - New test file
- `.pre-commit-config.yaml` - Add migration check hook

**Critical Path**: Only modify files within these directories. Any changes outside require a separate PRP.

## Tests to Pass
- `alembic upgrade head` runs cleanly
- `alembic check` shows no pending changes
- `pytest tests/unit/test_migrations.py` - All tests pass
- `alembic downgrade -1 && alembic upgrade head` - Round trip succeeds
- Pre-commit hook validates migrations

## Implementation Details

### Step 1: Fix Model Imports in alembic/env.py

The current issue is that not all models are being imported, causing `alembic check` to fail with "NoSuchTableError: businesses". Update env.py to properly import all models:

```python
# alembic/env.py
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import base first
from database.base import Base

# Import all models to ensure they're registered with Base.metadata
from database.models import *  # Core models including Business
from d3_assessment.models import *  # Assessment models
from d6_reports.models import *  # Report models
from d6_reports.lineage.models import *  # Lineage models
from d9_delivery.models import *  # Delivery models
from d11_orchestration.models import *  # Orchestration models
from batch_runner.models import *  # Batch runner models
from lead_explorer.models import *  # Lead explorer models
from governance.models import *  # Governance models

# Any other domain models...
from d1_targeting.models import *
from d2_sourcing.models import *
from d4_enrichment.models import *
from d5_scoring.models import *
from d7_storefront.models import *
from d8_personalization.models import *
from d10_analytics.models import *

target_metadata = Base.metadata
```

### Step 2: Create Comprehensive Migration Test

```python
# tests/unit/test_migrations.py
"""
Test database migrations are current and reversible.

Validates:
1. All models are captured in migrations
2. Migrations can be applied and rolled back
3. No schema drift exists
"""
import os
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import NullPool

from database.base import Base


class TestMigrations:
    """Test suite for database migrations."""
    
    @pytest.fixture
    def alembic_config(self):
        """Create Alembic configuration for testing."""
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Set up test database URL
        test_db_url = f"sqlite:///{db_path}"
        os.environ["DATABASE_URL"] = test_db_url
        
        # Create config
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", test_db_url)
        
        yield config
        
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
    
    def test_migrations_current(self, alembic_config):
        """Ensure no pending migrations exist."""
        # Run upgrade to head
        command.upgrade(alembic_config, "head")
        
        # Get connection
        engine = create_engine(
            alembic_config.get_main_option("sqlalchemy.url"),
            poolclass=NullPool
        )
        
        with engine.connect() as connection:
            # Set up migration context
            context = MigrationContext.configure(connection)
            
            # Check for differences
            from alembic.autogenerate import compare_metadata
            diff = compare_metadata(context, Base.metadata)
            
            # Assert no differences
            assert len(diff) == 0, f"Uncommitted model changes detected: {diff}"
    
    def test_alembic_check_passes(self, alembic_config):
        """Test that alembic check command passes."""
        # This should not raise an exception
        try:
            command.check(alembic_config)
        except SystemExit as e:
            if e.code != 0:
                pytest.fail(f"alembic check failed with exit code {e.code}")
    
    def test_migration_reversibility(self, alembic_config):
        """Test that migrations can be rolled back."""
        # Get current revision before upgrade
        engine = create_engine(
            alembic_config.get_main_option("sqlalchemy.url"),
            poolclass=NullPool
        )
        
        # Upgrade to head
        command.upgrade(alembic_config, "head")
        
        # Get current head revision
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            head_rev = context.get_current_revision()
        
        # Downgrade one revision
        command.downgrade(alembic_config, "-1")
        
        # Verify we're not at head anymore
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            assert current_rev != head_rev
        
        # Upgrade back to head
        command.upgrade(alembic_config, "head")
        
        # Verify we're back at head
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            assert current_rev == head_rev
    
    def test_all_models_have_tables(self, alembic_config):
        """Verify all SQLAlchemy models have corresponding tables."""
        # Upgrade to head
        command.upgrade(alembic_config, "head")
        
        # Get engine and inspector
        engine = create_engine(
            alembic_config.get_main_option("sqlalchemy.url"),
            poolclass=NullPool
        )
        inspector = inspect(engine)
        
        # Get all table names from database
        db_tables = set(inspector.get_table_names())
        
        # Get all table names from models
        model_tables = set(Base.metadata.tables.keys())
        
        # Find missing tables
        missing_tables = model_tables - db_tables
        assert len(missing_tables) == 0, f"Models without tables: {missing_tables}"
        
        # Find extra tables (not necessarily an error, but good to know)
        extra_tables = db_tables - model_tables - {'alembic_version'}
        if extra_tables:
            print(f"Warning: Extra tables in database: {extra_tables}")
    
    def test_foreign_keys_valid(self, alembic_config):
        """Verify all foreign keys reference existing tables and columns."""
        # Upgrade to head
        command.upgrade(alembic_config, "head")
        
        # Get engine and inspector
        engine = create_engine(
            alembic_config.get_main_option("sqlalchemy.url"),
            poolclass=NullPool
        )
        inspector = inspect(engine)
        
        # Check each table's foreign keys
        for table_name in inspector.get_table_names():
            fks = inspector.get_foreign_keys(table_name)
            for fk in fks:
                # Verify referenced table exists
                ref_table = fk['referred_table']
                assert ref_table in inspector.get_table_names(), \
                    f"Foreign key in {table_name} references non-existent table {ref_table}"
                
                # Verify referenced columns exist
                ref_columns = fk['referred_columns']
                actual_columns = [c['name'] for c in inspector.get_columns(ref_table)]
                for col in ref_columns:
                    assert col in actual_columns, \
                        f"Foreign key in {table_name} references non-existent column {ref_table}.{col}"
```

### Step 3: Pre-commit Hook Configuration

Add to `.pre-commit-config.yaml`:

```yaml
  - repo: local
    hooks:
      - id: check-migrations
        name: Check database migrations
        entry: bash -c 'alembic check'
        language: system
        pass_filenames: false
        files: '(alembic/.*|.*/models\.py)$'
```

### Step 4: Migration Validation Script

Create a helper script for CI:

```bash
#!/bin/bash
# scripts/validate_migrations.sh

set -e

echo "Validating database migrations..."

# Check migrations are current
echo "Running alembic check..."
alembic check

# Test upgrade/downgrade cycle
echo "Testing migration reversibility..."
alembic upgrade head
alembic downgrade -1
alembic upgrade head

echo "✅ Migration validation passed!"
```

## Example File/Pattern
**Fixed alembic/env.py with comprehensive model imports**

## Reference Documentation
- `tests/unit/test_migrations.py` - Comprehensive migration test suite
- `scripts/validate_migrations.sh` - CI validation script
- Alembic documentation: https://alembic.sqlalchemy.org/en/latest/

## Implementation Guide

### Step 1: Verify Dependencies
- Check `.claude/prp_progress.json` to ensure P0-003 shows "completed"
- Verify CI is green before starting
- Ensure Docker is running for isolated testing

### Step 2: Set Up Environment
- Python version must be 3.11.0 (check with `python --version`)
- Activate virtual environment: `source venv/bin/activate`
- Install any missing dependencies: `pip install -r requirements.txt`

### Step 3: Implementation
1. Update alembic/env.py to import all models
2. Create tests/unit/test_migrations.py with comprehensive tests
3. Add pre-commit hook for migration validation
4. Create validation script for CI
5. Run `alembic check` to verify fix works

### Step 4: Testing
- Run `pytest tests/unit/test_migrations.py -v`
- Verify `alembic check` exits with code 0
- Test rollback: `alembic downgrade -1 && alembic upgrade head`
- Run full test suite to ensure no regression

### Step 5: Validation
- All outcome-focused criteria must be demonstrably true
- Run full validation command suite
- Commit with descriptive message: `fix(P0-004): Fix model imports and add migration validation`

## Validation Commands
```bash
# Run task-specific tests
alembic check  # Should exit 0
alembic upgrade head  # Should complete without errors
alembic downgrade -1 && alembic upgrade head  # Should succeed
pytest tests/unit/test_migrations.py -v

# Run standard validation
bash scripts/validate_wave_a.sh

# Docker-specific validation
docker build -f Dockerfile.test -t leadfactory-test .
docker run --rm leadfactory-test alembic check
```

## Rollback Strategy
If migrations fail after deployment:
1. **Immediate**: Use `alembic downgrade -1` to revert to previous revision
2. **With data loss**: Restore from database backup taken before migration
3. **Emergency**: Use `alembic stamp head` to force revision (data integrity risk)

Always backup production database before running migrations.

## Feature Flag Requirements
No new feature flag required - this fix is unconditional and required for system stability.

## Security Considerations
- Migration files should never contain sensitive data
- Use parameterized migrations to prevent SQL injection
- Review auto-generated migrations for unintended changes
- Test migrations in staging before production

## Success Criteria
- [x] All specified tests passing
- [x] `alembic check` exits with code 0
- [x] Migration rollback tested successfully
- [x] Coverage ≥ 80% maintained
- [x] CI green after push
- [x] No performance regression
- [x] Pre-commit hook prevents bad migrations

## Critical Context

### Common Migration Issues
1. **Missing imports**: Models not imported in env.py won't be included in autogenerate
2. **Circular imports**: Use string references for foreign keys to avoid import cycles
3. **Database-specific types**: Use database-agnostic types when possible
4. **Migration order**: Ensure dependent tables are created in correct order

### From CURRENT_STATE.md
- Yelp columns have been removed (migration 01dbf243d224)
- New tables added: Lead, AuditLogLead, BatchReport, governance tables
- Schema must support both SQLite (tests) and PostgreSQL (production)

This PRP ensures database integrity by maintaining schema consistency between models and migrations, preventing runtime failures and data loss.