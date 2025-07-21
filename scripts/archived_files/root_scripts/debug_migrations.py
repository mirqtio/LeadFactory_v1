#!/usr/bin/env python
"""
Debug database migrations for P0-004.
"""

import os
import sqlite3
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.runtime.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402


def main():
    """Main function to debug migrations."""
    # Set up database
    db_path = "/tmp/leadfactory.db"
    db_url = f"sqlite:///{db_path}"

    # Remove old database
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed existing database: {db_path}")

    # Set environment variable
    os.environ["DATABASE_URL"] = db_url

    # Get alembic configuration
    alembic_ini = project_root / "alembic.ini"
    config = Config(str(alembic_ini))
    config.set_main_option("sqlalchemy.url", db_url)

    print(f"\nDatabase URL: {db_url}")
    print(f"Alembic config: {alembic_ini}")

    # Get script directory
    script_dir = ScriptDirectory.from_config(config)

    # Show available revisions
    print("\nAvailable revisions:")
    for rev in script_dir.walk_revisions():
        print(f"  - {rev.revision}: {rev.doc}")

    # Show current head
    head = script_dir.get_current_head()
    print(f"\nCurrent head: {head}")

    # Create engine and check current revision
    engine = create_engine(db_url)

    # Run migrations
    print("\n🔄 Running upgrade to head...")
    command.upgrade(config, "head")

    # Check if tables were created
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = cursor.fetchall()

    print(f"\n✅ Tables created ({len(tables)} total):")
    for table in tables:
        print(f"  - {table[0]}")

    # Check current revision
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_rev = context.get_current_revision()
        print(f"\nCurrent revision in DB: {current_rev}")

    conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
