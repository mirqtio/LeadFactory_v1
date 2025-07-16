# Pytest Marker System

This document describes the marker inheritance and enforcement system implemented for the test suite.

## Overview

The marker system automatically applies and validates markers on all tests to ensure proper categorization and organization. Every test must have at least one primary marker, and domain-specific tests automatically receive domain markers based on their location.

## Primary Markers (Required)

Every test **must** have at least one of these primary markers:

- **`@pytest.mark.unit`** - Unit tests that test individual components in isolation
- **`@pytest.mark.integration`** - Integration tests that test component interactions
- **`@pytest.mark.e2e`** - End-to-end tests that test complete user workflows
- **`@pytest.mark.smoke`** - Smoke tests for basic functionality verification

## Domain Markers (Auto-Applied)

Tests in domain-specific directories automatically receive these markers:

- **`@pytest.mark.d0_gateway`** - Gateway/API integration tests
- **`@pytest.mark.d1_targeting`** - Targeting and filtering tests
- **`@pytest.mark.d2_sourcing`** - Data sourcing tests
- **`@pytest.mark.d3_assessment`** - Assessment and evaluation tests
- **`@pytest.mark.d4_enrichment`** - Data enrichment tests
- **`@pytest.mark.d5_scoring`** - Scoring and ranking tests
- **`@pytest.mark.d6_reports`** - Reporting tests
- **`@pytest.mark.d7_storefront`** - Storefront API tests
- **`@pytest.mark.d8_personalization`** - Personalization tests
- **`@pytest.mark.d9_delivery`** - Delivery and notification tests
- **`@pytest.mark.d10_analytics`** - Analytics tests
- **`@pytest.mark.d11_orchestration`** - Orchestration and workflow tests

## Automatic Marker Application

The system automatically applies markers based on test file location:

1. **Primary markers** are applied based on directory:
   - Tests in `tests/unit/` automatically get `@pytest.mark.unit`
   - Tests in `tests/integration/` automatically get `@pytest.mark.integration`
   - Tests in `tests/e2e/` automatically get `@pytest.mark.e2e`
   - Tests in `tests/smoke/` automatically get `@pytest.mark.smoke`

2. **Domain markers** are applied based on subdirectory:
   - Tests in `tests/unit/d0_gateway/` get both `unit` and `d0_gateway` markers
   - Tests in `tests/integration/d3_assessment/` get both `integration` and `d3_assessment` markers

## Manual Override

You can manually specify markers to override automatic application:

```python
@pytest.mark.integration  # Override automatic 'unit' marker
def test_integration_in_unit_folder():
    """This test is in tests/unit/ but marked as integration."""
    pass
```

## Validation Commands

### Show Marker Report

Display a report of marker usage across all tests:

```bash
pytest --show-marker-report
```

### Validate Markers

Enforce marker validation (fails if tests are missing required markers):

```bash
pytest --validate-markers
```

## Examples

### Basic Unit Test (Auto-Marked)

```python
# File: tests/unit/test_calculator.py

def test_addition():
    """Automatically gets @pytest.mark.unit marker."""
    assert 1 + 1 == 2
```

### Domain-Specific Test (Auto-Marked)

```python
# File: tests/unit/d0_gateway/test_api_client.py

def test_api_connection():
    """Automatically gets @pytest.mark.unit and @pytest.mark.d0_gateway markers."""
    assert True
```

### Manually Marked Test

```python
# File: tests/test_performance.py

@pytest.mark.unit
@pytest.mark.performance
@pytest.mark.slow
def test_heavy_computation():
    """Manually marked with multiple markers."""
    pass
```

### Integration Test with Domain

```python
# File: tests/integration/d3_assessment/test_assessment_flow.py

def test_full_assessment_workflow():
    """Automatically gets @pytest.mark.integration and @pytest.mark.d3_assessment."""
    pass
```

## Running Tests by Marker

```bash
# Run only unit tests
pytest -m unit

# Run only d0_gateway tests
pytest -m d0_gateway

# Run unit tests for d0_gateway
pytest -m "unit and d0_gateway"

# Run all tests except slow ones
pytest -m "not slow"

# Run integration or e2e tests
pytest -m "integration or e2e"
```

## Troubleshooting

### Missing Primary Marker Error

If you see:
```
ERROR: tests/test_example.py::test_function: Missing required primary marker. Must have at least one of: e2e, integration, smoke, unit
```

**Solution**: Add one of the required primary markers to your test:
```python
@pytest.mark.unit
def test_function():
    pass
```

### Multiple Primary Markers Warning

If you see:
```
WARNING: tests/test_example.py::test_function: Multiple primary markers found: integration, unit. Consider using only one.
```

**Solution**: This is just a warning. Consider using only one primary marker unless the test truly serves multiple purposes.

### Unknown Marker Error

If you see:
```
ERROR: tests/test_example.py::test_function: Unknown markers found: my_custom_marker
```

**Solution**: Either remove the unknown marker or add it to `pytest.ini` if it's a valid custom marker.

## Implementation Details

The marker system is implemented in:
- `/conftest.py` - Hooks for automatic marker application and validation
- `/tests/markers.py` - Marker validation utilities and helpers
- `/tests/test_marker_enforcement.py` - Tests for the marker system itself

The system uses pytest hooks to:
1. Apply markers during test collection (`pytest_collection_modifyitems`)
2. Validate markers when requested (`pytest_sessionfinish`)
3. Generate reports on marker usage