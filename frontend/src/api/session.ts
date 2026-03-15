import { del, get, patch, post } from './client'
import type {
  SessionSummary,
  Recording,
  RecordingsResponse,
  Event,
  Detection,
} from '@/types'

export interface PathPoint {
  lat: number
  lon: number
}

export interface SessionPathResponse {
  path: PathPoint[]
  session_id: number
  home_lat?: number
  home_lon?: number
  home_source?: string
}

export interface SessionDebriefResponse {
  session_id: number
  summary: {
    session_duration_sec?: number
    phase_duration_sec?: Record<string, number>
    peak_distance_from_home_m?: number
    average_power_w?: number
    peak_power_w?: number
    minimum_voltage_v?: number
    top_events?: { name: string; count: number; duration_sec?: number }[]
    weak_return_margin_occurred?: boolean
    gps_degraded_occurred?: boolean
    unstable_attitude_occurred?: boolean
    assessment_tags?: string[]
  }
  compact?: Record<string, unknown>
  generated_summary?: string
  generated_debrief_at?: string
}

export interface SessionRecordingsResponse {
  session_id: number | null
  session_resolved: boolean
  fallback_used?: boolean
  count: number
  recordings: Recording[]
  recordings_dir?: string | null
}

export interface SessionDetectionsResponse {
  detections: Detection[]
  session_id: number
}

export interface DeleteSessionResponse {
  ok: boolean
  recordings_deleted?: number
  recordings_failed?: number
}

export interface SessionStartResponse {
  ok: boolean
  already_active?: boolean
  session_id?: number
  started_at?: string
  error?: string
}

export function startSession(): Promise<SessionStartResponse> {
  return post<SessionStartResponse>('/session/start', {})
}

export function stopSession(): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>('/session/stop')
}

export interface SessionsResponse {
  sessions: SessionSummary[]
  current_session_id?: number | null
  total: number
}

export function getSessions(params?: {
  autopilot?: string
  connection_mode?: string
  limit?: number
  offset?: number
}): Promise<SessionsResponse> {
  const q = new URLSearchParams()
  if (params?.autopilot) q.set('autopilot', params.autopilot)
  if (params?.connection_mode) q.set('connection_mode', params.connection_mode)
  if (params?.limit != null) q.set('limit', String(params.limit))
  if (params?.offset != null) q.set('offset', String(params.offset))
  const suffix = q.toString() ? '?' + q.toString() : ''
  return get<SessionsResponse>('/sessions' + suffix)
}

export function getSession(sid: number): Promise<SessionSummary> {
  return get<SessionSummary>(`/sessions/${sid}`)
}

export function getSessionPath(sid: number): Promise<SessionPathResponse> {
  return get<SessionPathResponse>(`/sessions/${sid}/path`)
}

export function getSessionDebrief(
  sid: number,
  generateSummary = false
): Promise<SessionDebriefResponse> {
  const q = generateSummary ? '?generate_summary=true' : ''
  return get<SessionDebriefResponse>(`/sessions/${sid}/debrief${q}`)
}

export function getSessionRecordings(
  sid: number
): Promise<SessionRecordingsResponse> {
  return get<SessionRecordingsResponse>(`/sessions/${sid}/recordings`)
}

export function getSessionDetections(
  sid: number
): Promise<SessionDetectionsResponse> {
  return get<SessionDetectionsResponse>(`/sessions/${sid}/detections`)
}

export function getRecentDetections(): Promise<{
  detections: Detection[]
  session_id: number | null
}> {
  return get<{ detections: Detection[]; session_id: number | null }>(
    '/recent-detections'
  )
}

export function getSessionFlightEvents(sid: number): Promise<{ events: Event[]; session_id: number }> {
  return get<{ events: Event[]; session_id: number }>(`/sessions/${sid}/flight-events`)
}

export function getSessionPhaseIntervals(
  sid: number
): Promise<{ intervals: unknown[]; session_id: number }> {
  return get<{ intervals: unknown[]; session_id: number }>(`/sessions/${sid}/phase-intervals`)
}

export interface ReplaySample {
  timestamp: string
  lat?: number | null
  lon?: number | null
  rel_alt_m?: number | null
  voltage_v?: number | null
  current_a?: number | null
  groundspeed_m_s?: number | null
  mode?: string | null
  heading_deg?: number | null
  roll_rad?: number | null
  pitch_rad?: number | null
  yaw_rad?: number | null
  airspeed_m_s?: number | null
  connected?: boolean | null
  watts?: number | null
  heartbeat_age_s?: number | null
  reconnect_count?: number | null
}

export interface TelemetrySamplesResponse {
  samples: ReplaySample[]
  session_id: number
}

export function getSessionTelemetrySamples(
  sid: number,
  params?: { limit?: number; order?: 'asc' | 'desc' }
): Promise<TelemetrySamplesResponse> {
  const q = new URLSearchParams()
  q.set('limit', String(params?.limit ?? 5000))
  q.set('order', params?.order ?? 'asc')
  return get<TelemetrySamplesResponse>(
    `/sessions/${sid}/telemetry-samples?${q.toString()}`
  )
}

export function patchSession(
  sid: number,
  body: { home_lat?: number; home_lon?: number; clear_home?: boolean }
): Promise<SessionSummary> {
  return patch<SessionSummary>(`/sessions/${sid}`, body)
}

export function deleteSession(sid: number): Promise<DeleteSessionResponse> {
  return del<DeleteSessionResponse>(`/sessions/${sid}`)
}

export function deleteRecording(filename: string): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/recordings/${encodeURIComponent(filename)}`)
}

export function getRecordings(sessionId?: number): Promise<RecordingsResponse> {
  const suffix = sessionId != null ? `?session_id=${sessionId}` : ''
  return get<RecordingsResponse>('/recordings' + suffix)
}

export interface RecentEventsResponse {
  events: Event[]
}

export function getRecentEvents(): Promise<RecentEventsResponse> {
  return get<RecentEventsResponse>('/recent-events')
}

export function normalizeSession(raw: unknown): SessionSummary {
  const r = raw as Record<string, unknown>
  return {
    id: Number(r?.id ?? 0),
    started_at: String(r?.started_at ?? ''),
    ended_at: (r?.ended_at as string | null) ?? null,
    autopilot: (r?.autopilot as string | null) ?? null,
    connection_mode: (r?.connection_mode as string | null) ?? null,
    telemetry_backend: (r?.telemetry_backend as string | null) ?? null,
    source_port: (r?.source_port as string | null) ?? null,
    baud: (r?.baud as number | null) ?? null,
    current_session_id: (r?.current_session_id as number | undefined),
    ...r,
  }
}

export function normalizeRecording(raw: unknown): Recording {
  const r = raw as Record<string, unknown>
  return {
    filename: String(r?.filename ?? ''),
    timestamp: String(r?.timestamp ?? ''),
    size_bytes: (r?.size_bytes as number | null) ?? null,
    duration_sec: (r?.duration_sec as number | null) ?? null,
    trigger: (r?.trigger as string | null) ?? null,
    session_id: (r?.session_id as number | null) ?? null,
  }
}

export function normalizeRecordingsResponse(
  raw: unknown
): RecordingsResponse {
  const r = raw as Record<string, unknown>
  const recordings = Array.isArray(r?.recordings)
    ? (r.recordings as unknown[]).map(normalizeRecording)
    : []
  return {
    session_id: (r?.session_id as number | null) ?? null,
    session_resolved: Boolean(r?.session_resolved),
    fallback_used: Boolean(r?.fallback_used),
    count: Number(r?.count ?? recordings.length),
    recordings,
    recordings_dir: (r?.recordings_dir as string | null) ?? null,
  }
}
