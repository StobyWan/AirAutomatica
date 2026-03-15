import { post } from './client'

export function postCameraReady(ready: boolean): Promise<{ ok?: boolean }> {
  return post<{ ok?: boolean }>('/camera/ready', { ready })
}

export function startRecording(): Promise<{ ok?: boolean }> {
  return post<{ ok?: boolean }>('/camera/recording/start')
}

export function stopRecording(): Promise<{ ok?: boolean }> {
  return post<{ ok?: boolean }>('/camera/recording/stop')
}
