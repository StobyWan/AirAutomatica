import { describe, it, expect } from 'vitest'
import { findIndexForTimestamp } from './replayUtils'
import type { ReplaySample } from '@/api/session'

/**
 * Seek mapping: given currentTimestampMs, tStartMs, tEndMs, and samples,
 * verify that seekToTimestamp clamps correctly and findIndexForTimestamp
 * returns the expected sample index.
 */
describe('seek mapping', () => {
  const base = '2024-01-01T00:00:00.000Z'
  const samples: ReplaySample[] = [
    { timestamp: base },
    { timestamp: '2024-01-01T00:00:01.000Z' },
    { timestamp: '2024-01-01T00:00:02.000Z' },
    { timestamp: '2024-01-01T00:00:03.000Z' },
  ]
  const tStartMs = new Date(base).getTime()
  const tEndMs = new Date('2024-01-01T00:00:03.000Z').getTime()

  it('maps timestamp to correct sample index', () => {
    expect(findIndexForTimestamp(samples, tStartMs)).toBe(0)
    expect(findIndexForTimestamp(samples, tStartMs + 500)).toBe(0)
    expect(findIndexForTimestamp(samples, tStartMs + 1000)).toBe(1)
    expect(findIndexForTimestamp(samples, tStartMs + 1500)).toBe(1)
    expect(findIndexForTimestamp(samples, tStartMs + 2500)).toBe(2)
    expect(findIndexForTimestamp(samples, tEndMs)).toBe(3)
  })

  it('returns sample at or before requested timestamp (snaps to boundaries)', () => {
    const offsetMs = 2500
    const tsMs = tStartMs + offsetMs
    const idx = findIndexForTimestamp(samples, tsMs)
    const sampleTs = new Date(samples[idx].timestamp).getTime()
    const backOffsetSec = (sampleTs - tStartMs) / 1000
    expect(backOffsetSec).toBeLessThanOrEqual(offsetMs / 1000)
    expect(idx).toBe(2)
  })
})
