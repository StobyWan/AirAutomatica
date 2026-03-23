"""Edge-triggered auto session start/stop based on armed state."""

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from airautomatica.config import get_session_auto_stop_disarm_debounce_sec
from airautomatica.models.connection_state import ConnectionState, SessionState
from airautomatica.services.persistence import build_session_start_params

if TYPE_CHECKING:
    from airautomatica.models.state import AircraftState
    from airautomatica.services.app_home_store import AppHomeStore
    from airautomatica.services.connection_state_store import ConnectionStateStore
    from airautomatica.services.persistence import PersistenceService

logger = logging.getLogger(__name__)

# Connection states where auto-start is allowed (not in setup/detecting)
_AUTO_ALLOWED: frozenset[ConnectionState] = frozenset(
    {
        ConnectionState.MOCK_IDLE,
        ConnectionState.CONNECTED_ARDUPILOT,
        ConnectionState.CONNECTED_INAV,
    }
)


class SessionAutoController:
    """Edge-triggered auto session start/stop based on armed state.

    When enabled: start session on arm, stop on disarm (with debounce).
    Only runs when connection_state is mock_idle or connected_*.
    """

    def __init__(
        self,
        persistence: "PersistenceService",
        session_ref: list[int | None],
        connection_store: "ConnectionStateStore",
        get_enabled_fn: Callable[[], bool],
        debounce_sec: Optional[float] = None,
        app_home_store: Optional["AppHomeStore"] = None,
    ) -> None:
        self._persistence = persistence
        self._session_ref = session_ref
        self._connection_store = connection_store
        self._get_enabled = get_enabled_fn
        self._app_home_store = app_home_store
        self._debounce_sec = (
            debounce_sec
            if debounce_sec is not None
            else get_session_auto_stop_disarm_debounce_sec()
        )
        self._last_armed: Optional[bool] = None
        self._disarm_since: Optional[float] = None

    def maybe_auto_start_stop(self, state: "AircraftState") -> None:
        """Call from telemetry loop. Start/stop session based on armed transitions."""
        if not self._get_enabled():
            return
        conn = self._connection_store.get_connection_state()
        if conn not in _AUTO_ALLOWED:
            return
        armed = state.armed
        sid = self._session_ref[0]

        if armed:
            self._disarm_since = None
            if (self._last_armed is None or not self._last_armed) and sid is None:
                sid_new = self._do_start_session()
                if sid_new is not None:
                    self._session_ref[0] = sid_new
                    self._connection_store.set_session_state(SessionState.ACTIVE)
                    logger.info("Auto session started on arm: #%s", sid_new)
        elif not armed and sid is not None:
            if not state.connected:
                return
            now = time.monotonic()
            if self._disarm_since is None:
                self._disarm_since = now
            if (
                self._debounce_sec <= 0
                or (now - self._disarm_since) >= self._debounce_sec
            ):
                logger.info(
                    "Auto session stopped on disarm (after %.1fs): #%s",
                    self._debounce_sec,
                    sid,
                )
                self._persistence.end_session(sid)
                self._session_ref[0] = None
                if self._app_home_store is not None:
                    self._app_home_store.clear_app_home()
                self._connection_store.set_session_state(SessionState.NONE)
                self._disarm_since = None
            else:
                return
        else:
            self._disarm_since = None

        self._last_armed = armed

    def _do_start_session(self) -> Optional[int]:
        """Start session using connection_store metadata. Returns session_id or None."""
        params = build_session_start_params(self._connection_store)
        return self._persistence.start_session(**params)
