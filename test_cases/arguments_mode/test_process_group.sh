#!/bin/bash
# Test script that spawns child processes to verify process group termination

echo "Parent PID: $$"
echo "Parent PGID: $(ps -o pgid= -p $$)"

# Spawn a child process that sleeps
(sleep 30 & echo "Child 1 PID: $!") &
child1=$!

# Spawn another child
(sleep 30 & echo "Child 2 PID: $!") &
child2=$!

echo "Spawned children: $child1, $child2"

# Sleep for a while to allow timeout test
sleep 60

echo "This should not appear if timeout works correctly"