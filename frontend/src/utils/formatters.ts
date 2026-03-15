/** Vue-safe formatters. No HTML strings. Use { text, na } where NA placeholder needed. */

const NA = '—'

export interface FmtResult {
  text: string
  na: boolean
}

function fmtValue(v: unknown, fallback: string = NA): FmtResult {
  const na = v == null || v === ''
  return { text: na ? fallback : String(v), na }
}

function fmtNumValue(v: unknown): FmtResult {
  const na =
    v == null ||
    (typeof v === 'number' && Number.isNaN(v))
  return { text: na ? NA : String(v), na }
}

export function fmt(v: unknown): FmtResult {
  return fmtValue(v)
}

export function fmtNum(v: unknown): FmtResult {
  return fmtNumValue(v)
}

export function fmtNumPrec(v: unknown, decimals: number): FmtResult {
  const na =
    v == null ||
    (typeof v === 'number' && Number.isNaN(v))
  return {
    text: na ? NA : Number(v).toFixed(decimals),
    na,
  }
}

export function fmtRate(v: unknown): string | null {
  if (v != null && typeof v === 'number' && Number.isFinite(v)) {
    return (v * 100).toFixed(1) + '%'
  }
  return null
}

export function fmtHeading(v: unknown): FmtResult {
  if (v == null || (typeof v === 'number' && Number.isNaN(v))) {
    return { text: NA, na: true }
  }
  const n = Number(v)
  if (
    n < 0 ||
    n > 360 ||
    !Number.isFinite(n) ||
    Math.abs(n) > 1e6
  ) {
    return { text: NA, na: true }
  }
  return { text: n.toFixed(0), na: false }
}

export function fmtDate(s: unknown): string {
  if (!s) return NA
  try {
    return new Date(s as string).toLocaleString()
  } catch {
    return String(s)
  }
}

export function fmtDuration(started: unknown, ended: unknown): string {
  if (!started || !ended) return NA
  try {
    const sec = Math.round(
      (new Date(ended as string).getTime() -
        new Date(started as string).getTime()) /
        1000
    )
    if (sec < 60) return sec + ' s'
    if (sec < 3600) return Math.floor(sec / 60) + ' m'
    return (
      Math.floor(sec / 3600) +
      ' h ' +
      Math.floor((sec % 3600) / 60) +
      ' m'
    )
  } catch {
    return NA
  }
}

export function formatDuration(sec: unknown): string {
  if (sec == null || (typeof sec === 'number' && Number.isNaN(sec))) {
    return NA
  }
  const s = Math.round(Number(sec))
  if (s < 60) return s + ' s'
  if (s < 3600) return Math.floor(s / 60) + ' m'
  return (
    Math.floor(s / 3600) + ' h ' + Math.floor((s % 3600) / 60) + ' m'
  )
}

export function fmtTs(ts: unknown): string {
  return ts ? new Date(ts as string).toLocaleString() : NA
}

export function fmtTsTime(ts: unknown): string {
  return ts ? new Date(ts as string).toLocaleTimeString() : NA
}

export function labelAutopilot(s: {
  autopilot?: string | null
  connection_mode?: string | null
}): string {
  const a = s?.autopilot
  if (a === 'mock' || (s?.connection_mode === 'mock' && !a)) {
    return 'Mock session'
  }
  if (a === 'ardupilot') return 'ArduPilot'
  if (a === 'inav') return 'iNav'
  if (a === 'generic') return 'iNav/Generic'
  return 'Unknown autopilot'
}

export function labelMode(s: {
  connection_mode?: string | null
  telemetry_backend?: string | null
}): string {
  const m =
    s?.connection_mode ??
    (s?.telemetry_backend === 'mock' ? 'mock' : null)
  if (m === 'mock') return 'Mock'
  if (m === 'ardupilot') return 'ArduPilot'
  if (m === 'inav') return 'iNav'
  return m ?? NA
}

export function labelSource(s: {
  connection_mode?: string
  telemetry_backend?: string
  source_port?: string
  baud?: number
}): string {
  if (
    s?.connection_mode === 'mock' ||
    s?.telemetry_backend === 'mock'
  ) {
    return 'Mock session'
  }
  if (s?.source_port) {
    return s.source_port + (s.baud ? ' @ ' + s.baud : '')
  }
  return 'No port'
}

export function formatMetersOrKm(m: unknown): string {
  if (m == null || (typeof m === 'number' && Number.isNaN(m))) {
    return NA
  }
  const n = Number(m)
  if (n >= 1000) return (n / 1000).toFixed(1) + ' km'
  return n.toFixed(0) + ' m'
}

export function formatDistance(m: unknown): string {
  if (m == null || !Number.isFinite(Number(m)) || Number(m) < 0) {
    return NA
  }
  const n = Number(m)
  if (n < 1000) return n.toFixed(0) + ' m'
  return (n / 1000).toFixed(2) + ' km'
}

export function formatWatts(w: unknown): string {
  if (w == null || (typeof w === 'number' && Number.isNaN(w))) {
    return NA
  }
  return Number(w).toFixed(1) + ' W'
}

export function formatVolts(v: unknown): string {
  if (v == null || (typeof v === 'number' && Number.isNaN(v))) {
    return NA
  }
  return Number(v).toFixed(2) + ' V'
}

export function fmtSourceBackend(source: unknown): FmtResult {
  if (source == null || source === '') return { text: NA, na: true }
  const s = String(source)
  const map: Record<string, string> = {
    aihat: 'AI HAT one-shot',
    ai_hat_recording: 'AI HAT recording',
    mock: 'Mission (mock)',
    ollama: 'Mission (Ollama)',
  }
  return { text: map[s] ?? s, na: false }
}
