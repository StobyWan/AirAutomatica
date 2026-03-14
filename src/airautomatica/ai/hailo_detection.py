"""Hailo AI HAT detection. Detects Raspberry Pi AI HAT+ (Hailo-8L) presence and readiness."""

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

HailoState = Literal[
    "ready",
    "disabled",
    "missing_cli",
    "missing_hardware",
    "identify_failed",
    "misconfigured",
]

RPCAM_ASSETS_PATH = Path("/usr/share/rpi-camera-assets/hailo_yolov6_inference.json")


@dataclass
class HailoStatusResult:
    """Result of Hailo AI HAT detection."""

    available: bool
    state: HailoState
    device_class: str | None
    board_name: str | None
    driver_ready: bool
    camera_ai_postprocess_available: bool
    errors: list[str]


def get_hailo_status() -> HailoStatusResult:
    """Detect Hailo AI HAT presence and readiness. Never raises; returns structured result."""
    errors: list[str] = []

    # 1. Check hailortcli exists
    hailortcli = shutil.which("hailortcli")
    if not hailortcli:
        logger.debug("hailortcli not found in PATH")
        return HailoStatusResult(
            available=False,
            state="missing_cli",
            device_class=None,
            board_name=None,
            driver_ready=False,
            camera_ai_postprocess_available=False,
            errors=["hailortcli not found in PATH"],
        )

    # 2. Run lspci and check for Hailo
    lspci_ok = False
    try:
        result = subprocess.run(
            ["lspci"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and "Hailo" in (result.stdout or ""):
            lspci_ok = True
        elif result.returncode != 0:
            errors.append(f"lspci failed: {result.stderr or 'unknown'}")
        else:
            errors.append("lspci: no Hailo device found")
    except FileNotFoundError:
        errors.append("lspci not available (non-Linux?)")
    except subprocess.TimeoutExpired:
        errors.append("lspci timed out")
    except Exception as e:
        logger.exception("lspci check failed")
        errors.append(str(e))

    if not lspci_ok:
        return HailoStatusResult(
            available=False,
            state="missing_hardware",
            device_class=None,
            board_name=None,
            driver_ready=False,
            camera_ai_postprocess_available=False,
            errors=errors,
        )

    # 3. Run hailortcli fw-control identify
    board_name: str | None = None
    device_arch: str | None = None
    identify_ok = False
    try:
        result = subprocess.run(
            [hailortcli, "fw-control", "identify"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            stdout = result.stdout or ""
            for line in stdout.splitlines():
                line = line.strip()
                if line.startswith("Board Name:"):
                    board_name = line.split(":", 1)[1].strip()
                elif line.startswith("Device Architecture:"):
                    device_arch = line.split(":", 1)[1].strip()
            if board_name and device_arch:
                identify_ok = True
                # Only accept HAILO8L / Hailo-8 (not H10 / AI HAT+ 2)
                if (
                    "HAILO8" not in device_arch.upper()
                    and "HAILO8L" not in device_arch.upper()
                ):
                    errors.append(
                        f"Unsupported device architecture: {device_arch} (expected HAILO8L)"
                    )
                    identify_ok = False
            else:
                errors.append(
                    "hailortcli identify: could not parse Board Name or Device Architecture"
                )
        else:
            errors.append(
                f"hailortcli identify failed: {result.stderr or result.stdout or 'unknown'}"
            )
    except subprocess.TimeoutExpired:
        errors.append("hailortcli identify timed out")
    except Exception as e:
        logger.exception("hailortcli identify failed")
        errors.append(str(e))

    if not identify_ok:
        return HailoStatusResult(
            available=False,
            state="identify_failed",
            device_class=device_arch.lower() if device_arch else None,
            board_name=board_name,
            driver_ready=False,
            camera_ai_postprocess_available=False,
            errors=errors,
        )

    # 4. Check rpicam Hailo postprocess assets
    camera_ai_available = RPCAM_ASSETS_PATH.exists()
    if not camera_ai_available:
        errors.append(f"rpicam Hailo postprocess assets not found: {RPCAM_ASSETS_PATH}")

    # Normalize device_class for response (e.g. HAILO8L -> hailo8l)
    device_class = (
        (device_arch or "").lower().replace(" ", "") if device_arch else "hailo8l"
    )

    return HailoStatusResult(
        available=True,
        state="ready",
        device_class=device_class,
        board_name=board_name,
        driver_ready=True,
        camera_ai_postprocess_available=camera_ai_available,
        errors=errors if not camera_ai_available else [],
    )
