"""Live camera preview stream. Uses rpicam-still in a loop when not recording."""

import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Iterator

logger = logging.getLogger(__name__)

_PREVIEW_INTERVAL_SEC = 0.15  # ~6–7 fps
_CAPTURE_TIMEOUT_SEC = 5
_BOUNDARY = b"frame"


def _capture_frame() -> bytes | None:
    """Capture one JPEG frame via rpicam-still. Returns None on failure."""
    rpicam = shutil.which("rpicam-still")
    if not rpicam:
        return None
    path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            path = Path(f.name)
        result = subprocess.run(
            [
                rpicam,
                "-t",
                "1",
                "--immediate",
                "-n",
                "-o",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=_CAPTURE_TIMEOUT_SEC,
        )
        if result.returncode != 0:
            logger.debug("Preview capture failed: %s", result.stderr or result.stdout)
            return None
        if not path.exists():
            return None
        return path.read_bytes()
    except subprocess.TimeoutExpired:
        logger.debug("Preview capture timed out")
        return None
    except OSError as e:
        logger.debug("Preview capture error: %s", e)
        return None
    finally:
        if path is not None and path.exists():
            path.unlink(missing_ok=True)


def stream_preview_frames(
    is_recording: Callable[[], bool],
) -> Iterator[bytes]:
    """Yield MJPEG multipart chunks. Caller checks is_recording before starting."""
    while True:
        if is_recording():
            break
        frame = _capture_frame()
        if frame is None:
            time.sleep(_PREVIEW_INTERVAL_SEC)
            continue
        chunk = (
            b"--"
            + _BOUNDARY
            + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(frame)).encode()
            + b"\r\n\r\n"
            + frame
            + b"\r\n"
        )
        yield chunk
        time.sleep(_PREVIEW_INTERVAL_SEC)
