"""Scan serial ports for MAVLink HEARTBEAT. Returns detection result."""

import glob
import logging
import os
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


def _configured_serial_skip_realpath() -> str | None:
    """Realpath of SERIAL_PORT to skip probing (live reader or mock+configured cable)."""
    try:
        from airautomatica.config import get_serial_port, get_telemetry_backend

        if get_telemetry_backend() not in ("serial", "mock"):
            return None
        cfg = (get_serial_port() or "").strip()
        if not cfg:
            return None
        return os.path.realpath(cfg)
    except Exception:
        return None


def scan_and_detect() -> DetectionResult:
    """Scan ports, read messages in loop until HEARTBEAT or timeout."""
    ports = []
    for pattern in DEFAULT_PORTS:
        ports.extend(glob.glob(pattern))
    ports = sorted(set(ports))
    skip_live = _configured_serial_skip_realpath()
    for port in ports:
        try:
            if skip_live is not None and os.path.realpath(port) == skip_live:
                continue
        except OSError:
            pass
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


def detect_on_port_skips_open_if_live_link(
    port: str,
    baud: int,
    *,
    fallback_autopilot: str | None = None,
    fallback_message: str | None = None,
) -> DetectionResult | None:
    """If serial backend already uses this port/baud, return a result without opening.

    Caller supplies autopilot/message from connection_store when known; otherwise
    defaults are conservative for the API response shape.
    """
    try:
        from airautomatica.config import (
            get_serial_baud,
            get_serial_port,
            get_telemetry_backend,
        )

        if get_telemetry_backend() != "serial":
            return None
        if int(baud) != int(get_serial_baud()):
            return None
        try:
            if os.path.realpath(port) != os.path.realpath(get_serial_port()):
                return None
        except OSError:
            return None
    except Exception:
        return None
    ap = (fallback_autopilot or "ardupilot").lower()
    if ap not in ("ardupilot", "inav", "generic"):
        ap = "ardupilot"
    msg = fallback_message or f"Live telemetry on {port} @ {baud} (probe skipped)"
    return DetectionResult(
        detected=True,
        port=port,
        baud=baud,
        autopilot=ap,
        message=msg,
        heartbeat_age_ms=None,
    )


def detect_on_port(port: str, baud: int) -> DetectionResult:
    """Probe a single port for MAVLink HEARTBEAT. Returns detection result."""
    found, autopilot = _probe_port_quick(port, baud, HEARTBEAT_TIMEOUT)
    if found and autopilot:
        return DetectionResult(
            detected=True,
            port=port,
            baud=baud,
            autopilot=autopilot,
            message=f"Found {autopilot} on {port} @ {baud}",
        )
    return DetectionResult(
        detected=False,
        port=port,
        baud=baud,
        autopilot=None,
        message=f"No MAVLink HEARTBEAT found on {port} @ {baud}",
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

    # Do not open the configured UART for probes while mock or serial uses it as the
    # designated FC link — periodic UI scans would steal the port and log noise.
    skip_probe_realpath = _configured_serial_skip_realpath()

    for port in ports:
        if skip_probe_realpath is not None:
            try:
                if os.path.realpath(port) == skip_probe_realpath:
                    result.append(
                        PortInfo(
                            path=port,
                            mavlink_active=True,
                            autopilot=None,
                            baud=PORTS_LIST_BAUD,
                            status="telemetry",
                        )
                    )
                    continue
            except OSError:
                pass

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
