#!/usr/bin/env bash
set -euo pipefail

# One-shot diagnostic snapshot. Prints to stdout and saves to tmp/pi-bench-snapshot-*.txt

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TMP_DIR="$REPO_ROOT/tmp"
# shellcheck source=throttled_decode.sh
source "$SCRIPT_DIR/throttled_decode.sh"

read_temp() {
  local t
  if command -v vcgencmd >/dev/null 2>&1; then
    t=$(vcgencmd measure_temp 2>/dev/null || true)
    if [[ "$t" =~ temp=([0-9.]+) ]]; then
      echo "${BASH_REMATCH[1]}"
      return
    fi
  fi
  if [[ -f /sys/class/thermal/thermal_zone0/temp ]]; then
    echo "$(($(cat /sys/class/thermal/thermal_zone0/temp) / 1000))"
  else
    echo "N/A"
  fi
}

read_throttled() {
  local out
  if command -v vcgencmd >/dev/null 2>&1; then
    out=$(vcgencmd get_throttled 2>/dev/null || true)
    if [[ "$out" =~ throttled=(0x[0-9a-fA-F]+) ]]; then
      echo "${BASH_REMATCH[1]}"
      return
    fi
  fi
  echo "N/A"
}

read_pi_model() {
  if [[ -f /proc/device-tree/model ]]; then
    tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo "N/A"
  elif [[ -f /sys/firmware/devicetree/base/model ]]; then
    tr -d '\0' < /sys/firmware/devicetree/base/model 2>/dev/null || echo "N/A"
  else
    echo "N/A"
  fi
}

collect_snapshot() {
  local temp raw
  temp=$(read_temp)
  raw=$(read_throttled)
  if [[ "$raw" != "N/A" ]]; then
    decode_throttled "$raw"
  else
    THROTTLED_CURRENT_SUMMARY="N/A"
    THROTTLED_HISTORICAL_SUMMARY="N/A"
    THROTTLED_CONCLUSION="vcgencmd not available"
  fi

  echo "=== AirAutomatica Pi Benchmark Snapshot ==="
  echo ""
  echo "--- System ---"
  echo "Hostname:  $(hostname)"
  echo "Date:      $(date)"
  echo "Uptime:    $(uptime -p 2>/dev/null || uptime)"
  echo "Pi model:  $(read_pi_model)"
  echo "Kernel:    $(uname -r)"
  echo ""
  echo "--- Thermal ---"
  [[ "$temp" =~ ^[0-9] ]] && temp="${temp}C"
  echo "Temp:      $temp"
  echo "Throttled: $raw"
  echo "Current:   $THROTTLED_CURRENT_SUMMARY"
  echo "Historical:$THROTTLED_HISTORICAL_SUMMARY"
  echo "Conclusion:$THROTTLED_CONCLUSION"
  echo ""
  echo "--- Memory ---"
  if command -v free &>/dev/null; then
    free -h | head -6
  elif [[ -f /proc/meminfo ]]; then
    head -5 /proc/meminfo
  else
    echo "Memory info not available"
  fi
  echo ""
  echo "--- Disk ---"
  df -h / 2>/dev/null || df -h 2>/dev/null || echo "Disk info not available"
  echo ""
  echo "--- Top 10 CPU ---"
  (ps aux --sort=-%cpu 2>/dev/null || ps -eo pid,pcpu,pmem,comm --sort=-pcpu 2>/dev/null || ps -e 2>/dev/null) | head -11 || true
  echo ""
  echo "--- Top 10 Memory ---"
  (ps aux --sort=-%mem 2>/dev/null || ps -eo pid,pcpu,pmem,comm --sort=-pmem 2>/dev/null || ps -e 2>/dev/null) | head -11 || true
}

main() {
  mkdir -p "$TMP_DIR"
  local stamp
  stamp=$(date '+%Y%m%d-%H%M%S')
  local outfile="$TMP_DIR/pi-bench-snapshot-$stamp.txt"

  local snapshot
  snapshot=$(collect_snapshot)
  echo "$snapshot"
  echo "$snapshot" > "$outfile"
  echo ""
  echo "Saved to: $outfile"
}

main "$@"
