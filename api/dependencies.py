"""
API dependencies
"""

from typing import AsyncGenerator, Optional

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from core.config import get_settings
from database.session import SessionLocal

# Get settings
settings = get_settings()

# Async engine and session factory (for async endpoints)
async_engine = None
AsyncSessionLocal = None

# Initialize async database if PostgreSQL
if not settings.database_url.startswith("sqlite"):
    # Convert sync PostgreSQL URL to async
    async_db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
    async_engine = create_async_engine(
        async_db_url,
        pool_size=settings.database_pool_size,
        echo=settings.database_echo,
    )
    AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# Redis client singleton
_redis_client: Optional[aioredis.Redis] = None


def get_db() -> Session:
    """Get synchronous database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Get asynchronous database session"""
    if AsyncSessionLocal is None:
        raise RuntimeError("Async database not available for SQLite. Use PostgreSQL for async support.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> aioredis.Redis:
    """Get Redis client (singleton pattern)"""
    global _redis_client

    if _redis_client is None:
        _redis_client = await aioredis.from_url(settings.redis_url, decode_responses=True, encoding="utf-8")

    return _redis_client


async def get_current_user_optional() -> Optional[str]:
    """Get current user if available (optional)"""
    # TODO: Implement actual authentication
    # For now, return None to allow anonymous access
    return None


async def close_redis():
    """Close Redis connection (for app shutdown)"""
    global _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None
