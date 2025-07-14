"""
Configuration for integration tests
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from database.base import Base

# Import all models to ensure they're registered
try:
    import batch_runner.models  # noqa: F401
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
    import database.governance_models  # noqa: F401
    import database.models  # noqa: F401
    import lead_explorer.models  # noqa: F401
    from d6_reports.lineage.models import ReportLineage, ReportLineageAudit  # noqa: F401
except ImportError:
    pass


@pytest.fixture(scope="function")
def db_session():
    """Create a database session for testing"""
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:", echo=False, poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)

    Session = scoped_session(sessionmaker(bind=engine))
    session = Session()

    yield session

    session.close()
    Session.remove()
