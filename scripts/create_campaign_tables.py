#!/usr/bin/env python3
"""
Create campaigns table in the database
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from core.logging import get_logger

logger = get_logger(__name__)

def create_campaigns_table():
    """Create campaigns table without foreign key constraints"""
    database_url = os.getenv("DATABASE_URL", "postgresql://leadfactory:leadfactory_prod_2024@postgres:5432/leadfactory")
    engine = create_engine(database_url)
    
    with engine.begin() as conn:
        # Create a simple campaigns table
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            vertical VARCHAR(50) NOT NULL,
            geo_targets TEXT[] NOT NULL,
            daily_quota INTEGER NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        )
        """))
        
        logger.info("Created campaigns table successfully")
        
        # Check if table was created
        result = conn.execute(text("SELECT COUNT(*) FROM campaigns"))
        count = result.scalar()
        logger.info(f"Campaigns table has {count} records")

if __name__ == "__main__":
    create_campaigns_table()