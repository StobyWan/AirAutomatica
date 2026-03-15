"""Scan serial ports for MAVLink HEARTBEAT. Returns detection result."""

import glob
import logging
import time
from dataclasses import dataclass
from typing import Any

from airautomatica.telemetry.mavlink import detect_autopilot_from_heartbeat
from airautomatica.telemetry.transport.serial_transport import SerialTransport

logger = logging.getLogger(__name__)

DEFAULT_PORTS = ["/dev/ttyACM*", "/dev/ttyUSB*", "/dev/cu.usb*"]
DEFAULT_BAUDS = [921600, 57600, 115200]
HEARTBEAT_TIMEOUT = 3.0
# Short timeout for lightweight port listing; avoids blocking the UI
PORTS_LIST_PROBE_TIMEOUT = 0.5
PORTS_LIST_BAUD = 921600  # Single baud for fast summary; full detect uses all bauds


@dataclass
class PortInfo:
    """Summary of a serial port for the ports panel."""

    path: str
    mavlink_active: bool
    autopilot: str | None
    baud: int | None
    status: str


@dataclass
class DetectionResult:
    """Result of FC detection scan. generic autopilot maps to iNav in v1."""

    detected: bool
    port: str | None
    baud: int | None
    autopilot: str | None
    message: str
    heartbeat_age_ms: float | None = None


def scan_and_detect() -> DetectionResult:
    """Scan ports, read messages in loop until HEARTBEAT or timeout."""
    ports = []
    for pattern in DEFAULT_PORTS:
        ports.extend(glob.glob(pattern))
    ports = sorted(set(ports))
    for port in ports:
        for baud in DEFAULT_BAUDS:
            try:
                t = SerialTransport(port, baud)
                t.connect()
                deadline = time.monotonic() + HEARTBEAT_TIMEOUT
                heartbeat = None
                while time.monotonic() < deadline:
                    msg = t.read_message(timeout=0.5)
                    if msg and msg.get_type() == "HEARTBEAT":
                        heartbeat = msg
                        break
                t.close()
                if heartbeat is not None:
                    autopilot = detect_autopilot_from_heartbeat(heartbeat)
                    return DetectionResult(
                        detected=True,
                        port=port,
                        baud=baud,
                        autopilot=autopilot,
                        message=f"Found {autopilot} on {port} @ {baud}",
                    )
            except Exception as e:
                logger.debug("Detect %s@%s: %s", port, baud, e)
                continue
    return DetectionResult(
        detected=False,
        port=None,
        baud=None,
        autopilot=None,
        message="No MAVLink HEARTBEAT found on scanned ports",
    )


def _probe_port_quick(port: str, baud: int, timeout: float) -> tuple[bool, str | None]:
    """Probe a port for MAVLink HEARTBEAT. Returns (found, autopilot)."""
    try:
        t = SerialTransport(port, baud)
        t.connect()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg: Any | None = t.read_message(timeout=min(0.2, timeout))
            if msg and msg.get_type() == "HEARTBEAT":
                autopilot = detect_autopilot_from_heartbeat(msg)
                t.close()
                return True, autopilot
        t.close()
    except Exception as e:
        logger.debug("Probe %s@%s: %s", port, baud, e)
    return False, None


def list_ports_with_status() -> list[PortInfo]:
    """List detected ports with lightweight MAVLink status. Fast, non-blocking summary.

    Uses short timeout (0.5s) and single baud to avoid slow scans. Non-active ports
    are reported as 'available' rather than deeply classified.
    """
    result: list[PortInfo] = [
        PortInfo(
            path="Mock",
            mavlink_active=True,
            autopilot="mock",
            baud=None,
            status="active",
        )
    ]
    ports: list[str] = []
    for pattern in DEFAULT_PORTS:
        ports.extend(glob.glob(pattern))
    ports = sorted(set(ports))
    for port in ports:
        found, autopilot = _probe_port_quick(
            port, PORTS_LIST_BAUD, PORTS_LIST_PROBE_TIMEOUT
        )
        if found and autopilot:
            result.append(
                PortInfo(
                    path=port,
                    mavlink_active=True,
                    autopilot=autopilot,
                    baud=PORTS_LIST_BAUD,
                    status="active",
                )
            )
        else:
            result.append(
                PortInfo(
                    path=port,
                    mavlink_active=False,
                    autopilot=None,
                    baud=None,
                    status="available",
                )
            )
    return result
