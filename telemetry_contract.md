# Telemetry Contract

Target: **Matek F405-WING V2** running **ArduPilot Plane** over MAVLink.

## MAVLink Messages Consumed

| Message | ID | Purpose |
|---------|-----|---------|
| HEARTBEAT | 0 | Flight mode, connection liveness |
| GLOBAL_POSITION_INT | 33 | Position, altitude, heading |
| ATTITUDE | 30 | Roll, pitch, yaw (radians) |
| SYS_STATUS | 1 | Battery voltage, current |
| VFR_HUD | 74 | Heading, groundspeed, airspeed |

---

## Message Field Conversions

### HEARTBEAT (id 0)

| Field | Type | Units | Sentinel | Conversion |
|-------|------|-------|----------|------------|
| `custom_mode` | uint32 | - | - | Map to mode string via ArduPilot Plane mapping (see below) |
| `system_status` | uint8 | MAV_STATE | - | Armed/disarmed; not used for flight mode |
| `type` | uint8 | MAV_TYPE | - | MAV_TYPE_FIXED_WING=1 for Plane |

**Flight mode mapping (ArduPilot Plane, mode_mapping_apm):**

| custom_mode | Mode |
|-------------|------|
| 0 | MANUAL |
| 1 | CIRCLE |
| 2 | STABILIZE |
| 3 | TRAINING |
| 4 | ACRO |
| 5 | FBWA |
| 6 | FBWB |
| 7 | CRUISE |
| 8 | AUTOTUNE |
| 10 | AUTO |
| 11 | RTL |
| 12 | LOITER |
| 13 | TAKEOFF |
| 14 | AVOID_ADSB |
| 15 | GUIDED |
| 16 | INITIALISING |
| 17-26 | QSTABILIZE, QHOVER, QLOITER, QLAND, QRTL, etc. |

Unknown values → `"UNKNOWN"`.

---

### GLOBAL_POSITION_INT (id 33)

| Field | Type | Units | Sentinel | Conversion |
|-------|------|-------|----------|------------|
| `lat` | int32 | degE7 | - | `lat / 1e7` → degrees |
| `lon` | int32 | degE7 | - | `lon / 1e7` → degrees |
| `relative_alt` | int32 | mm | - | `relative_alt / 1000` → m |
| `hdg` | uint16 | cdeg | UINT16_MAX (65535) | If != 65535: `hdg / 100` → deg (0–359.99) |

---

### ATTITUDE (id 30)

| Field | Type | Units | Sentinel | Conversion |
|-------|------|-------|----------|------------|
| `roll` | float | rad | - | Direct (range -π..+π) |
| `pitch` | float | rad | - | Direct |
| `yaw` | float | rad | - | Direct |

---

### SYS_STATUS (id 1)

| Field | Type | Units | Sentinel | Conversion |
|-------|------|-------|----------|------------|
| `voltage_battery` | uint16 | mV | UINT16_MAX (65535) | If != 65535: `voltage_battery / 1000` → V |
| `current_battery` | int16 | cA | -1 | If != -1: `current_battery / 100` → A |

---

### VFR_HUD (id 74)

| Field | Type | Units | Sentinel | Conversion |
|-------|------|-------|----------|------------|
| `heading` | int16 | deg | - | Direct (0–360) |
| `groundspeed` | float | m/s | - | Direct |
| `airspeed` | float | m/s | - | Direct |

**Heading precedence:** VFR_HUD.heading overrides GLOBAL_POSITION_INT.hdg when both are available (VFR_HUD is HUD-oriented).

---

## Internal AircraftState Fields

| Field | Type | Units | Notes |
|-------|------|-------|-------|
| `connected` | bool | - | False if no HEARTBEAT within timeout (default 3s) |
| `heartbeat` | int | - | Count of HEARTBEAT messages received |
| `telemetry_status` | TelemetryStatus | - | Lifecycle status (see below) |
| `reconnect_count` | int | - | Number of reconnects since start |
| `last_disconnect_reason` | str \| None | - | Reason for last disconnect |
| `last_heartbeat_at` | datetime \| None | - | UTC time of last HEARTBEAT; None if never |
| `heartbeat_age_s` | float | s | Seconds since last HEARTBEAT; NaN if never (API returns null) |
| `mode` | str | - | Flight mode name |

**TelemetryStatus values:** `starting`, `connecting`, `connected`, `stale`, `disconnected`, `backoff`. See [Telemetry Lifecycle States](#telemetry-lifecycle-states).
| `lat` | float | deg | NaN if unknown |
| `lon` | float | deg | NaN if unknown |
| `rel_alt_m` | float | m | Altitude above home; NaN if unknown |
| `heading_deg` | float | deg | 0–360; NaN if unknown |
| `roll_rad` | float | rad | NaN if unknown |
| `pitch_rad` | float | rad | NaN if unknown |
| `yaw_rad` | float | rad | NaN if unknown |
| `voltage_v` | float | V | NaN if unknown |
| `current_a` | float | A | NaN if unknown |
| `groundspeed_m_s` | float | m/s | NaN if unknown |
| `airspeed_m_s` | float | m/s | NaN if unknown |
| `timestamp` | datetime | - | Local receive time (UTC) |

---

## Serial Port and Baud Configuration

See [ArduPilot Raspberry Pi MAVLink](https://ardupilot.org/dev/docs/raspberry-pi-via-mavlink.html) and [common-serial-options](https://ardupilot.org/plane/docs/common-serial-options.html).

| Connection | Port (Pi) | Baud | FC Parameter |
|------------|-----------|------|--------------|
| USB (SERIAL0) | `/dev/ttyACM0` | 921600 or 115200 | SERIAL0_BAUD |
| UART (SERIAL2/TELEM2) | `/dev/serial0` | 921600 | SERIAL2_BAUD=921 |
| Telemetry radio | `/dev/ttyUSB0` etc | 57600 | SERIAL_BAUD=57600 via env |

**SERIALx_BAUD mapping:** ArduPilot uses parameter codes; `921` = 921600 baud.

**Matek F405-WING:** SERIAL0=USB, SERIAL1=Telem1, SERIAL2=empty. For UART companion, set SERIAL2_PROTOCOL=2 (MAVLink2), SERIAL2_BAUD=921.

---

## Telemetry Lifecycle States

The serial MAVLink backend derives `telemetry_status` from the connection lifecycle:

| Status | Meaning |
|--------|---------|
| `starting` | Initial state before first connection attempt |
| `connecting` | Waiting for HEARTBEAT from flight controller |
| `connected` | HEARTBEAT received recently, reader active |
| `stale` | HEARTBEAT timeout exceeded; reader may still be active |
| `disconnected` | Connection lost; about to enter backoff |
| `backoff` | In reconnect backoff; will retry after delay |

**API:** `heartbeat_age_s` is `null` in JSON when unknown (no heartbeat yet). `/health` and `/state` expose `telemetry_status`, `reconnect_count`, and `last_disconnect_reason`.

---

## Autopilot Detection and Capability Probes

HEARTBEAT `autopilot` (uint8) drives adapter selection: ArduPilot=3 (MAV_AUTOPILOT_ARDUPILOTMEGA), INAV=13, others → generic read-only profile. Each adapter exposes a capability profile (params read/write, missions, guided, etc.). Adapters may run optional probes (e.g. param read); probe failures add downgrade reasons and reduce reported capabilities. See `/health` `capabilities` block and dashboard Autopilot Capabilities panel.

---

## TODOs

- **BATTERY_STATUS**: Richer battery data (cell voltages, etc.). Currently use SYS_STATUS only. Consider BATTERY_STATUS if needed.
- **Timestamp source**: Currently `datetime.now()`. MAVLink has `time_boot_ms` (ATTITUDE, GLOBAL_POSITION_INT) and `time_unix_usec` (SYSTEM_TIME). Optionally use SYSTEM_TIME for timestamp if available.
