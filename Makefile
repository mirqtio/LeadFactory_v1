.PHONY: help install test lint format clean docker-build docker-test run-stubs

# Default target
help:
	@echo "LeadFactory Development Commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make test         - Run tests locally"
	@echo "  make docker-test  - Run tests in Docker"
	@echo "  make lint         - Run linting"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean temporary files"
	@echo "  make run-stubs    - Run stub server"
	@echo "  make run          - Run development server"
	@echo "  make db-upgrade   - Run database migrations"

# Install dependencies
install:
	pip install -r requirements.txt -r requirements-dev.txt
	pre-commit install

# Run tests locally
test:
	mkdir -p tmp
	pytest -xvs --tb=short --cov=. --cov-report=term-missing

# Run tests in Docker
docker-test:
	docker build -f Dockerfile.test -t leadfactory-test .
	docker run --rm -v $(PWD):/app leadfactory-test

# Build Docker images
docker-build:
	docker build -f Dockerfile -t leadfactory:latest .
	docker build -f Dockerfile.test -t leadfactory:test .
	docker build -f Dockerfile.stub -t leadfactory:stub .

# Run linting
lint:
	flake8 . --max-line-length=120 --max-complexity=15 --ignore=E203,W503
	mypy --ignore-missing-imports .
	bandit -r . --skip B101

# Format code
format:
	black . --line-length=120
	isort . --profile=black --line-length=120

# Clean temporary files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage coverage.xml htmlcov
	rm -rf tmp/*.db

# Run stub server
run-stubs:
	uvicorn stubs.server:app --host 0.0.0.0 --port 5010 --reload

# Run development server
run:
	uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Database commands
db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

db-history:
	alembic history

# Docker compose commands
compose-up:
	docker-compose up -d

compose-down:
	docker-compose down

compose-logs:
	docker-compose logs -f

# CI simulation
ci-local:
	@echo "Running CI pipeline locally..."
	make lint
	make docker-test
	@echo "CI pipeline passed!"