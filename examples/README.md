# LeadFactory Code Examples

This directory contains code examples and patterns used throughout the LeadFactory project. These examples serve as references for the PRP generator when creating implementation plans.

## Directory Structure

```
examples/
├── README.md                    # This file
├── gateway/                     # Gateway pattern examples
│   ├── base_client.py          # BaseAPIClient implementation
│   └── provider_example.py     # How to implement a new provider
├── coordinators/               # Coordinator pattern examples
│   └── coordinator_example.py  # Base coordinator structure
├── models/                     # SQLAlchemy model examples
│   └── model_example.py        # Model with relationships
├── tests/                      # Testing pattern examples
│   ├── unit_test_example.py    # Unit test structure
│   └── integration_test.py     # Integration test patterns
└── flows/                      # Prefect flow examples
    └── flow_example.py         # Basic flow structure
```

## Usage

When creating an INITIAL.md file for a new feature, reference specific examples:

```markdown
## EXAMPLES:
- Follow gateway pattern from examples/gateway/base_client.py
- Use coordinator structure from examples/coordinators/coordinator_example.py
- Test patterns from examples/tests/unit_test_example.py
```

## Key Patterns

### 1. Gateway Pattern
All external API clients follow the gateway pattern with:
- Cost tracking
- Rate limiting
- Error handling
- Stub support for testing

### 2. Coordinator Pattern
Business logic coordinators that:
- Orchestrate multiple services
- Handle caching
- Provide consistent interfaces

### 3. Testing Patterns
- Unit tests with mocks
- Integration tests with Docker
- Stub server for external APIs
- Deterministic test data

### 4. Model Patterns
- SQLAlchemy declarative base
- UUID primary keys
- Timestamp tracking
- Soft deletes where appropriate