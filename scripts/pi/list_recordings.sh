#!/usr/bin/env bash
set -euo pipefail

# List, count, or play AirAutomatica recordings on Pi.
# Uses AIRAUTOMATICA_RECORDINGS_DIR or RECORDINGS_DIR env, else default path.

RECORDINGS_DIR="${AIRAUTOMATICA_RECORDINGS_DIR:-${RECORDINGS_DIR:-/var/lib/airautomatica/.airautomatica/recordings}}"
LIST_LIMIT=30

usage() {
  echo "Usage: $0 [--count] [--play] [--min-size N]"
  echo "  Default: list newest ${LIST_LIMIT} recordings"
  echo "  --count     Print total count of .mp4 files"
  echo "  --play      Play most recent recording (vlc, mpv, or ffplay)"
  echo "  --min-size N  Exclude files smaller than N (e.g. 1k, 100k)"
  echo ""
  echo "Recordings dir: $RECORDINGS_DIR"
}

main() {
  local do_count=false
  local do_play=false
  local min_size=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --count)   do_count=true; shift ;;
      --play)    do_play=true; shift ;;
      --min-size) min_size="$2"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
  done

  if [[ ! -d "$RECORDINGS_DIR" ]]; then
    echo "Recordings dir not found: $RECORDINGS_DIR" >&2
    exit 1
  fi

  if [[ "$do_count" == true ]]; then
    if [[ -n "$min_size" ]]; then
      find "$RECORDINGS_DIR" -maxdepth 1 -name "*.mp4" -size "+${min_size}" 2>/dev/null | wc -l
    else
      ls "$RECORDINGS_DIR"/*.mp4 2>/dev/null | wc -l
    fi
    return
  fi

  if [[ "$do_play" == true ]]; then
    local latest
    if [[ -n "$min_size" ]]; then
      latest=$(find "$RECORDINGS_DIR" -maxdepth 1 -name "*.mp4" -size "+${min_size}" -print0 2>/dev/null | xargs -0 -r ls -t 2>/dev/null | head -1)
    else
      latest=$(ls -t "$RECORDINGS_DIR"/*.mp4 2>/dev/null | head -1)
    fi
    if [[ -z "$latest" || ! -f "$latest" ]]; then
      echo "No recording to play" >&2
      exit 1
    fi
    if command -v vlc >/dev/null 2>&1; then
      vlc "$latest" 2>/dev/null &
    elif command -v mpv >/dev/null 2>&1; then
      mpv "$latest" 2>/dev/null
    elif command -v ffplay >/dev/null 2>&1; then
      ffplay -nodisp -autoexit "$latest" 2>/dev/null
    else
      echo "No player found (vlc, mpv, or ffplay)" >&2
      exit 1
    fi
    return
  fi

  # Default: list newest
  if [[ -n "$min_size" ]]; then
    find "$RECORDINGS_DIR" -maxdepth 1 -name "*.mp4" -size "+${min_size}" -print0 2>/dev/null | xargs -0 -r ls -lht 2>/dev/null | head -"$LIST_LIMIT"
  else
    ls -lht "$RECORDINGS_DIR"/*.mp4 2>/dev/null | head -"$LIST_LIMIT"
  fi
}

main "$@"
