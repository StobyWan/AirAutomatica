# Video Playback Fix Design (Pre-Deploy Validation)

**Date**: 2026-03-11
**Status**: Implemented (fragmented MP4), pending Pi verification

## Problem

Recordings open in VLC but do not play. Root cause: when rpicam-vid pipes raw h264 to ffmpeg with `-movflags +faststart`, ffmpeg writes the moov atom at the end, then rewrites the file to move it to the start. If the pipe closes before ffmpeg finishes, the file is truncated and unplayable.

## Solution: Fragmented MP4

Switched ffmpeg movflags from `+faststart` to `frag_keyframe+empty_moov+default_base_moof` in [camera_recording.py](../../src/airautomatica/services/camera_recording.py).

- **frag_keyframe**: Fragments at keyframes; each fragment is self-contained
- **empty_moov**: Moov atom written at start (required for pipe/streaming)
- **default_base_moof**: Proper fragment timing

## Research Summary

| Source | Approach | Relevance |
|--------|----------|-----------|
| Stack Overflow 55698581 | `frag_keyframe+empty_moov` for raw h264 pipe | Explicitly recommended |
| Pi Forums 384633 | `--codec libav --libav-format mpegts` | Requires libav; codebase avoids it |
| Pi regression (Forums 332970) | `empty_moov` + h264_v4l2m2m | Does not apply; we use `-c copy` |

## Alternatives Considered

- **MPEG-TS pipe**: Would require libav; tests explicitly avoid it for Pi 5 baseline
- **Longer muxer wait**: Does not fix core issue; pipe close timing unchanged

## Pre-Deploy Verification

Run on a Pi before deploying:

```bash
make pi-verify-video
# or: uv run python scripts/pi/verify_video_playback.py
```

1. **Smoke test**: Record 10–15 seconds, stop. Open `.mp4` in VLC; confirm playback.
2. **Short recording**: Record 2–3 seconds, stop. Verify short file plays.
3. **Unexpected exit**: Kill camera mid-recording. Confirm cleanup and partial file behavior.

If "No start code" errors occur, simplify to `frag_keyframe+empty_moov` (remove `default_base_moof`).

## Rollback

Revert the `-movflags` change to `+faststart` if fragmented MP4 fails in production.
