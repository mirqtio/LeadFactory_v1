.PHONY: help install test lint format clean docker-build docker-test run-stubs smoke heartbeat prod-test

# Default target
help:
	@echo "LeadFactory Commands"
	@echo "===================="
	@echo ""
	@echo "Development:"
	@echo "  make install      - Install dependencies"
	@echo "  make test         - Run tests locally"
	@echo "  make docker-test  - Run tests in Docker"
	@echo "  make lint         - Run linting"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean temporary files"
	@echo "  make run-stubs    - Run stub server"
	@echo "  make run          - Run development server"
	@echo ""
	@echo "Production Testing:"
	@echo "  make smoke        - Run smoke tests only"
	@echo "  make heartbeat    - Run heartbeat checks only"
	@echo "  make prod-test    - Run full production readiness suite"
	@echo ""
	@echo "Database:"
	@echo "  make db-upgrade   - Run database migrations"
	@echo "  make db-downgrade - Rollback last migration"
	@echo "  make db-history   - Show migration history"
	@echo ""
	@echo "Deployment:"
	@echo "  make check-env    - Validate environment configuration"
	@echo "  make deploy-local - Deploy to local production (with tests)"
	@echo "  make schedule-tests - Schedule Prefect test flows"

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

# Production testing commands
smoke:
	@echo "Running smoke tests..."
	python scripts/run_production_tests.py --smoke-only

heartbeat:
	@echo "Running heartbeat checks..."
	python scripts/run_production_tests.py --heartbeat-only

prod-test:
	@echo "Running full production readiness tests..."
	python scripts/run_production_tests.py

# Environment validation
check-env:
	@echo "Checking environment configuration..."
	@python scripts/validate_config.py || echo "Config validation script not found"

# Local production deployment
deploy-local: prod-test
	@echo "Tests passed! Starting production services..."
	docker-compose -f docker-compose.production.yml up -d
	@echo "Production services started!"
	@echo "Access the app at http://localhost:8000"

# Prefect scheduling
schedule-tests:
	@echo "Setting up Prefect scheduled tests..."
	python scripts/prefect_schedule_tests.py

start-agent:
	@echo "Starting Prefect agent..."
	prefect agent start -q leadfactory

# Production monitoring
prod-logs:
	@echo "Tailing production logs..."
	docker-compose -f docker-compose.production.yml logs -f app

prod-status:
	@echo "Checking production status..."
	@curl -s http://localhost:8000/health || echo "Service not responding"
	@echo ""
	@docker-compose -f docker-compose.production.yml ps