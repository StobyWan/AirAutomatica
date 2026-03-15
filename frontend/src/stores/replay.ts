import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  getSessionTelemetrySamples,
  getSessionPath,
  getSessionRecordings,
  getSessionFlightEvents,
  getSessionPhaseIntervals,
} from '@/api/session'
import type { ReplaySample } from '@/api/session'
import type { Recording } from '@/types'
import type { PathPoint } from '@/api/session'
import {
  findIndexForTimestamp,
  precomputeChartData,
  selectPrimaryRecording as selectPrimaryRecordingUtil,
  type ChartData,
  type FlightEvent,
  type PhaseInterval,
} from '@/components/replay/replayUtils'

export const useReplayStore = defineStore('replay', () => {
  const sessionId = ref<number | null>(null)
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  const samples = ref<ReplaySample[]>([])
  const recordings = ref<Recording[]>([])
  const primaryRecording = ref<Recording | null>(null)
  const events = ref<FlightEvent[]>([])
  const phases = ref<PhaseInterval[]>([])
  const path = ref<PathPoint[]>([])
  const homeLat = ref<number | null>(null)
  const homeLon = ref<number | null>(null)

  const tStartMs = ref(0)
  const tEndMs = ref(0)
  const currentTimestampMs = ref(0)
  const isPlaying = ref(false)
  const playbackSpeed = ref(1)
  const hoverTimestampMs = ref<number | null>(null)
  const recordingOffsetSec = ref(0)

  let rafId: number | null = null
  let lastTickTime = 0
  let loadId = 0

  const currentIndex = computed(() => {
    const s = samples.value
    const ts = currentTimestampMs.value
    if (s.length === 0) return 0
    return findIndexForTimestamp(s, ts)
  })

  const currentSample = computed(() => {
    const s = samples.value
    const i = currentIndex.value
    return s[i] ?? null
  })

  const rangeMs = computed(() => Math.max(0, tEndMs.value - tStartMs.value))

  const currentOffsetMs = computed(() => {
    const off = currentTimestampMs.value - tStartMs.value
    return Math.max(0, Math.min(rangeMs.value, off))
  })

  const currentOffsetPct = computed(() => {
    const r = rangeMs.value
    return r > 0 ? currentOffsetMs.value / r : 0
  })

  const hasData = computed(() => samples.value.length > 0)
  const hasRecording = computed(() => primaryRecording.value != null)

  const chartData = computed((): ChartData | null => {
    const s = samples.value
    const tStart = tStartMs.value
    if (s.length === 0) return null
    return precomputeChartData(s, tStart)
  })

  function selectPrimaryRecording(
    recs: Recording[],
    sessionStartMs: number
  ): Recording | null {
    return selectPrimaryRecordingUtil(recs, sessionStartMs, sessionId.value)
  }

  async function load(sid: number) {
    if (sessionId.value === sid && loaded.value) return

    const thisLoadId = ++loadId
    sessionId.value = sid
    loading.value = true
    error.value = null
    loaded.value = false
    samples.value = []
    recordings.value = []
    primaryRecording.value = null
    events.value = []
    phases.value = []
    path.value = []
    homeLat.value = null
    homeLon.value = null
    tStartMs.value = 0
    tEndMs.value = 0
    currentTimestampMs.value = 0
    isPlaying.value = false
    hoverTimestampMs.value = null
    recordingOffsetSec.value = 0
    if (rafId != null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }

    try {
      const [samplesRes, pathRes, recordingsRes, eventsRes, phasesRes] =
        await Promise.all([
          getSessionTelemetrySamples(sid, { limit: 5000, order: 'asc' }),
          getSessionPath(sid),
          getSessionRecordings(sid),
          getSessionFlightEvents(sid),
          getSessionPhaseIntervals(sid),
        ])

      if (thisLoadId !== loadId) return

      const rawSamples = samplesRes.samples ?? []
      samples.value = rawSamples

      path.value = pathRes.path ?? []
      homeLat.value = pathRes.home_lat ?? null
      homeLon.value = pathRes.home_lon ?? null

      const recs = recordingsRes.recordings ?? []
      recordings.value = recs

      const rawEvents = (eventsRes.events ?? []) as FlightEvent[]
      events.value = rawEvents.map((e) => ({
        ...e,
        event_name: e.event_name ?? e.name ?? '',
      }))

      phases.value = (phasesRes.intervals ?? []) as PhaseInterval[]

      if (rawSamples.length > 0) {
        const first = new Date(rawSamples[0].timestamp).getTime()
        const last = new Date(rawSamples[rawSamples.length - 1].timestamp).getTime()
        tStartMs.value = first
        tEndMs.value = last
        currentTimestampMs.value = first
        primaryRecording.value = selectPrimaryRecording(recs, first)
      } else {
        primaryRecording.value = selectPrimaryRecording(recs, 0)
      }

      loaded.value = true
    } catch (e) {
      if (thisLoadId !== loadId) return
      error.value = e instanceof Error ? e.message : 'Failed to load replay data'
      throw e
    } finally {
      if (thisLoadId === loadId) loading.value = false
    }
  }

  function seekToTimestamp(tsMs: number) {
    const start = tStartMs.value
    const end = tEndMs.value
    const clamped = Math.max(start, Math.min(end, tsMs))
    currentTimestampMs.value = clamped
  }

  function seekToOffset(offsetMs: number) {
    seekToTimestamp(tStartMs.value + offsetMs)
  }

  function seekToPct(pct: number) {
    seekToOffset(pct * rangeMs.value)
  }

  function _tick(now: number) {
    if (!isPlaying.value) return
    const elapsed = (now - lastTickTime) / 1000
    lastTickTime = now
    const speed = playbackSpeed.value
    const range = rangeMs.value
    const newOffset = currentOffsetMs.value + elapsed * 1000 * speed
    if (newOffset >= range) {
      seekToTimestamp(tEndMs.value)
      isPlaying.value = false
      if (rafId != null) {
        cancelAnimationFrame(rafId)
        rafId = null
      }
      return
    }
    seekToOffset(newOffset)
    rafId = requestAnimationFrame(_tick)
  }

  function play() {
    if (!hasData.value) return
    isPlaying.value = true
    lastTickTime = performance.now()
    rafId = requestAnimationFrame(_tick)
  }

  function pause() {
    isPlaying.value = false
    if (rafId != null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }

  function setPlaybackSpeed(speed: number) {
    playbackSpeed.value = speed
  }

  function nextEvent() {
    const ts = currentTimestampMs.value
    const evts = events.value
    for (const e of evts) {
      const start = new Date(e.started_at).getTime()
      if (start > ts) {
        seekToTimestamp(start)
        return
      }
    }
  }

  function prevEvent() {
    const ts = currentTimestampMs.value
    const evts = events.value
    for (let i = evts.length - 1; i >= 0; i--) {
      const start = new Date(evts[i].started_at).getTime()
      if (start < ts) {
        seekToTimestamp(start)
        return
      }
    }
  }

  function setHoverTimestamp(tsMs: number | null) {
    hoverTimestampMs.value = tsMs
  }

  function setRecordingOffset(sec: number) {
    recordingOffsetSec.value = sec
  }

  return {
    sessionId,
    loading,
    loaded,
    error,
    samples,
    recordings,
    primaryRecording,
    events,
    phases,
    path,
    homeLat,
    homeLon,
    tStartMs,
    tEndMs,
    currentTimestampMs,
    isPlaying,
    playbackSpeed,
    hoverTimestampMs,
    recordingOffsetSec,
    currentIndex,
    currentSample,
    rangeMs,
    currentOffsetMs,
    currentOffsetPct,
    hasData,
    hasRecording,
    chartData,
    load,
    seekToTimestamp,
    seekToOffset,
    seekToPct,
    play,
    pause,
    setPlaybackSpeed,
    nextEvent,
    prevEvent,
    setHoverTimestamp,
    setRecordingOffset,
  }
})
