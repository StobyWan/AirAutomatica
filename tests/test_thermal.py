"""Tests for Raspberry Pi thermal helper."""

from unittest.mock import MagicMock, patch

import pytest

from airautomatica.system.thermal import (
    ThermalState,
    get_thermal_state,
    read_temperature_c,
    read_throttled_flags,
)


def test_read_temperature_parses_vcgencmd_output() -> None:
    """Parse temp=45.2'C format."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = type(
            "R", (), {"returncode": 0, "stdout": "temp=45.2'C\n"}
        )()
        assert read_temperature_c() == 45.2


def test_read_temperature_handles_integer_part_only() -> None:
    """Parse temp=72 when no decimals."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = type(
            "R", (), {"returncode": 0, "stdout": "temp=72'C\n"}
        )()
        assert read_temperature_c() == 72.0


def test_read_temperature_returns_none_on_vcgencmd_missing() -> None:
    """Fail safe when vcgencmd not found."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        assert read_temperature_c() is None


def test_read_temperature_returns_none_on_nonzero_return() -> None:
    """Return None when vcgencmd fails."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
        assert read_temperature_c() is None


def test_read_throttled_parses_hex_value() -> None:
    """Parse throttled=0x0 and throttled=0x50000."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = type(
            "R", (), {"returncode": 0, "stdout": "throttled=0x0\n"}
        )()
        assert read_throttled_flags() == 0

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = type(
            "R", (), {"returncode": 0, "stdout": "throttled=0x50000\n"}
        )()
        assert read_throttled_flags() == 0x50000


def test_read_throttled_returns_none_on_missing() -> None:
    """Fail safe when vcgencmd not found."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        assert read_throttled_flags() is None


@patch("airautomatica.system.thermal.read_temperature_c")
@patch("airautomatica.system.thermal.read_throttled_flags")
def test_get_thermal_state_normal_when_unavailable(
    mock_flags: MagicMock, mock_temp: MagicMock
) -> None:
    """When vcgencmd unavailable, treat as NORMAL (fail-safe)."""
    mock_temp.return_value = None
    mock_flags.return_value = None
    assert get_thermal_state() == ThermalState.NORMAL


@patch("airautomatica.system.thermal.read_temperature_c")
@patch("airautomatica.system.thermal.read_throttled_flags")
def test_get_thermal_state_by_temp(mock_flags: MagicMock, mock_temp: MagicMock) -> None:
    """Thermal state derived from temperature thresholds."""
    mock_flags.return_value = 0
    mock_temp.return_value = 65.0
    assert get_thermal_state() == ThermalState.NORMAL
    mock_temp.return_value = 72.0
    assert get_thermal_state() == ThermalState.WARM
    mock_temp.return_value = 82.0
    assert get_thermal_state() == ThermalState.HOT
    mock_temp.return_value = 86.0
    assert get_thermal_state() == ThermalState.THROTTLED


@patch("airautomatica.system.thermal.read_temperature_c")
@patch("airautomatica.system.thermal.read_throttled_flags")
def test_get_thermal_state_throttled_flags_override_temp(
    mock_flags: MagicMock, mock_temp: MagicMock
) -> None:
    """Throttled flags (current bits) override temperature."""
    mock_temp.return_value = 65.0
    mock_flags.return_value = 0x4  # bit 2: currently throttled
    assert get_thermal_state() == ThermalState.THROTTLED
