"""
Shared test configuration for D9 Delivery tests
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from database.base import Base

# Import all models to ensure foreign key references are available
try:
    import d1_targeting.models  # noqa: F401
    import d2_sourcing.models  # noqa: F401
    import d3_assessment.models  # noqa: F401
    import d4_enrichment.models  # noqa: F401
    import d5_scoring.models  # noqa: F401
    import d6_reports.models  # noqa: F401
    import d7_storefront.models  # noqa: F401
    import d8_personalization.models  # noqa: F401
    import d9_delivery.models  # noqa: F401
    import d10_analytics.models  # noqa: F401
    import d11_orchestration.models  # noqa: F401
    import database.models  # noqa: F401
except ImportError:
    # If imports fail, models will be registered when tests import them
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
