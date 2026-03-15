const basePath = (import.meta.env.VITE_BASE_PATH || '').replace(/\/$/, '')
export const API_BASE = basePath || ''
export const RECORDINGS_BASE = basePath ? basePath + '/recordings' : '/recordings'

export function recordingsUrl(filename: string): string {
  if (!filename || typeof filename !== 'string') {
    return ''
  }
  return RECORDINGS_BASE + '/' + encodeURIComponent(filename)
}
