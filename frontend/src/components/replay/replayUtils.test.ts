import { describe, it, expect } from 'vitest'
import {
  findIndexForTimestamp,
  precomputeChartData,
  selectPrimaryRecording,
  formatOffsetMs,
} from './replayUtils'
import type { ReplaySample } from '@/api/session'

describe('findIndexForTimestamp', () => {
  const samples: ReplaySample[] = [
    { timestamp: '2024-01-01T00:00:00.000Z' },
    { timestamp: '2024-01-01T00:00:01.000Z' },
    { timestamp: '2024-01-01T00:00:02.000Z' },
    { timestamp: '2024-01-01T00:00:03.000Z' },
    { timestamp: '2024-01-01T00:00:04.000Z' },
  ]
  const t0 = new Date('2024-01-01T00:00:00.000Z').getTime()

  it('returns 0 for empty array', () => {
    expect(findIndexForTimestamp([], t0)).toBe(0)
  })

  it('returns 0 when ts before first', () => {
    expect(findIndexForTimestamp(samples, t0 - 1000)).toBe(0)
  })

  it('returns last index when ts after last', () => {
    expect(findIndexForTimestamp(samples, t0 + 10000)).toBe(samples.length - 1)
  })

  it('returns exact index for exact match', () => {
    expect(findIndexForTimestamp(samples, t0)).toBe(0)
    expect(findIndexForTimestamp(samples, t0 + 2000)).toBe(2)
  })

  it('returns correct index for value between samples', () => {
    expect(findIndexForTimestamp(samples, t0 + 500)).toBe(0)
    expect(findIndexForTimestamp(samples, t0 + 1500)).toBe(1)
    expect(findIndexForTimestamp(samples, t0 + 2500)).toBe(2)
  })
})

describe('precomputeChartData', () => {
  const samples: ReplaySample[] = [
    { timestamp: '2024-01-01T00:00:00.000Z', groundspeed_m_s: 10, heading_deg: 90, roll_rad: 0 },
    { timestamp: '2024-01-01T00:00:01.000Z', groundspeed_m_s: 20, heading_deg: 180, roll_rad: Math.PI / 180 },
  ]
  const tStartMs = new Date('2024-01-01T00:00:00.000Z').getTime()

  it('computes labels as seconds from start', () => {
    const data = precomputeChartData(samples, tStartMs)
    expect(data.labels).toEqual([0, 1])
  })

  it('converts groundspeed to km/h', () => {
    const data = precomputeChartData(samples, tStartMs)
    expect(data.speedKmh).toEqual([36, 72])
  })

  it('passes through bearing degrees', () => {
    const data = precomputeChartData(samples, tStartMs)
    expect(data.bearingDeg).toEqual([90, 180])
  })

  it('converts roll rad to deg', () => {
    const data = precomputeChartData(samples, tStartMs)
    expect(data.rollDeg[0]).toBe(0)
    expect(data.rollDeg[1]).toBeCloseTo(1, 5)
  })

  it('handles null/undefined with defaults', () => {
    const sparse: ReplaySample[] = [
      { timestamp: '2024-01-01T00:00:00.000Z' },
    ]
    const data = precomputeChartData(sparse, tStartMs)
    expect(data.speedKmh[0]).toBe(0)
    expect(data.bearingDeg[0]).toBe(0)
    expect(data.rollDeg[0]).toBe(0)
  })
})

describe('selectPrimaryRecording', () => {
  const recs = [
    { timestamp: '2024-01-01T00:00:00.000Z', trigger: 'manual', session_id: 1 },
    { timestamp: '2024-01-01T00:00:05.000Z', trigger: 'auto', session_id: 1 },
    { timestamp: '2024-01-01T00:00:10.000Z', trigger: 'manual', session_id: 1 },
  ]
  const sessionStartMs = new Date('2024-01-01T00:00:00.000Z').getTime()

  it('returns null for empty array', () => {
    expect(selectPrimaryRecording([], sessionStartMs, 1)).toBeNull()
  })

  it('prefers auto-trigger matching session', () => {
    const r = selectPrimaryRecording(recs, sessionStartMs, 1)
    expect(r?.trigger).toBe('auto')
    expect(r?.timestamp).toBe('2024-01-01T00:00:05.000Z')
  })

  it('falls back to closest when no auto match', () => {
    const noAuto = recs.filter((r) => r.trigger !== 'auto')
    const r = selectPrimaryRecording(noAuto, sessionStartMs, 1)
    expect(r?.timestamp).toBe('2024-01-01T00:00:00.000Z')
  })

  it('picks closest to session start when no auto', () => {
    const shifted = [
      { timestamp: '2024-01-01T00:00:10.000Z', trigger: 'manual', session_id: 1 },
      { timestamp: '2024-01-01T00:00:02.000Z', trigger: 'manual', session_id: 1 },
    ]
    const r = selectPrimaryRecording(shifted, sessionStartMs, 1)
    expect(r?.timestamp).toBe('2024-01-01T00:00:02.000Z')
  })
})

describe('formatOffsetMs', () => {
  it('formats 0 as 0:00', () => {
    expect(formatOffsetMs(0)).toBe('0:00')
  })

  it('formats 65 seconds as 1:05', () => {
    expect(formatOffsetMs(65000)).toBe('1:05')
  })

  it('formats 5 minutes 30 seconds', () => {
    expect(formatOffsetMs(330000)).toBe('5:30')
  })
})
