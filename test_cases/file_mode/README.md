# File Mode Test Cases

This directory contains test cases for the traditional file mode (backward compatibility test).

## Files

- `task1.sh`, `task2.sh`, `task3.sh` - Simple test scripts that execute independently

## Test Commands

### Test traditional directory-based discovery
```bash
# Dry run
python bin/parallelr.py -T test_cases/file_mode -C "bash @TASK@"

# Execute
python bin/parallelr.py -T test_cases/file_mode -C "bash @TASK@" -r
```

### Test with specific files
```bash
# Dry run
python bin/parallelr.py -T test_cases/file_mode/task1.sh -T test_cases/file_mode/task2.sh -C "bash @TASK@"

# Execute
python bin/parallelr.py -T test_cases/file_mode/task1.sh -T test_cases/file_mode/task2.sh -C "bash @TASK@" -r
```

## Expected Behavior

- Each `.sh` file in the directory becomes a separate task
- Tasks execute independently in parallel
- Traditional behavior should be preserved