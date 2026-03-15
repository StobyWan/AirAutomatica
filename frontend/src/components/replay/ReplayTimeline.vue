<template>
  <div class="flex flex-col gap-2">
    <div class="flex flex-wrap items-center gap-3">
      <button
        type="button"
        class="px-2 py-1 rounded bg-slate-600 hover:bg-slate-500 text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        title="Previous event"
        :disabled="!canPrevEvent"
        @click="store.prevEvent()"
      >
        ⏮
      </button>
      <button
        type="button"
        class="px-2 py-1 rounded bg-slate-600 hover:bg-slate-500 text-white text-sm"
        :title="isPlaying ? 'Pause' : 'Play'"
        @click="togglePlay"
      >
        {{ isPlaying ? '⏸' : '▶' }}
      </button>
      <button
        type="button"
        class="px-2 py-1 rounded bg-slate-600 hover:bg-slate-500 text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        title="Next event"
        :disabled="!canNextEvent"
        @click="store.nextEvent()"
      >
        ⏭
      </button>
      <select
        :value="speedVal"
        class="rounded bg-slate-700 text-slate-200 text-sm px-2 py-1 border border-slate-600"
        @change="onSpeedChange"
      >
        <option :value="0.5">0.5×</option>
        <option :value="1">1×</option>
        <option :value="2">2×</option>
      </select>
      <span class="text-sm font-mono text-slate-400">
        {{ timeDisplay }}
      </span>
    </div>
    <div
      ref="trackRef"
      class="relative h-8 cursor-ew-resize rounded overflow-hidden bg-slate-700/50"
      @click="onTrackClick"
      @mousedown="onTrackMouseDown"
    >
      <!-- Phase bands -->
      <div
        v-for="(phase, i) in phaseBands"
        :key="i"
        class="absolute top-0 bottom-0 pointer-events-none"
        :style="{
          left: phase.leftPct * 100 + '%',
          width: phase.widthPct * 100 + '%',
          backgroundColor: phase.color,
        }"
      />
      <div
        class="absolute top-0 bottom-0 w-1 bg-cyan-400 rounded pointer-events-none transition-[left] duration-75 z-10"
        :style="{ left: currentOffsetPct * 100 + '%', transform: 'translateX(-50%)' }"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useReplayStore } from '@/stores/replay'
import { formatOffsetMs } from './replayUtils'

const store = useReplayStore()
const {
  currentOffsetPct,
  currentOffsetMs,
  rangeMs,
  isPlaying,
  events,
  phases,
  tStartMs,
  currentTimestampMs,
} = storeToRefs(store)

const trackRef = ref<HTMLDivElement | null>(null)
const speedVal = ref(1)

const timeDisplay = computed(() => {
  const current = formatOffsetMs(currentOffsetMs.value)
  const total = formatOffsetMs(rangeMs.value)
  return `${current} / ${total}`
})

const canPrevEvent = computed(() => {
  const ts = currentTimestampMs.value
  return events.value.some((e) => new Date(e.started_at).getTime() < ts)
})

const canNextEvent = computed(() => {
  const ts = currentTimestampMs.value
  return events.value.some((e) => new Date(e.started_at).getTime() > ts)
})

const PHASE_COLORS: Record<string, string> = {
  pre_arm: 'rgba(148, 163, 184, 0.4)',
  armed: 'rgba(34, 197, 94, 0.4)',
  takeoff: 'rgba(59, 130, 246, 0.4)',
  cruise: 'rgba(139, 92, 246, 0.4)',
  landing: 'rgba(249, 115, 22, 0.4)',
  disarmed: 'rgba(100, 116, 139, 0.4)',
}

const phaseBands = computed(() => {
  const p = phases.value
  const r = rangeMs.value
  if (r <= 0 || p.length === 0) return []
  const tStart = tStartMs.value
  return p.map((iv) => {
    const start = new Date(iv.started_at).getTime()
    const end = new Date(iv.ended_at).getTime()
    const leftPct = Math.max(0, (start - tStart) / r)
    const widthPct = Math.min(1 - leftPct, (end - start) / r)
    const phaseName = (iv.phase ?? 'unknown').toLowerCase().replace(/\s/g, '_')
    const color = PHASE_COLORS[phaseName] ?? 'rgba(100, 116, 139, 0.3)'
    return { leftPct, widthPct, color }
  })
})

function togglePlay() {
  if (isPlaying.value) store.pause()
  else store.play()
}

function onSpeedChange(e: Event) {
  const val = (e.target as HTMLSelectElement).value
  const speed = parseFloat(val) || 1
  speedVal.value = speed
  store.setPlaybackSpeed(speed)
}

watch(
  () => store.playbackSpeed,
  (s) => {
    speedVal.value = s
  },
  { immediate: true }
)

function getPctFromEvent(e: MouseEvent): number {
  const el = trackRef.value
  if (!el) return 0
  const rect = el.getBoundingClientRect()
  const x = e.clientX - rect.left
  return Math.max(0, Math.min(1, x / rect.width))
}

function onTrackClick(e: MouseEvent) {
  store.seekToPct(getPctFromEvent(e))
}

let dragging = false

function onTrackMouseDown(e: MouseEvent) {
  if (e.button !== 0) return
  dragging = true
  store.seekToPct(getPctFromEvent(e))

  function onMouseMove(ev: MouseEvent) {
    if (!dragging) return
    store.seekToPct(getPctFromEvent(ev))
  }

  function onMouseUp() {
    dragging = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

onUnmounted(() => {
  dragging = false
})
</script>
