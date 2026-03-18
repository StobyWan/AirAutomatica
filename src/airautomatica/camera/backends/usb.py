"""USB (V4L2) backend. Preview and recording via ffmpeg."""

import shutil
from pathlib import Path
from typing import Optional

from airautomatica.camera.descriptor import CameraDescriptor

_FFMPEG = "ffmpeg"
_PREVIEW_WIDTH = 640
_PREVIEW_HEIGHT = 480


def _get_ffmpeg() -> Optional[str]:
    """Return ffmpeg path if available."""
    return shutil.which(_FFMPEG)


def usb_preview_argv(descriptor: Optional[CameraDescriptor]) -> Optional[list[str]]:
    """Build argv for USB preview (MJPEG stream). Returns None if not USB or ffmpeg missing."""
    if descriptor is None or descriptor.source_type != "usb" or not descriptor.path:
        return None
    ffmpeg = _get_ffmpeg()
    if not ffmpeg:
        return None
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "v4l2",
        "-video_size",
        f"{_PREVIEW_WIDTH}x{_PREVIEW_HEIGHT}",
        "-framerate",
        "15",
        "-i",
        descriptor.path,
        "-c:v",
        "mjpeg",
        "-q:v",
        "5",
        "-f",
        "mjpeg",
        "pipe:1",
    ]


def usb_recording_argv(
    descriptor: Optional[CameraDescriptor],
    output_path: Path,
) -> Optional[list[str]]:
    """Build argv for USB recording (MP4). Returns None if not USB or ffmpeg missing."""
    if descriptor is None or descriptor.source_type != "usb" or not descriptor.path:
        return None
    ffmpeg = _get_ffmpeg()
    if not ffmpeg:
        return None
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "v4l2",
        "-video_size",
        "1280x720",
        "-framerate",
        "30",
        "-i",
        descriptor.path,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-movflags",
        "frag_keyframe+empty_moov+default_base_moof",
        str(output_path),
    ]


def usb_still_capture_argv(
    descriptor: Optional[CameraDescriptor],
    output_path: Path,
) -> Optional[list[str]]:
    """Build argv for USB still capture (single frame via ffmpeg v4l2). Returns None if not USB or ffmpeg missing."""
    if descriptor is None or descriptor.source_type != "usb" or not descriptor.path:
        return None
    ffmpeg = _get_ffmpeg()
    if not ffmpeg:
        return None
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "v4l2",
        "-video_size",
        "1280x720",
        "-framerate",
        "30",
        "-i",
        descriptor.path,
        "-vframes",
        "1",
        "-f",
        "image2",
        "-c:v",
        "mjpeg",
        "-q:v",
        "3",
        str(output_path),
    ]
