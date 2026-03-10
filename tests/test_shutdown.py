"""Tests for shutdown coordination."""

from unittest.mock import MagicMock

from airautomatica.main import _shutdown_cleanup
from airautomatica.services.persistence import PersistenceService


def test_session_ended_on_shutdown() -> None:
    """_shutdown_cleanup calls end_session when session_ref has a session."""
    persistence = MagicMock(spec=PersistenceService)
    session_ref: list[int | None] = [42]

    _shutdown_cleanup(persistence, session_ref)

    persistence.end_session.assert_called_once_with(42)
    persistence.insert_system_event.assert_called_once()
    call_kw = persistence.insert_system_event.call_args.kwargs
    assert call_kw["event_type"] == "app_shutdown"
    assert call_kw["session_id"] == 42
    assert session_ref[0] is None


def test_repeated_shutdown_idempotent() -> None:
    """Calling _shutdown_cleanup twice only ends session once."""
    persistence = MagicMock(spec=PersistenceService)
    session_ref: list[int | None] = [99]

    _shutdown_cleanup(persistence, session_ref)
    _shutdown_cleanup(persistence, session_ref)

    persistence.end_session.assert_called_once_with(99)
    assert session_ref[0] is None


def test_shutdown_cleanup_no_op_when_no_session() -> None:
    """_shutdown_cleanup does not call end_session when session_ref is None."""
    persistence = MagicMock(spec=PersistenceService)
    session_ref: list[int | None] = [None]

    _shutdown_cleanup(persistence, session_ref)

    persistence.end_session.assert_not_called()
    persistence.insert_system_event.assert_not_called()
