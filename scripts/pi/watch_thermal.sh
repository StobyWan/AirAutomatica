#!/usr/bin/env bash
set -euo pipefail

# Watch thermal state, throttled flags, CPU freq, and load. Refresh every 1 second.
# Press Ctrl+C to exit.

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

read_cpu_freq() {
  if [[ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq ]]; then
    local hz
    hz=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo "0")
    echo "$((hz / 1000)) MHz"
  else
    echo "N/A"
  fi
}

read_load() {
  if [[ -f /proc/loadavg ]]; then
    awk '{print $1, $2, $3}' /proc/loadavg 2>/dev/null || echo "N/A"
  else
    echo "N/A"
  fi
}

# Print header once
printf "%-19s %6s %10s %-20s %10s %s\n" "timestamp" "temp" "throttled" "current" "CPU freq" "load"
printf "%-19s %6s %10s %-20s %10s %s\n" "-------------------" "------" "----------" "--------------------" "----------" "---"

while true; do
  ts=$(date '+%Y-%m-%d %H:%M:%S')
  temp=$(read_temp)
  raw=$(read_throttled)
  freq=$(read_cpu_freq)
  load=$(read_load)

  if [[ "$raw" != "N/A" ]]; then
    decode_throttled "$raw"
    current="$THROTTLED_CURRENT_COMPACT"
  else
    current="N/A"
  fi

  [[ "$temp" =~ ^[0-9] ]] && temp="${temp}C"
  printf "%-19s %6s %10s %-20s %10s %s\n" "$ts" "$temp" "$raw" "$current" "$freq" "$load"
  sleep 1
done
