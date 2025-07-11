# Prerequisites Checklist

## System Requirements
- [ ] Python 3.11.0 installed (check with `python --version`)
- [ ] Docker 20.10+ installed (check with `docker --version`)
- [ ] Docker Compose 2.0+ installed (check with `docker-compose --version`)
- [ ] PostgreSQL client tools (for database operations)
- [ ] Git configured with user name and email

## Environment Setup
- [ ] Virtual environment created (`python -m venv venv`)
- [ ] Virtual environment activated (`source venv/bin/activate`)
- [ ] `.env` file created from `.env.example`
- [ ] Required environment variables set:
  - [ ] `DATABASE_URL`
  - [ ] `SECRET_KEY`
  - [ ] `ENVIRONMENT`
  - [ ] `USE_STUBS` (for testing)

## Dependencies
- [ ] Run `pip install -r requirements.txt`
- [ ] Run `pip install -r requirements-dev.txt`
- [ ] Verify no errors with `pip check`

## Database
- [ ] PostgreSQL running (local or Docker)
- [ ] Database created
- [ ] Run migrations: `alembic upgrade head`
- [ ] Verify schema: `alembic check`

## Verification
- [ ] Run `pytest --collect-only` (should find tests without errors)
- [ ] Run `python -m py_compile **/*.py` (no syntax errors)
- [ ] Run `docker build -f Dockerfile.test -t test .` (if Dockerfile.test exists)

## Documentation
- [ ] Read CLAUDE.md for development rules
- [ ] Read planning/README.md for task workflow
- [ ] Understand the two-wave implementation plan