"""Command policy scaffold for future ArduPilot command-back. NOT YET OPERATIONAL."""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airautomatica.ai.models import AiResult
    from airautomatica.models.state import AircraftState


@dataclass
class CommandPolicy:
    """Policy for evaluating whether a command may be sent. Scaffold only—no MAVLink send."""

    command_enabled: bool = False
    allowed_commands: frozenset[str] = frozenset()
    command_cooldown_sec: float = 5.0  # TODO: enforce when command-back enabled
    require_connected: bool = True
    heartbeat_max_age_sec: float = 5.0
    require_min_confidence: Optional[float] = None

    def evaluate(
        self,
        command_name: str,
        state: Optional["AircraftState"],
        ai_result: Optional["AiResult"] = None,
    ) -> tuple[bool, str]:
        """Return (allowed, reason). No outbound MAVLink—policy check only."""
        if not self.command_enabled:
            return False, "commands_disabled"
        if command_name not in self.allowed_commands:
            return False, "command_not_allowed"
        if state is None:
            return False, "no_state"
        if self.require_connected and not state.connected:
            return False, "telemetry_not_connected"
        if math.isnan(state.heartbeat_age_s) or state.heartbeat_age_s > self.heartbeat_max_age_sec:
            return False, "stale_heartbeat"
        if self.require_min_confidence is not None and ai_result is not None:
            if ai_result.confidence < self.require_min_confidence:
                return False, "low_confidence"
        return True, "ok"
