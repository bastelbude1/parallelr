#!/bin/bash
# Test script for arguments mode feature

set -e

echo "=== Arguments Mode Test Suite ==="
echo "Testing from directory: $(pwd)"
echo ""

# Change to parallelr root directory
cd ../..

echo "1. Testing basic environment variable mode..."
echo "   Command: python bin/parallelr.py -T test_cases/arguments_mode/template.sh -A test_cases/arguments_mode/hosts.txt -E HOSTNAME -C \"bash @TASK@\""
python bin/parallelr.py -T test_cases/arguments_mode/template.sh -A test_cases/arguments_mode/hosts.txt -E HOSTNAME -C "bash @TASK@" | head -10
echo ""

echo "2. Testing @ARG@ replacement mode..."
echo "   Command: python bin/parallelr.py -T test_cases/arguments_mode/template.sh -A test_cases/arguments_mode/hosts.txt -C \"bash @TASK@ --host @ARG@\""
python bin/parallelr.py -T test_cases/arguments_mode/template.sh -A test_cases/arguments_mode/hosts.txt -C "bash @TASK@ --host @ARG@" | head -10
echo ""

echo "3. Testing both environment and @ARG@..."
echo "   Command: python bin/parallelr.py -T test_cases/arguments_mode/test_both.sh -A test_cases/arguments_mode/hosts.txt -E HOSTNAME -C \"bash @TASK@ @ARG@\""
python bin/parallelr.py -T test_cases/arguments_mode/test_both.sh -A test_cases/arguments_mode/hosts.txt -E HOSTNAME -C "bash @TASK@ @ARG@" | head -10
echo ""

echo "4. Testing ptasker mode (auto HOSTNAME)..."
echo "   Command: bin/ptasker -T test_cases/arguments_mode/template.sh -A test_cases/arguments_mode/hosts.txt"
bin/ptasker -T test_cases/arguments_mode/template.sh -A test_cases/arguments_mode/hosts.txt 2>&1 | head -15
echo ""

echo "5. Running actual execution test with 2 workers..."
echo "   Command: python bin/parallelr.py -T test_cases/arguments_mode/test_both.sh -A test_cases/arguments_mode/hosts.txt -E HOSTNAME -C \"bash @TASK@ @ARG@\" -r -m 2"
python bin/parallelr.py -T test_cases/arguments_mode/test_both.sh -A test_cases/arguments_mode/hosts.txt -E HOSTNAME -C "bash @TASK@ @ARG@" -r -m 2 > /tmp/test_output.txt 2>&1

if grep -q "Completed Successfully: 5" /tmp/test_output.txt; then
    echo "✓ Execution test passed - 5 tasks completed successfully"
else
    echo "✗ Execution test failed"
    cat /tmp/test_output.txt
    exit 1
fi

echo ""
echo "=== All tests passed successfully ==="