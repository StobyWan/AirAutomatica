import { get, post } from './client'
import type { Detection } from '@/types'

export interface AiDetectResponse {
  state?: unknown
  detections?: Detection[]
  errors?: string[]
}

export function aiDetect(): Promise<AiDetectResponse> {
  return post<AiDetectResponse>('/api/ai/detect', {})
}

export function getAiStatus(): Promise<Record<string, unknown>> {
  return get<Record<string, unknown>>('/api/ai/status')
}

export function getLastDetection(): Promise<Record<string, unknown> | null> {
  return get<Record<string, unknown> | null>('/api/ai/last-detection')
}

export function getTelemetrySummary(): Promise<{ summary: string }> {
  return post<{ summary: string }>('/ai/telemetry-summary', {})
}

export function getEventClassification(): Promise<{
  classification?: Record<string, unknown>
}> {
  return post<{ classification?: Record<string, unknown> }>(
    '/ai/event-classification',
    {}
  )
}
