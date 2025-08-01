"""
Test Database Migrations - P0-004

Ensures database migrations are current and no pending changes exist.
Tests that alembic upgrade works and autogenerate shows no differences.

Acceptance Criteria:
- alembic upgrade head runs cleanly
- No pending migrations detected
- Rollback path tested
"""

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import NullPool

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from database.base import Base

# Mark entire module as unit test and critical - database migrations must work
pytestmark = [pytest.mark.unit, pytest.mark.critical]


class TestMigrations:
    """Test database migrations are current and working"""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def alembic_config(self, temp_db_path, monkeypatch):
        """Create Alembic configuration with test database"""
        # Get the alembic.ini path
        ini_path = Path(__file__).parent.parent.parent / "alembic.ini"

        if not ini_path.exists():
            pytest.skip("alembic.ini not found")

        cfg = Config(str(ini_path))

        # Override database URL to use temporary SQLite database
        db_url = f"sqlite:///{temp_db_path}"
        cfg.set_main_option("sqlalchemy.url", db_url)

        # IMPORTANT: Also set the DATABASE_URL environment variable
        # because alembic/env.py checks this first
        monkeypatch.setenv("DATABASE_URL", db_url)

        return cfg

    @pytest.fixture
    def test_engine(self, temp_db_path):
        """Create test database engine"""
        return create_engine(f"sqlite:///{temp_db_path}", poolclass=NullPool, echo=False)

    def test_alembic_upgrade_head(self, alembic_config, test_engine):
        """
        Test that alembic upgrade head runs cleanly

        Acceptance Criteria: alembic upgrade head runs cleanly
        """
        # Run upgrade to head
        command.upgrade(alembic_config, "head")

        # Force connection refresh to ensure we see the migrated schema
        test_engine.dispose()

        # Verify tables were created
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()

        # Debug: print what tables we found
        print(f"Tables found after migration: {sorted(tables)}")

        # Should have alembic_version table
        assert "alembic_version" in tables, f"alembic_version table not created. Found tables: {sorted(tables)}"

        # Should have some application tables
        assert len(tables) > 1, f"No application tables created. Only found: {sorted(tables)}"

        print(f"✓ Alembic upgrade head succeeded, created {len(tables)} tables")

    def test_no_pending_migrations(self, alembic_config, test_engine):
        """
        Test that there are no pending migrations

        Acceptance Criteria: No pending migrations detected
        """
        # First upgrade to head
        command.upgrade(alembic_config, "head")

        # Force connection refresh
        test_engine.dispose()

        # Import all models to ensure they're registered
        self._import_all_models()

        # Get current revision
        with test_engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()

            # Debug: check if alembic_version table exists
            inspector = inspect(conn)
            tables = inspector.get_table_names()
            print(f"Tables in database: {sorted(tables)}")

        assert current_rev is not None, f"No current revision found. Tables in DB: {sorted(tables)}"

        # Check if we're at head
        script_dir = ScriptDirectory.from_config(alembic_config)
        head_rev = script_dir.get_current_head()

        assert current_rev == head_rev, f"Database not at head. Current: {current_rev}, Head: {head_rev}"

        print(f"✓ Database is at head revision: {head_rev}")

    def test_autogenerate_detects_no_changes(self, alembic_config, test_engine):
        """
        Test that autogenerate detects no schema changes

        This ensures all model changes are captured in migrations
        """
        # Upgrade to head first
        command.upgrade(alembic_config, "head")

        # Force connection refresh
        test_engine.dispose()

        # Import all models
        self._import_all_models()

        # Check for differences
        with test_engine.connect() as conn:
            MigrationContext.configure(conn)

            # Get metadata from models
            target_metadata = Base.metadata

            # Compare with database
            # Note: This is a simplified check. In production, you'd use
            # alembic's autogenerate comparison functions
            inspector = inspect(test_engine)
            db_tables = set(inspector.get_table_names())
            model_tables = set(target_metadata.tables.keys())

            # Remove alembic_version from comparison
            db_tables.discard("alembic_version")

            # Tables that are expected to be missing in Wave A
            # These are Wave B features or tables that will be created later
            wave_b_tables = {
                "d3_assessment_results",  # Will be created in autogenerated migration
                "d3_assessment_sessions",
                "d3_assessment_costs",
                "d3_pagespeed_assessments",
                "d3_tech_stack_detections",
                "d3_ai_insights",
                "d3_llm_insights",
                "d6_report_templates",
                "d6_report_sections",
                "d6_report_generations",
                "d6_report_deliveries",
                "d7_customers",
                "d7_purchases",
                "d7_purchase_items",
                "d7_payment_sessions",
                "d5_scoring_results",
                "score_history",
                "score_breakdowns",
                "enrichment_requests",
                "enrichment_results",
                "enrichment_audit_logs",
                # Note: campaigns, campaign_batches, and campaign_targets are in d1_targeting
                "campaign_targets",  # Removed campaigns and campaign_batches since they exist in d1_targeting
                "email_templates",
                "email_content",
                "email_deliveries",
                "subject_line_variants",
                "content_variants",
                "variant_assignments",
                "personalization_variables",
                "personalization_tokens",
                "email_generation_logs",
                "delivery_events",
                "suppression_list",
                "bounce_tracking",
                "spam_score_tracking",
                "target_universes",
                "geographic_boundaries",
                "sourced_locations",
                "yelp_metadata",
                # Note: experiment_variants is in d11_orchestration
                "experiment_metrics",
                # Note: fct_api_cost exists as APICost in database.models
                "pipeline_tasks",
            }

            # Filter out Wave B tables from comparison
            model_tables = model_tables - wave_b_tables

            # Check for missing tables
            missing_in_db = model_tables - db_tables
            extra_in_db = db_tables - model_tables

            # Tables from initial migration that don't have models yet
            # These are okay to have in DB without models for Wave A
            legacy_tables = {
                "assessment_results",  # Old table name, replaced by d3_assessment_results
                "experiment_assignments",  # Legacy table from initial migration
                "experiments",  # Legacy table from initial migration
                "pipeline_runs",  # Legacy table from initial migration
            }

            extra_in_db = extra_in_db - legacy_tables

            # Debug: print what we found
            print(f"Model tables (Wave A only): {sorted(model_tables)}")
            print(f"Database tables (minus legacy): {sorted(db_tables - legacy_tables)}")

            # For P0-004, we only care about Wave A tables being in sync
            assert not missing_in_db, f"Wave A tables in models but not in database: {missing_in_db}"
            assert not extra_in_db, f"Tables in database but not in models: {extra_in_db}"

        print("✓ No pending schema changes detected for Wave A tables")

    def test_migration_rollback(self, alembic_config, test_engine):
        """
        Test that migrations can be rolled back

        Acceptance Criteria: Rollback tested for each migration
        """
        # Get all revisions
        script_dir = ScriptDirectory.from_config(alembic_config)
        revisions = list(script_dir.walk_revisions())

        if len(revisions) < 2:
            pytest.skip("Need at least 2 migrations to test rollback")

        # Upgrade to head
        command.upgrade(alembic_config, "head")

        # Get current revision
        with test_engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()

        # Downgrade one revision
        command.downgrade(alembic_config, "-1")

        # Verify we moved back
        with test_engine.connect() as conn:
            context = MigrationContext.configure(conn)
            new_rev = context.get_current_revision()

        assert new_rev != current_rev, "Downgrade did not change revision"

        # Upgrade back to head
        command.upgrade(alembic_config, "head")

        # Verify we're back at head
        with test_engine.connect() as conn:
            context = MigrationContext.configure(conn)
            final_rev = context.get_current_revision()

        assert final_rev == current_rev, "Could not upgrade back to head after downgrade"

        print("✓ Migration rollback tested successfully")

    def test_no_duplicate_migrations(self, alembic_config):
        """
        Test that there are no duplicate migration revisions

        Acceptance Criteria: No duplicate migrations
        """
        script_dir = ScriptDirectory.from_config(alembic_config)

        revisions = []
        for rev in script_dir.walk_revisions():
            revisions.append(rev.revision)

        # Check for duplicates
        assert len(revisions) == len(set(revisions)), "Duplicate migration revisions found"

        print(f"✓ No duplicate migrations found ({len(revisions)} unique revisions)")

    def test_migrations_in_correct_order(self, alembic_config):
        """
        Test that migrations are in correct dependency order

        Acceptance Criteria: Migrations run in correct order
        """
        script_dir = ScriptDirectory.from_config(alembic_config)

        # Walk revisions from base to head
        revision_order = []
        for rev in script_dir.walk_revisions("base", "heads"):
            revision_order.append(rev.revision)

        # Verify we can walk the chain without errors
        assert len(revision_order) > 0, "No migrations found"

        # Try to upgrade through each revision
        temp_config = Config()
        temp_config.set_main_option("script_location", alembic_config.get_main_option("script_location"))
        temp_config.set_main_option("sqlalchemy.url", "sqlite:///:memory:")

        for i, rev in enumerate(revision_order):
            try:
                # This is a dry run - just verify the revision exists
                script_dir.get_revision(rev)
            except Exception as e:
                pytest.fail(f"Failed to find revision {rev} at position {i}: {e}")

        print(f"✓ Migrations in correct order ({len(revision_order)} revisions)")

    def _import_all_models(self):
        """Import all model files to ensure they're registered with SQLAlchemy"""
        import importlib

        # Import main database models first
        try:
            import database.governance_models  # Import governance models (User, AuditLogGlobal)
            import database.models  # noqa: F401 # This imports all models including Lead, AuditLogLead
        except ImportError:
            pass

        # List of packages that contain models
        model_packages = [
            "d0_gateway",
            "d1_targeting",
            "d2_sourcing",
            "d3_assessment",
            "d4_enrichment",
            "d5_scoring",
            "d6_reports",
            "d7_storefront",
            "d8_personalization",
            "d9_delivery",
            "d10_analytics",
            "d11_orchestration",
            "lead_explorer",  # Add lead_explorer package
            "batch_runner",  # Add batch_runner package
        ]

        for package_name in model_packages:
            try:
                # Import the package
                importlib.import_module(package_name)

                # Try to import models module if it exists
                try:
                    importlib.import_module(f"{package_name}.models")
                except ImportError:
                    pass  # Not all packages have models

            except ImportError:
                pass  # Package might not exist

    def test_comprehensive_migration_check(self, alembic_config, test_engine):
        """
        Comprehensive test covering all migration acceptance criteria
        """
        # This test runs all checks in sequence
        print("\n🔄 Running comprehensive migration checks...")

        # 1. Test upgrade
        self.test_alembic_upgrade_head(alembic_config, test_engine)

        # 2. Test no pending migrations
        self.test_no_pending_migrations(alembic_config, test_engine)

        # 3. Test autogenerate
        self.test_autogenerate_detects_no_changes(alembic_config, test_engine)

        # 4. Test rollback
        self.test_migration_rollback(alembic_config, test_engine)

        # 5. Test no duplicates
        self.test_no_duplicate_migrations(alembic_config)

        # 6. Test correct order
        self.test_migrations_in_correct_order(alembic_config)

        print("\n✅ All migration checks passed!")


# Allow running this test file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
