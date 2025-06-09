"""
Shared test configuration for D6 Reports tests
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from database.base import Base


@pytest.fixture(scope="function")
def db_session():
    """Create a database session for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    Session = scoped_session(sessionmaker(bind=engine))
    session = Session()

    yield session

    session.close()
    Session.remove()
