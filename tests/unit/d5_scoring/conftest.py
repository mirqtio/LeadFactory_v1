"""
Shared test configuration for D5 Scoring tests
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from database.base import Base
# Import all models to ensure foreign key references are available
try:
    import database.models  # Main database models
    import d1_targeting.models  # D1 targeting models
    import d2_sourcing.models  # D2 sourcing models
    import d3_assessment.models  # D3 assessment models
    import d4_enrichment.models  # D4 enrichment models
    import d5_scoring.models  # D5 scoring models
    import d6_reports.models  # D6 reports models
    import d7_storefront.models  # D7 storefront models
    import d8_personalization.models  # D8 personalization models
    import d9_delivery.models  # D9 delivery models
    import d10_analytics.models  # D10 analytics models
    import d11_orchestration.models  # D11 orchestration models
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