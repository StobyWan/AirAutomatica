# Aviation UI Implementation Summary

## Overview

Aviation UI elements for the AirAutomatica dashboard: FlightStatusStrip, Artificial Horizon (attitude), Home Direction, Altitude/Vertical Speed, Speed, and Power/Endurance panels. Implemented as a lightweight UAV companion display with clear fallbacks when telemetry is missing.

## Changed Files (Round 1 + Round 2)

- `src/airautomatica/models/state.py` – Added climb_rate_m_s, gps_fix_type, satellites_visible, home_lat, home_lon
- `src/airautomatica/telemetry/mavlink_parser.py` – Parse GLOBAL_POSITION_INT.vz, GPS_RAW_INT, HOME_POSITION
- `src/airautomatica/telemetry/mock.py` – Mock values for new fields
- `src/airautomatica/ui/templates/dashboard.html` – FlightStatusStrip, Aviation card (Attitude, Home, Altitude, Speed, Power), telemetry utilities, updateAviationWidgets(), updateFlightStatusStrip()
- `docs/AVIATION_UI_IMPLEMENTATION.md` – This document

## Telemetry Dependencies

### FlightStatusStrip

| Field             | Source        | Required | Notes                                  |
|-------------------|---------------|----------|----------------------------------------|
| armed             | AircraftState | No       | ARMED / Disarmed chip                   |
| mode              | AircraftState | No       | Flight mode string                      |
| satellites_visible| AircraftState | No       | From GPS_RAW_INT                        |
| gps_fix_type      | AircraftState | No       | From GPS_RAW_INT (2=2D, 3+=3D)         |
| telemetry_status  | AircraftState / health_update | No | connected / stale / disconnected |

**Fallback:** Each field shows "—" when unavailable.

### Artificial Horizon (Attitude)

| Field     | Source        | Required | Notes                          |
|-----------|---------------|----------|--------------------------------|
| roll_rad  | AircraftState | Yes      | Radians; used for bank display |
| pitch_rad | AircraftState | Yes      | Radians; used for horizon tilt  |

**Fallback:** Shows "Unavailable" when either roll or pitch is null/NaN.

### Home Direction

| Field   | Source                 | Required | Notes                                      |
|---------|------------------------|----------|--------------------------------------------|
| lat, lon| AircraftState          | Yes      | Current position                            |
| home    | state.home_lat/lon or path[0] | Yes | Explicit HOME_POSITION preferred; path[0] fallback |

**Derived:** Distance (haversine), bearing to home, relative bearing (home direction vs heading).

**Fallback:** Shows "Position unavailable" or "Home unavailable" when position or home is missing.

**Home position priority:** 1) Explicit home from `state.home_lat`, `state.home_lon` (HOME_POSITION message). 2) Fallback: first path point from `telemetry_path_update` when HOME_POSITION not in telemetry. `cachedHome` is reset when session_id changes.

**Live vs replay home:** The live dashboard uses autopilot home (or path[0] fallback). The session detail page has a "Replay home override" for past sessions only—it affects replay and debrief metrics, not the flight controller's RTL home. App home overrides do not change the FC.

### Altitude / Vertical Speed

| Field          | Source        | Required | Notes                          |
|----------------|---------------|----------|--------------------------------|
| rel_alt_m      | AircraftState | No       | Above home (m)                 |
| climb_rate_m_s | AircraftState | No       | From GLOBAL_POSITION_INT.vz    |

**Fallback:** Shows "Unavailable" when neither altitude nor climb rate is available. Individual fields show "—" when missing.

### Speed

| Field            | Source        | Required | Notes                          |
|------------------|---------------|----------|--------------------------------|
| airspeed_m_s     | AircraftState | No       | Preferred when valid           |
| groundspeed_m_s  | AircraftState | No       | Fallback when airspeed missing |

**Logic:** Prefer airspeed; else groundspeed. Label clearly: "Airspeed" or "Ground Speed".

**Fallback:** Shows "Unavailable" when neither is valid.

### Power / Endurance

| Field                 | Source        | Required | Notes                          |
|-----------------------|---------------|----------|--------------------------------|
| voltage_v             | AircraftState | No       | Shown when available           |
| current_a             | AircraftState | No       | Shown when available           |
| battery_remaining_pct | AircraftState | No       | Not in model; shows "—"        |
| battery_remaining_mah | AircraftState | No       | Not in model; shows "—"        |

**Derived:** Endurance (min) = remaining_mah / (current_a * 1000) * 60 when both are available.

**Fallback:** Shows "No power data" only when no voltage or current. Individual fields show "—" when missing.

## Raw vs Derived Values

| Value           | Type   | Source / Derivation                          |
|-----------------|--------|----------------------------------------------|
| roll_rad, pitch_rad | Raw | ATTITUDE message                             |
| climb_rate_m_s  | Raw    | GLOBAL_POSITION_INT.vz (negated, cm/s → m/s) |
| gps_fix_type    | Raw    | GPS_RAW_INT                                  |
| satellites_visible | Raw | GPS_RAW_INT                                  |
| home_lat, home_lon | Raw | HOME_POSITION message                        |
| Distance to home| Derived| Haversine(aircraft, home)                    |
| Bearing to home | Derived| atan2 formula                                 |
| Relative bearing| Derived| bearing_to_home - heading                     |
| Endurance       | Derived| remaining_mah / current_a * 60               |

## Telemetry Utilities

- `haversineM(lat1, lon1, lat2, lon2)` – Distance in meters
- `bearingDeg(lat1, lon1, lat2, lon2)` – Bearing from point 1 to point 2
- `relativeBearing(headingDeg, bearingToTargetDeg)` – Angle from heading to target
- `safeNum(v, decimals)` – Safe number formatting with null/NaN handling
- `formatDistance(m)` – m or km as appropriate
- `enduranceMin(remainingMah, currentA)` – Estimated minutes remaining
- `getHomeFromState(state)` – Returns {lat, lon} from state.home_lat/lon or null

## Current Limitations

1. **GPS / satellites:** Only available when GPS_RAW_INT is parsed (ArduPilot/INAV).
2. **Climb rate:** Only available when GLOBAL_POSITION_INT includes vz.
3. **Home position:** Uses path[0] fallback when HOME_POSITION not received. App home overrides affect only app calculations; they do not change the FC's RTL home.
4. **Battery remaining % / mAh:** Not in model; endurance always "—" until extended.

## Recommended Next Steps

1. **Battery:** Add battery_remaining_pct, battery_remaining_mah, consumed_mah to model if MAVLink provides them.
2. **Altitude source label:** Consider showing "MSL" or "AGL" if alt/alt_agl are added.
3. **Speed units:** Optional knots toggle for operator preference.
4. **Vertical speed trend:** Sparkline or trend indicator for climb rate.
