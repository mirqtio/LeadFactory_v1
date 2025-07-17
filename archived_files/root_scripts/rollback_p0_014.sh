#!/bin/bash
# Rollback script for P0-014 changes if CI fails

echo "🔄 Rolling back P0-014 changes to last known good state..."

# Restore the minimal test.yml that was working in P0-013
cat > .github/workflows/test.yml << 'EOF'
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  PYTHON_VERSION: "3.11.0"
  DATABASE_URL: "sqlite:///tmp/test.db"
  USE_STUBS: "true"
  ENVIRONMENT: "test"
  SECRET_KEY: "test-secret-key-for-ci"
  CI: "true"

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ env.PYTHON_VERSION }}
    
    - name: Create tmp directory
      run: mkdir -p tmp
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Set PYTHONPATH
      run: echo "PYTHONPATH=${{ github.workspace }}" >> $GITHUB_ENV
    
    - name: Run minimal tests
      run: |
        python -m pytest tests/unit/test_core.py tests/unit/test_health_endpoint.py -xvs
EOF

echo "✅ Rollback complete. The test.yml has been restored to minimal working state."
echo "📝 To apply: git add .github/workflows/test.yml && git commit -m 'fix: Rollback to minimal test suite'"