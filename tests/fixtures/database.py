"""
Database fixtures for test isolation and setup.

Provides:
- Isolated test databases with automatic rollback
- Async and sync database sessions
- Database seeding utilities
- Migration helpers for tests
"""
import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator, Optional

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from database.base import Base
from database.session import SessionLocal as ProductionSession

# Import all models to ensure they're registered
from tests.fixtures.model_imports import import_all_models

# Ensure models are imported
import_all_models()


@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """
    Create an isolated test database session with automatic rollback.

    This fixture:
    - Creates an in-memory SQLite database
    - Creates all tables from registered models
    - Provides a session that rolls back after the test
    - Ensures complete test isolation

    Yields:
        Session: SQLAlchemy database session
    """
    engine = create_engine(
        "sqlite:///:memory:", echo=False, poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    # Create all tables
    Base.metadata.create_all(engine)

    # Create session factory
    TestSession = scoped_session(sessionmaker(bind=engine))
    session = TestSession()

    # Begin a transaction
    connection = engine.connect()
    transaction = connection.begin()

    # Configure session to use our connection
    session.bind = connection

    try:
        yield session
    finally:
        # Clean up in correct order
        session.close()
        TestSession.remove()
        try:
            transaction.rollback()
        except Exception:
            # Transaction might already be closed
            pass
        connection.close()
        engine.dispose()


@pytest.fixture(scope="function")
async def async_test_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Create an isolated async test database session with automatic rollback.

    This fixture:
    - Creates an in-memory SQLite database for async operations
    - Creates all tables from registered models
    - Provides an async session that rolls back after the test
    - Ensures complete test isolation

    Yields:
        AsyncSession: SQLAlchemy async database session
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    TestAsyncSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create session with transaction
    async with TestAsyncSession() as session:
        async with session.begin():
            yield session
            # Automatic rollback on context exit

    await engine.dispose()


@pytest.fixture(scope="function")
def db_with_rollback(test_db: Session) -> Generator[Session, None, None]:
    """
    Provides a database session with explicit rollback capability.
    Useful for tests that need to verify rollback behavior.

    Yields:
        Session: Database session with rollback on exit
    """
    yield test_db
    test_db.rollback()


@pytest.fixture(scope="function")
def db_transaction(test_db: Session) -> Generator[Session, None, None]:
    """
    Provides a database session within an explicit transaction context.
    The transaction is automatically rolled back after the test.

    Yields:
        Session: Database session within a transaction
    """
    # Start a savepoint
    test_db.begin_nested()

    @event.listens_for(test_db, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    yield test_db

    # Rollback to savepoint
    test_db.rollback()


class DatabaseSeeder:
    """Utility class for seeding test databases with sample data."""

    def __init__(self, session: Session):
        self.session = session

    def seed_businesses(self, count: int = 5) -> list:
        """Seed database with sample businesses."""
        from database.models import Business

        businesses = []
        for i in range(count):
            business = Business(
                name=f"Test Business {i}",
                url=f"https://testbusiness{i}.com",
                website=f"https://testbusiness{i}.com",
                phone=f"+1-555-{i:04d}",
                email=f"info@testbusiness{i}.com",
                address=f"{i} Tech St",
                city="San Francisco",
                state="CA",
                zip_code="94105",
                rating=4.5 - (i * 0.1),
                user_ratings_total=100 + i * 20,
                categories=["Technology", "Software"],
                vertical="Technology",
                business_status="OPERATIONAL",
            )
            self.session.add(business)
            businesses.append(business)

        self.session.commit()
        return businesses

    def seed_companies(self, count: int = 5) -> list:
        """Seed database with sample companies."""
        from d2_sourcing.models import Company

        companies = []
        for i in range(count):
            company = Company(
                name=f"Test Company {i}",
                domain=f"testcompany{i}.com",
            )
            self.session.add(company)
            companies.append(company)

        self.session.commit()
        return companies

    def seed_leads(self, count: int = 10, business_ids: Optional[list] = None) -> list:
        """Seed database with sample leads."""
        from database.models import EnrichmentStatus, Lead

        leads = []
        for i in range(count):
            # Use unique domain for each lead to avoid constraint violations
            lead = Lead(
                email=f"lead{i}@example.com",
                domain=f"example-lead-{i}.com",  # Unique domain per lead
                company_name=f"Test Company {i % 5}",
                contact_name=f"Test Lead {i}",
                enrichment_status=EnrichmentStatus.PENDING,
                is_manual=False,
                source="test_fixture",
            )
            self.session.add(lead)
            leads.append(lead)

        self.session.commit()
        return leads

    def seed_targets(self, count: int = 3) -> list:
        """Seed database with sample targets."""
        from database.models import GeoType, Target

        targets = []
        geos = ["94105", "10001", "60601"]  # SF, NYC, Chicago
        verticals = ["restaurants", "retail", "services"]

        for i in range(count):
            target = Target(
                geo_type=GeoType.ZIP,
                geo_value=geos[i % len(geos)],
                vertical=verticals[i % len(verticals)],
                estimated_businesses=100 + i * 50,
                priority_score=0.5 + (i * 0.1),
                is_active=True,
            )
            self.session.add(target)
            targets.append(target)

        self.session.commit()
        return targets

    def seed_campaigns(self, count: int = 3) -> list:
        """Seed database with sample campaigns."""
        from d1_targeting.models import Campaign, TargetUniverse
        from d1_targeting.types import CampaignStatus

        # First create a target universe
        target_universe = TargetUniverse(
            name="Test Universe",
            description="Test target universe for campaigns",
            verticals=["restaurants", "retail"],
            geography_config={"level": "city", "values": ["San Francisco"]},
            estimated_size=1000,
            is_active=True,
        )
        self.session.add(target_universe)
        self.session.commit()

        campaigns = []
        for i in range(count):
            campaign = Campaign(
                name=f"Test Campaign {i}",
                description=f"Test campaign {i} description",
                target_universe_id=target_universe.id,
                status=CampaignStatus.RUNNING.value,
                campaign_type="lead_generation",
                total_cost=100.0 + (i * 50),
            )
            self.session.add(campaign)
            campaigns.append(campaign)

        self.session.commit()
        return campaigns


@pytest.fixture
def db_seeder(test_db: Session) -> DatabaseSeeder:
    """
    Provides a database seeder for populating test data.

    Returns:
        DatabaseSeeder: Utility for seeding test data
    """
    return DatabaseSeeder(test_db)


@pytest.fixture
def seeded_db(test_db: Session, db_seeder: DatabaseSeeder) -> dict:
    """
    Provides a pre-seeded database with sample data.

    Returns:
        dict: Dictionary containing seeded entities
    """
    businesses = db_seeder.seed_businesses(5)
    companies = db_seeder.seed_companies(5)
    leads = db_seeder.seed_leads(10, [b.id for b in businesses])
    targets = db_seeder.seed_targets(3)
    campaigns = db_seeder.seed_campaigns(3)

    return {
        "businesses": businesses,
        "companies": companies,
        "leads": leads,
        "targets": targets,
        "campaigns": campaigns,
        "session": test_db,
    }


# Migration helpers
class TestMigrationHelper:
    """Helper class for testing database migrations."""

    @staticmethod
    def create_test_schema(engine):
        """Create test schema for migration testing."""
        Base.metadata.create_all(engine)

    @staticmethod
    def drop_test_schema(engine):
        """Drop test schema after migration testing."""
        Base.metadata.drop_all(engine)

    @staticmethod
    @contextmanager
    def temp_migration_db():
        """Create a temporary database for migration testing."""
        engine = create_engine("sqlite:///test_migration.db", echo=False)

        try:
            yield engine
        finally:
            engine.dispose()
            # Clean up the test database file
            import os

            if os.path.exists("test_migration.db"):
                os.remove("test_migration.db")


@pytest.fixture
def migration_helper():
    """Provides migration testing utilities."""
    return TestMigrationHelper()


# Async context managers for use in async tests
@asynccontextmanager
async def async_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    Useful for manual session management in tests.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, poolclass=StaticPool)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestAsyncSession = async_sessionmaker(engine, class_=AsyncSession)

    async with TestAsyncSession() as session:
        yield session

    await engine.dispose()


# Production database session override (optional)
@pytest.fixture
def mock_production_db(monkeypatch, test_db):
    """
    Replace production database session with test session.
    Use this fixture when testing code that directly uses SessionLocal.
    """
    monkeypatch.setattr("database.session.SessionLocal", lambda: test_db)
    return test_db
