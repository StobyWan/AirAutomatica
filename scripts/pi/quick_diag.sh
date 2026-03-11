#!/usr/bin/env bash
set -euo pipefail

# Concise SSH-friendly diagnostic. One-shot checks.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

main() {
  local raw
  raw=$(read_throttled)
  if [[ "$raw" != "N/A" ]]; then
    decode_throttled "$raw"
  else
    THROTTLED_CURRENT_SUMMARY="N/A"
    THROTTLED_HISTORICAL_SUMMARY="N/A"
    THROTTLED_CONCLUSION="vcgencmd not available"
  fi

  local t
  t=$(read_temp)
  [[ "$t" =~ ^[0-9] ]] && t="${t}C"
  echo "--- Quick Diag ---"
  echo "temp:      $t"
  echo "throttled: $raw"
  echo "current:   $THROTTLED_CURRENT_SUMMARY"
  echo "historical:$THROTTLED_HISTORICAL_SUMMARY"
  echo ""
  echo "--- Memory ---"
  if command -v free &>/dev/null; then free -h | head -2; else echo "free not available"; fi
  echo ""
  echo "--- Disk ---"
  df -h / 2>/dev/null | tail -1 || df -h 2>/dev/null | tail -1 || echo "df not available"
  echo ""
  echo "--- Top 5 CPU ---"
  (ps aux --sort=-%cpu 2>/dev/null || ps -eo pid,pcpu,pmem,comm --sort=-pcpu 2>/dev/null || ps -e 2>/dev/null) | head -6 || true
  echo ""
  echo "--- Serial ---"
  ls /dev/ttyAMA* /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "none"
  echo ""
  echo "--- Video ---"
  ls /dev/video* 2>/dev/null || echo "none"
}

main "$@"
