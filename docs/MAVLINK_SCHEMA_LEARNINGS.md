# MAVLink Schema: Key Learnings and References

Summary of the ArduPilot vs INAV MAVLink schema overlap analysis and implementation for AirAutomatica.

---

## Key Learnings

### 1. Home-Origin: Two Messages, Same Semantics

- **HOME_POSITION** (id 242) is a standard MAVLink message in common.xml.
- **ArduPilot** sends HOME_POSITION for home-origin semantics.
- **INAV** does not send HOME_POSITION in its MAVLink implementation; it uses **GPS_GLOBAL_ORIGIN** (id 49) instead.
- Both use the same field units (latitude/longitude degE7) and map to `home_lat`, `home_lon` in AircraftState.
- **Schema is standard; implementation behavior differs.**

### 2. INAV HEARTBEAT custom_mode

- INAV mavlink.c maps internal flight modes to **ArduPilot custom_mode values** for GCS compatibility (`inavToArduCopterMap`, `inavToArduPlaneMap`).
- Use the default APM mode mapping for INAV; do not use INAV-specific mode mapping.
- This keeps FlightPhaseEngine, debrief, and UI working with modes like "RTL", "LOITER", etc.

### 3. Two Correctness Fixes Implemented

| Fix | Impact |
|-----|--------|
| **GPS_GLOBAL_ORIGIN parsing** | INAV users get `home_lat`/`home_lon`; distance-to-home, debrief, and UI work correctly. |
| **INAV mode mapping** | Phase classification, trend summaries, debrief, and mode UX use correct semantics. |

### 4. Architecture Fit

- MavlinkNormalizer is the right place for GPS_GLOBAL_ORIGIN.
- AircraftState.home_lat/home_lon already provides the normalized shape.
- Preprocessing/debrief engines consume that contract without changes.
- Small parser changes, broad system improvement.

---

## Canonical MAVLink Sources

| Source | Purpose |
|--------|---------|
| [mavlink.io/common](https://mavlink.io/en/messages/common.html) | Standard message definitions (HEARTBEAT, SYS_STATUS, ATTITUDE, GLOBAL_POSITION_INT, VFR_HUD, GPS_RAW_INT, GPS_GLOBAL_ORIGIN, HOME_POSITION, BATTERY_STATUS) |
| [mavlink.io/ardupilotmega](https://mavlink.io/en/messages/ardupilotmega.html) | ArduPilot dialect extensions |
| [ardupilot.org/dev/docs/mavlink-commands](https://ardupilot.org/dev/docs/mavlink-commands.html) | ArduPilot MAVLink interface docs |
| [iNavFlight/inav mavlink.c](https://raw.githubusercontent.com/iNavFlight/inav/master/src/main/telemetry/mavlink.c) | INAV transmit implementation (primary source for INAV behavior) |
| [iNavFlight/inav Telemetry.md](https://raw.githubusercontent.com/iNavFlight/inav/master/docs/Telemetry.md) | INAV telemetry documentation |

---

## AirAutomatica Docs

| Document | Content |
|----------|---------|
| [docs/mavlink_schema.md](mavlink_schema.md) | Standard MAVLink definitions, ArduPilot behavior, INAV behavior, normalized contract |
| [telemetry_contract.md](../telemetry_contract.md) | MAVLink messages consumed, field conversions, home-origin note |

---

## Message Availability (ArduPilot vs INAV)

| Message | ArduPilot | INAV | Notes |
|---------|-----------|------|-------|
| HEARTBEAT | Yes | Yes | INAV sends ArduPilot custom_mode |
| SYS_STATUS | Yes | Yes | voltage_battery, current_battery |
| ATTITUDE | Yes | Yes | roll, pitch, yaw rad |
| GLOBAL_POSITION_INT | Yes | Yes (when GPS) | lat, lon, relative_alt, hdg, vz |
| VFR_HUD | Yes | Yes | heading, groundspeed, airspeed |
| GPS_RAW_INT | Yes | Yes (when GPS) | fix_type, satellites_visible |
| GPS_GLOBAL_ORIGIN | Yes | Yes (when GPS) | INAV uses for home |
| HOME_POSITION | Yes | No | ArduPilot sends; INAV does not |

---

## Related Code

- **Parser**: `src/airautomatica/telemetry/mavlink_parser.py` — MavlinkNormalizer, GPS_GLOBAL_ORIGIN handler
- **INAV adapter**: `src/airautomatica/telemetry/adapters/inav.py` — Uses default APM mapping
- **State model**: `src/airautomatica/models/state.py` — AircraftState with home_lat, home_lon
