#!/bin/bash
# Test to verify multiple argument-based tasks don't collide
# Each task should have a unique HOSTNAME value

echo "Task running with HOSTNAME=$HOSTNAME"
echo "Worker PID: $$"
echo "Parent PPID: $PPID"

# Verify HOSTNAME is set and not empty
if [ -z "$HOSTNAME" ]; then
    echo "ERROR: HOSTNAME not set!"
    exit 1
fi

# Brief sleep to simulate work
sleep 0.5

echo "Completed successfully for $HOSTNAME"