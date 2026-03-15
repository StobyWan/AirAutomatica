<template>
  <div class="p-4 max-w-4xl mx-auto">
    <nav class="mb-6">
      <router-link
        :to="{ name: 'Dashboard' }"
        class="inline-flex items-center gap-2 text-slate-400 hover:text-slate-200 transition-colors text-sm font-medium"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
        Back to dashboard
      </router-link>
    </nav>

    <header class="mb-6">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight text-white">
          Session <span class="text-cyan-400 font-mono">{{ sid }}</span>
        </h1>
        <p class="text-slate-500 text-sm mt-1">Flight path, telemetry, detections, and recordings</p>
        <div v-if="session" class="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-400">
          <span>{{ fmtDate(session.started_at) }}</span>
          <span v-if="session.ended_at">– {{ fmtDate(session.ended_at) }}</span>
          <span>{{ labelAutopilot(session) }}</span>
          <span>{{ labelMode(session) }}</span>
        </div>
      </div>
    </header>

    <!-- Delete session modal -->
    <BaseModal v-model="showDeleteSessionModal">
      <h3 class="text-lg font-semibold text-white">Delete this session?</h3>
      <p class="mt-2 text-sm text-slate-400">
        This will permanently delete the session and all its recordings. This cannot be undone.
      </p>
      <div class="mt-6 flex gap-3 justify-end">
        <BaseButton variant="secondary" @click="showDeleteSessionModal = false">
          Cancel
        </BaseButton>
        <BaseButton
          variant="danger"
          :disabled="deletingSession"
          @click="confirmDeleteSession"
        >
          {{ deletingSession ? 'Deleting…' : 'Delete' }}
        </BaseButton>
      </div>
    </BaseModal>

    <div v-if="loading" class="rounded-xl bg-slate-900/50 border border-slate-800 p-8 text-center">
      <div class="inline-flex items-center gap-2 text-slate-400">
        <BaseSpinner />
        Loading…
      </div>
    </div>

    <div v-else-if="error" class="rounded-xl bg-red-950/30 border border-red-900/50 p-6 text-red-200 text-sm">
      {{ error }}
    </div>

    <div v-else class="grid grid-rows-[minmax(0,1fr)_auto] gap-6 max-h-[calc(100vh-12rem)] min-h-[32rem]">
      <!-- Top: path, debrief, detections, AI -->
      <div class="overflow-y-auto min-h-0 space-y-6 pr-1">
      <!-- Flight path (lazy-loaded when in view) -->
      <section ref="pathSectionRef" class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-base font-semibold text-slate-200 mb-3">Flight Path</h2>
        <div v-if="pathData.path.length > 0" class="flex flex-wrap items-center gap-2 mb-2 text-sm">
          <span class="text-slate-400">Replay home: {{ homeLabel }}</span>
          <button
            type="button"
            class="px-2 py-1 rounded bg-slate-600 hover:bg-slate-500 text-white text-xs"
            @click="setHomeFirst"
          >
            Use first path point
          </button>
          <button
            type="button"
            class="px-2 py-1 rounded bg-slate-600 hover:bg-slate-500 text-white text-xs"
            @click="showHomeModal = true"
          >
            Enter coordinates…
          </button>
          <button
            v-if="pathData.home_lat != null"
            type="button"
            class="px-2 py-1 rounded bg-slate-600 hover:bg-slate-500 text-white text-xs"
            @click="clearHome"
          >
            Clear override
          </button>
        </div>
        <div class="path-svg rounded-lg overflow-hidden bg-black/20">
          <!-- eslint-disable vue/no-v-html -- SVG from internal pathPlot utility, not user input -->
          <svg
            v-if="pathSvg"
            width="100%"
            height="220"
            :viewBox="`0 0 200 220`"
            class="block"
            v-html="pathSvg"
          />
          <!-- eslint-enable vue/no-v-html -->
          <div
            v-else-if="pathLoading"
            class="flex items-center justify-center h-[220px] text-slate-500 text-sm"
          >
            <BaseSpinner color="slate" />
            <span class="ml-2">Loading path…</span>
          </div>
          <div v-else class="flex items-center justify-center h-[220px] text-slate-500 text-sm">
            No path data
          </div>
        </div>

        <!-- Home override modal -->
        <BaseModal v-model="showHomeModal" size="sm">
          <h3 class="text-lg font-medium text-white mb-3">Override home for replay</h3>
          <p class="text-xs text-slate-500 mb-3">
            Affects replay and debrief only. Does not change the flight controller's RTL home.
          </p>
          <div class="space-y-2 mb-4">
            <label class="block text-sm text-slate-400">Latitude</label>
            <input
              v-model.number="homeModalLat"
              type="number"
              step="any"
              min="-90"
              max="90"
              class="w-full rounded-lg bg-slate-700 text-white px-3 py-2 border border-slate-600"
              placeholder="e.g. 37.6213"
            />
            <label class="block text-sm text-slate-400">Longitude</label>
            <input
              v-model.number="homeModalLon"
              type="number"
              step="any"
              min="-180"
              max="180"
              class="w-full rounded-lg bg-slate-700 text-white px-3 py-2 border border-slate-600"
              placeholder="e.g. -122.379"
            />
          </div>
          <div class="flex gap-2 justify-end">
            <BaseButton variant="secondary" size="sm" @click="showHomeModal = false">
              Cancel
            </BaseButton>
            <BaseButton variant="primary" size="sm" @click="applyHomeOverride">
              Apply
            </BaseButton>
          </div>
        </BaseModal>
      </section>

      <!-- Debrief -->
      <section class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-base font-semibold text-slate-200 mb-3">Debrief</h2>
        <p class="text-xs text-slate-500 mb-3">Post-flight summary from telemetry</p>
        <div v-if="debriefLoading" class="py-6 text-center">
          <BaseSpinner color="slate" center />
        </div>
        <div v-else-if="!debrief" class="py-6 text-center text-slate-500 text-sm">
          No debrief data for this session.
        </div>
        <div v-else>
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <div class="rounded bg-slate-800/40 px-3 py-2">
              <span class="text-slate-500 text-xs">Duration</span>
              <p class="text-sm font-mono text-slate-200">{{ formatDuration(debrief.summary?.session_duration_sec) }}</p>
            </div>
            <div class="rounded bg-slate-800/40 px-3 py-2">
              <span class="text-slate-500 text-xs">Peak distance</span>
              <p class="text-sm font-mono text-slate-200">{{ formatMetersOrKm(debrief.summary?.peak_distance_from_home_m) }}</p>
            </div>
            <div class="rounded bg-slate-800/40 px-3 py-2">
              <span class="text-slate-500 text-xs">Avg power</span>
              <p class="text-sm font-mono text-slate-200">{{ formatWatts(debrief.summary?.average_power_w) }}</p>
            </div>
            <div class="rounded bg-slate-800/40 px-3 py-2">
              <span class="text-slate-500 text-xs">Min voltage</span>
              <p class="text-sm font-mono text-slate-200">{{ formatVolts(debrief.summary?.minimum_voltage_v) }}</p>
            </div>
          </div>
          <div v-if="debrief.summary?.top_events?.length" class="mb-3 flex flex-wrap gap-2">
            <template v-for="e in debrief.summary.top_events.slice(0, 5)" :key="e.name">
              <span class="text-sm text-slate-300">
                {{ (e.name || '').replace(/_/g, ' ') }}{{ e.count != null ? ` (${e.count})` : '' }}{{ e.duration_sec != null ? ' · ' + formatDuration(e.duration_sec) : '' }}
              </span>
              <span class="text-slate-600">·</span>
            </template>
          </div>
          <div v-if="debrief.summary?.assessment_tags?.length" class="flex flex-wrap gap-1.5 mb-4">
            <span
              v-for="t in debrief.summary.assessment_tags"
              :key="t"
              class="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-slate-700/60 text-slate-300"
            >
              {{ (t || '').replace(/_/g, ' ') }}
            </span>
          </div>
          <div v-if="debrief.generated_summary" class="rounded-lg bg-slate-800/50 border border-slate-700/50 p-3 text-sm text-slate-200 mb-2">
            <div class="whitespace-pre-wrap">{{ debrief.generated_summary }}</div>
            <p v-if="debrief.generated_debrief_at" class="text-xs text-slate-500 mt-2">{{ fmtDate(debrief.generated_debrief_at) }}</p>
          </div>
          <div v-else class="py-2">
            <span class="text-slate-500 text-sm">AI summary not generated yet.</span>
            <button
              type="button"
              class="ml-2 px-3 py-1 rounded-lg bg-cyan-600/80 hover:bg-cyan-600 text-white text-sm font-medium"
              :disabled="generatingSummary"
              @click="generateDebriefSummary"
            >
              {{ generatingSummary ? 'Generating…' : 'Generate AI Summary' }}
            </button>
          </div>
        </div>
      </section>

      <!-- Detections -->
      <section class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-base font-semibold text-slate-200 mb-3">Detections</h2>
        <p class="text-xs text-slate-500 mb-2">Persisted detections for this session</p>
        <div v-if="detections.length > 0" class="flex items-center gap-2 mb-3">
          <label for="detections-filter-source" class="text-xs text-slate-400">Source</label>
          <select
            id="detections-filter-source"
            v-model="detectionSourceFilter"
            class="px-2 py-1 rounded bg-slate-700/50 border border-slate-600 text-sm text-slate-200"
          >
            <option value="">All</option>
            <option value="mission">Mission (mock/Ollama)</option>
            <option value="ai_hat_recording">AI HAT recording</option>
            <option value="aihat">AI HAT one-shot</option>
          </select>
        </div>
        <div v-if="detections.length === 0" class="py-6 text-center text-slate-500 text-sm">
          No detections
        </div>
        <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          <div
            v-for="(d, i) in filteredDetections"
            :key="i"
            class="rounded-lg bg-slate-800/40 border border-slate-700/50 p-3 text-sm"
          >
            <div class="font-medium text-slate-200">{{ d.label }}</div>
            <div class="text-slate-400 text-xs mt-0.5">
              {{ fmtRate(d.confidence) ?? '—' }}
              <span v-if="d.source_backend" class="ml-1">· {{ fmtSourceBackend(d.source_backend).text }}</span>
            </div>
            <p v-if="d.summary" class="text-slate-400 text-xs mt-1">{{ d.summary }}</p>
          </div>
        </div>
      </section>

      <!-- AI Analysis -->
      <section class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-base font-semibold text-slate-200 mb-3">AI Analysis</h2>
        <p class="text-xs text-slate-500 mb-3">Local AI interpretation of this session's telemetry and events</p>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h3 class="text-xs font-semibold text-slate-400 mb-1">Telemetry Summary</h3>
            <p class="text-xs text-slate-500 mb-2">AI interpretation of session telemetry (Ollama or mock)</p>
            <button
              type="button"
              class="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium disabled:opacity-50"
              :disabled="telemetrySummaryLoading"
              @click="runTelemetrySummary"
            >
              {{ telemetrySummaryLoading ? 'Summarizing…' : 'Summarize' }}
            </button>
            <div class="mt-2 text-sm text-slate-300">
              {{ telemetrySummaryContent }}
            </div>
          </div>
          <div>
            <h3 class="text-xs font-semibold text-slate-400 mb-1">Event Classification</h3>
            <p class="text-xs text-slate-500 mb-2">AI analysis of session system events (Ollama or mock)</p>
            <button
              type="button"
              class="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium disabled:opacity-50"
              :disabled="eventClassificationLoading"
              @click="runEventClassification"
            >
              {{ eventClassificationLoading ? 'Classifying…' : 'Classify' }}
            </button>
            <div class="mt-2 text-sm text-slate-300">
              {{ eventClassificationContent }}
            </div>
          </div>
        </div>
      </section>
      </div>

      <!-- Bottom: Recordings + Delete -->
      <div class="overflow-y-auto min-h-0 space-y-6">
      <section class="rounded-lg border border-slate-700 bg-slate-800/50 p-4 shrink-0">
        <h2 class="text-base font-semibold text-slate-200 mb-3">Recordings</h2>
        <p class="text-xs text-slate-500 mb-3">Recordings for this flight session</p>
        <div v-if="recordingsLoading" class="py-6 text-center">
          <BaseSpinner size="lg" color="slate" center />
        </div>
        <div v-else-if="recordings.length === 0" class="py-6 text-center">
          <p class="text-slate-500 text-sm">No recordings for this session</p>
        </div>
        <div v-else>
          <div class="space-y-2">
            <div
              v-for="r in recordings"
              :key="r.filename"
              class="flex items-center justify-between gap-2 rounded bg-slate-800/40 px-3 py-2"
            >
              <button
                type="button"
                class="text-left text-sm text-cyan-400 hover:text-cyan-300 truncate flex-1"
                @click="playRecording(r.filename)"
              >
                {{ r.filename }}
              </button>
              <span class="text-xs text-slate-500 shrink-0">{{ fmtTsTime(r.timestamp) }}</span>
              <button
                type="button"
                class="px-2 py-1 rounded text-xs text-red-400 hover:bg-red-900/30"
                @click="openDeleteRecordingModal(r.filename)"
              >
                Delete
              </button>
            </div>
          </div>
          <div v-if="playingFilename" class="mt-4 rounded-lg bg-black overflow-hidden max-w-2xl max-h-[60vh]">
            <video
              ref="videoEl"
              controls
              class="w-full h-full object-contain"
              preload="metadata"
              :src="recordingsUrl(playingFilename)"
              @ended="playingFilename = null"
            />
          </div>
        </div>

        <!-- Delete recording modal -->
        <BaseModal v-model="showDeleteRecordingModal">
          <template #default>
            <h3 class="text-lg font-semibold text-white">Delete recording?</h3>
            <p class="mt-2 text-sm text-slate-400 font-mono">{{ deleteRecordingFilename }}</p>
            <p class="mt-2 text-sm text-slate-500">This cannot be undone.</p>
            <div class="mt-6 flex gap-3 justify-end">
              <BaseButton variant="secondary" @click="showDeleteRecordingModal = false">
                Cancel
              </BaseButton>
              <BaseButton
                variant="danger"
                :disabled="deletingRecording"
                @click="confirmDeleteRecording"
              >
                {{ deletingRecording ? 'Deleting…' : 'Delete' }}
              </BaseButton>
            </div>
          </template>
        </BaseModal>
      </section>

      <!-- Delete session (bottom) -->
      <section
        v-if="session && !isCurrentSession"
        class="rounded-lg border border-slate-700 bg-slate-800/50 p-4 flex justify-end shrink-0"
      >
        <button
          type="button"
          class="px-3 py-1.5 rounded-lg bg-red-900/50 hover:bg-red-800/60 text-red-200 text-sm font-medium border border-red-800/50"
          @click="showDeleteSessionModal = true"
        >
          Delete session
        </button>
      </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import {
  getSession,
  getSessionPath,
  getSessionDebrief,
  getSessionRecordings,
  getSessionDetections,
  patchSession,
  deleteSession,
  deleteRecording,
} from '@/api/session'
import { getTelemetrySummary, getEventClassification } from '@/api/ai'
import { recordingsUrl } from '@/config'
import { renderPathPlot } from '@/utils/pathPlot'
import {
  fmtDate,
  fmtTsTime,
  formatDuration,
  formatMetersOrKm,
  formatWatts,
  formatVolts,
  fmtRate,
  fmtSourceBackend,
  labelAutopilot,
  labelMode,
} from '@/utils/formatters'
import type { SessionSummary } from '@/types'
import type { PathPoint } from '@/api/session'
import type { Detection } from '@/types'

const route = useRoute()
const router = useRouter()

const sid = computed(() => {
  const id = route.params.id
  return typeof id === 'string' ? parseInt(id, 10) : Number(id)
})

const loading = ref(true)
const error = ref('')
const session = ref<SessionSummary | null>(null)
const pathData = ref<{ path: PathPoint[]; home_lat?: number; home_lon?: number }>({ path: [] })
const debrief = ref<Awaited<ReturnType<typeof getSessionDebrief>> | null>(null)
const debriefLoading = ref(true)
const generatingSummary = ref(false)
const detections = ref<Detection[]>([])
const recordings = ref<{ filename: string; timestamp: string }[]>([])
const recordingsLoading = ref(true)
const showDeleteSessionModal = ref(false)
const deletingSession = ref(false)
const showHomeModal = ref(false)
const homeModalLat = ref<number | ''>('')
const homeModalLon = ref<number | ''>('')
const playingFilename = ref<string | null>(null)
const videoEl = ref<HTMLVideoElement | null>(null)
const deleteRecordingFilename = ref<string | null>(null)
const deletingRecording = ref(false)
const detectionSourceFilter = ref('')
const telemetrySummaryLoading = ref(false)
const telemetrySummaryContent = ref('Click Summarize to get AI interpretation')
const eventClassificationLoading = ref(false)
const eventClassificationContent = ref('Click Classify to analyze session events')
const pathSectionRef = ref<HTMLElement | null>(null)
const pathLoading = ref(false)
const pathLoadTriggered = ref(false)

const showDeleteRecordingModal = computed({
  get: () => !!deleteRecordingFilename.value,
  set: (v) => {
    if (!v) deleteRecordingFilename.value = null
  },
})

const isCurrentSession = computed(() => session.value?.current_session_id === sid.value)

const homeLabel = computed(() => {
  const h = pathData.value
  if (h.home_lat != null && h.home_lon != null) {
    return `${h.home_lat.toFixed(4)}, ${h.home_lon.toFixed(4)}`
  }
  return '—'
})

const homePoint = computed((): PathPoint | null => {
  const h = pathData.value
  if (h.home_lat != null && h.home_lon != null) {
    return { lat: h.home_lat, lon: h.home_lon }
  }
  return null
})

const detectionPoints = computed((): PathPoint[] => {
  return detections.value
    .filter((d) => d.lat != null && d.lon != null)
    .map((d) => ({ lat: d.lat as number, lon: d.lon as number }))
})

const filteredDetections = computed(() => {
  const f = detectionSourceFilter.value
  if (!f) return detections.value
  return detections.value.filter((d) => {
    const s = d.source_backend ?? ''
    if (f === 'mission') return s === 'mock' || s === 'ollama'
    if (f === 'ai_hat_recording') return s === 'ai_hat_recording'
    if (f === 'aihat') return s === 'aihat'
    return true
  })
})

const pathSvg = computed(() => {
  const path = pathData.value.path
  const home = homePoint.value
  return renderPathPlot(path, null, detectionPoints.value, home, { width: 200, height: 220 })
})

async function loadSession() {
  if (!Number.isFinite(sid.value)) return
  loading.value = true
  error.value = ''
  try {
    session.value = await getSession(sid.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load session'
    return
  } finally {
    loading.value = false
  }
}

async function loadPath() {
  if (!Number.isFinite(sid.value) || pathLoadTriggered.value) return
  pathLoadTriggered.value = true
  pathLoading.value = true
  try {
    const res = await getSessionPath(sid.value)
    pathData.value = { path: res.path, home_lat: res.home_lat, home_lon: res.home_lon }
  } catch {
    pathData.value = { path: [] }
  } finally {
    pathLoading.value = false
  }
}

function maybeLoadPath() {
  if (session.value && !pathLoadTriggered.value) loadPath()
}

async function loadDebrief() {
  if (!Number.isFinite(sid.value)) return
  debriefLoading.value = true
  try {
    debrief.value = await getSessionDebrief(sid.value, false)
  } catch {
    debrief.value = null
  } finally {
    debriefLoading.value = false
  }
}

async function loadDetections() {
  if (!Number.isFinite(sid.value)) return
  try {
    const res = await getSessionDetections(sid.value)
    detections.value = res.detections
  } catch {
    detections.value = []
  }
}

async function loadRecordings() {
  if (!Number.isFinite(sid.value)) return
  recordingsLoading.value = true
  try {
    const res = await getSessionRecordings(sid.value)
    recordings.value = res.recordings.map((r) => ({ filename: r.filename, timestamp: r.timestamp }))
  } catch {
    recordings.value = []
  } finally {
    recordingsLoading.value = false
  }
}

async function setHomeFirst() {
  const path = pathData.value.path
  if (path.length === 0) return
  const first = path[0]
  await patchSession(sid.value, { home_lat: first.lat, home_lon: first.lon })
  pathData.value = { ...pathData.value, home_lat: first.lat, home_lon: first.lon }
}

async function clearHome() {
  await patchSession(sid.value, { clear_home: true })
  pathData.value = { ...pathData.value, home_lat: undefined, home_lon: undefined }
}

async function applyHomeOverride() {
  const lat = homeModalLat.value
  const lon = homeModalLon.value
  if (typeof lat !== 'number' || typeof lon !== 'number' || lat < -90 || lat > 90 || lon < -180 || lon > 180) return
  await patchSession(sid.value, { home_lat: lat, home_lon: lon })
  pathData.value = { ...pathData.value, home_lat: lat, home_lon: lon }
  showHomeModal.value = false
}

async function generateDebriefSummary() {
  if (!Number.isFinite(sid.value)) return
  generatingSummary.value = true
  try {
    debrief.value = await getSessionDebrief(sid.value, true)
  } finally {
    generatingSummary.value = false
  }
}

function playRecording(filename: string) {
  playingFilename.value = filename
}

async function runTelemetrySummary() {
  if (!Number.isFinite(sid.value)) return
  telemetrySummaryLoading.value = true
  telemetrySummaryContent.value = 'Summarizing…'
  try {
    const res = await getTelemetrySummary(sid.value)
    telemetrySummaryContent.value = res.summary ?? 'No summary returned'
  } catch (e) {
    telemetrySummaryContent.value = e instanceof Error ? e.message : 'Summarize failed'
  } finally {
    telemetrySummaryLoading.value = false
  }
}

async function runEventClassification() {
  if (!Number.isFinite(sid.value)) return
  eventClassificationLoading.value = true
  eventClassificationContent.value = 'Classifying…'
  try {
    const res = await getEventClassification(sid.value)
    const { severity, category, summary, likely_causes, recommended_checks } = res as Record<string, unknown>
    if (summary != null) {
      const parts: string[] = [String(summary)]
      if (severity != null) parts.push(`Severity: ${severity}`)
      if (category != null) parts.push(`Category: ${category}`)
      if (Array.isArray(likely_causes) && likely_causes.length) {
        parts.push(`Likely causes: ${likely_causes.join(', ')}`)
      }
      if (Array.isArray(recommended_checks) && recommended_checks.length) {
        parts.push(`Checks: ${recommended_checks.join(', ')}`)
      }
      eventClassificationContent.value = parts.join('\n\n')
    } else {
      eventClassificationContent.value = 'No classification returned'
    }
  } catch (e) {
    eventClassificationContent.value = e instanceof Error ? e.message : 'Classify failed'
  } finally {
    eventClassificationLoading.value = false
  }
}

function openDeleteRecordingModal(filename: string) {
  deleteRecordingFilename.value = filename
}

async function confirmDeleteRecording() {
  const fn = deleteRecordingFilename.value
  if (!fn) return
  deletingRecording.value = true
  try {
    await deleteRecording(fn)
    recordings.value = recordings.value.filter((r) => r.filename !== fn)
    if (playingFilename.value === fn) playingFilename.value = null
    deleteRecordingFilename.value = null
  } finally {
    deletingRecording.value = false
  }
}

async function confirmDeleteSession() {
  if (!Number.isFinite(sid.value)) return
  deletingSession.value = true
  try {
    await deleteSession(sid.value)
    router.push({ name: 'Dashboard' })
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to delete session'
  } finally {
    deletingSession.value = false
    showDeleteSessionModal.value = false
  }
}

watch(sid, () => {
  pathLoadTriggered.value = false
  loadSession()
  loadDebrief()
  loadDetections()
  loadRecordings()
}, { immediate: true })

let pathObserver: IntersectionObserver | null = null
let pathFallbackTimer: ReturnType<typeof setTimeout> | null = null

function setupPathLazyLoad() {
  if (pathFallbackTimer) clearTimeout(pathFallbackTimer)
  pathFallbackTimer = null
  pathObserver?.disconnect()
  pathObserver = null
  const el = pathSectionRef.value
  if (!el || pathLoadTriggered.value) return
  pathFallbackTimer = setTimeout(maybeLoadPath, 300)
  pathObserver = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting) {
        if (pathFallbackTimer) {
          clearTimeout(pathFallbackTimer)
          pathFallbackTimer = null
        }
        maybeLoadPath()
      }
    },
    { rootMargin: '100px', threshold: 0 }
  )
  pathObserver.observe(el)
}

watch(session, () => {
  if (session.value && !error.value) {
    nextTick(setupPathLazyLoad)
  }
}, { immediate: true })

onUnmounted(() => {
  if (pathFallbackTimer) clearTimeout(pathFallbackTimer)
  pathObserver?.disconnect()
})
</script>

<style scoped>
.path-svg {
  height: 220px;
}
</style>
