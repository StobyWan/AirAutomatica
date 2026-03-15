/** Replay utilities: binary search, chart precompute, types. */

import type { ReplaySample } from '@/api/session'

export interface FlightEvent {
  event_name?: string
  name?: string
  started_at: string
  ended_at?: string | null
  severity?: string
}

export interface PhaseInterval {
  phase: string
  started_at: string
  ended_at: string
}

export interface ChartData {
  labels: number[]
  speedKmh: number[]
  bearingDeg: number[]
  rollDeg: number[]
}

/**
 * Binary search: index of sample with timestamp <= tsMs.
 * Returns 0 if before first, samples.length - 1 if after last.
 */
export function findIndexForTimestamp(
  samples: ReplaySample[],
  tsMs: number
): number {
  if (samples.length === 0) return 0
  const first = new Date(samples[0].timestamp).getTime()
  const last = new Date(samples[samples.length - 1].timestamp).getTime()
  if (tsMs <= first) return 0
  if (tsMs >= last) return samples.length - 1
  let lo = 0
  let hi = samples.length - 1
  while (lo < hi) {
    const mid = (lo + hi + 1) >>> 1
    const t = new Date(samples[mid].timestamp).getTime()
    if (t <= tsMs) lo = mid
    else hi = mid - 1
  }
  return lo
}

/**
 * Precompute chart-friendly arrays. All conversions done once.
 */
export function precomputeChartData(
  samples: ReplaySample[],
  tStartMs: number
): ChartData {
  const labels: number[] = []
  const speedKmh: number[] = []
  const bearingDeg: number[] = []
  const rollDeg: number[] = []
  for (const s of samples) {
    const t = new Date(s.timestamp).getTime()
    labels.push((t - tStartMs) / 1000)
    speedKmh.push((s.groundspeed_m_s ?? 0) * 3.6)
    bearingDeg.push(s.heading_deg ?? 0)
    rollDeg.push(((s.roll_rad ?? 0) * 180) / Math.PI)
  }
  return { labels, speedKmh, bearingDeg, rollDeg }
}

/** Format offset ms as M:SS */
export function formatOffsetMs(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}
