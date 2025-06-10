"""
Simple integration test to debug the issue
"""

import pytest
# Create FastAPI test app
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from d11_orchestration.api import router
from database.base import Base
from database.session import get_db

app = FastAPI()
app.include_router(router)


def test_simple_integration():
    """Test simple pipeline trigger"""
    # Create in-memory database
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )

    # Import all models to ensure tables are created
    from d11_orchestration.models import (Experiment, ExperimentVariant,
                                          PipelineRun, VariantAssignment)
    from database.models import Business

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        # Test health first
        response = client.get("/orchestration/health")
        print(f"Health: {response.status_code} - {response.text}")
        assert response.status_code == 200

        # Test simple pipeline trigger
        request_data = {"pipeline_name": "test_pipeline", "triggered_by": "test_user"}

        response = client.post("/orchestration/pipelines/trigger", json=request_data)
        print(f"Pipeline trigger: {response.status_code} - {response.text}")

        if response.status_code != 200:
            return False

        return True


if __name__ == "__main__":
    result = test_simple_integration()
    print(f"Test result: {result}")
