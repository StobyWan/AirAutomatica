#!/usr/bin/env bash
set -euo pipefail

# Compare two bench_snapshot.sh output files. Usage: compare_snapshots.sh <before> <after>

usage() {
  echo "Usage: compare_snapshots.sh <before_snapshot.txt> <after_snapshot.txt>"
  exit 1
}

[[ $# -lt 2 ]] && usage

before="$1"
after="$2"
[[ ! -f "$before" ]] && { echo "Error: $before not found"; exit 1; }
[[ ! -f "$after" ]] && { echo "Error: $after not found"; exit 1; }

parse_temp() {
  grep -E '^Temp:' "$1" 2>/dev/null | sed 's/^Temp:[[:space:]]*//' || echo "N/A"
}

parse_throttled() {
  grep -E '^Throttled:' "$1" 2>/dev/null | sed 's/^Throttled:[[:space:]]*//' || echo "N/A"
}

parse_mem_used() {
  grep -E '^Mem:' "$1" 2>/dev/null | awk '{print $3}' || echo "N/A"
}

# Extract first data line from "--- Top 10 CPU ---" section: process name and %CPU
parse_top_cpu() {
  local in_section=0
  while IFS= read -r line; do
    if [[ "$line" == *"--- Top 10 CPU ---"* ]]; then
      in_section=1
      continue
    fi
    if [[ $in_section -eq 1 ]]; then
      # Skip section headers (--- ... ---) and blank lines
      [[ "$line" == *"---"* ]] && continue
      [[ -z "${line// }" ]] && continue
      # Skip ps header line (USER PID %CPU ...)
      [[ "$line" =~ ^[[:space:]]*[A-Za-z]+[[:space:]]+PID ]] && continue
      # Data line: extract %CPU (col 3) and command (col 11+)
      local pcpu comm
      pcpu=$(echo "$line" | awk '{print $3}')
      comm=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s%s", $i, (i<NF?" ":"\n")}')
      [[ -z "$comm" ]] && comm=$(echo "$line" | awk '{print $NF}')
      [[ -n "$pcpu" && -n "$comm" ]] && echo "$comm ($pcpu%)" && return
      [[ -n "$line" ]] && echo "$line" && return
    fi
  done < "$1"
  echo "N/A"
}

parse_top_mem() {
  local in_section=0
  while IFS= read -r line; do
    if [[ "$line" == *"--- Top 10 Memory ---"* ]]; then
      in_section=1
      continue
    fi
    if [[ $in_section -eq 1 ]]; then
      [[ "$line" == *"---"* ]] && continue
      [[ -z "${line// }" ]] && continue
      [[ "$line" =~ ^[[:space:]]*[A-Za-z]+[[:space:]]+PID ]] && continue
      local pmem comm
      pmem=$(echo "$line" | awk '{print $4}')
      comm=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s%s", $i, (i<NF?" ":"\n")}')
      [[ -z "$comm" ]] && comm=$(echo "$line" | awk '{print $NF}')
      [[ -n "$pmem" && -n "$comm" ]] && echo "$comm ($pmem%)" && return
      [[ -n "$line" ]] && echo "$line" && return
    fi
  done < "$1"
  echo "N/A"
}

t_before=$(parse_temp "$before")
t_after=$(parse_temp "$after")
th_before=$(parse_throttled "$before")
th_after=$(parse_throttled "$after")
mem_before=$(parse_mem_used "$before")
mem_after=$(parse_mem_used "$after")
cpu_before=$(parse_top_cpu "$before")
cpu_after=$(parse_top_cpu "$after")
memproc_before=$(parse_top_mem "$before")
memproc_after=$(parse_top_mem "$after")

echo "=== Snapshot comparison ==="
echo "Before: $before"
echo "After:  $after"
echo ""
printf "%-14s %-12s -> %-12s\n" "Temp:" "$t_before" "$t_after"
printf "%-14s %-12s -> %-12s\n" "Throttled:" "$th_before" "$th_after"
printf "%-14s %-12s -> %-12s\n" "Memory used:" "$mem_before" "$mem_after"
printf "%-14s %-24s -> %-24s\n" "Top CPU:" "$cpu_before" "$cpu_after"
printf "%-14s %-24s -> %-24s\n" "Top memory:" "$memproc_before" "$memproc_after"
