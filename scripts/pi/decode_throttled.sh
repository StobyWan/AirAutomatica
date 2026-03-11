#!/usr/bin/env bash
set -euo pipefail

# Decode Raspberry Pi throttled flags from vcgencmd get_throttled or optional argument.
# Exit nonzero only on script error, not when throttling is detected.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=throttled_decode.sh
source "$SCRIPT_DIR/throttled_decode.sh"

get_throttled_raw() {
  local out
  if ! command -v vcgencmd >/dev/null 2>&1; then
    echo ""
    return 1
  fi
  out=$(vcgencmd get_throttled 2>/dev/null || true)
  if [[ "$out" =~ throttled=(0x[0-9a-fA-F]+) ]]; then
    echo "${BASH_REMATCH[1]}"
    return 0
  fi
  echo ""
  return 1
}

main() {
  local raw
  if [[ -n "${1:-}" ]]; then
    raw="$1"
  else
    raw=$(get_throttled_raw) || true
    if [[ -z "$raw" ]]; then
      echo "vcgencmd not available or failed. Pass throttled value as argument, e.g. 0xe0000" >&2
      exit 1
    fi
  fi

  decode_throttled "$raw"

  echo "Raw value:        $raw"
  echo "Current issues:   $THROTTLED_CURRENT_SUMMARY"
  echo "Historical:       $THROTTLED_HISTORICAL_SUMMARY"
  echo ""
  echo "$THROTTLED_CONCLUSION"
}

main "$@"
