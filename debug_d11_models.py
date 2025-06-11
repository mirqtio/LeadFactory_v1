#!/usr/bin/env python3
"""Debug D11 model imports and table creation"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Create test engine
engine = create_engine("sqlite:///:memory:", echo=True)

# Import Base
from database.base import Base

print("Base metadata tables before imports:")
print(list(Base.metadata.tables.keys()))

# Import D11 models specifically
from d11_orchestration.models import PipelineRun, Experiment, ExperimentVariant, VariantAssignment

print("\nBase metadata tables after D11 imports:")
print(list(Base.metadata.tables.keys()))

# Create tables
Base.metadata.create_all(bind=engine)

print("\nTables created successfully")

# Test inserting a pipeline run
Session = sessionmaker(bind=engine)
session = Session()

pipeline_run = PipelineRun(
    pipeline_name="test",
    pipeline_type="MANUAL",
    status="PENDING",
    triggered_by="test"
)
session.add(pipeline_run)
session.commit()

print(f"\nPipeline run created with ID: {pipeline_run.run_id}")