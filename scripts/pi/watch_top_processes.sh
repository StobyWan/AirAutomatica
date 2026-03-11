#!/usr/bin/env bash
set -euo pipefail

# Watch top CPU and memory processes. Refresh every 2 seconds.
# Press Ctrl+C to exit.

show_top() {
  clear
  echo "=== Top CPU processes ==="
  (ps aux --sort=-%cpu 2>/dev/null || ps -eo pid,pcpu,pmem,comm --sort=-pcpu 2>/dev/null || ps -e 2>/dev/null) | head -12 || true
  echo ""
  echo "=== Top memory processes ==="
  (ps aux --sort=-%mem 2>/dev/null || ps -eo pid,pcpu,pmem,comm --sort=-pmem 2>/dev/null || ps -e 2>/dev/null) | head -12 || true
  echo ""
  echo "Refreshing every 2s (Ctrl+C to exit)..."
}

while true; do
  show_top
  sleep 2
done
