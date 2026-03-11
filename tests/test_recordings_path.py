"""Tests for recordings path resolution (packaged/systemd path bug fix)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from airautomatica.api.server import create_app
from airautomatica.config import get_recordings_dir
from airautomatica.services.camera_recording import CameraRecordingService
from airautomatica.services.state_store import StateStore


def test_recordings_dir_resolved_absolute(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """get_recordings_dir() always returns an absolute path regardless of env value."""
    # Relative path in env -> should resolve to absolute (cwd-dependent)
    rel_dir = tmp_path / "recordings"
    rel_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AIRAUTOMATICA_RECORDINGS_DIR", "recordings")
    monkeypatch.delenv("RECORDINGS_DIR", raising=False)
    result = get_recordings_dir()
    assert Path(result).is_absolute()
    assert Path(result).resolve() == rel_dir.resolve()

    # Tilde in env -> should expand and resolve to absolute
    monkeypatch.setenv("AIRAUTOMATICA_RECORDINGS_DIR", "~/.airautomatica/recordings")
    result = get_recordings_dir()
    assert Path(result).is_absolute()
    assert "~" not in result

    # Absolute path -> should stay absolute
    abs_path = str(tmp_path / "abs_recordings")
    monkeypatch.setenv("AIRAUTOMATICA_RECORDINGS_DIR", abs_path)
    result = get_recordings_dir()
    assert Path(result).is_absolute()
    assert result == str(Path(abs_path).resolve())


def test_file_exists_but_wrong_path_regression(
    tmp_path: Path,
) -> None:
    """Regression: file exists on disk at path A but API looks at path B -> 404."""
    dir_a = tmp_path / "dir_a" / "recordings"
    dir_b = tmp_path / "dir_b" / "recordings"
    dir_a.mkdir(parents=True)
    dir_b.mkdir(parents=True)
    # File exists in dir_b only
    (dir_b / "exists.mp4").write_bytes(b"video in B")
    # Service is configured to look in dir_a
    camera_svc = CameraRecordingService(recordings_dir=str(dir_a))
    store = StateStore()
    client = TestClient(create_app(store, camera_recording_service=camera_svc))
    r = client.get("/recordings/exists.mp4")
    assert r.status_code == 404
