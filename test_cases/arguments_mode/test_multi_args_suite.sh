#!/bin/bash
set -euo pipefail

# Multi-Argument Feature Test Suite
# Tests the new delimiter-based multi-argument support

echo "=== Multi-Argument Mode Test Suite ==="
echo "Testing from directory: $(pwd)"
echo ""

# Test 1: Space delimiter
echo "1. Testing space delimiter..."
OUTPUT=$(timeout 10 python ../../bin/parallelr.py \
    -T test_multi_args.sh \
    -A multi_args_space.txt \
    -S space \
    -E HOSTNAME,PORT,ENV \
    -C "bash @TASK@ @ARG_1@ @ARG_2@ @ARG_3@" \
    -r -m 3 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✓ Space delimiter test passed"
else
    echo "   ✗ Space delimiter test failed"
    echo "   Output: $OUTPUT"
    exit 1
fi

# Test 2: Tab delimiter
echo "2. Testing tab delimiter..."
OUTPUT=$(timeout 10 python ../../bin/parallelr.py \
    -T test_multi_args.sh \
    -A multi_args_tab.txt \
    -S tab \
    -E HOSTNAME,PORT,ENV \
    -C "bash @TASK@ @ARG_1@ @ARG_2@ @ARG_3@" \
    -r -m 3 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✓ Tab delimiter test passed"
else
    echo "   ✗ Tab delimiter test failed"
    echo "   Output: $OUTPUT"
    exit 1
fi

# Test 3: Comma delimiter with indexed placeholders
echo "3. Testing comma delimiter with indexed placeholders..."
OUTPUT=$(timeout 10 python ../../bin/parallelr.py \
    -T test_multi_args.sh \
    -A multi_args_comma.txt \
    -S comma \
    -E HOSTNAME,PORT,ENV \
    -C "bash @TASK@ @ARG_1@ @ARG_2@ @ARG_3@" \
    -r -m 5 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✓ Comma delimiter test passed"
else
    echo "   ✗ Comma delimiter test failed"
    echo "   Output: $OUTPUT"
    exit 1
fi

# Test 4: Semicolon delimiter
echo "4. Testing semicolon delimiter..."
OUTPUT=$(timeout 10 python ../../bin/parallelr.py \
    -T test_multi_args.sh \
    -A multi_args_semicolon.txt \
    -S semicolon \
    -E HOSTNAME,PORT,ENV \
    -C "bash @TASK@ @ARG_1@ @ARG_2@ @ARG_3@" \
    -r -m 3 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✓ Semicolon delimiter test passed"
else
    echo "   ✗ Semicolon delimiter test failed"
    echo "   Output: $OUTPUT"
    exit 1
fi

# Test 5: Pipe delimiter
echo "5. Testing pipe delimiter..."
OUTPUT=$(timeout 10 python ../../bin/parallelr.py \
    -T test_multi_args.sh \
    -A multi_args_pipe.txt \
    -S pipe \
    -E HOSTNAME,PORT,ENV \
    -C "bash @TASK@ @ARG_1@ @ARG_2@ @ARG_3@" \
    -r -m 3 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✓ Pipe delimiter test passed"
else
    echo "   ✗ Pipe delimiter test failed"
    echo "   Output: $OUTPUT"
    exit 1
fi

# Test 6: Colon delimiter
echo "6. Testing colon delimiter..."
OUTPUT=$(timeout 10 python ../../bin/parallelr.py \
    -T test_multi_args.sh \
    -A multi_args_colon.txt \
    -S colon \
    -E HOSTNAME,PORT,ENV \
    -C "bash @TASK@ @ARG_1@ @ARG_2@ @ARG_3@" \
    -r -m 3 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✓ Colon delimiter test passed"
else
    echo "   ✗ Colon delimiter test failed"
    echo "   Output: $OUTPUT"
    exit 1
fi

# Test 7: Fewer env vars than arguments (should log error but continue)
echo "7. Testing fewer env vars than arguments (validation warning)..."
OUTPUT=$(python ../../bin/parallelr.py \
    -T template.sh \
    -A multi_args_comma.txt \
    -S comma \
    -E HOSTNAME,PORT \
    -C "bash @TASK@" \
    -r -m 3 2>&1)
if echo "$OUTPUT" | grep -q "Environment variable count mismatch"; then
    echo "   ✓ Validation warning test passed"
else
    echo "   ✗ Validation warning test failed"
    exit 1
fi

# Test 8: More env vars than arguments (should fail)
echo "8. Testing more env vars than arguments (validation error)..."
OUTPUT=$(timeout 5 python ../../bin/parallelr.py \
    -T template.sh \
    -A multi_args_comma.txt \
    -S comma \
    -E HOSTNAME,PORT,ENV,EXTRA \
    -C "bash @TASK@" \
    -r 2>&1 || true)
if echo "$OUTPUT" | grep -q "Cannot proceed"; then
    echo "   ✓ Validation error test passed"
else
    echo "   ✗ Validation error test failed"
    echo "Output was: $OUTPUT"
    exit 1
fi

# Test 9: Backward compatibility - single argument without delimiter
echo "9. Testing backward compatibility (single argument)..."
OUTPUT=$(timeout 10 python ../../bin/parallelr.py \
    -T template.sh \
    -A hosts.txt \
    -E HOSTNAME \
    -C "bash @TASK@" \
    -r -m 3 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✓ Backward compatibility test passed"
else
    echo "   ✗ Backward compatibility test failed"
    echo "   Output: $OUTPUT"
    exit 1
fi

# Test 10: Indexed placeholders without environment variables
echo "10. Testing indexed placeholders without env vars..."
OUTPUT=$(timeout 10 python ../../bin/parallelr.py \
    -T template.sh \
    -A multi_args_comma.txt \
    -S comma \
    -C "bash -c 'echo @ARG_1@ @ARG_2@ @ARG_3@'" \
    -r -m 3 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✓ Indexed placeholders test passed"
else
    echo "   ✗ Indexed placeholders test failed"
    echo "   Output: $OUTPUT"
    exit 1
fi

# Test 11: Inconsistent argument counts (should fail)
echo "11. Testing inconsistent argument count validation..."
OUTPUT=$(timeout 5 python ../../bin/parallelr.py \
    -T template.sh \
    -A inconsistent_args.txt \
    -S comma \
    -C "bash @TASK@" 2>&1 || true)
if echo "$OUTPUT" | grep -q "Inconsistent argument counts"; then
    echo "   ✓ Inconsistent argument count validation passed"
else
    echo "   ✗ Inconsistent argument count validation failed"
    echo "Output was: $OUTPUT"
    exit 1
fi

# Test 12: Separator without arguments file (should fail)
echo "12. Testing -S without -A validation..."
OUTPUT=$(timeout 5 python ../../bin/parallelr.py \
    -T ../../test_cases/file_mode/task1.sh \
    -S comma \
    -C "bash @TASK@" 2>&1 || true)
if echo "$OUTPUT" | grep -q "separator can only be used with.*arguments-file"; then
    echo "   ✓ Separator validation passed"
else
    echo "   ✗ Separator validation failed"
    echo "Output was: $OUTPUT"
    exit 1
fi

# Test 13: Invalid placeholder index (should fail)
echo "13. Testing invalid placeholder index validation..."
OUTPUT=$(timeout 5 python ../../bin/parallelr.py \
    -T template.sh \
    -A two_args.txt \
    -S comma \
    -C "bash @TASK@ @ARG_1@ @ARG_2@ @ARG_3@" 2>&1 || true)
if echo "$OUTPUT" | grep -q "placeholder.*@ARG_3@.*only 2 argument"; then
    echo "   ✓ Placeholder index validation passed"
else
    echo "   ✗ Placeholder index validation failed"
    echo "Output was: $OUTPUT"
    exit 1
fi

# Test 14: Multiple invalid placeholders (should fail)
echo "14. Testing multiple invalid placeholders..."
OUTPUT=$(timeout 5 python ../../bin/parallelr.py \
    -T template.sh \
    -A two_args.txt \
    -S comma \
    -C "bash @TASK@ @ARG_4@ @ARG_5@" 2>&1 || true)
if echo "$OUTPUT" | grep -q "placeholder.*@ARG_4@.*@ARG_5@"; then
    echo "   ✓ Multiple placeholder validation passed"
else
    echo "   ✗ Multiple placeholder validation failed"
    echo "Output was: $OUTPUT"
    exit 1
fi

# Test 15: Dry run mode with multi-arguments
echo "15. Testing dry run mode display..."
OUTPUT=$(timeout 10 python ../../bin/parallelr.py \
    -T template.sh \
    -A multi_args_comma.txt \
    -S comma \
    -E HOSTNAME,PORT \
    -C "bash @TASK@ @ARG_1@ @ARG_2@" 2>&1)
if echo "$OUTPUT" | grep -q "server1.example.com" && echo "$OUTPUT" | grep -q "8080"; then
    echo "   ✓ Dry run display test passed"
else
    echo "   ✗ Dry run display test failed"
    echo "   Output: $OUTPUT"
    exit 1
fi

# Test 16: Unmatched placeholder detection (no arguments provided but placeholders used)
echo "16. Testing unmatched placeholder detection..."
OUTPUT=$(timeout 5 python ../../bin/parallelr.py \
    -T template.sh \
    -C "bash @TASK@ @ARG@ @ARG_1@" \
    -r 2>&1 || true)
if echo "$OUTPUT" | grep -q "unmatched argument placeholder"; then
    echo "   ✓ Unmatched placeholder detection passed"
else
    echo "   ✗ Unmatched placeholder detection failed"
    echo "Output was: $OUTPUT"
    exit 1
fi

# Test 17: Empty environment variable validation
echo "17. Testing empty environment variable detection..."
OUTPUT=$(timeout 5 python ../../bin/parallelr.py \
    -T template.sh \
    -A hosts.txt \
    -E 'VAR1, ,VAR3' \
    -C "bash @TASK@" 2>&1 || true)
if echo "$OUTPUT" | grep -q "empty entries"; then
    echo "   ✓ Empty env var detection passed"
else
    echo "   ✗ Empty env var detection failed"
    echo "Output was: $OUTPUT"
    exit 1
fi

echo ""
echo "=== All multi-argument tests passed successfully ==="
