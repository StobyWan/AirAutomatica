"""Live camera preview stream. Prefers rpicam-vid MJPEG for smooth streaming; falls back to rpicam-still."""

import logging
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Iterator, Optional

logger = logging.getLogger(__name__)

_active_preview_process: Optional[subprocess.Popen[bytes]] = None
_preview_lock = threading.Lock()


def release_camera_for_recording() -> None:
    """Terminate any active preview stream so recording can acquire the camera.
    Call before recording.start_recording()."""
    with _preview_lock:
        global _active_preview_process
        if _active_preview_process is None:
            return
        try:
            _active_preview_process.terminate()
            _active_preview_process.wait(timeout=2)
        except Exception as e:
            logger.debug("Preview terminate during release: %s", e)
            try:
                _active_preview_process.kill()
                _active_preview_process.wait(timeout=1)
            except Exception:
                pass
        _active_preview_process = None
        time.sleep(0.3)  # Allow libcamera to release the device


_JPEG_SOI = b"\xff\xd8\xff"
_JPEG_EOI = b"\xff\xd9"
_PREVIEW_INTERVAL_SEC = 0.1  # fallback: ~10 fps
_CAPTURE_TIMEOUT_SEC = 5
_BOUNDARY = b"frame"


def _get_rpicam_vid() -> str | None:
    """Return rpicam-vid or libcamera-vid path if available."""
    for cmd in ("rpicam-vid", "libcamera-vid"):
        if shutil.which(cmd):
            return cmd
    return None


def _stream_mjpeg_from_vid(
    proc: subprocess.Popen[bytes],
    is_recording: Callable[[], bool],
) -> Iterator[bytes]:
    """Parse MJPEG stream from rpicam-vid stdout, yield multipart chunks."""
    buf = b""
    try:
        while not is_recording():
            chunk = proc.stdout.read(8192) if proc.stdout else b""
            if not chunk:
                break
            buf += chunk
            while True:
                soi = buf.find(_JPEG_SOI)
                if soi < 0:
                    break
                eoi = buf.find(_JPEG_EOI, soi)
                if eoi <= soi:
                    break
                frame = buf[soi : eoi + 2]
                buf = buf[eoi + 2 :]
                yield (
                    b"--"
                    + _BOUNDARY
                    + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(frame)).encode()
                    + b"\r\n\r\n"
                    + frame
                    + b"\r\n"
                )
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            proc.kill()


def _capture_frame_still() -> bytes | None:
    """Capture one JPEG via rpicam-still. Fallback when rpicam-vid unavailable."""
    rpicam = shutil.which("rpicam-still")
    if not rpicam:
        return None
    path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            path = Path(f.name)
        result = subprocess.run(
            [rpicam, "-t", "1", "--immediate", "-n", "-o", str(path)],
            capture_output=True,
            text=True,
            timeout=_CAPTURE_TIMEOUT_SEC,
        )
        if result.returncode != 0 or not path.exists():
            return None
        return path.read_bytes()
    except (subprocess.TimeoutExpired, OSError):
        return None
    finally:
        if path is not None and path.exists():
            path.unlink(missing_ok=True)


def stream_preview_frames(
    is_recording: Callable[[], bool],
) -> Iterator[bytes]:
    """Yield MJPEG multipart chunks. Prefers rpicam-vid stream; falls back to rpicam-still loop."""
    vid_cmd = _get_rpicam_vid()
    if vid_cmd:
        try:
            proc = subprocess.Popen(
                [
                    vid_cmd,
                    "-t",
                    "0",
                    "--codec",
                    "mjpeg",
                    "-o",
                    "-",
                    "--width",
                    "640",
                    "--height",
                    "480",
                    "--nopreview",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            if proc.stdout:
                with _preview_lock:
                    global _active_preview_process
                    _active_preview_process = proc
                try:
                    yield from _stream_mjpeg_from_vid(proc, is_recording)
                finally:
                    with _preview_lock:
                        if _active_preview_process is proc:
                            _active_preview_process = None
                return
        except Exception as e:
            logger.debug("rpicam-vid preview failed, falling back to still: %s", e)

    while True:
        if is_recording():
            break
        frame = _capture_frame_still()
        if frame:
            yield (
                b"--"
                + _BOUNDARY
                + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                + str(len(frame)).encode()
                + b"\r\n\r\n"
                + frame
                + b"\r\n"
            )
        time.sleep(_PREVIEW_INTERVAL_SEC)
