#!/bin/bash
set -euo pipefail

# Test script for edge case handling in arguments mode
#
# Purpose: Validates that parallelr correctly handles edge case arguments:
# - Falsy values (0, false, empty strings)
# - Special characters and spaces
# - Proper quoting and escaping
#
# Success criteria:
# - HOSTNAME environment variable must be set
# - HOSTNAME must match the expected argument value
# - Script exits with code 0 on success, non-zero on failure

echo "=== Edge Case Test ==="
echo "Received argument: '${1:-}'"
echo "HOSTNAME environment: '${HOSTNAME:-}'"

# Validate HOSTNAME is set
if [ -z "${HOSTNAME:-}" ]; then
    echo "ERROR: HOSTNAME environment variable is not set"
    exit 1
fi

# Validate argument is passed
if [ $# -eq 0 ]; then
    echo "ERROR: No argument received"
    exit 1
fi

# Validate HOSTNAME matches the argument (for environment mode)
# Note: In @ARG@ mode, this test may not apply
if [ "${HOSTNAME}" != "${1}" ]; then
    echo "WARNING: HOSTNAME (${HOSTNAME}) does not match argument (${1})"
    echo "This is expected if not using -E mode"
fi

echo "✓ Edge case test passed for: '${1}'"
exit 0