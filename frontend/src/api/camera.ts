import { get, post } from './client'

export interface CameraInfo {
  id: string
  display_name: string
  source_type: string
  is_selected: boolean
}

export interface CameraStatusResponse {
  cameras: CameraInfo[]
  configured_source_id: string
  configured_auto_fallback: boolean
  active_camera_id: string | null
  active_camera_label: string | null
  active_camera_kind: string | null
  preview_available: boolean
  recording_available: boolean
  still_capture_available: boolean
  recording_active: boolean
}

export function getCameraStatus(): Promise<CameraStatusResponse> {
  return get<CameraStatusResponse>('/camera/status')
}

export function postCameraReady(ready: boolean): Promise<{ ok?: boolean }> {
  return post<{ ok?: boolean }>('/camera/ready', { ready })
}

export function startRecording(): Promise<{ ok?: boolean }> {
  return post<{ ok?: boolean }>('/camera/recording/start')
}

export function stopRecording(): Promise<{ ok?: boolean }> {
  return post<{ ok?: boolean }>('/camera/recording/stop')
}
