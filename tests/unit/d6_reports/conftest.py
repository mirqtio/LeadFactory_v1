"""
Shared test configuration for D6 Reports tests
"""
import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

# Add current directory to Python path for module resolution
current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from database.base import Base
# Import all models to ensure foreign key references are available
try:
    import database.models  # Main database models
except ImportError:
    pass

try:
    import d6_reports.models  # D6 reports models
except ImportError:
    # If import fails, models will be registered when tests import them
    pass


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
