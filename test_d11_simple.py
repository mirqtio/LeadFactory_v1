#!/usr/bin/env python3
"""Simple test to verify D11 model setup"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Create engine with thread safety for FastAPI
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False}
)

# Import Base
from database.base import Base

# Import all models to register with Base
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

# Import D11 models
from d11_orchestration.models import PipelineRun, PipelineType, PipelineRunStatus

# Create tables
Base.metadata.create_all(bind=engine)

# Check tables
with engine.connect() as conn:
    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    tables = [row[0] for row in result]
    print(f"Tables created: {tables}")
    
    # Check if pipeline_runs exists
    if 'pipeline_runs' in tables:
        print("✓ pipeline_runs table created successfully")
    else:
        print("✗ pipeline_runs table NOT created")
        
# Test the API
from fastapi import FastAPI
from d11_orchestration.api import router
from database.session import get_db

app = FastAPI()
app.include_router(router)

# Create session
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# Test the endpoint
response = client.get("/orchestration/health")
print(f"\nHealth check status: {response.status_code}")

# Test pipeline trigger
request_data = {
    "pipeline_name": "test_pipeline",
    "pipeline_type": "manual",
    "triggered_by": "test_user",
}

response = client.post("/orchestration/pipelines/trigger", json=request_data)
print(f"\nPipeline trigger status: {response.status_code}")
if response.status_code != 200:
    print(f"Error: {response.text}")