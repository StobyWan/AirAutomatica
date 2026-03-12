"""Tests for RecordingsService: sidecar .meta read, RecordingInfo, delete."""

import json
from pathlib import Path

import pytest

from airautomatica.services.recordings_service import (
    RecordingsService,
    _meta_path_for_recording,
    _read_recording_meta,
)


def test_meta_path_for_recording() -> None:
    """_meta_path_for_recording returns path with .meta suffix."""
    p = Path("/dir/2025-03-12_143000_cam.mp4")
    meta = _meta_path_for_recording(p)
    assert meta == Path("/dir/2025-03-12_143000_cam.mp4.meta")


def test_read_recording_meta_missing(tmp_path: Path) -> None:
    """_read_recording_meta returns (None, None) when .meta does not exist."""
    vid = tmp_path / "2025-03-12_143000_cam.mp4"
    vid.write_bytes(b"x")
    trigger, session_id = _read_recording_meta(vid)
    assert trigger is None
    assert session_id is None


def test_read_recording_meta_present(tmp_path: Path) -> None:
    """_read_recording_meta returns (trigger, session_id) when .meta exists."""
    vid = tmp_path / "2025-03-12_143000_cam.mp4"
    vid.write_bytes(b"x")
    meta = tmp_path / "2025-03-12_143000_cam.mp4.meta"
    meta.write_text('{"trigger":"auto","session_id":123}', encoding="utf-8")
    trigger, session_id = _read_recording_meta(vid)
    assert trigger == "auto"
    assert session_id == 123


def test_read_recording_meta_invalid_json(tmp_path: Path) -> None:
    """_read_recording_meta returns (None, None) on parse error."""
    vid = tmp_path / "2025-03-12_143000_cam.mp4"
    vid.write_bytes(b"x")
    meta = tmp_path / "2025-03-12_143000_cam.mp4.meta"
    meta.write_text("not json", encoding="utf-8")
    trigger, session_id = _read_recording_meta(vid)
    assert trigger is None
    assert session_id is None


def test_get_recordings_includes_trigger_session_id(tmp_path: Path) -> None:
    """get_recordings returns RecordingInfo with trigger and session_id when .meta present."""
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / "2025-03-12_143000_cam.mp4").write_bytes(b"video")
    (rec_dir / "2025-03-12_143000_cam.mp4.meta").write_text(
        '{"trigger":"auto","session_id":456}', encoding="utf-8"
    )
    svc = RecordingsService(recordings_dir=str(rec_dir))
    result = svc.get_recordings(session_id=None)
    assert result.count == 1
    r = result.recordings[0]
    assert r.trigger == "auto"
    assert r.session_id == 456


def test_get_recordings_omits_trigger_session_id_when_no_meta(tmp_path: Path) -> None:
    """get_recordings returns RecordingInfo with trigger/session_id None when no .meta."""
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / "2025-03-12_143000_cam.mp4").write_bytes(b"video")
    svc = RecordingsService(recordings_dir=str(rec_dir))
    result = svc.get_recordings(session_id=None)
    assert result.count == 1
    r = result.recordings[0]
    assert r.trigger is None
    assert r.session_id is None


def test_delete_recording_removes_meta(tmp_path: Path) -> None:
    """delete_recording removes .meta file when recording is deleted."""
    rec_dir = tmp_path / "recordings"
    rec_dir.mkdir()
    (rec_dir / "2025-03-12_143000_cam.mp4").write_bytes(b"video")
    (rec_dir / "2025-03-12_143000_cam.mp4.meta").write_text(
        '{"trigger":"auto","session_id":1}', encoding="utf-8"
    )
    svc = RecordingsService(recordings_dir=str(rec_dir))
    ok = svc.delete_recording("2025-03-12_143000_cam.mp4")
    assert ok is True
    assert not (rec_dir / "2025-03-12_143000_cam.mp4").exists()
    assert not (rec_dir / "2025-03-12_143000_cam.mp4.meta").exists()
