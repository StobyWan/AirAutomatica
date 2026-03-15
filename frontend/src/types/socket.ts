/** Socket.io event payload shapes. */

import type { AircraftState } from './state'
import type { Detection } from './api'
import type { Event } from './api'
import type { SessionSummary } from './api'

export interface HealthUpdatePayload {
  session_id?: number | null
  camera_recording?: boolean
  camera_ready?: boolean
  camera_recording_started_at?: string | null
  camera_recording_file?: string | null
  camera_recording_last_file?: string | null
  camera_recording_mode?: string
  telemetry_backend?: string
  mode?: string | null
  source_port?: string | null
  baud?: number | null
  [key: string]: unknown
}

export type AppHomeSource = 'manual_live' | 'autopilot' | 'fallback'

export interface StateUpdatePayload {
  state: AircraftState
  app_home_source?: AppHomeSource
}

export interface DetectionsUpdatePayload {
  detections: Detection[]
}

export interface EventsUpdatePayload {
  events: Event[]
}

export interface SessionsUpdatePayload {
  sessions: SessionSummary[]
  current_session_id?: number | null
}

export interface PathPoint {
  lat: number
  lon: number
}

export interface TelemetryPathUpdatePayload {
  path: PathPoint[]
  current_position?: PathPoint | null
  detections?: PathPoint[]
  session_id?: number | null
}

export interface TrendsUpdatePayload {
  voltage?: number[]
  rel_alt?: number[]
  groundspeed?: number[]
  heartbeat?: number[]
}
