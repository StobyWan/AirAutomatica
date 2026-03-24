"""Tests for applying saved serial telemetry over a mock default environment."""

import json
import os
from pathlib import Path

import pytest

from airautomatica.settings import reconcile_telemetry_env_from_settings_file


def test_reconcile_applies_serial_when_env_mock_and_port_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_port = tmp_path / "ttyFAKE"
    fake_port.write_text("")
    settings_dir = tmp_path / ".airautomatica"
    settings_dir.mkdir()
    settings_file = settings_dir / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "TELEMETRY_BACKEND": "serial",
                "SERIAL_PORT": str(fake_port),
                "SERIAL_BAUD": "57600",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
    monkeypatch.setattr("airautomatica.settings._SETTINGS_FILE", settings_file)
    monkeypatch.setenv("TELEMETRY_BACKEND", "mock")
    monkeypatch.delenv("SERIAL_PORT", raising=False)
    monkeypatch.delenv("SERIAL_BAUD", raising=False)

    reconcile_telemetry_env_from_settings_file()

    assert os.environ["TELEMETRY_BACKEND"] == "serial"
    assert os.environ["SERIAL_PORT"] == str(fake_port)
    assert os.environ["SERIAL_BAUD"] == "57600"


def test_reconcile_skips_when_saved_serial_port_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings_dir = tmp_path / ".airautomatica"
    settings_dir.mkdir()
    settings_file = settings_dir / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "TELEMETRY_BACKEND": "serial",
                "SERIAL_PORT": "/dev/nonexistent_port_xyz",
                "SERIAL_BAUD": "921600",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
    monkeypatch.setattr("airautomatica.settings._SETTINGS_FILE", settings_file)
    monkeypatch.setenv("TELEMETRY_BACKEND", "mock")

    reconcile_telemetry_env_from_settings_file()

    assert os.environ["TELEMETRY_BACKEND"] == "mock"


def test_reconcile_respects_skip_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_port = tmp_path / "ttyFAKE2"
    fake_port.write_text("")
    settings_dir = tmp_path / ".airautomatica"
    settings_dir.mkdir()
    settings_file = settings_dir / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "TELEMETRY_BACKEND": "serial",
                "SERIAL_PORT": str(fake_port),
                "SERIAL_BAUD": "921600",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("airautomatica.settings._SETTINGS_DIR", settings_dir)
    monkeypatch.setattr("airautomatica.settings._SETTINGS_FILE", settings_file)
    monkeypatch.setenv("TELEMETRY_BACKEND", "mock")
    monkeypatch.setenv("AIRAUTOMATICA_SKIP_FILE_TELEMETRY_RECONCILE", "1")

    reconcile_telemetry_env_from_settings_file()

    assert os.environ["TELEMETRY_BACKEND"] == "mock"
