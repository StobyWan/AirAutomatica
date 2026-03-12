# Phase 3: FC Home Sync — Implementation Plan

**Status**: Future work. Not yet implemented.

**Goal**: Allow the operator to set the flight controller's actual RTL/navigation home via MAVLink. This is distinct from the app home override (Phase 2), which affects only AirAutomatica's calculations and UI.

---

## 1. Scope

- **MAV_CMD_DO_SET_HOME (179)** via COMMAND_LONG
- Supported by ArduPilot and INAV (both have `supports_command_long=True`)
- Generic profile: `supports_command_long=False` — no-op or 503
- Mock telemetry: no transport — 503

**Behavior**:
- Set home to current aircraft position
- Set home to specified lat/lon/alt
- Explicit confirmation in UI (separate from "Set app home")
- Does NOT affect app home; app home remains a separate concept

---

## 2. MAVLink Command Format

From [ArduPilot MAVLink docs](https://ardupilot.org/dev/docs/mavlink-get-set-home-and-origin.html):

**COMMAND_LONG**:
| Field | Value |
|-------|-------|
| command | MAV_CMD_DO_SET_HOME = 179 |
| param1 | 1 = use current location, 0 = use specified location |
| param2–4 | 0 (unused) |
| param5 | Latitude (degrees) — used when param1=0 |
| param6 | Longitude (degrees) — used when param1=0 |
| param7 | Altitude (m, AMSL) — used when param1=0 |

**Use current**: `param1=1`, param5–7 ignored.
**Use specified**: `param1=0`, param5=lat, param6=lon, param7=alt.

---

## 3. Architecture: Transport Access

**Problem**: The MAVLink transport is created inside `MavlinkTelemetrySource.stream()` and is not exposed to the API layer.

**Solution**: FcCommandSender + transport registration.

1. **FcCommandSender** (`src/airautomatica/commands/fc_command_sender.py`):
   - Thread-safe or asyncio-safe holder for `(transport, sysid, compid)`
   - `register(transport)` — called when telemetry connects
   - `unregister()` — called when telemetry disconnects
   - `send_do_set_home(use_current: bool, lat?: float, lon?: float, alt?: float) -> bool` — sends COMMAND_LONG, returns True if sent

2. **VehicleConnectionManager** changes:
   - Add optional `on_connected_callback: Callable[[Any], None] | None`
   - After adapter selection and before reader loop, call `on_connected_callback(transport)` with the transport
   - In `finally` (on disconnect), call `on_unconnected_callback()` if provided

3. **MavlinkTelemetrySource** changes:
   - Accept optional `fc_command_sender: FcCommandSender | None`
   - When creating `VehicleConnectionManager`, pass callbacks that register/unregister the transport
   - Only when backend is `serial`; mock source does not use this

4. **main.py** wiring:
   - Create `FcCommandSender()` when backend is serial
   - Pass to `_create_telemetry_source` (or to the source constructor)
   - Pass to `create_app` for the API

---

## 4. API Design

**POST /fc/home**

Body:
- `{ "use_current": true }` — set FC home to current aircraft position
- `{ "lat": float, "lon": float, "alt_m"?: float }` — set FC home to specified position (alt optional, default 0)

Response:
- `200`: `{ "ok": true }` — command sent (no ACK wait in v1)
- `400`: invalid params
- `503`: FC command not available (mock, generic, or transport disconnected)

**Preconditions**:
- Telemetry backend = serial
- Capability `supports_command_long` = true
- Transport registered (connected)
- Optional: CommandPolicy allows MAV_CMD_DO_SET_HOME

---

## 5. UI Design

**Location**: Dashboard, in or near the "App home" section.

**New subsection**: "FC home (RTL/navigation)"
- Disclaimer: "Sets the flight controller's RTL home. Use with caution."
- Buttons:
  - "Set FC home to current position" — requires confirmation modal
  - "Set FC home to coordinates…" — modal with lat/lon/alt, then confirmation
- Shown only when:
  - Telemetry backend = serial
  - Capabilities include `supports_command_long`
  - Transport connected

**Confirmation modal**: "This will change where the aircraft returns in RTL mode. Continue?"

---

## 6. Files to Create/Modify

| File | Changes |
|------|---------|
| `src/airautomatica/commands/fc_command_sender.py` | **New**. FcCommandSender with register/unregister, send_do_set_home |
| `src/airautomatica/telemetry/services/vehicle_connection_manager.py` | Add on_connected/on_unconnected callbacks |
| `src/airautomatica/telemetry/mavlink_telemetry.py` | Accept fc_command_sender; wire callbacks when backend=serial |
| `src/airautomatica/main.py` | Create FcCommandSender when serial; pass to source and create_app |
| `src/airautomatica/api/server.py` | Add POST /fc/home; accept fc_command_sender |
| `src/airautomatica/ui/templates/dashboard.html` | Add FC home subsection, modal, API calls |
| `docs/commands.md` | Update: MAV_CMD_DO_SET_HOME operational when Phase 3 implemented |

---

## 7. Risks and Tests

**Risks**:
- Transport can disconnect between API call and send; handle gracefully
- No COMMAND_ACK wait in v1 — we fire-and-forget; FC may reject
- INAV support for DO_SET_HOME should be verified on real hardware

**Tests**:
- Unit: FcCommandSender.send_do_set_home when no transport → returns False
- Unit: FcCommandSender.send_do_set_home with mock transport → command_long_send called with correct params
- Integration: POST /fc/home returns 503 when backend=mock
- Integration: POST /fc/home with serial + mock transport → verify command format

---

## 8. Implementation Order

1. Create `FcCommandSender` with register/unregister and `send_do_set_home`
2. Add callbacks to `VehicleConnectionManager`
3. Wire `MavlinkTelemetrySource` to register transport when serial
4. Add `POST /fc/home` to API
5. Add dashboard UI with confirmation
6. Update docs

---

## 9. Relation to App Home

| Concept | Phase | Affects |
|---------|-------|---------|
| App home override | 2 | AirAutomatica distance, bearing, return margin, UI only |
| FC home sync | 3 | Actual ArduPilot/INAV RTL/navigation home |

They are independent. Setting FC home does not change app home. Setting app home does not change FC home.
