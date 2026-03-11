#!/usr/bin/env bash
set -euo pipefail

# Log thermal and process metrics to CSV every 5 seconds until Ctrl+C.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TMP_DIR="$REPO_ROOT/tmp"

read_temp_c() {
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

read_cpu_freq_khz() {
  if [[ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq ]]; then
    cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo "N/A"
  else
    echo "N/A"
  fi
}

read_load1() {
  if [[ -f /proc/loadavg ]]; then
    awk '{print $1}' /proc/loadavg 2>/dev/null || echo "N/A"
  else
    echo "N/A"
  fi
}

# Escape CSV field (wrap in quotes if contains comma or quote)
csv_escape() {
  local v="$1"
  v="${v//\"/\"\"}"
  if [[ "$v" == *","* ]] || [[ "$v" == *'"'* ]] || [[ "$v" == *' '* ]]; then
    echo "\"$v\""
  else
    echo "$v"
  fi
}

trap 'echo ""; echo "Stopped. Log saved to: $outfile"; exit 0' INT

mkdir -p "$TMP_DIR"
stamp=$(date '+%Y%m%d-%H%M%S')
outfile="$TMP_DIR/pi-thermal-$stamp.csv"
echo "timestamp,temp_c,throttled_raw,cpu_freq_khz,load1,top_cpu_pid,top_cpu_name,top_cpu_percent" > "$outfile"
echo "Logging to $outfile (Ctrl+C to stop)..."

while true; do
  ts=$(date '+%Y-%m-%d %H:%M:%S')
  temp=$(read_temp_c)
  raw=$(read_throttled)
  freq=$(read_cpu_freq_khz)
  load1=$(read_load1)

  top_line=$(ps aux --sort=-%cpu 2>/dev/null | sed -n '2p' || ps -eo pid,pcpu,comm --sort=-pcpu 2>/dev/null | sed -n '2p' || true)
  if [[ -n "$top_line" ]]; then
    top_pid=$(echo "$top_line" | awk '{print $2}')
    top_pcpu=$(echo "$top_line" | awk '{print $3}')
    top_comm=$(echo "$top_line" | awk '{for(i=11;i<=NF;i++) printf "%s%s", $i, (i<NF?" ":"\n")}' 2>/dev/null)
    [[ -z "$top_comm" ]] && top_comm=$(echo "$top_line" | awk '{print $NF}')
    top_comm=$(csv_escape "$top_comm")
  else
    top_pid="N/A"
    top_pcpu="N/A"
    top_comm="N/A"
  fi

  echo "$ts,$temp,$raw,$freq,$load1,$top_pid,$top_comm,$top_pcpu" >> "$outfile"
  sleep 5
done
