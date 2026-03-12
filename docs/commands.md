# Command Policy (Scaffold)

Future ArduPilot command-back support. **NOT YET OPERATIONAL**—no outbound MAVLink commands.

## Phased Plan

1. **Read-only** (current): Telemetry in, state exposed. No commands.
2. **Advisory**: CommandPolicy evaluates allow/deny. Still no send.
3. **Guarded command-back** (later): Integrate MAVLink command send when policy allows.

## Phase 3: FC Home Sync (Future)

See [PHASE_3_FC_HOME_SYNC_PLAN.md](PHASE_3_FC_HOME_SYNC_PLAN.md) for a concrete implementation plan for MAV_CMD_DO_SET_HOME (179) to set the flight controller's RTL/navigation home. Distinct from app home override (Phase 2).

## CommandPolicy

- `command_enabled`: Master kill switch. Default False.
- `allowed_commands`: Set of command names (e.g. "DO_SET_MODE", "MAV_CMD_DO_SET_MODE").
- `require_connected`: Block if telemetry not connected.
- `heartbeat_max_age_sec`: Block if heartbeat stale.
- `require_min_confidence`: When AI result provided, block if below threshold.

TODO: Cooldown enforcement, MAVLink integration.
