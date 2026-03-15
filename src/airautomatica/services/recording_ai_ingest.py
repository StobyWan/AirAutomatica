"""Recording-time AI detection ingestion.

Extracts frames from in-progress recording, runs Hailo inference, persists detections
to Recent Detections. Source: ai_hat_recording. Distinct from one-shot (aihat) and
mission flow (mock/ollama).
"""

import logging
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from airautomatica.ai.detection_models import DetectionResult
from airautomatica.ai.hailo_detection_impl import run_inference_on_image_bytes
from airautomatica.ai.models import AiResult
from airautomatica.config import (
    get_recording_ai_persist_interval_sec,
    get_recording_ai_persist_startup_delay_sec,
    get_recording_ai_persist_threshold,
)
from airautomatica.models.state import nan_to_none

if TYPE_CHECKING:
    from airautomatica.models.state import AircraftState
    from airautomatica.services.persistence import PersistenceService

logger = logging.getLogger(__name__)

_DEDUPE_WINDOW_SEC = 30.0
_FFMPEG_COMMAND = "ffmpeg"
_FAILURE_THRESHOLD_BEFORE_WARN = 5


def _extract_latest_frame(output_path: Path) -> bytes | None:
    """Extract one frame from video file via ffmpeg. Returns None if file not ready or extraction fails."""
    ffmpeg = shutil.which(_FFMPEG_COMMAND)
    if not ffmpeg:
        return None
    if not output_path.exists():
        return None
    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(output_path),
                "-vframes",
                "1",
                "-f",
                "image2",
                "pipe:1",
            ],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        return result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return None


class RecordingAiIngest:
    """Background task: extract frames from recording, run inference, persist detections."""

    def __init__(
        self,
        output_path: Path,
        get_session_id: Callable[[], int | None],
        persistence: Optional["PersistenceService"],
        *,
        get_state: Optional[Callable[[], "AircraftState | None"]] = None,
        interval_sec: Optional[float] = None,
        startup_delay_sec: Optional[float] = None,
    ) -> None:
        self._output_path = output_path
        self._get_session_id = get_session_id
        self._persistence = persistence
        self._get_state = get_state
        self._interval_sec = interval_sec or get_recording_ai_persist_interval_sec()
        self._startup_delay_sec = (
            startup_delay_sec or get_recording_ai_persist_startup_delay_sec()
        )
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_persisted: dict[str, float] = {}
        self._failure_count = 0

    def start(self) -> None:
        """Start the background ingestion thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(
            "Recording AI persist enabled: interval=%.0fs startup_delay=%.0fs persist_threshold=%.2f",
            self._interval_sec,
            self._startup_delay_sec,
            get_recording_ai_persist_threshold(),
        )

    def stop(self) -> None:
        """Stop the background ingestion thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval_sec * 2)
            self._thread = None

    def _run_loop(self) -> None:
        """Main loop: startup delay, then periodic extraction + inference + persist."""
        if self._startup_delay_sec > 0:
            if self._stop_event.wait(timeout=self._startup_delay_sec):
                return
        while not self._stop_event.is_set():
            self._tick()
            if self._stop_event.wait(timeout=self._interval_sec):
                break

    def _tick(self) -> None:
        """Single iteration: extract frame, run inference, persist detections."""
        frame_bytes = _extract_latest_frame(self._output_path)
        if frame_bytes is None:
            logger.debug(
                "Recording AI ingest: file not ready or ffmpeg returned nothing, path=%s",
                self._output_path,
            )
            return
        result, success = run_inference_on_image_bytes(frame_bytes)
        if not success or result.state != "ready":
            logger.debug(
                "Recording AI ingest: inference failed or no detections, state=%s",
                result.state,
            )
            self._failure_count += 1
            if self._failure_count >= _FAILURE_THRESHOLD_BEFORE_WARN:
                logger.warning(
                    "Recording AI ingest: repeated inference failures (count=%s)",
                    self._failure_count,
                )
            return
        self._failure_count = 0
        session_id = self._get_session_id()
        if session_id is None or self._persistence is None:
            logger.debug(
                "Recording AI ingest: no session or persistence, skipping persist"
            )
            return
        self._persist_detections(session_id, result)

    def _persist_detections(self, session_id: int, result: DetectionResult) -> None:
        """Persist each detection with confidence >= threshold (inclusive), with deduplication."""
        if self._persistence is None:
            return
        persist_threshold = get_recording_ai_persist_threshold()
        now = time.monotonic()
        for det in result.detections:
            label = det.label
            if det.confidence < persist_threshold:
                logger.debug(
                    "Recording AI ingest: skipped low-confidence label=%s confidence=%.2f (below persist threshold %.2f)",
                    label,
                    det.confidence,
                    persist_threshold,
                )
                continue
            last_ts = self._last_persisted.get(label)
            if last_ts is not None and (now - last_ts) < _DEDUPE_WINDOW_SEC:
                logger.debug(
                    "Recording AI ingest: skipped duplicate label=%s (within %.0fs)",
                    label,
                    _DEDUPE_WINDOW_SEC,
                )
                continue
            bbox = None
            if det.bbox is not None:
                bbox = (det.bbox.x, det.bbox.y, det.bbox.width, det.bbox.height)
            state = self._get_state() if self._get_state else None
            lat = nan_to_none(state.lat) if state is not None else None
            lon = nan_to_none(state.lon) if state is not None else None
            rel_alt_m = nan_to_none(state.rel_alt_m) if state is not None else None

            ai_result = AiResult(
                label=label,
                confidence=det.confidence,
                summary=f"{label} detected (AI HAT recording)",
                source_backend="ai_hat_recording",
                timestamp=datetime.now(timezone.utc),
                bbox=bbox,
                metadata={"recording": True},
            )
            self._persistence.insert_detection(
                session_id=session_id,
                result=ai_result,
                lat=lat,
                lon=lon,
                rel_alt_m=rel_alt_m,
            )
            self._last_persisted[label] = now
            logger.info(
                "Recording AI persist: persisted label=%s confidence=%.2f (source=ai_hat_recording)",
                label,
                det.confidence,
            )
