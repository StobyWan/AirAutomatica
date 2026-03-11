"""Raspberry Pi thermal state. Uses vcgencmd when available; fails safe to NORMAL."""

import logging
import re
import subprocess
from enum import Enum

logger = logging.getLogger(__name__)

# Fixed thresholds (Celsius). Pi 5 throttles at 80C, max 85C.
_TEMP_NORMAL_MAX = 70.0
_TEMP_WARM_MAX = 79.0
_TEMP_HOT_MAX = 84.0
# >= 85C or throttled flag = THROTTLED

# Current throttling bits (0-3). Any set = actively throttled.
_THROTTLED_CURRENT_MASK = 0x0F


class ThermalState(str, Enum):
    """Thermal state for scheduler backoff."""

    NORMAL = "normal"
    WARM = "warm"
    HOT = "hot"
    THROTTLED = "throttled"


def read_temperature_c() -> float | None:
    """Read CPU temperature via vcgencmd measure_temp. Returns None if unavailable."""
    try:
        result = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        # Format: temp=45.2'C
        match = re.search(r"temp=([\d.]+)", result.stdout.strip())
        if match:
            return float(match.group(1))
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as e:
        logger.debug("Could not read temperature: %s", e)
        return None


def read_throttled_flags() -> int | None:
    """Read throttled flags via vcgencmd get_throttled. Returns None if unavailable."""
    try:
        result = subprocess.run(
            ["vcgencmd", "get_throttled"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        # Format: throttled=0x0 or throttled=0x50000
        match = re.search(r"throttled=(0x[0-9a-fA-F]+)", result.stdout.strip())
        if match:
            return int(match.group(1), 16)
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as e:
        logger.debug("Could not read throttled flags: %s", e)
        return None


def get_thermal_state() -> ThermalState:
    """Determine thermal state. Returns NORMAL if vcgencmd unavailable (fail-safe)."""
    temp = read_temperature_c()
    flags = read_throttled_flags()

    # Any current throttling bit set = THROTTLED
    if flags is not None and (flags & _THROTTLED_CURRENT_MASK) != 0:
        return ThermalState.THROTTLED

    if temp is None:
        return ThermalState.NORMAL

    if temp >= 85.0:
        return ThermalState.THROTTLED
    if temp >= 80.0:
        return ThermalState.HOT
    if temp >= 70.0:
        return ThermalState.WARM
    return ThermalState.NORMAL
