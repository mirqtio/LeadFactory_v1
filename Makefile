.PHONY: help install test test-unit test-integration test-e2e test-parallel lint format clean docker-build docker-test run-stubs smoke heartbeat prod-test rollback bpci pre-push quick-check test-critical test-fast test-data-pipeline test-business-logic test-delivery test-full

# Default target
help:
	@echo "LeadFactory Commands"
	@echo "===================="
	@echo ""
	@echo "Development:"
	@echo "  make install      - Install dependencies"
	@echo "  make test         - Run tests locally (auto-parallel)"
	@echo "  make test-unit    - Run unit tests (max parallelization)"
	@echo "  make test-integration - Run integration tests (limited parallel)"
	@echo "  make test-e2e     - Run e2e tests (serial execution)"
	@echo "  make test-parallel - Run tests with parallelization report"
	@echo "  make docker-test  - Run tests in Docker"
	@echo ""
	@echo "CI Job Test Targets:"
	@echo "  make test-critical - Run critical/smoke tests (<1 min)"
	@echo "  make test-fast    - Alias for test-critical"
	@echo "  make test-data-pipeline - Test data pipeline domains"
	@echo "  make test-business-logic - Test business logic domains"
	@echo "  make test-delivery - Test delivery/orchestration domains"
	@echo "  make test-full    - Run full test suite with coverage"
	@echo "  make lint         - Run linting"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean temporary files"
	@echo "  make run-stubs    - Run stub server"
	@echo "  make run          - Run development server"
	@echo ""
	@echo "CI Validation (Choose based on time available):"
	@echo "  make bpci-fast    - GitHub CI mirror (<5 min) - SQLite, exact CI match"
	@echo "  make bpci-prod    - Production mirror (~15 min) - PostgreSQL validation"
	@echo "  make bpci         - Full validation (~20 min) - Both SQLite + PostgreSQL"
	@echo "  make quick-check  - Pre-commit validation (30 sec) - lint & format"
	@echo "  make pre-push     - GitHub CI validation before git push"
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

# Run tests locally (auto-parallel based on available resources)
test:
	mkdir -p tmp
	pytest -xvs --tb=short --cov=. --cov-report=term-missing

# Run unit tests with maximum parallelization
test-unit:
	mkdir -p tmp
	@echo "🚀 Running unit tests with optimal parallelization..."
	@python scripts/test_parallelization_config.py --type unit
	pytest -m unit -n auto --dist worksteal --tb=short --cov=. --cov-report=term-missing

# Run integration tests with limited parallelization
test-integration:
	mkdir -p tmp
	@echo "🔧 Running integration tests with controlled parallelization..."
	@python scripts/test_parallelization_config.py --type integration
	pytest -m integration -n 2 --dist worksteal --tb=short --cov=. --cov-report=term-missing

# Run e2e tests serially
test-e2e:
	mkdir -p tmp
	@echo "🌐 Running e2e tests serially..."
	pytest -m e2e -v --tb=short

# Run all tests with parallel configuration report
test-parallel:
	mkdir -p tmp
	@echo "📊 Test Parallelization Report:"
	@python scripts/test_parallelization_config.py --type auto
	@echo ""
	pytest --tb=short --cov=. --cov-report=term-missing

# Run slow tests only
test-slow:
	mkdir -p tmp
	@echo "🐌 Running slow tests only..."
	pytest -m slow -v --tb=short

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

# BPCI-Fast - GitHub CI mirror (<5 minutes) using SQLite
bpci-fast:
	bash scripts/bpci-fast.sh

# BPCI-Prod - Production mirror (~15 minutes) using PostgreSQL
bpci-prod:
	bash scripts/bpci-prod.sh

# Pre-push validation - runs exact GitHub CI checks locally
pre-push: clean
	@echo "🔍 Pre-push validation using GitHub CI mirror..."
	$(MAKE) bpci-fast

# Quick validation - for frequent commits (with parallelization)
quick-check:
	@echo "⚡ Quick validation..."
	make format
	make lint
	pytest tests/unit/core/ -x --tb=no -n auto
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

# Performance testing commands
test-performance:
	@echo "🚀 Running performance test suite..."
	pytest tests/performance/ -v -m performance --tb=short

test-performance-audit:
	@echo "📊 Running P3-003 audit performance tests..."
	pytest tests/performance/test_p3_003_audit_performance.py -v --tb=short

test-performance-integration:
	@echo "🔗 Running P3-003 + P2-040 integration performance tests..."
	pytest tests/performance/test_integration_performance.py -v --tb=short

test-performance-monitoring:
	@echo "📈 Running production monitoring performance tests..."
	pytest tests/performance/test_production_monitoring.py -v --tb=short

test-performance-full:
	@echo "🧪 Running complete performance validation suite..."
	pytest tests/performance/ -v -m performance --tb=short --cov=lead_explorer.audit --cov=orchestrator.budget_monitor --cov-report=term-missing

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

# CI Job Test Targets - Optimized for parallel execution
# ========================================================

# Critical/smoke tests for fast feedback (<1 minute)
test-critical:
	@echo "🚀 Running critical/smoke tests for fast feedback..."
	pytest -v -m 'critical or smoke' --tb=short -n 4

# Alias for test-critical
test-fast: test-critical

# Data pipeline domain tests
test-data-pipeline:
	@echo "📊 Running data pipeline tests (d0-d4)..."
	pytest -v tests/unit/d0_gateway tests/unit/d1_targeting tests/unit/d2_sourcing \
		tests/unit/d3_assessment tests/unit/d4_enrichment \
		-m 'not slow and not integration' --tb=short -n 4

# Business logic domain tests
test-business-logic:
	@echo "💼 Running business logic tests (d5-d8)..."
	pytest -v tests/unit/d5_scoring tests/unit/d6_reports \
		tests/unit/d7_storefront tests/unit/d8_personalization \
		-m 'not slow and not integration' --tb=short -n 4

# Delivery and orchestration domain tests
test-delivery:
	@echo "📬 Running delivery/orchestration tests (d9-d11)..."
	pytest -v tests/unit/d9_delivery tests/unit/d10_analytics tests/unit/d11_orchestration \
		-m 'not slow and not integration' --tb=short -n 4

# Full test suite with coverage
test-full:
	@echo "🧪 Running full test suite with coverage..."
	pytest -v -m 'not slow and not phase_future' --tb=short \
		--cov=. --cov-report=xml --cov-report=term --cov-report=html:coverage/html \
		--junitxml=test-results/junit.xml -n auto