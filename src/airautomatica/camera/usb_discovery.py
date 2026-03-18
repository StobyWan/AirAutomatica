"""USB camera discovery via v4l2. Prefers /dev/v4l/by-id when available."""

import logging
import re
import shutil
import subprocess
from pathlib import Path

from airautomatica.camera.descriptor import (
    CameraCapabilities,
    CameraDescriptor,
)

logger = logging.getLogger(__name__)

_V4L2_BY_ID = Path("/dev/v4l/by-id")
_V4L2_CTL = "v4l2-ctl"
_DEV_VIDEO_RE = re.compile(r"^\s*(/dev/video\d+)\s*$")
_DEVICE_HEADER_RE = re.compile(r"^(.+?)\s+\(([^)]+)\)\s*:?\s*$")


def _get_v4l2_ctl() -> str | None:
    """Return v4l2-ctl path if available."""
    return shutil.which(_V4L2_CTL)


def _discover_usb_via_by_id() -> list[tuple[str, str]]:
    """Discover USB cameras via /dev/v4l/by-id. Returns [(id, path), ...].

    id is usb:/dev/v4l/by-id/xxx, path is the by-id path for ffmpeg.
    """
    result: list[tuple[str, str]] = []
    if not _V4L2_BY_ID.exists():
        return result
    try:
        for entry in sorted(_V4L2_BY_ID.iterdir()):
            if not entry.is_symlink():
                continue
            name = entry.name
            if not name.startswith("usb-"):
                continue
            target = entry.resolve()
            if "/video" not in str(target):
                continue
            path = str(entry)
            camera_id = f"usb:{path}"
            result.append((camera_id, path))
    except OSError as e:
        logger.debug("by-id discovery failed: %s", e)
    return result


def _parse_v4l2_list_devices(stdout: str) -> list[tuple[str, str]]:
    """Parse v4l2-ctl --list-devices output. Returns [(device_name, /dev/videoN), ...].

    Only includes USB devices (bus-info contains 'usb'). Uses first /dev/videoN per device.
    """
    result: list[tuple[str, str]] = []
    lines = stdout.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        match = _DEVICE_HEADER_RE.match(line)
        if match:
            device_name = match.group(1).strip()
            bus_info = match.group(2).strip()
            if "usb" not in bus_info.lower():
                i += 1
                while i < len(lines) and (
                    lines[i].startswith("\t") or lines[i].startswith(" ")
                ):
                    i += 1
                continue
            i += 1
            first_video: str | None = None
            while i < len(lines):
                rest = lines[i]
                if not (rest.startswith("\t") or rest.startswith(" ")):
                    break
                dev_match = _DEV_VIDEO_RE.match(rest.strip())
                if dev_match and first_video is None:
                    first_video = dev_match.group(1)
                i += 1
            if first_video is not None:
                result.append((device_name, first_video))
            continue
        i += 1
    return result


def discover_usb_cameras() -> list[CameraDescriptor]:
    """Discover USB cameras. Prefers by-id paths; fallback to /dev/videoN."""
    by_id_pairs = _discover_usb_via_by_id()
    by_id_paths = {p for (_, p) in by_id_pairs}

    v4l2_cmd = _get_v4l2_ctl()
    v4l2_devices: list[tuple[str, str]] = []
    if v4l2_cmd:
        try:
            result = subprocess.run(
                [v4l2_cmd, "--list-devices"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout:
                v4l2_devices = _parse_v4l2_list_devices(result.stdout)
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.debug("v4l2-ctl --list-devices failed: %s", e)

    seen_video_paths: set[str] = set()
    descriptors: list[CameraDescriptor] = []

    for camera_id, path in by_id_pairs:
        descriptors.append(
            CameraDescriptor(
                id=camera_id,
                source_type="usb",
                display_name=f"USB Camera ({Path(path).name})",
                path=path,
                capabilities=CameraCapabilities(),
                available=True,
            )
        )
        try:
            resolved = str(Path(path).resolve())
            seen_video_paths.add(resolved)
        except OSError:
            pass

    for device_name, video_path in v4l2_devices:
        real_path = (
            str(Path(video_path).resolve()) if Path(video_path).exists() else video_path
        )
        if real_path in seen_video_paths:
            continue
        seen_video_paths.add(real_path)
        camera_id = f"usb:{video_path}"
        display_name = f"USB Camera ({device_name})"
        if len(display_name) > 60:
            display_name = f"USB Camera ({device_name[:50]}...)"
        descriptors.append(
            CameraDescriptor(
                id=camera_id,
                source_type="usb",
                display_name=display_name,
                path=video_path,
                capabilities=CameraCapabilities(),
                available=True,
            )
        )

    return descriptors
