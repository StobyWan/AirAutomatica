/** API response shapes aligned to backend. */

export interface ConnectionStateResponse {
  connection_state: string
  session_state?: string
  mode: string | null
  session_id: number | null
  detection_result: DetectionResult | null
}

export interface DetectionResult {
  detected: boolean
  port?: string
  baud?: number
  autopilot?: string
  message?: string
  heartbeat_age_ms?: number
}

export interface PortInfo {
  path: string
  mavlink_active: boolean
  autopilot: string | null
  baud: number | null
  status: string
}

export interface PortsResponse {
  ports: PortInfo[]
  error?: string
}

export interface SessionSummary {
  id: number
  started_at: string
  ended_at?: string | null
  autopilot?: string | null
  connection_mode?: string | null
  telemetry_backend?: string | null
  source_port?: string | null
  baud?: number | null
  current_session_id?: number
  [key: string]: unknown
}

export interface Recording {
  filename: string
  timestamp: string
  size_bytes?: number | null
  duration_sec?: number | null
  trigger?: string | null
  session_id?: number | null
}

export interface RecordingsResponse {
  session_id: number | null
  session_resolved: boolean
  fallback_used?: boolean
  count: number
  recordings: Recording[]
  recordings_dir?: string | null
}

export interface Event {
  name: string
  started_at?: string
  ended_at?: string
  duration_sec?: number
  [key: string]: unknown
}

export interface Detection {
  label: string
  confidence: number
  summary?: string
  source_backend?: string
  timestamp?: string
  [key: string]: unknown
}

export type Settings = Record<string, string | number | boolean | null>
