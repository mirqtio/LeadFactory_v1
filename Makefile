.PHONY: help install test lint format clean docker-build docker-test run-stubs smoke heartbeat prod-test rollback bpci pre-push quick-check

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
	@echo "  make bpci         - Run Bulletproof CI (catches issues before GitHub CI)"
	@echo "  make pre-push     - Pre-push validation using BPCI"
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

# Run linting (enhanced to catch syntax errors like GitHub CI)
lint:
	@echo "🔍 Critical syntax error check (mirrors GitHub CI exactly)..."
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	@echo "🔍 Full linting check..."
	flake8 .

# Format code
format:
	black . --line-length=120 --exclude="(.venv|venv)"
	isort . --profile=black --line-length=120 --skip=.venv --skip=venv

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

# CI simulation - EXACTLY matches GitHub CI
ci-local:
	@echo "🚀 Running COMPLETE CI pipeline locally..."
	@echo "Phase 1: Linting and Code Quality"
	make lint
	@echo "Phase 2: Minimal Test Suite"
	STUB_BASE_URL=http://localhost:5010 pytest tests/unit/core/test_config.py::TestEnvironmentConfiguration::test_default_settings -v
	@echo "Phase 3: Docker Build"
	make docker-build
	@echo "Phase 4: Full Test Suite"
	make docker-test
	@echo "✅ Complete CI pipeline passed locally!"

# BPCI - Bulletproof CI validation that catches issues BEFORE GitHub CI
bpci:
	bash scripts/bpci.sh

# Pre-push validation - runs ALL CI checks locally using BPCI
pre-push: clean
	@echo "🔍 Pre-push validation using BPCI..."
	$(MAKE) bpci

# Quick validation - for frequent commits
quick-check:
	@echo "⚡ Quick validation..."
	make format
	make lint
	pytest tests/unit/core/ -x --tb=no
	@echo "✅ Quick check passed!"

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

# Legacy validation targets - replaced by BPCI
# Use 'make bpci' for full CI validation
# Use 'make quick-check' for rapid validation

# Rollback command
rollback:
	@echo "Running rollback script..."
	@bash scripts/rollback.sh || echo "Rollback script not found"