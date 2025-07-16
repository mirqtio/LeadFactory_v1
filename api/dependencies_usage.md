# API Dependencies Usage Guide

This guide shows how to use the dependency functions in your FastAPI endpoints.

## Database Dependencies

### Synchronous Database Session

For traditional synchronous endpoints:

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from api.dependencies import get_db

@router.get("/items")
def get_items(db: Session = Depends(get_db)):
    # Use the database session
    items = db.query(Item).all()
    return items
```

### Asynchronous Database Session

For async endpoints (PostgreSQL only):

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from api.dependencies import get_async_db

@router.get("/items")
async def get_items(db: AsyncSession = Depends(get_async_db)):
    # Use the async database session
    result = await db.execute(select(Item))
    items = result.scalars().all()
    return items
```

Note: Async database sessions are only available when using PostgreSQL. SQLite connections will raise a `RuntimeError`.

## Redis Dependencies

For caching and rate limiting:

```python
from fastapi import Depends
import redis.asyncio as aioredis
from api.dependencies import get_redis

@router.get("/cached-data")
async def get_cached_data(redis: aioredis.Redis = Depends(get_redis)):
    # Check cache
    cached = await redis.get("my-key")
    if cached:
        return json.loads(cached)
    
    # Generate data
    data = {"result": "expensive computation"}
    
    # Cache for 1 hour
    await redis.setex("my-key", 3600, json.dumps(data))
    return data
```

## Authentication Dependencies

For optional authentication:

```python
from fastapi import Depends
from typing import Optional
from api.dependencies import get_current_user_optional

@router.get("/public-endpoint")
async def public_endpoint(
    current_user: Optional[str] = Depends(get_current_user_optional)
):
    if current_user:
        return {"message": f"Hello {current_user}"}
    return {"message": "Hello anonymous"}
```

## App Lifecycle Management

In your main FastAPI app:

```python
from fastapi import FastAPI
from api.dependencies import close_redis

app = FastAPI()

@app.on_event("shutdown")
async def shutdown_event():
    # Close Redis connection on app shutdown
    await close_redis()
```

## Environment Configuration

The dependencies use settings from `core.config`:

- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection string (default: `redis://localhost:6379/0`)
- `DATABASE_POOL_SIZE`: Database connection pool size (default: 10)
- `DATABASE_ECHO`: Enable SQL query logging (default: False)