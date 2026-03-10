"""Persistence service and throttled telemetry sampler."""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

from airautomatica.db.base import get_engine
from airautomatica.db.models import Detection, FlightSession, TelemetrySample
from airautomatica.db.session import get_session
from airautomatica.models.state import nan_to_none

if TYPE_CHECKING:
    from airautomatica.ai.models import AiResult
    from airautomatica.models.state import AircraftState

logger = logging.getLogger(__name__)


class PersistenceService:
    """Repository layer for SQLite persistence. All methods catch exceptions and no-op on failure."""

    def __init__(self) -> None:
        self._last_error: str | None = None
        self._last_error_lock = threading.Lock()

    def _record_error(self, msg: str) -> None:
        with self._last_error_lock:
            self._last_error = msg

    def get_last_persistence_error(self) -> str | None:
        """Return last persistence error message, if any."""
        with self._last_error_lock:
            return self._last_error

    def start_session(
        self,
        telemetry_backend: str,
        ai_backend: str,
        notes: str | None = None,
    ) -> int | None:
        """Insert flight_sessions row. Return session_id or None on failure."""
        if get_engine() is None:
            return None
        try:
            with get_session() as session:
                if session is None:
                    return None
                row = FlightSession(
                    started_at=datetime.now(timezone.utc),
                    ended_at=None,
                    telemetry_backend=telemetry_backend,
                    ai_backend=ai_backend,
                    notes=notes,
                )
                session.add(row)
                session.flush()
                return row.id
        except Exception as e:
            self._record_error(str(e))
            logger.exception("start_session failed: %s", e)
            return None

    def end_session(self, session_id: int) -> None:
        """Set ended_at for the session."""
        if get_engine() is None:
            return
        try:
            with get_session() as session:
                if session is None:
                    return
                row = session.get(FlightSession, session_id)
                if row is not None:
                    row.ended_at = datetime.now(timezone.utc)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("end_session failed: %s", e)

    def insert_telemetry_sample(self, session_id: int, state: "AircraftState") -> None:
        """Insert telemetry_samples row. Converts NaN to None."""
        if get_engine() is None:
            return
        try:
            with get_session() as session:
                if session is None:
                    return
                row = TelemetrySample(
                    session_id=session_id,
                    timestamp=state.timestamp,
                    telemetry_status=state.telemetry_status,
                    lat=nan_to_none(state.lat),
                    lon=nan_to_none(state.lon),
                    rel_alt_m=nan_to_none(state.rel_alt_m),
                    heading_deg=nan_to_none(state.heading_deg),
                    voltage_v=nan_to_none(state.voltage_v),
                    current_a=nan_to_none(state.current_a),
                    groundspeed_m_s=nan_to_none(state.groundspeed_m_s),
                    airspeed_m_s=nan_to_none(state.airspeed_m_s),
                )
                session.add(row)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("insert_telemetry_sample failed: %s", e)

    def insert_detection(
        self,
        session_id: int,
        result: "AiResult",
        lat: float | None,
        lon: float | None,
        rel_alt_m: float | None,
    ) -> None:
        """Insert detections row."""
        if get_engine() is None:
            return
        try:
            lat_n = nan_to_none(lat)
            lon_n = nan_to_none(lon)
            alt_n = nan_to_none(rel_alt_m)
            metadata_json = json.dumps(result.metadata or {})
            with get_session() as session:
                if session is None:
                    return
                row = Detection(
                    session_id=session_id,
                    timestamp=result.timestamp,
                    label=result.label,
                    confidence=result.confidence,
                    summary=result.summary,
                    source_backend=result.source_backend,
                    lat=lat_n,
                    lon=lon_n,
                    rel_alt_m=alt_n,
                    metadata_json=metadata_json,
                )
                session.add(row)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("insert_detection failed: %s", e)

    def get_recent_detections(
        self,
        session_id: int | None,
        limit: int = 20,
    ) -> list[dict]:
        """Fetch recent detections for session. Newest first. Returns [] when DB disabled or on error."""
        if get_engine() is None or session_id is None:
            return []
        try:
            with get_session() as session:
                if session is None:
                    return []
                result = session.execute(
                    select(Detection)
                    .where(Detection.session_id == session_id)
                    .order_by(Detection.timestamp.desc())
                    .limit(limit)
                )
                rows = result.scalars().all()
                out: list[dict] = []
                for row in rows:
                    try:
                        meta = (
                            json.loads(row.metadata_json) if row.metadata_json else {}
                        )
                    except json.JSONDecodeError:
                        meta = {}
                    out.append(
                        {
                            "id": row.id,
                            "session_id": row.session_id,
                            "timestamp": row.timestamp.isoformat(),
                            "label": row.label,
                            "confidence": row.confidence,
                            "summary": row.summary,
                            "source_backend": row.source_backend,
                            "lat": row.lat,
                            "lon": row.lon,
                            "rel_alt_m": row.rel_alt_m,
                            "metadata": meta,
                        }
                    )
                return out
        except Exception as e:
            self._record_error(str(e))
            logger.exception("get_recent_detections failed: %s", e)
            return []

    def insert_system_event(
        self,
        session_id: int | None,
        level: str,
        event_type: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        """Insert system_events row."""
        if get_engine() is None:
            return
        try:
            from airautomatica.db.models import SystemEvent

            metadata_json = json.dumps(metadata) if metadata else None
            with get_session() as session:
                if session is None:
                    return
                row = SystemEvent(
                    session_id=session_id,
                    timestamp=datetime.now(timezone.utc),
                    level=level,
                    event_type=event_type,
                    message=message,
                    metadata_json=metadata_json,
                )
                session.add(row)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("insert_system_event failed: %s", e)

    def insert_command_sent(
        self,
        session_id: int,
        command_name: str,
        status: str,
        metadata: dict | None = None,
    ) -> None:
        """Insert commands_sent row."""
        if get_engine() is None:
            return
        try:
            from airautomatica.db.models import CommandSent

            metadata_json = json.dumps(metadata) if metadata else None
            with get_session() as session:
                if session is None:
                    return
                row = CommandSent(
                    session_id=session_id,
                    timestamp=datetime.now(timezone.utc),
                    command_name=command_name,
                    status=status,
                    metadata_json=metadata_json,
                )
                session.add(row)
        except Exception as e:
            self._record_error(str(e))
            logger.exception("insert_command_sent failed: %s", e)


class TelemetryLifecycleLogger:
    """Logs telemetry_status transitions as system_events. Only logs when status changes."""

    def __init__(
        self,
        persistence: PersistenceService,
        session_id: int | None,
    ) -> None:
        self._persistence = persistence
        self._session_id = session_id
        self._last_status: str | None = None

    def maybe_log_transition(self, state: "AircraftState") -> None:
        """If telemetry_status changed, log system_event. No-op if persistence unavailable."""
        if self._session_id is None:
            return
        if get_engine() is None:
            return
        status = state.telemetry_status
        if self._last_status == status:
            return
        prev = self._last_status
        self._last_status = status

        metadata: dict = {"from": prev, "to": status}
        if state.reconnect_count > 0:
            metadata["reconnect_count"] = state.reconnect_count
        if state.last_disconnect_reason is not None:
            metadata["last_disconnect_reason"] = state.last_disconnect_reason

        event_type = "telemetry_status_transition"
        message = f"Telemetry {prev or 'initial'} -> {status}"
        level = (
            "info"
            if status == "connected"
            else "warning" if status in ("stale", "backoff") else "info"
        )
        self._persistence.insert_system_event(
            session_id=self._session_id,
            level=level,
            event_type=event_type,
            message=message,
            metadata=metadata,
        )


class TelemetrySampler:
    """Throttled sampling wrapper. Samples at most once per interval_sec."""

    def __init__(
        self,
        persistence: PersistenceService,
        session_id: int | None,
        interval_sec: float = 1.0,
    ) -> None:
        self._persistence = persistence
        self._session_id = session_id
        self._interval_sec = interval_sec
        self._last_sample_time: float = 0.0

    def maybe_sample(self, state: "AircraftState") -> None:
        """If session_id and persistence available, and interval elapsed, insert sample."""
        if self._session_id is None:
            return
        if get_engine() is None:
            return
        now = time.monotonic()
        if now - self._last_sample_time >= self._interval_sec:
            self._last_sample_time = now
            self._persistence.insert_telemetry_sample(self._session_id, state)
