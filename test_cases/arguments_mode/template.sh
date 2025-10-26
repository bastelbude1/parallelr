#!/bin/bash
set -euo pipefail
echo "Processing with HOSTNAME=$HOSTNAME"
echo "Script file: ${1:-}"
echo "Timestamp: $(date)"
sleep 1