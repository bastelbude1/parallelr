#!/usr/bin/env python
"""
Parallelr Summary Report (PSR) - Standalone JSONL to CSV reporting tool

Reads parallelr results files in JSONL format and generates CSV reports
with customizable columns and filtering.
"""

import sys
import json
import csv
import argparse
from pathlib import Path


def read_jsonl(file_path):
    """Read JSONL file and return session metadata and task results."""
    session = None
    tasks = []

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                if data.get('type') == 'session':
                    session = data
                elif data.get('type') == 'task':
                    tasks.append(data)
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping invalid JSON line: {e}", file=sys.stderr)

    return session, tasks


def get_nested_value(obj, path):
    """Get nested value from object using dot notation (e.g., 'env_vars.TASK_ID')."""
    keys = path.split('.')
    value = obj

    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list):
            try:
                index = int(key)
                value = value[index] if 0 <= index < len(value) else None
            except (ValueError, IndexError):
                value = None
        else:
            value = None

        if value is None:
            break

    return value


def filter_tasks(tasks, filter_expr):
    """Filter tasks based on filter expression (e.g., 'status=FAILED')."""
    if not filter_expr:
        return tasks

    filtered = []
    for task in tasks:
        # Parse filter: field=value or field!=value
        if '!=' in filter_expr:
            field, value = filter_expr.split('!=', 1)
            task_value = str(get_nested_value(task, field.strip()))
            if task_value != value.strip():
                filtered.append(task)
        elif '=' in filter_expr:
            field, value = filter_expr.split('=', 1)
            task_value = str(get_nested_value(task, field.strip()))
            if task_value == value.strip():
                filtered.append(task)

    return filtered


def generate_csv(tasks, columns, output_file=None):
    """Generate CSV output with specified columns."""
    # Default columns
    if not columns:
        columns = [
            'start_time', 'end_time', 'status', 'process_id', 'worker_id',
            'command_executed', 'exit_code', 'duration_seconds',
            'memory_mb', 'cpu_percent', 'error_message'
        ]
    else:
        columns = [c.strip() for c in columns.split(',')]

    # Collect all data rows
    data_rows = []
    for task in tasks:
        row = []
        for col in columns:
            value = get_nested_value(task, col)
            # Convert None to empty string, handle special types
            if value is None:
                row.append('')
            elif isinstance(value, (dict, list)):
                row.append(json.dumps(value))
            else:
                row.append(str(value))
        data_rows.append(row)

    # Prepare output - use newline='' for CSV writer when writing to file
    if output_file is None:
        output = sys.stdout
    else:
        output = open(output_file, 'w', newline='', encoding='utf-8')

    try:
        # Create CSV writer
        writer = csv.writer(output)

        # Write header row (uppercase column names)
        header_row = [col.upper() for col in columns]
        writer.writerow(header_row)

        # Write data rows
        for row in data_rows:
            writer.writerow(row)
    finally:
        if output_file is not None:
            output.close()


def print_statistics(session, tasks):
    """Print statistics about the execution."""
    if not tasks:
        print("No tasks found.")
        return

    total = len(tasks)
    by_status = {}
    total_duration = 0.0

    for task in tasks:
        status = task.get('status', 'UNKNOWN')
        by_status[status] = by_status.get(status, 0) + 1
        total_duration += task.get('duration_seconds', 0.0)

    avg_duration = total_duration / total if total > 0 else 0.0

    print("=" * 60)
    print("EXECUTION STATISTICS")
    print("=" * 60)

    if session:
        print(f"\nSession ID: {session.get('session_id')}")
        print(f"Hostname: {session.get('hostname')}")
        print(f"User: {session.get('user')}")
        print(f"Command Template: {session.get('command_template')}")

    print(f"\nTotal Tasks: {total}")
    print("\nBy Status:")
    for status, count in sorted(by_status.items()):
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {status}: {count} ({pct:.1f}%)")

    print(f"\nTotal Duration: {total_duration:.2f}s")
    print(f"Average Duration: {avg_duration:.2f}s per task")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Parallelr Summary Report - Generate CSV reports from JSONL results',
        epilog='Examples:\n'
               '  %(prog)s results.jsonl\n'
               '  %(prog)s results.jsonl --columns start_time,status,env_vars.TASK_ID,exit_code\n'
               '  %(prog)s results.jsonl --filter status=FAILED\n'
               '  %(prog)s results.jsonl --stats\n'
               '  %(prog)s results.jsonl --output report.csv',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('jsonl_file', help='Path to parallelr results.jsonl file')

    parser.add_argument('--columns', '-c',
                       help='Comma-separated list of columns (supports nested fields like env_vars.TASK_ID)')

    parser.add_argument('--filter', '-f',
                       help='Filter tasks (e.g., status=FAILED, status!=SUCCESS)')

    parser.add_argument('--output', '-o',
                       help='Output CSV file (default: stdout)')

    parser.add_argument('--stats', '-s', action='store_true',
                       help='Print statistics instead of CSV')

    args = parser.parse_args()

    # Check if file exists
    if not Path(args.jsonl_file).exists():
        print(f"Error: File not found: {args.jsonl_file}", file=sys.stderr)
        sys.exit(1)

    # Read JSONL file
    try:
        session, tasks = read_jsonl(args.jsonl_file)
    except (IOError, OSError) as e:
        print(f"Error reading JSONL file: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSONL file: {e}", file=sys.stderr)
        sys.exit(1)

    # Filter tasks if requested
    if args.filter:
        tasks = filter_tasks(tasks, args.filter)

    # Generate output
    if args.stats:
        print_statistics(session, tasks)
    else:
        generate_csv(tasks, args.columns, args.output)


if __name__ == '__main__':
    main()
