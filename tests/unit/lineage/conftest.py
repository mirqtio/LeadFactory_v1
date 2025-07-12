"""
Test configuration for lineage unit tests
"""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from database.base import Base


@pytest.fixture
async def async_db_session(db_session):
    """
    Create an async database session for async tests
    Uses the sync session's bind URL
    """
    # Get database URL from sync session
    db_url = str(db_session.bind.url)
    
    # Convert to async URL (sqlite -> sqlite+aiosqlite)
    if db_url.startswith("sqlite"):
        async_db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
    else:
        # For other databases, add appropriate async driver
        async_db_url = db_url
    
    # Create async engine
    engine = create_async_engine(async_db_url, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        yield session
        await session.rollback()
    
    await engine.dispose()