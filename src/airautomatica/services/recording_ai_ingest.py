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
from airautomatica.ai.hailo_detection_impl import (
    DetectionMode,
    run_detection_pipeline,
)
from airautomatica.ai.models import AiResult
from airautomatica.config import get_detection_config
from airautomatica.models.state import nan_to_none

if TYPE_CHECKING:
    from airautomatica.models.state import AircraftState
    from airautomatica.services.persistence import PersistenceService

logger = logging.getLogger(__name__)

_DEDUPE_WINDOW_SEC = 30.0
_FFMPEG_COMMAND = "ffmpeg"
_FAILURE_THRESHOLD_BEFORE_WARN = 5


def _extract_latest_frame(output_path: Path) -> bytes | None:
    """Extract one frame from video file via ffmpeg. Prefers latest frame (near EOF);
    falls back to first frame if seeking fails (e.g. fragmented MP4 being written).
    Returns None if file not ready or extraction fails."""
    ffmpeg = shutil.which(_FFMPEG_COMMAND)
    if not ffmpeg:
        logger.debug("Recording AI ingest: ffmpeg not found")
        return None
    if not output_path.exists():
        logger.debug("Recording AI ingest: file not found path=%s", output_path)
        return None
    # Try latest frame first (seek 1s before EOF). For in-progress recordings,
    # this yields a representative frame; first frame is often dark/empty.
    latest_args = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-sseof",
        "-1",
        "-i",
        str(output_path),
        "-vframes",
        "1",
        "-f",
        "image2",
        "pipe:1",
    ]
    try:
        result = subprocess.run(
            latest_args,
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout:
            logger.debug(
                "Recording AI ingest: extracted latest frame path=%s len=%s",
                output_path,
                len(result.stdout),
            )
            return result.stdout
        # Fallback: first decodable frame (original behavior). Works when -sseof
        # fails (e.g. fragmented MP4, very short file, or read-while-write).
        if result.returncode != 0 or not result.stdout:
            logger.debug(
                "Recording AI ingest: latest-frame failed rc=%s stderr=%r, trying first frame",
                result.returncode,
                (result.stderr or b"").decode("utf-8", errors="replace")[:200],
            )
        first_args = [
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
        ]
        result = subprocess.run(
            first_args,
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout:
            logger.debug(
                "Recording AI ingest: first-frame also failed rc=%s stderr=%r path=%s",
                result.returncode,
                (result.stderr or b"").decode("utf-8", errors="replace")[:200],
                output_path,
            )
            return None
        logger.debug(
            "Recording AI ingest: extracted first frame (fallback) path=%s len=%s",
            output_path,
            len(result.stdout),
        )
        return result.stdout
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.debug(
            "Recording AI ingest: ffmpeg exception path=%s err=%s", output_path, e
        )
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
        cfg = get_detection_config()
        self._interval_sec = interval_sec or cfg.recording_persist_interval_sec
        self._startup_delay_sec = (
            startup_delay_sec or cfg.recording_persist_startup_delay_sec
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
            get_detection_config().persist_threshold,
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
        logger.debug(
            "Recording AI ingest: frame extracted path=%s len=%s",
            self._output_path,
            len(frame_bytes),
        )
        result, success = run_detection_pipeline(
            frame_bytes, DetectionMode.RECORDING_TIME
        )
        logger.debug(
            "Recording AI ingest: inference state=%s success=%s detections=%s",
            result.state,
            success,
            len(result.detections),
        )
        if not success or result.state != "ready":
            self._failure_count += 1
            if self._failure_count >= _FAILURE_THRESHOLD_BEFORE_WARN:
                logger.warning(
                    "Recording AI ingest: repeated inference failures (count=%s) state=%s",
                    self._failure_count,
                    result.state,
                )
            return
        self._failure_count = 0
        session_id = self._get_session_id()
        if session_id is None or self._persistence is None:
            logger.info(
                "Recording AI ingest: skipping persist session_id=%s persistence=%s (start session before recording for detections)",
                session_id,
                "none" if self._persistence is None else "ok",
            )
            return
        self._persist_detections(session_id, result)

    def _persist_detections(self, session_id: int, result: DetectionResult) -> None:
        """Persist each detection with confidence >= threshold (inclusive), with deduplication."""
        if self._persistence is None:
            return
        persist_threshold = get_detection_config().persist_threshold
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
