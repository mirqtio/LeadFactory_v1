#!/usr/bin/env python3
"""Test the validation gates"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recursive_prp_processor import PRPGenerator, Task

# Create a test task
test_task = Task(
    priority="P0-001",
    title="Fix Database Connection Pool",
    dependencies=[],
    goal="Resolve connection exhaustion under load",
    integration_points=["leadfactory/data/crud.py", "leadfactory/core/database.py"],
    tests_to_pass=["pytest tests/test_database.py"],
    acceptance_criteria=["Connection pool handles 100 concurrent requests", "No connection leaks after 1 hour"],
    wave="A"
)

# Test with good task
print("Testing valid PRP...")
generator = PRPGenerator(".claude/PRPs_test")
path, success = generator.generate_prp(test_task)
print(f"Result: {'SUCCESS' if success else 'FAILED'}")
print()

# Test with policy violation
print("Testing PRP with policy violation...")
bad_task = Task(
    priority="P1-001",
    title="Add Yelp Integration",  # This should fail policy check
    dependencies=["P0-001"],
    goal="Integrate Yelp API for business data",
    integration_points=["leadfactory/providers/provider_yelp.py"],
    tests_to_pass=["pytest tests/test_yelp.py"],
    acceptance_criteria=["Yelp data fetched successfully"],
    wave="B"
)

path, success = generator.generate_prp(bad_task)
print(f"Result: {'SUCCESS' if success else 'FAILED'}")
print()

# Test with bad schema
print("Testing PRP with invalid schema...")
invalid_task = Task(
    priority="INVALID",  # Bad format
    title="X",  # Too short
    dependencies=[],
    goal="test",
    integration_points=[],  # Empty list should fail
    tests_to_pass=[],
    acceptance_criteria=[],  # Empty list should fail
    wave="C"  # Invalid wave
)

try:
    path, success = generator.generate_prp(invalid_task)
    print(f"Result: {'SUCCESS' if success else 'FAILED'}")
except Exception as e:
    print(f"Exception caught: {e}")
