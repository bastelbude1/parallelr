#!/bin/bash
set -euo pipefail

# Test script for multi-argument support
#
# Purpose: Validates that parallelr correctly handles:
# - Multiple arguments per line with different delimiters
# - Indexed placeholders @ARG_1@, @ARG_2@, @ARG_3@
# - Multiple environment variables
# - Proper validation of env var count vs argument count
#
# Success criteria:
# - All arguments are received correctly
# - Environment variables are set correctly
# - Script exits with code 0 on success

echo "=== Multi-Argument Test ==="
echo "Received arguments:"
echo "  ARG_1: '${1:-}'"
echo "  ARG_2: '${2:-}'"
echo "  ARG_3: '${3:-}'"

echo "Environment variables:"
echo "  HOSTNAME: '${HOSTNAME:-}'"
echo "  PORT: '${PORT:-}'"
echo "  ENV: '${ENV:-}'"

# Validate all arguments are provided
if [ $# -lt 3 ]; then
    echo "ERROR: Expected 3 arguments, got $#"
    exit 1
fi

# Validate environment variables match arguments
if [ "${HOSTNAME:-}" != "${1}" ]; then
    echo "ERROR: HOSTNAME (${HOSTNAME:-}) does not match ARG_1 (${1})"
    exit 1
fi

if [ "${PORT:-}" != "${2}" ]; then
    echo "ERROR: PORT (${PORT:-}) does not match ARG_2 (${2})"
    exit 1
fi

if [ "${ENV:-}" != "${3}" ]; then
    echo "ERROR: ENV (${ENV:-}) does not match ARG_3 (${3})"
    exit 1
fi

echo "✓ Multi-argument test passed for: '${1}' '${2}' '${3}'"
exit 0
