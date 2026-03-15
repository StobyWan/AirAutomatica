import { get, post } from './client'
import type { Settings } from '@/types'

export interface SettingsResponse {
  settings: Settings
  effective_settings: Settings
  apply_modes: Record<string, string>
  telemetry_reconnect_available?: boolean
  ai_reconnect_available?: boolean
  ollama_available?: boolean
  ollama_ready?: boolean
  provider_reason?: string
  active_summary?: string
}

export interface SettingsSaveResponse {
  ok: boolean
  message: string
  changed_keys: string[]
  live: string[]
  reconnect: string[]
  restart: string[]
  restart_required: boolean
  reconnect_required: boolean
  active_telemetry_backend?: string
  active_ai_provider?: string
  active_summary?: string
}

export function getSettings(): Promise<SettingsResponse> {
  return get<SettingsResponse>('/settings')
}

export function postSettings(updates: Record<string, string | number | boolean>): Promise<SettingsSaveResponse> {
  const body: Record<string, string> = {}
  for (const [k, v] of Object.entries(updates)) {
    body[k] = typeof v === 'boolean' ? (v ? '1' : '0') : String(v)
  }
  return post<SettingsSaveResponse>('/settings', body)
}
