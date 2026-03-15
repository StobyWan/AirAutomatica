"""Telemetry overlay for ffmpeg drawtext: formatter and file writer with change detection."""

import logging
import math
import os
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from airautomatica.models.state import AircraftState

logger = logging.getLogger(__name__)

_UPDATE_INTERVAL_SEC = 0.5
_PLACEHOLDER_LINE1 = "Mode: — | Alt: — | Spd: —"
_PLACEHOLDER_LINE2 = "Batt: — | Armed: — | Sats: —"


def _safe_float(v: float | None, fmt: str = ".1f") -> str:
    """Return formatted float or dash if None/NaN."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return format(v, fmt)


def format_telemetry(state: "AircraftState | None") -> str:
    """Format telemetry for drawtext overlay. Two compact lines to fit video frame.
    Line 1: mode, alt, speed. Line 2: battery, armed, sats."""
    dash = "—"
    if state is None:
        return f"{_PLACEHOLDER_LINE1}\n{_PLACEHOLDER_LINE2}"
    mode = state.mode or dash
    alt = _safe_float(state.rel_alt_m)
    spd = _safe_float(state.groundspeed_m_s)
    batt = _safe_float(state.voltage_v)
    armed = "YES" if state.armed else "NO"
    sats = (
        str(state.satellites_visible) if state.satellites_visible is not None else dash
    )
    return f"Mode: {mode} | Alt: {alt}m | Spd: {spd}m/s\nBatt: {batt}V | Armed: {armed} | Sats: {sats}"


class TelemetryWriter:
    """Writes formatted telemetry to a temp file. Only writes when content changes. 500ms interval."""

    def __init__(
        self,
        get_state: Callable[[], "AircraftState | None"],
    ) -> None:
        self._get_state = get_state
        self._temp_path: Optional[Path] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._last_content: Optional[str] = None

    def start(self) -> Path:
        """Create temp file, start writer thread. Returns path for ffmpeg textfile=."""
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="telemetry_overlay_")
        os.close(fd)
        self._temp_path = Path(path)
        self._last_content = None
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Telemetry overlay writer started path=%s", self._temp_path)
        return self._temp_path

    def stop(self) -> None:
        """Stop writer and remove temp file."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._cleanup()

    def _cleanup(self) -> None:
        """Remove temp file if it exists."""
        if self._temp_path is not None and self._temp_path.exists():
            try:
                self._temp_path.unlink()
                logger.info(
                    "Telemetry overlay temp file removed path=%s", self._temp_path
                )
            except OSError as e:
                logger.warning(
                    "Failed to remove telemetry overlay temp file %s: %s",
                    self._temp_path,
                    e,
                )
        self._temp_path = None

    def _run(self) -> None:
        """Writer loop: poll get_state every 500ms, write only when content changes."""
        try:
            while not self._stop.wait(timeout=_UPDATE_INTERVAL_SEC):
                if self._temp_path is None:
                    break
                content = format_telemetry(self._get_state())
                if content != self._last_content:
                    self._last_content = content
                    try:
                        self._temp_path.write_text(content, encoding="utf-8")
                    except OSError as e:
                        logger.warning("Telemetry overlay write failed: %s", e)
        finally:
            self._cleanup()
