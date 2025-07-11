#!/bin/bash
# LeadFactory Development Setup Script
# This script sets up the development environment for new contributors

set -e  # Exit on any error

echo "🚀 LeadFactory Development Setup"
echo "================================"

# Check Python version
echo "📦 Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
REQUIRED_VERSION="3.11.0"

if [ "$PYTHON_VERSION" != "$REQUIRED_VERSION" ]; then
    echo "❌ Error: Python $REQUIRED_VERSION required, but $PYTHON_VERSION found"
    echo "Please install Python 3.11.0 using pyenv or your system package manager"
    exit 1
fi
echo "✅ Python $PYTHON_VERSION"

# Check Docker
echo "📦 Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker not found"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+')
if [ "$(printf '%s\n' "20.10" "$DOCKER_VERSION" | sort -V | head -n1)" != "20.10" ]; then
    echo "❌ Error: Docker ≥ 20.10 required, but $DOCKER_VERSION found"
    exit 1
fi
echo "✅ Docker $DOCKER_VERSION"

# Check Docker Compose
echo "📦 Checking Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: Docker Compose not found"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

COMPOSE_VERSION=$(docker-compose --version | grep -oE '[0-9]+\.[0-9]+')
if [ "$(printf '%s\n' "2.0" "$COMPOSE_VERSION" | sort -V | head -n1)" != "2.0" ]; then
    echo "❌ Error: Docker Compose ≥ 2.0 required, but $COMPOSE_VERSION found"
    exit 1
fi
echo "✅ Docker Compose $COMPOSE_VERSION"

# Create virtual environment
echo ""
echo "🐍 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo ""
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install -r requirements-dev.txt

# Create .env file if it doesn't exist
echo ""
echo "🔧 Setting up environment variables..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ Created .env from .env.example"
    echo "⚠️  Please update .env with your API keys"
else
    echo "✅ .env file already exists"
fi

# Set up pre-commit hooks
echo ""
echo "🔧 Setting up pre-commit hooks..."
pre-commit install
echo "✅ Pre-commit hooks installed"

# Initialize database
echo ""
echo "🗄️  Setting up database..."
docker-compose up -d db
echo "⏳ Waiting for database to be ready..."
sleep 5

# Run migrations
echo ""
echo "🗄️  Running database migrations..."
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/leadfactory_test"
alembic upgrade head
echo "✅ Database migrations completed"

# Run test collection to verify setup
echo ""
echo "🧪 Verifying pytest setup..."
pytest --collect-only -q
echo "✅ Pytest collection successful"

# Build Docker test image
echo ""
echo "🐳 Building Docker test image..."
docker build -f Dockerfile.test -t leadfactory-test .
echo "✅ Docker test image built"

# Summary
echo ""
echo "✨ Setup Complete!"
echo "=================="
echo ""
echo "Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Update .env with your API keys"
echo "3. Run tests: pytest"
echo "4. Run tests in Docker: docker run --rm leadfactory-test"
echo ""
echo "For more information, see README.md"