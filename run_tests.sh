#!/bin/bash

# Test script for discount-app
set -e

echo "🧪 Running discount-app test suite..."

# Check if dependencies are installed
if ! python -m pytest --version > /dev/null 2>&1; then
    echo "Installing test dependencies..."
    pip install pytest pytest-mock pytest-cov
fi

# Run all tests with coverage
echo "Running all tests with coverage..."
python -m pytest --cov=app --cov-report=html:htmlcov --cov-report=term-missing --cov-fail-under=40 -v

# Run specific test categories if argument provided
if [ "$1" = "unit" ]; then
    echo "Running unit tests only..."
    python -m pytest test_unit.py -v
elif [ "$1" = "integration" ]; then
    echo "Running integration tests only..."
    python -m pytest test_integration.py -v
elif [ "$1" = "quick" ]; then
    echo "Running quick smoke tests..."
    python -m pytest -k "test_health_check or test_validate_pw_email" -v
fi

echo "✅ Test suite completed!"
echo "📊 Coverage report generated in htmlcov/index.html"