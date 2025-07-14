"""
Configuration for integration tests
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from database.base import Base

# Import all models to ensure they're registered
try:
    import database.models
    import d1_targeting.models
    import d2_sourcing.models
    import d3_assessment.models
    import d4_enrichment.models
    import d5_scoring.models
    import d6_reports.models
    import d7_storefront.models
    import d8_personalization.models
    import d9_delivery.models
    import d10_analytics.models
    import d11_orchestration.models
    import lead_explorer.models
    import batch_runner.models
    from d6_reports.lineage.models import ReportLineage, ReportLineageAudit
except ImportError:
    pass


@pytest.fixture(scope="function")
def db_session():
    """Create a database session for testing"""
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:", 
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)

    Session = scoped_session(sessionmaker(bind=engine))
    session = Session()

    yield session

    session.close()
    Session.remove()