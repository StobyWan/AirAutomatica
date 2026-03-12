# MAVLink Schema: ArduPilot vs INAV for AirAutomatica

This document separates standard MAVLink definitions from autopilot-specific behavior and describes the AirAutomatica normalized contract.

---

## 1. Standard MAVLink Message Definitions

All messages below are from the MAVLink common dialect (common.xml). See [mavlink.io/en/messages/common.html](https://mavlink.io/en/messages/common.html).

| Message | ID | Key Fields | Units / Sentinels |
|---------|-----|------------|-------------------|
| HEARTBEAT | 0 | custom_mode, base_mode, autopilot | custom_mode: autopilot-specific; base_mode bit 7 = armed |
| SYS_STATUS | 1 | voltage_battery, current_battery | mV (65535=invalid), cA (-1=invalid) |
| ATTITUDE | 30 | roll, pitch, yaw | rad |
| GLOBAL_POSITION_INT | 33 | lat, lon, relative_alt, hdg, vz | degE7, mm, cdeg (65535=invalid), cm/s |
| VFR_HUD | 74 | heading, groundspeed, airspeed, climb | deg, m/s |
| GPS_RAW_INT | 24 | fix_type, satellites_visible | 255=unknown sats |
| GPS_GLOBAL_ORIGIN | 49 | latitude, longitude, altitude | degE7, mm |
| HOME_POSITION | 242 | latitude, longitude, altitude | degE7, mm |
| BATTERY_STATUS | 147 | voltages, current_battery, battery_remaining | mV, cA, % |

---

## 2. ArduPilot Behavior

- **Message rates**: Responds to SET_MESSAGE_INTERVAL. AirAutomatica requests 10 Hz for GLOBAL_POSITION_INT, ATTITUDE, SYS_STATUS, VFR_HUD.
- **Home origin**: Sends HOME_POSITION (id 242) for home-origin semantics.
- **custom_mode**: ArduPilot Plane/Copter mode numbers (mode_mapping_apm).
- **GPS**: Sends GPS_RAW_INT, GLOBAL_POSITION_INT when GPS available.

---

## 3. INAV Behavior

- **Transmit-only**: No SET_MESSAGE_INTERVAL. Uses DATA_STREAM rates (MAV_DATA_STREAM_*). Rates configured via INAV CLI.
- **Home origin**: Does not send HOME_POSITION in its MAVLink implementation. Sends GPS_GLOBAL_ORIGIN (id 49) for home-origin semantics instead. Same field units (degE7, mm).
- **custom_mode**: INAV mavlink.c maps internal modes to ArduPilot custom_mode values (inavToArduCopterMap, inavToArduPlaneMap) for GCS compatibility. HEARTBEAT contains ArduPilot-style custom_mode.
- **GPS**: Sends GPS_RAW_INT, GLOBAL_POSITION_INT, GPS_GLOBAL_ORIGIN when GPS available.

**Clarification**: HOME_POSITION is a standard MAVLink message. ArduPilot sends it. INAV does not send it in its MAVLink implementation; INAV uses GPS_GLOBAL_ORIGIN for the same semantic purpose. The schema is standard; the implementation behavior differs.

---

## 4. AirAutomatica Normalized Contract

AircraftState fields and how they map from both autopilots:

| AircraftState Field | ArduPilot Source | INAV Source |
|---------------------|------------------|-------------|
| connected | HEARTBEAT timeout | HEARTBEAT timeout |
| mode | HEARTBEAT.custom_mode (APM mapping) | HEARTBEAT.custom_mode (APM mapping; INAV sends ArduPilot values) |
| armed | HEARTBEAT.base_mode & 128 | HEARTBEAT.base_mode & 128 |
| lat, lon | GLOBAL_POSITION_INT | GLOBAL_POSITION_INT |
| rel_alt_m | GLOBAL_POSITION_INT.relative_alt | GLOBAL_POSITION_INT.relative_alt |
| heading_deg | GLOBAL_POSITION_INT.hdg or VFR_HUD.heading | GLOBAL_POSITION_INT.hdg or VFR_HUD.heading |
| roll_rad, pitch_rad, yaw_rad | ATTITUDE | ATTITUDE |
| voltage_v, current_a | SYS_STATUS | SYS_STATUS |
| groundspeed_m_s, airspeed_m_s | VFR_HUD | VFR_HUD |
| climb_rate_m_s | GLOBAL_POSITION_INT.vz | GLOBAL_POSITION_INT.vz |
| gps_fix_type, satellites_visible | GPS_RAW_INT | GPS_RAW_INT |
| home_lat, home_lon | HOME_POSITION | GPS_GLOBAL_ORIGIN |

Both HOME_POSITION and GPS_GLOBAL_ORIGIN populate home_lat, home_lon via the same accumulator in MavlinkNormalizer.

**App home vs FC home:** AirAutomatica does not send any MAVLink command to set home on the flight controller. The app only reads HOME_POSITION and GPS_GLOBAL_ORIGIN. App-level home overrides (session replay/debrief override, future live app home) affect only AirAutomatica's calculations and UI. They do not change the FC's RTL or navigation home.
