# Arguments Mode Test Cases

This directory contains test cases for the new arguments mode feature in parallelr.

## Files

- `template.sh` - Test template that uses HOSTNAME environment variable
- `test_both.sh` - Test template that uses both environment variable and command-line argument
- `hosts.txt` - Sample arguments file with hostnames (one per line)

## Test Commands

### 1. Basic Arguments Mode with Environment Variable
```bash
# Dry run
python bin/parallelr.py -T test_cases/arguments_mode/template.sh -A test_cases/arguments_mode/hosts.txt -E HOSTNAME -C "bash @TASK@"

# Execute with 2 workers
python bin/parallelr.py -T test_cases/arguments_mode/template.sh -A test_cases/arguments_mode/hosts.txt -E HOSTNAME -C "bash @TASK@" -r -m 2
```

### 2. Arguments Mode with @ARG@ Replacement
```bash
# Dry run
python bin/parallelr.py -T test_cases/arguments_mode/template.sh -A test_cases/arguments_mode/hosts.txt -C "bash @TASK@ --host @ARG@"

# Execute
python bin/parallelr.py -T test_cases/arguments_mode/template.sh -A test_cases/arguments_mode/hosts.txt -C "bash @TASK@ --host @ARG@" -r
```

### 3. Both Environment Variable and @ARG@ Replacement
```bash
# Dry run
python bin/parallelr.py -T test_cases/arguments_mode/test_both.sh -A test_cases/arguments_mode/hosts.txt -E HOSTNAME -C "bash @TASK@ @ARG@"

# Execute
python bin/parallelr.py -T test_cases/arguments_mode/test_both.sh -A test_cases/arguments_mode/hosts.txt -E HOSTNAME -C "bash @TASK@ @ARG@" -r
```

### 4. ptasker Mode (Auto-sets HOSTNAME)
```bash
# Dry run (automatically sets HOSTNAME environment variable)
bin/ptasker -T test_cases/arguments_mode/template.sh -A test_cases/arguments_mode/hosts.txt

# Execute with custom project name
bin/ptasker -T test_cases/arguments_mode/template.sh -A test_cases/arguments_mode/hosts.txt -p myproject -r
```

## Expected Behavior

- Each line in `hosts.txt` becomes a separate parallel task
- Comment lines (starting with #) and empty lines are skipped
- With `-E HOSTNAME`, each task runs with HOSTNAME environment variable set to the line value
- With `@ARG@` in command, it's replaced with the line value
- ptasker mode automatically sets HOSTNAME when using `-A`

## Output Files

Check the logs directory for:
- Main execution log
- Summary CSV with task results
- Output file with stdout/stderr from each task