#!/usr/bin/env python3
"""Pre-deploy verification for fragmented MP4 video playback fix.

Run on a Pi with camera and rpicam-vid/ffmpeg. Creates test recordings and
prints paths for manual VLC playback verification.

Usage:
  uv run python scripts/pi/verify_video_playback.py
  # Or: python -m scripts.pi.verify_video_playback (from project root)
"""

import sys
import tempfile
import time
from pathlib import Path

# Add project root for imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from airautomatica.services.camera_recording import CameraRecordingService


def main() -> None:
    recordings_dir = (
        Path(tempfile.mkdtemp(prefix="airautomatica_verify_")) / "recordings"
    )
    recordings_dir.mkdir(parents=True, exist_ok=True)
    svc = CameraRecordingService(recordings_dir=str(recordings_dir))

    if not svc.is_available():
        print("SKIP: rpicam-vid or libcamera-vid not found. Run on a Pi with camera.")
        sys.exit(0)

    print("=== Video Playback Pre-Deploy Verification ===\n")
    files: list[Path] = []

    try:
        # 1. Smoke test: 12 seconds
        print("1. Smoke test (12s recording)...")
        state, err = svc.start_recording()
        if err:
            print(f"   FAIL: {err}")
            sys.exit(1)
        time.sleep(12)
        state, err = svc.stop_recording()
        if err:
            print(f"   FAIL on stop: {err}")
        elif state.last_recorded_file:
            p = recordings_dir / state.last_recorded_file
            files.append(p)
            print(f"   OK: {p}")

        # 2. Short recording: 3 seconds
        print("\n2. Short recording (3s)...")
        state, err = svc.start_recording()
        if err:
            print(f"   FAIL: {err}")
            sys.exit(1)
        time.sleep(3)
        state, err = svc.stop_recording()
        if err:
            print(f"   FAIL on stop: {err}")
        elif state.last_recorded_file:
            p = recordings_dir / state.last_recorded_file
            files.append(p)
            print(f"   OK: {p}")

        print("\n--- Manual VLC verification ---")
        print("Open each file in VLC and confirm playback:")
        for f in files:
            print(f"  {f}")
        print(
            "\n3. Unexpected exit (manual): Start recording, kill rpicam-vid mid-stream,"
        )
        print(
            "   then call get_recording_state. Confirm cleanup and partial file behavior."
        )
        print("\nDone.")
    finally:
        print(f"\nRecordings kept in: {recordings_dir.parent}")


if __name__ == "__main__":
    main()
