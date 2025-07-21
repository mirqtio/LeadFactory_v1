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

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from alembic import command  # noqa: E402
from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402

# Import Base and all models
from database.base import Base  # noqa: E402
from database.governance_models import *  # noqa: E402, F403
from database.models import *  # noqa: E402, F403

# Import domain models
try:
    from d1_targeting.models import *  # noqa: F403
except ImportError:
    pass

try:
    from d2_sourcing.models import *  # noqa: F403
except ImportError:
    pass

try:
    from d3_assessment.models import *  # noqa: F403
except ImportError:
    pass

try:
    from d4_enrichment.models import *  # noqa: F403
except ImportError:
    pass

try:
    from d5_scoring.models import *  # noqa: F403
except ImportError:
    pass

try:
    from d6_reports.models import *  # noqa: F403
except ImportError:
    pass

try:
    from d6_reports.lineage.models import *  # noqa: F403
except ImportError:
    pass

try:
    from d7_storefront.models import *  # noqa: F403
except ImportError:
    pass

try:
    from d8_personalization.models import *  # noqa: F403
except ImportError:
    pass

try:
    from d9_delivery.models import *  # noqa: F403
except ImportError:
    pass

try:
    from d10_analytics.models import *  # noqa: F403
except ImportError:
    pass

try:
    from d11_orchestration.models import *  # noqa: F403
except ImportError:
    pass

try:
    from batch_runner.models import *  # noqa: F403
except ImportError:
    pass

try:
    from lead_explorer.models import *  # noqa: F403
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
        print("❌ Schema differences detected:")
        for d in diff:
            print(f"  - {d}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
