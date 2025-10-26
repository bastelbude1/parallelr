#!/bin/bash
# Master Test Runner for parallelr
# Runs all test suites and generates reports

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "=========================================="
echo "  parallelr Complete Test Suite"
echo "=========================================="
echo ""

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}✗ pytest is not installed${NC}"
    echo "Install with: pip install -r tests/requirements-test.txt"
    exit 1
fi

echo -e "${YELLOW}Running Unit Tests...${NC}"
pytest tests/unit/ -v --tb=short || {
    echo -e "${RED}✗ Unit tests failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Unit tests passed${NC}"
echo ""

# Integration tests (if they exist)
if [ -d "tests/integration" ] && [ "$(ls -A tests/integration/*.py 2>/dev/null)" ]; then
    echo -e "${YELLOW}Running Integration Tests...${NC}"
    pytest tests/integration/ -v --tb=short || {
        echo -e "${RED}✗ Integration tests failed${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ Integration tests passed${NC}"
    echo ""
fi

# Security tests (if they exist)
if [ -d "tests/security" ] && [ "$(ls -A tests/security/*.py 2>/dev/null)" ]; then
    echo -e "${YELLOW}Running Security Tests...${NC}"
    pytest tests/security/ -v --tb=short || {
        echo -e "${RED}✗ Security tests failed${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ Security tests passed${NC}"
    echo ""
fi

# Performance tests (optional - only if RUN_PERFORMANCE=1)
if [ "$RUN_PERFORMANCE" = "1" ]; then
    if [ -d "tests/performance" ] && [ "$(ls -A tests/performance/*.py 2>/dev/null)" ]; then
        echo -e "${YELLOW}Running Performance Tests...${NC}"
        pytest tests/performance/ -v --tb=short || {
            echo -e "${RED}✗ Performance tests failed${NC}"
            exit 1
        }
        echo -e "${GREEN}✓ Performance tests passed${NC}"
        echo ""
    fi
fi

# E2E tests (if they exist)
if [ -d "tests/e2e" ] && [ "$(ls -A tests/e2e/*.py 2>/dev/null)" ]; then
    echo -e "${YELLOW}Running E2E Tests...${NC}"
    pytest tests/e2e/ -v --tb=short || {
        echo -e "${RED}✗ E2E tests failed${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ E2E tests passed${NC}"
    echo ""
fi

# Legacy bash tests
echo -e "${YELLOW}Running Legacy Bash Tests...${NC}"
cd test_cases/arguments_mode

bash test_multi_args_suite.sh || {
    echo -e "${RED}✗ Multi-argument tests failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Multi-argument tests passed${NC}"
echo ""

bash run_tests.sh || {
    echo -e "${RED}✗ Backward compatibility tests failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Backward compatibility tests passed${NC}"
echo ""

cd "${REPO_ROOT}"

# Coverage report (if --cov was used)
if [ "$GENERATE_COVERAGE" = "1" ]; then
    echo -e "${YELLOW}Generating Coverage Report...${NC}"
    pytest tests/ --cov=bin/parallelr.py --cov-report=html --cov-report=term-missing
    echo -e "${GREEN}✓ Coverage report generated in htmlcov/${NC}"
    echo ""
fi

echo "=========================================="
echo -e "${GREEN}✓ All Tests Passed Successfully!${NC}"
echo "=========================================="
