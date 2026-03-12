"""Scan serial ports for MAVLink HEARTBEAT. Returns detection result."""

import glob
import logging
import time
from dataclasses import dataclass

from airautomatica.telemetry.mavlink import detect_autopilot_from_heartbeat
from airautomatica.telemetry.transport.serial_transport import SerialTransport

logger = logging.getLogger(__name__)

DEFAULT_PORTS = ["/dev/ttyACM*", "/dev/ttyUSB*", "/dev/cu.usb*"]
DEFAULT_BAUDS = [921600, 57600, 115200]
HEARTBEAT_TIMEOUT = 3.0


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
