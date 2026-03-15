import { get, post } from './client'
import type {
  ConnectionStateResponse,
  DetectionResult,
  PortsResponse,
} from '@/types'

export function getConnectionState(): Promise<ConnectionStateResponse> {
  return get<ConnectionStateResponse>('/connection/state')
}

export function getAvailablePorts(): Promise<PortsResponse> {
  return get<PortsResponse>('/connection/ports')
}

export interface DetectResponse {
  detected: boolean
  connection_state?: string
  message?: string
  port?: string | null
  baud?: number | null
}

export function detectConnection(body?: {
  port?: string
  baud?: number
}): Promise<DetectResponse> {
  return post<DetectResponse>('/connection/detect', body ?? {})
}

export type ConnectionMode =
  | 'mock'
  | 'mock_ardupilot'
  | 'mock_inav'
  | 'ardupilot'
  | 'inav'

export function setConnectionMode(
  mode: ConnectionMode,
  port?: string,
  baud?: number
): Promise<{ restart_required?: boolean }> {
  const body: Record<string, unknown> = { mode }
  if (port != null) body.port = port
  if (baud != null) body.baud = baud
  return post<{ restart_required?: boolean }>('/connection/mode', body)
}

export function disconnect(): Promise<void> {
  return post<void>('/connection/disconnect')
}

export function normalizeConnectionState(
  raw: unknown
): ConnectionStateResponse {
  const r = raw as Record<string, unknown>
  return {
    connection_state: String(r?.connection_state ?? 'setup'),
    session_state: r?.session_state as string | undefined,
    mode: (r?.mode as string | null) ?? null,
    session_id: (r?.session_id as number | null) ?? null,
    detection_result: (r?.detection_result as DetectionResult | null) ?? null,
  }
}
