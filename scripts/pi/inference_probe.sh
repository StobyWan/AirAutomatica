#!/usr/bin/env bash
set -euo pipefail

# Run a short Ollama inference and capture thermal state before/after.

MODEL="${1:-gemma3:1b}"

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

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama not installed. Install from https://ollama.com"
  exit 0
fi

temp_before=$(read_temp)
throttled_before=$(read_throttled)

start=$(date +%s)
ollama run "$MODEL" "Say hello in one word." >/dev/null 2>&1 || true
end=$(date +%s)
elapsed=$((end - start))

temp_after=$(read_temp)
throttled_after=$(read_throttled)

[[ "$temp_before" =~ ^[0-9] ]] && temp_before="${temp_before}C"
[[ "$temp_after" =~ ^[0-9] ]] && temp_after="${temp_after}C"

echo "=== Ollama inference probe ==="
echo "Model: $MODEL"
echo "Temp before: $temp_before  after: $temp_after"
echo "Throttled before: $throttled_before  after: $throttled_after"
echo "Elapsed: ${elapsed}s"
