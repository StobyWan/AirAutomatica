"""Persistence recorders: EventPersistenceRecorder, PhasePersistenceRecorder, PathRecorder, TelemetrySampler, TelemetryLifecycleLogger."""

import logging
import math
import time
import typing
from datetime import datetime

from airautomatica.db.base import get_engine
from airautomatica.models.state import nan_to_none

if typing.TYPE_CHECKING:
    from airautomatica.models.state import AircraftState
    from airautomatica.services.persistence import PersistenceService

logger = logging.getLogger(__name__)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in meters between two lat/lon points."""
    R = 6_371_000  # Earth radius in m
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class EventPersistenceRecorder:
    """Persists EventEngine output when events close. Tracks open events, persists on close."""

    def __init__(
        self,
        persistence: "PersistenceService",
        session_ref: list[int | None],
        get_events_fn: typing.Callable[[], list],
    ) -> None:
        self._persistence = persistence
        self._session_ref = session_ref
        self._get_events_fn = get_events_fn
        self._open_events: dict[str, dict] = {}
        self._last_session_id: int | None = None

    def maybe_persist_events(self, now: datetime) -> None:
        """Detect closed events and persist them. Update open-event tracking."""
        session_id = self._session_ref[0] if self._session_ref else None
        if session_id is None:
            if self._last_session_id is not None and self._open_events:
                self._flush_open_events(self._last_session_id, now)
                self._open_events.clear()
            self._last_session_id = None
            return
        self._last_session_id = session_id
        if get_engine() is None:
            return
        current = self._get_events_fn()
        current_names = {e.name for e in current}
        for name in list(self._open_events.keys()):
            if name not in current_names:
                info = self._open_events.pop(name)
                self._persistence.insert_flight_event(
                    session_id=session_id,
                    event_name=name,
                    severity=info["severity"],
                    started_at=info["started_at"],
                    ended_at=now,
                    evidence=info["evidence"],
                    operator_hint=info.get("operator_hint"),
                )
        for e in current:
            if e.name not in self._open_events:
                self._open_events[e.name] = {
                    "started_at": e.started_at,
                    "severity": e.severity,
                    "evidence": dict(e.evidence),
                    "operator_hint": e.operator_hint,
                }

    def _flush_open_events(self, session_id: int, ended_at: datetime) -> None:
        """Persist all open events (e.g. on session end)."""
        if get_engine() is None:
            return
        for name, info in self._open_events.items():
            self._persistence.insert_flight_event(
                session_id=session_id,
                event_name=name,
                severity=info["severity"],
                started_at=info["started_at"],
                ended_at=ended_at,
                evidence=info["evidence"],
                operator_hint=info.get("operator_hint"),
            )


class PhasePersistenceRecorder:
    """Persists FlightPhaseEngine output when phase transitions. Tracks current phase."""

    def __init__(
        self,
        persistence: "PersistenceService",
        session_ref: list[int | None],
        get_phase_fn: typing.Callable[[], str],
    ) -> None:
        self._persistence = persistence
        self._session_ref = session_ref
        self._get_phase_fn = get_phase_fn
        self._last_phase: str | None = None
        self._interval_started_at: datetime | None = None
        self._last_session_id: int | None = None

    def maybe_persist_phase(self, now: datetime) -> None:
        """Detect phase transitions and persist closed intervals."""
        session_id = self._session_ref[0] if self._session_ref else None
        if session_id is None:
            if self._last_session_id is not None and self._last_phase is not None:
                self._flush_open_interval(self._last_session_id, now)
            self._last_phase = None
            self._interval_started_at = None
            self._last_session_id = None
            return
        self._last_session_id = session_id
        if get_engine() is None:
            return
        current_phase = self._get_phase_fn()
        if self._last_phase is None:
            self._last_phase = current_phase
            self._interval_started_at = now
            return
        if current_phase != self._last_phase:
            if self._interval_started_at is not None:
                self._persistence.insert_phase_interval(
                    session_id=session_id,
                    phase=self._last_phase,
                    started_at=self._interval_started_at,
                    ended_at=now,
                )
            self._last_phase = current_phase
            self._interval_started_at = now

    def _flush_open_interval(self, session_id: int, ended_at: datetime) -> None:
        """Persist current open interval (e.g. on session end)."""
        if (
            get_engine() is None
            or self._last_phase is None
            or self._interval_started_at is None
        ):
            return
        self._persistence.insert_phase_interval(
            session_id=session_id,
            phase=self._last_phase,
            started_at=self._interval_started_at,
            ended_at=ended_at,
        )
        self._last_phase = None
        self._interval_started_at = None


class TelemetryLifecycleLogger:
    """Logs telemetry_status transitions as system_events. Only logs when status changes."""

    def __init__(
        self,
        persistence: "PersistenceService",
        session_ref: list[int | None],
    ) -> None:
        self._persistence = persistence
        self._session_ref = session_ref
        self._last_status: str | None = None

    def maybe_log_transition(self, state: "AircraftState") -> None:
        """If telemetry_status changed, log system_event. No-op if persistence unavailable."""
        session_id = self._session_ref[0] if self._session_ref else None
        if session_id is None:
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
            session_id=session_id,
            level=level,
            event_type=event_type,
            message=message,
            metadata=metadata,
        )


class PathRecorder:
    """Distance-based path recorder. Stores a point only when aircraft has moved > min_distance_m."""

    def __init__(
        self,
        persistence: "PersistenceService",
        session_ref: list[int | None],
        min_distance_m: float = 5.0,
    ) -> None:
        self._persistence = persistence
        self._session_ref = session_ref
        self._min_distance_m = min_distance_m
        self._last_lat: float | None = None
        self._last_lon: float | None = None

    def maybe_record(self, state: "AircraftState") -> None:
        """If moved enough from last point (or first valid point), insert path point."""
        session_id = self._session_ref[0] if self._session_ref else None
        if session_id is None:
            return
        if get_engine() is None:
            return
        lat = nan_to_none(state.lat)
        lon = nan_to_none(state.lon)
        if lat is None or lon is None:
            return
        if self._last_lat is None or self._last_lon is None:
            self._persistence.insert_path_point(
                session_id,
                state.timestamp,
                lat,
                lon,
                nan_to_none(state.rel_alt_m),
            )
            self._last_lat = lat
            self._last_lon = lon
            return
        dist = _haversine_m(self._last_lat, self._last_lon, lat, lon)
        if dist >= self._min_distance_m:
            self._persistence.insert_path_point(
                session_id,
                state.timestamp,
                lat,
                lon,
                nan_to_none(state.rel_alt_m),
            )
            self._last_lat = lat
            self._last_lon = lon


class TelemetrySampler:
    """Throttled sampling wrapper. Samples at most once per interval_sec."""

    def __init__(
        self,
        persistence: "PersistenceService",
        session_ref: list[int | None],
        interval_sec: float = 1.0,
    ) -> None:
        self._persistence = persistence
        self._session_ref = session_ref
        self._interval_sec = interval_sec
        self._last_sample_time: float = 0.0

    def maybe_sample(self, state: "AircraftState") -> None:
        """If session_id and persistence available, and interval elapsed, insert sample."""
        session_id = self._session_ref[0] if self._session_ref else None
        if session_id is None:
            return
        if get_engine() is None:
            return
        now = time.monotonic()
        if now - self._last_sample_time >= self._interval_sec:
            self._last_sample_time = now
            self._persistence.insert_telemetry_sample(session_id, state)
