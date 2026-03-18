"""Backend-neutral still capture. Dispatches to CSI or USB based on descriptor."""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from airautomatica.camera.backends.csi import csi_still_capture_argv
from airautomatica.camera.backends.usb import usb_still_capture_argv
from airautomatica.camera.descriptor import CameraDescriptor
from airautomatica.camera.selector import CameraSelector

logger = logging.getLogger(__name__)

_CAPTURE_TIMEOUT_SEC = 20


def capture_still(
    descriptor: Optional[CameraDescriptor] = None,
) -> tuple[bytes | None, str | None]:
    """Capture one still frame from the given or selected camera. Returns (jpeg_bytes, error).

    When descriptor is None, uses CameraSelector().resolve() to get the active camera.
    Dispatches to CSI (rpicam-still/libcamera-still) or USB (ffmpeg v4l2) based on
    descriptor.source_type. Does not crash on missing tools; returns (None, error_msg).
    """
    desc = descriptor if descriptor is not None else CameraSelector().resolve()
    if desc is None:
        return None, "No camera available"

    path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            path = Path(f.name)

        argv: Optional[list[str]] = None
        backend_name: str = ""

        csi_argv = csi_still_capture_argv(desc, path)
        if csi_argv is not None:
            argv = csi_argv
            backend_name = "CSI (rpicam-still/libcamera-still)"

        if argv is None:
            usb_argv = usb_still_capture_argv(desc, path)
            if usb_argv is not None:
                argv = usb_argv
                backend_name = "USB (ffmpeg v4l2)"

        if argv is None:
            return None, f"Still capture not available for {desc.source_type} camera"

        logger.info("Still capture using %s for %s", backend_name, desc.id)

        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_CAPTURE_TIMEOUT_SEC,
        )

        if result.returncode != 0:
            err = result.stderr or result.stdout or "unknown"
            path.unlink(missing_ok=True)
            logger.warning("Still capture failed (exit %d): %s", result.returncode, err)
            return None, f"Still capture failed: {err}"

        if not path.exists():
            return None, "Still capture did not produce output"

        data = path.read_bytes()
        path.unlink(missing_ok=True)
        return data, None

    except subprocess.TimeoutExpired:
        if path is not None and path.exists():
            path.unlink(missing_ok=True)
        return None, "Camera capture timed out"
    except Exception as e:
        if path is not None and path.exists():
            path.unlink(missing_ok=True)
        logger.exception("Still capture failed")
        return None, f"Camera capture failed: {e}"
