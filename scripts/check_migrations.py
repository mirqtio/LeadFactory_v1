#!/usr/bin/env python
"""
Check if all migrations are current.
This script verifies that the database schema matches the SQLAlchemy models.
"""
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import NullPool

# Import Base and all models
from database.base import Base
from database.models import *
from database.governance_models import *

# Import domain models
try:
    from d1_targeting.models import *
except ImportError:
    pass

try:
    from d2_sourcing.models import *
except ImportError:
    pass

try:
    from d3_assessment.models import *
except ImportError:
    pass

try:
    from d4_enrichment.models import *
except ImportError:
    pass

try:
    from d5_scoring.models import *
except ImportError:
    pass

try:
    from d6_reports.models import *
except ImportError:
    pass

try:
    from d6_reports.lineage.models import *
except ImportError:
    pass

try:
    from d7_storefront.models import *
except ImportError:
    pass

try:
    from d8_personalization.models import *
except ImportError:
    pass

try:
    from d9_delivery.models import *
except ImportError:
    pass

try:
    from d10_analytics.models import *
except ImportError:
    pass

try:
    from d11_orchestration.models import *
except ImportError:
    pass

try:
    from batch_runner.models import *
except ImportError:
    pass

try:
    from lead_explorer.models import *
except ImportError:
    pass


def main():
    """Main function to check migrations."""
    # Get database URL
    db_url = os.environ.get("DATABASE_URL", "sqlite:///tmp/leadfactory.db")
    print(f"Checking migrations for database: {db_url}")
    
    # Create engine
    engine = create_engine(db_url, poolclass=NullPool)
    
    # Get alembic configuration
    alembic_ini = project_root / "alembic.ini"
    config = Config(str(alembic_ini))
    config.set_main_option("sqlalchemy.url", db_url)
    
    # First, ensure we're at head
    print("\nUpgrading to head...")
    command.upgrade(config, "head")
    
    # Get current revision
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()
        print(f"Current revision: {current_rev}")
    
    # Now check for differences
    print("\nChecking for schema differences...")
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        
        # Compare metadata
        diff = compare_metadata(context, Base.metadata)
        
        if not diff:
            print("✅ No schema differences found! All migrations are current.")
            return 0
        else:
            print("❌ Schema differences detected:")
            for d in diff:
                print(f"  - {d}")
            return 1


if __name__ == "__main__":
    sys.exit(main())