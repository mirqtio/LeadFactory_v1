#!/bin/bash

# Start the Python agent system

echo "🚀 Starting LeadFactory Agent System"

# Check for .env file
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "⚠️  No .env file found. Creating from .env.example..."
        cp .env.example .env
        echo "📝 Please edit .env and add your ANTHROPIC_API_KEY"
        exit 1
    else
        echo "❌ No .env file found. Please create one with your configuration."
        exit 1
    fi
fi

# Check for ANTHROPIC_API_KEY
if ! grep -q "ANTHROPIC_API_KEY=sk-" .env; then
    echo "❌ ANTHROPIC_API_KEY not configured in .env file"
    echo "📝 Please add your Anthropic API key to the .env file"
    exit 1
fi

# Check Redis
echo "🔍 Checking Redis connection..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running. Please start Redis first."
    echo "💡 On macOS: brew services start redis"
    echo "💡 On Linux: sudo systemctl start redis"
    exit 1
fi
echo "✅ Redis is running"

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Run tests first
echo "🧪 Running system tests..."
cd tests
python -m pytest test_agent_system.py -v

if [ $? -ne 0 ]; then
    echo "❌ Tests failed. Please fix issues before starting the system."
    exit 1
fi
cd ..

echo "✅ All tests passed"

# Start the orchestrator
echo "🎯 Starting orchestrator with agents..."

# Parse PM agent count from .env
PM_COUNT=$(grep PM_AGENT_COUNT .env | cut -d '=' -f2 || echo "3")

# Optional: Clear queues on start
if [ "$1" == "--reset" ]; then
    echo "🧹 Resetting all queues..."
    python orchestrator.py --reset
fi

# Start the main orchestrator
echo "🚀 Starting orchestrator with $PM_COUNT PM agents..."
python orchestrator.py --pm-agents $PM_COUNT

# Cleanup on exit
echo "🛑 Shutting down agent system..."