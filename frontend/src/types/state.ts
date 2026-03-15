/** Mirrors backend AircraftState.to_dict() shape. */

export type TelemetryStatus =
  | 'starting'
  | 'connecting'
  | 'connected'
  | 'stale'
  | 'disconnected'
  | 'backoff'

export interface AircraftState {
  connected: boolean
  heartbeat: number
  telemetry_status: TelemetryStatus
  reconnect_count: number
  last_disconnect_reason: string | null
  last_heartbeat_at: string | null
  heartbeat_age_s: number | null
  mode: string
  lat: number | null
  lon: number | null
  rel_alt_m: number | null
  heading_deg: number | null
  roll_rad: number | null
  pitch_rad: number | null
  yaw_rad: number | null
  voltage_v: number | null
  current_a: number | null
  groundspeed_m_s: number | null
  airspeed_m_s: number | null
  timestamp: string
  armed: boolean
  climb_rate_m_s: number | null
  gps_fix_type?: number
  satellites_visible?: number
  home_lat?: number
  home_lon?: number
}
