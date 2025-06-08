# LeadFactory MVP

AI-powered website audit platform that generates revenue through automated audit report sales.

## Quick Start

```bash
# Setup
docker build -f Dockerfile.test -t leadfactory-test .

# Run tests
docker run --rm leadfactory-test

# Start development
docker-compose up
```

## Architecture

- **12 domains** (D0-D11) for modular development
- **CI-first** development with Docker-based testing
- **250,000 businesses** processed daily from 5,000 Yelp API calls
- **$199 audit reports** with Stripe payment processing

## Development

All code must pass tests in Docker before committing:

```bash
# Run specific test
docker run --rm leadfactory-test pytest tests/unit/test_models.py

# Run all tests with coverage
docker run --rm leadfactory-test
```

## Documentation

See `PRD.md` for complete specifications.