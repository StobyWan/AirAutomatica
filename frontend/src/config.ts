// API and recordings are served at root; VITE_BASE_PATH is only for SPA routing and assets
export const API_BASE = ''
export const RECORDINGS_BASE = '/recordings'

export function recordingsUrl(filename: string): string {
  if (!filename || typeof filename !== 'string') {
    return ''
  }
  return RECORDINGS_BASE + '/' + encodeURIComponent(filename)
}
