"""Tests for config getters."""

import sys
from pathlib import Path

import pytest

from airautomatica.config import (
    get_camera_recording_mode,
    get_ollama_num_thread,
    get_ollama_required,
    get_recording_ai_overlay_enabled,
    get_recording_ai_persist_threshold,
    validate_serial_config,
)


def test_get_ollama_num_thread_default() -> None:
    """Default is 4 when env not set."""
    with pytest.MonkeyPatch.context() as m:
        m.delenv("OLLAMA_NUM_THREAD", raising=False)
        m.delenv("AIRAUTOMATICA_OLLAMA_NUM_THREAD", raising=False)
        assert get_ollama_num_thread() == 4


def test_get_ollama_num_thread_env_override() -> None:
    """OLLAMA_NUM_THREAD env overrides default."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("OLLAMA_NUM_THREAD", "6")
        m.delenv("AIRAUTOMATICA_OLLAMA_NUM_THREAD", raising=False)
        assert get_ollama_num_thread() == 6


def test_get_ollama_num_thread_airautomatica_prefix() -> None:
    """AIRAUTOMATICA_OLLAMA_NUM_THREAD takes precedence over OLLAMA_NUM_THREAD."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("AIRAUTOMATICA_OLLAMA_NUM_THREAD", "2")
        m.setenv("OLLAMA_NUM_THREAD", "8")
        assert get_ollama_num_thread() == 2


def test_get_ollama_num_thread_clamped() -> None:
    """Values outside 1-8 are clamped."""
    with pytest.MonkeyPatch.context() as m:
        m.delenv("AIRAUTOMATICA_OLLAMA_NUM_THREAD", raising=False)
        m.setenv("OLLAMA_NUM_THREAD", "0")
        assert get_ollama_num_thread() == 1
        m.setenv("OLLAMA_NUM_THREAD", "99")
        assert get_ollama_num_thread() == 8


def test_get_ollama_num_thread_invalid_fallback() -> None:
    """Invalid string falls back to 4."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("OLLAMA_NUM_THREAD", "invalid")
        m.delenv("AIRAUTOMATICA_OLLAMA_NUM_THREAD", raising=False)
        assert get_ollama_num_thread() == 4


def test_get_ollama_required_default() -> None:
    """Default is False when env not set."""
    with pytest.MonkeyPatch.context() as m:
        m.delenv("OLLAMA_REQUIRED", raising=False)
        m.delenv("AIRAUTOMATICA_OLLAMA_REQUIRED", raising=False)
        assert get_ollama_required() is False


def test_get_ollama_required_env_true() -> None:
    """OLLAMA_REQUIRED=1 returns True."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("OLLAMA_REQUIRED", "1")
        m.delenv("AIRAUTOMATICA_OLLAMA_REQUIRED", raising=False)
        assert get_ollama_required() is True


def test_get_ollama_required_airautomatica_wins() -> None:
    """AIRAUTOMATICA_OLLAMA_REQUIRED takes precedence over OLLAMA_REQUIRED."""
    with pytest.MonkeyPatch.context() as m:
        m.setenv("AIRAUTOMATICA_OLLAMA_REQUIRED", "0")
        m.setenv("OLLAMA_REQUIRED", "1")
        assert get_ollama_required() is False
        m.setenv("AIRAUTOMATICA_OLLAMA_REQUIRED", "true")
        assert get_ollama_required() is True


def test_validate_serial_config_mock_always_ok() -> None:
    """Mock backend always passes validation."""
    ok, err = validate_serial_config("mock", "")
    assert ok is True
    assert err is None


def test_validate_serial_config_serial_empty_port_fails() -> None:
    """Serial backend with empty port fails."""
    ok, err = validate_serial_config("serial", "")
    assert ok is False
    assert "required" in (err or "").lower()


def test_validate_serial_config_serial_nonexistent_port_fails() -> None:
    """Serial backend with non-existent port fails on Unix."""
    if sys.platform not in ("linux", "darwin"):
        pytest.skip("Port existence check only on Unix")
    ok, err = validate_serial_config("serial", "/dev/nonexistent999")
    assert ok is False
    assert "not found" in (err or "").lower()


def test_get_camera_recording_mode_live_update_from_save(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save_settings updates persisted value; get_camera_recording_mode reads it for live updates."""
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("airautomatica.settings._SETTINGS_FILE", settings_file)
    monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", tmp_path)
    monkeypatch.delenv("CAMERA_RECORDING_MODE", raising=False)

    from airautomatica.settings import save_settings

    assert get_camera_recording_mode() == "manual"
    save_settings({"CAMERA_RECORDING_MODE": "auto"})
    assert get_camera_recording_mode() == "auto"

    save_settings({"CAMERA_RECORDING_MODE": "off"})
    assert get_camera_recording_mode() == "off"


def test_get_recording_ai_overlay_enabled_default_when_ai_hat_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When AI HAT disabled, overlay is False regardless of env."""
    monkeypatch.setenv("AI_HAT_ENABLED", "0")
    monkeypatch.delenv("RECORDING_AI_OVERLAY_ENABLED", raising=False)
    assert get_recording_ai_overlay_enabled() is False


def test_get_recording_ai_overlay_enabled_default_when_ai_hat_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When AI HAT enabled and env unset, overlay defaults to True."""
    monkeypatch.setenv("AI_HAT_ENABLED", "1")
    monkeypatch.delenv("RECORDING_AI_OVERLAY_ENABLED", raising=False)
    assert get_recording_ai_overlay_enabled() is True


def test_get_recording_ai_overlay_enabled_explicit_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When AI HAT enabled and RECORDING_AI_OVERLAY_ENABLED=0, overlay is False."""
    monkeypatch.setenv("AI_HAT_ENABLED", "1")
    monkeypatch.setenv("RECORDING_AI_OVERLAY_ENABLED", "0")
    assert get_recording_ai_overlay_enabled() is False


def test_get_detection_config_resolves_dependency_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_detection_config resolves overlay and persist from ai_hat chain."""
    monkeypatch.setenv("AI_HAT_ENABLED", "1")
    monkeypatch.delenv("RECORDING_AI_OVERLAY_ENABLED", raising=False)
    monkeypatch.delenv("RECORDING_AI_PERSIST_ENABLED", raising=False)
    from airautomatica.config import DetectionConfig, get_detection_config

    cfg = get_detection_config()
    assert isinstance(cfg, DetectionConfig)
    assert cfg.ai_hat_enabled is True
    assert cfg.recording_overlay_enabled is True
    assert cfg.recording_persist_enabled is True
    assert cfg.inference_threshold == 0.25
    assert cfg.persist_threshold == 0.5


def test_get_detection_config_persist_independent_of_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist is independent of overlay; overlay=0 + persist=1 yields persist=True."""
    monkeypatch.setenv("AI_HAT_ENABLED", "1")
    monkeypatch.setenv("RECORDING_AI_OVERLAY_ENABLED", "0")
    monkeypatch.setenv("RECORDING_AI_PERSIST_ENABLED", "1")
    from airautomatica.config import get_detection_config

    cfg = get_detection_config()
    assert cfg.recording_overlay_enabled is False
    assert cfg.recording_persist_enabled is True


def test_get_detection_config_overlay_and_persist_both_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When overlay=1 and persist=1, config returns both True; runtime skip is in camera_recording."""
    monkeypatch.setenv("AI_HAT_ENABLED", "1")
    monkeypatch.setenv("RECORDING_AI_OVERLAY_ENABLED", "1")
    monkeypatch.setenv("RECORDING_AI_PERSIST_ENABLED", "1")
    from airautomatica.config import get_detection_config

    cfg = get_detection_config()
    assert cfg.recording_overlay_enabled is True
    assert cfg.recording_persist_enabled is True


def test_get_recording_ai_persist_threshold_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default is 0.5 when env not set."""
    monkeypatch.delenv("RECORDING_AI_PERSIST_THRESHOLD", raising=False)
    assert get_recording_ai_persist_threshold() == 0.5


def test_get_recording_ai_persist_threshold_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RECORDING_AI_PERSIST_THRESHOLD env overrides default."""
    monkeypatch.setenv("RECORDING_AI_PERSIST_THRESHOLD", "0.4")
    assert get_recording_ai_persist_threshold() == 0.4
    monkeypatch.setenv("RECORDING_AI_PERSIST_THRESHOLD", "0.8")
    assert get_recording_ai_persist_threshold() == 0.8
