#!/usr/bin/env python
"""
Run database migrations for P0-004.
"""
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic import command
from alembic.config import Config

def main():
    """Main function to run migrations."""
    # Get database URL
    db_url = os.environ.get("DATABASE_URL", "sqlite:///tmp/leadfactory.db")
    print(f"Running migrations for database: {db_url}")
    
    # Get alembic configuration
    alembic_ini = project_root / "alembic.ini"
    config = Config(str(alembic_ini))
    
    # Override database URL
    config.set_main_option("sqlalchemy.url", db_url)
    
    # Also set environment variable for alembic/env.py
    os.environ["DATABASE_URL"] = db_url
    
    # Run upgrade to head
    print("\nUpgrading to head...")
    command.upgrade(config, "head")
    print("✅ Migrations completed successfully!")
    
    # Show current revision
    command.current(config)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())