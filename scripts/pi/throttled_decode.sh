# throttled_decode.sh - Sourceable library for decoding Raspberry Pi throttled flags
# Usage: source "$(dirname "$0")/throttled_decode.sh"  (or similar)
#        decode_throttled <raw_value>
# raw_value can be hex (0xe0000) or decimal. Sets THROTTLED_* variables.

# Current flags (low nibble)
# 0x1 = undervoltage now
# 0x2 = arm frequency capped now
# 0x4 = throttling now
# 0x8 = soft temp limit now
# Historical flags (high bits)
# 0x10000 = undervoltage occurred
# 0x20000 = arm frequency capping occurred
# 0x40000 = throttling occurred
# 0x80000 = soft temp limit occurred

decode_throttled() {
  local raw="$1"
  THROTTLED_CURRENT_SUMMARY=""
  THROTTLED_HISTORICAL_SUMMARY=""
  THROTTLED_CONCLUSION=""
  THROTTLED_CURRENT_COMPACT=""

  # Parse hex or decimal
  local val=0
  if [[ -z "$raw" ]] || [[ "$raw" == "N/A" ]]; then
    THROTTLED_CURRENT_SUMMARY="N/A"
    THROTTLED_HISTORICAL_SUMMARY="N/A"
    THROTTLED_CONCLUSION="No throttled value provided."
    THROTTLED_CURRENT_COMPACT="N/A"
    return 0
  fi
  if [[ "$raw" =~ ^0x[0-9a-fA-F]+$ ]]; then
    val=$((raw))
  elif [[ "$raw" =~ ^[0-9]+$ ]]; then
    val=$((raw))
  else
    THROTTLED_CURRENT_SUMMARY="N/A"
    THROTTLED_HISTORICAL_SUMMARY="N/A"
    THROTTLED_CONCLUSION="Invalid throttled value: $raw"
    THROTTLED_CURRENT_COMPACT="N/A"
    return 0
  fi

  # Current flags (0x0F)
  local current_parts=()
  (( (val & 0x1) )) && current_parts+=("undervoltage")
  (( (val & 0x2) )) && current_parts+=("arm-capped")
  (( (val & 0x4) )) && current_parts+=("throttling")
  (( (val & 0x8) )) && current_parts+=("soft-temp-limit")
  if [[ ${#current_parts[@]} -eq 0 ]]; then
    THROTTLED_CURRENT_SUMMARY="none"
    THROTTLED_CURRENT_COMPACT="ok"
  else
    THROTTLED_CURRENT_SUMMARY=$(IFS=,; echo "${current_parts[*]}")
    THROTTLED_CURRENT_COMPACT=$(IFS=,; echo "${current_parts[*]}")
  fi

  # Historical flags
  local hist_parts=()
  (( (val & 0x10000) )) && hist_parts+=("undervoltage")
  (( (val & 0x20000) )) && hist_parts+=("arm-capped")
  (( (val & 0x40000) )) && hist_parts+=("throttling")
  (( (val & 0x80000) )) && hist_parts+=("soft-temp-limit")
  if [[ ${#hist_parts[@]} -eq 0 ]]; then
    THROTTLED_HISTORICAL_SUMMARY="none"
  else
    THROTTLED_HISTORICAL_SUMMARY=$(IFS=,; echo "${hist_parts[*]}")
  fi

  # Plain-English conclusion
  if [[ "$THROTTLED_CURRENT_SUMMARY" == "none" ]]; then
    if [[ "$THROTTLED_HISTORICAL_SUMMARY" == "none" ]]; then
      THROTTLED_CONCLUSION="No throttling detected. System is healthy."
    else
      THROTTLED_CONCLUSION="No current throttling. Historical issues: $THROTTLED_HISTORICAL_SUMMARY."
    fi
  else
    THROTTLED_CONCLUSION="CURRENT throttling: $THROTTLED_CURRENT_SUMMARY. Check power supply and cooling."
  fi
}
