// API and recordings are served at root; VITE_BASE_PATH is only for SPA routing and assets
export const API_BASE = ''
export const RECORDINGS_BASE = '/recordings'

/** In dev, Socket.IO connects directly to backend (avoids proxy issues). Set VITE_API_PORT to match backend (default 8000). */
export const SOCKET_URL = import.meta.env.DEV
  ? `http://localhost:${import.meta.env.VITE_API_PORT || '8000'}`
  : ''

export function recordingsUrl(filename: string): string {
  if (!filename || typeof filename !== 'string') {
    return ''
  }
  return RECORDINGS_BASE + '/' + encodeURIComponent(filename)
}
