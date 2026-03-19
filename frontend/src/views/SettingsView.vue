<template>
  <div class="p-4 max-w-2xl">
    <h1 class="text-2xl font-bold text-slate-100 tracking-tight mb-2">Settings</h1>
    <p class="text-sm text-slate-400 mb-4">
      Changes are saved to <code class="text-slate-500">~/.airautomatica/settings.json</code>.
      Some apply immediately; others require reconnect or app restart.
    </p>
    <p v-if="activeSummary" class="text-xs text-slate-500 mb-4">{{ activeSummary }}</p>

    <div v-if="loading" class="flex items-center gap-2 py-6">
      <BaseSpinner />
      <span class="text-sm text-slate-400">Loading settings…</span>
    </div>

    <form v-else class="space-y-6" @submit.prevent="save">
      <!-- Vehicle Mode -->
      <section class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-base font-semibold text-slate-200 mb-3">Vehicle Mode</h2>
        <div class="space-y-3">
          <div>
            <label for="VEHICLE_MODE" class="block text-sm text-slate-300 mb-1">Mode</label>
            <select
              id="VEHICLE_MODE"
              v-model="form.VEHICLE_MODE"
              class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm"
            >
              <option value="drone">drone</option>
              <option value="rover">rover</option>
              <option value="bench">bench</option>
            </select>
            <p class="text-xs text-slate-500 mt-1">drone: MAVLink telemetry, flight path. rover: teleoperated ground vehicle. bench: safe testing without actuators. Restart required.</p>
          </div>
        </div>
      </section>

      <!-- Telemetry -->
      <section class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-base font-semibold text-slate-200 mb-3">Telemetry</h2>
        <div class="space-y-3">
          <div>
            <label for="TELEMETRY_BACKEND" class="block text-sm text-slate-300 mb-1">Telemetry backend</label>
            <select
              id="TELEMETRY_BACKEND"
              v-model="form.TELEMETRY_BACKEND"
              class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm"
            >
              <option value="mock">mock</option>
              <option value="serial">serial</option>
            </select>
          </div>
          <div>
            <label for="SERIAL_PORT" class="block text-sm text-slate-300 mb-1">Serial port</label>
            <input
              id="SERIAL_PORT"
              v-model="form.SERIAL_PORT"
              type="text"
              placeholder="/dev/ttyUSB0"
              class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm placeholder-slate-500"
            />
            <p class="text-xs text-slate-500 mt-1">Pi 5 bench: CP2102 → /dev/ttyUSB0. Matek F405-WING: TELEM1/2 → CP2102. Native USB FC → /dev/ttyACM0.</p>
          </div>
          <div>
            <label for="SERIAL_BAUD" class="block text-sm text-slate-300 mb-1">Serial baud rate</label>
            <input
              id="SERIAL_BAUD"
              v-model="form.SERIAL_BAUD"
              type="number"
              placeholder="921600"
              min="9600"
              max="2000000"
              class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm"
            />
          </div>
        </div>
      </section>

      <!-- AI Provider -->
      <section class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-base font-semibold text-slate-200 mb-3">AI Provider</h2>
        <p v-if="providerReason" class="text-xs text-slate-500 mb-3">{{ providerReason }}</p>
        <div class="space-y-3">
          <div>
            <label for="LOCAL_LLM_PROVIDER" class="block text-sm text-slate-300 mb-1">AI provider</label>
            <select
              id="LOCAL_LLM_PROVIDER"
              v-model="form.LOCAL_LLM_PROVIDER"
              class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm"
            >
              <option value="ollama">ollama</option>
              <option value="mock">mock</option>
            </select>
          </div>
          <template v-if="form.LOCAL_LLM_PROVIDER === 'ollama'">
            <div>
              <label for="LOCAL_LLM_BASE_URL" class="block text-sm text-slate-300 mb-1">Ollama base URL</label>
              <input
                id="LOCAL_LLM_BASE_URL"
                v-model="form.LOCAL_LLM_BASE_URL"
                type="text"
                placeholder="http://127.0.0.1:11434"
                class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm placeholder-slate-500"
              />
            </div>
            <div>
              <label for="LOCAL_LLM_MODEL" class="block text-sm text-slate-300 mb-1">Ollama model name</label>
              <input
                id="LOCAL_LLM_MODEL"
                v-model="form.LOCAL_LLM_MODEL"
                type="text"
                placeholder="gemma3:1b"
                class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm placeholder-slate-500"
              />
            </div>
            <div>
              <label for="LOCAL_LLM_TIMEOUT" class="block text-sm text-slate-300 mb-1">Local LLM timeout (seconds)</label>
              <input
                id="LOCAL_LLM_TIMEOUT"
                v-model="form.LOCAL_LLM_TIMEOUT"
                type="number"
                placeholder="30"
                min="1"
                class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm"
              />
            </div>
            <div>
              <label for="OLLAMA_NUM_THREAD" class="block text-sm text-slate-300 mb-1">Ollama threads</label>
              <input
                id="OLLAMA_NUM_THREAD"
                v-model="form.OLLAMA_NUM_THREAD"
                type="number"
                placeholder="4"
                min="1"
                max="8"
                class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm"
              />
              <p class="text-xs text-slate-500 mt-1">Lower values reduce CPU load and heat. Recommended Pi 5: 4.</p>
            </div>
          </template>
        </div>
      </section>

      <!-- Camera Recording -->
      <section class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-base font-semibold text-slate-200 mb-3">Camera Recording</h2>
        <div class="space-y-3">
          <div>
            <label for="CAMERA_RECORDING_MODE" class="block text-sm text-slate-300 mb-1">Recording mode</label>
            <select
              id="CAMERA_RECORDING_MODE"
              v-model="form.CAMERA_RECORDING_MODE"
              class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm"
            >
              <option value="off">off</option>
              <option value="manual">manual</option>
              <option value="auto">auto</option>
            </select>
            <p class="text-xs text-slate-500 mt-1">off: disabled. manual: API/UI only. auto: start on armed, stop on disarmed.</p>
          </div>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              v-model="form.RECORDING_AI_OVERLAY_ENABLED"
              type="checkbox"
              class="rounded border-slate-600 bg-slate-700 text-cyan-600 focus:ring-cyan-500"
            />
            <span class="text-sm text-slate-300">Recording AI overlay</span>
          </label>
          <p class="text-xs text-slate-500">When AI HAT enabled: draw detection bounding boxes on recorded video.</p>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              v-model="form.RECORDING_AI_PERSIST_ENABLED"
              type="checkbox"
              class="rounded border-slate-600 bg-slate-700 text-cyan-600 focus:ring-cyan-500"
            />
            <span class="text-sm text-slate-300">Recording AI persist</span>
          </label>
          <p class="text-xs text-slate-500">Extract frames and run Hailo inference; save to Recent Detections. Overlay and persist cannot both run.</p>
          <div>
            <label for="CAMERA_SOURCE_ID" class="block text-sm text-slate-300 mb-1">Camera source</label>
            <select
              id="CAMERA_SOURCE_ID"
              v-model="form.CAMERA_SOURCE_ID"
              class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm"
            >
              <option value="">Auto (first available)</option>
              <option
                v-for="cam in cameraSelectOptions"
                :key="cam.id"
                :value="cam.id"
              >
                {{ cam.display_name }} ({{ cam.source_type }})
              </option>
            </select>
            <p class="text-xs text-slate-500 mt-1">Which camera to use for preview, recording, and one-shot detection. Restart required after change.</p>
          </div>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              v-model="form.CAMERA_SOURCE_AUTO_FALLBACK"
              type="checkbox"
              class="rounded border-slate-600 bg-slate-700 text-cyan-600 focus:ring-cyan-500"
            />
            <span class="text-sm text-slate-300">Auto-fallback when selected camera unavailable</span>
          </label>
          <p class="text-xs text-slate-500">When enabled, use first available camera if the selected one is unplugged. Restart required.</p>
        </div>
      </section>

      <!-- Session -->
      <section class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-base font-semibold text-slate-200 mb-3">Session</h2>
        <label class="flex items-center gap-2 cursor-pointer">
          <input
            v-model="form.SESSION_AUTO_START_ON_ARM"
            type="checkbox"
            class="rounded border-slate-600 bg-slate-700 text-cyan-600 focus:ring-cyan-500"
          />
          <span class="text-sm text-slate-300">Auto-start session when armed</span>
        </label>
        <p class="text-xs text-slate-500 mt-1">When enabled, session starts on arm and stops on disarm. Takes effect immediately.</p>
      </section>

      <!-- AI HAT -->
      <section class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h2 class="text-base font-semibold text-slate-200 mb-3">AI HAT</h2>
        <label class="flex items-center gap-2 cursor-pointer">
          <input
            v-model="form.AI_HAT_ENABLED"
            type="checkbox"
            class="rounded border-slate-600 bg-slate-700 text-cyan-600 focus:ring-cyan-500"
          />
          <span class="text-sm text-slate-300">Enable AI HAT layer</span>
        </label>
        <p class="text-xs text-slate-500 mt-1">Optional vision/perception layer on Pi 5. Additive: runs alongside mock for mission loop.</p>
      </section>

      <!-- Advanced -->
      <section class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <button
          type="button"
          class="flex items-center gap-2 text-base font-semibold text-slate-200 hover:text-slate-100"
          :aria-expanded="advancedOpen"
          @click="advancedOpen = !advancedOpen"
        >
          <span class="transition-transform" :class="advancedOpen ? 'rotate-0' : '-rotate-90'">▼</span>
          Advanced
        </button>
        <div v-show="advancedOpen" class="mt-3 space-y-3">
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              v-model="form.AIRAUTOMATICA_PREPROCESSING_ENABLED"
              type="checkbox"
              class="rounded border-slate-600 bg-slate-700 text-cyan-600 focus:ring-cyan-500"
            />
            <span class="text-sm text-slate-300">Enable telemetry preprocessing</span>
          </label>
          <p class="text-xs text-slate-500">Required for Ollama telemetry summary. Default: on.</p>
          <div>
            <label for="AI_HAT_DETECTION_THRESHOLD" class="block text-sm text-slate-300 mb-1">AI HAT one-shot threshold (0–1)</label>
            <input
              id="AI_HAT_DETECTION_THRESHOLD"
              v-model="form.AI_HAT_DETECTION_THRESHOLD"
              type="number"
              placeholder="0.25"
              min="0"
              max="1"
              step="0.05"
              class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm"
            />
            <p class="text-xs text-slate-500 mt-1">Min confidence for AI HAT one-shot detections. Default: 0.25.</p>
          </div>
          <div>
            <label for="AI_MIN_CONFIDENCE" class="block text-sm text-slate-300 mb-1">AI min confidence (0–1)</label>
            <input
              id="AI_MIN_CONFIDENCE"
              v-model="form.AI_MIN_CONFIDENCE"
              type="number"
              placeholder="0.5"
              min="0"
              max="1"
              step="0.1"
              class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm"
            />
            <p class="text-xs text-slate-500 mt-1">Mission logic: min confidence to persist.</p>
          </div>
          <div>
            <label for="AI_DUPLICATE_WINDOW_SEC" class="block text-sm text-slate-300 mb-1">AI duplicate window (seconds)</label>
            <input
              id="AI_DUPLICATE_WINDOW_SEC"
              v-model="form.AI_DUPLICATE_WINDOW_SEC"
              type="number"
              placeholder="30"
              min="1"
              class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm"
            />
          </div>
          <div>
            <label for="AI_SCHEDULER_COOLDOWN_SEC" class="block text-sm text-slate-300 mb-1">AI scheduler cooldown (seconds)</label>
            <input
              id="AI_SCHEDULER_COOLDOWN_SEC"
              v-model="form.AI_SCHEDULER_COOLDOWN_SEC"
              type="number"
              placeholder="8"
              min="0"
              step="0.5"
              class="w-full px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-slate-200 text-sm"
            />
            <p class="text-xs text-slate-500 mt-1">Delay between Ollama jobs. Applies immediately.</p>
          </div>
        </div>
      </section>

      <div class="flex items-center gap-3">
        <button
          type="submit"
          :disabled="saving"
          class="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm"
        >
          {{ saving ? 'Saving…' : 'Save' }}
        </button>
        <span v-if="statusMessage" class="text-sm text-slate-500">{{ statusMessage }}</span>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { getSettings, postSettings } from '@/api/settings'
import { getCameraStatus } from '@/api/camera'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { CHECKBOX_KEYS } from '@/constants/settings'
import type { Settings } from '@/types'

const loading = ref(true)
const cameraOptions = ref<{ id: string; display_name: string; source_type: string }[]>([])

const cameraSelectOptions = computed(() => {
  const opts = cameraOptions.value
  const current = String(form.CAMERA_SOURCE_ID || '').trim()
  if (!current) return opts
  const found = opts.some((c) => c.id === current)
  if (found) return opts
  return [{ id: current, display_name: current, source_type: '—' }, ...opts]
})
const saving = ref(false)
const statusMessage = ref('')
const activeSummary = ref('')
const providerReason = ref('')
const advancedOpen = ref(false)

const form = reactive<Record<string, string | boolean>>({
  TELEMETRY_BACKEND: 'mock',
  SERIAL_PORT: '',
  SERIAL_BAUD: '',
  LOCAL_LLM_PROVIDER: 'ollama',
  LOCAL_LLM_BASE_URL: '',
  LOCAL_LLM_MODEL: '',
  LOCAL_LLM_TIMEOUT: '',
  OLLAMA_NUM_THREAD: '',
  AI_HAT_ENABLED: false,
  AI_HAT_REQUIRE_HARDWARE: false,
  AI_HAT_CAMERA_PIPELINE_ENABLED: false,
  AI_HAT_OBJECT_DETECTION_ENABLED: false,
  AI_HAT_DETECTION_THRESHOLD: '',
  AIRAUTOMATICA_PREPROCESSING_ENABLED: true,
  AI_MIN_CONFIDENCE: '',
  AI_DUPLICATE_WINDOW_SEC: '',
  AI_SCHEDULER_COOLDOWN_SEC: '',
  CAMERA_RECORDING_MODE: 'off',
  RECORDING_AI_OVERLAY_ENABLED: false,
  RECORDING_AI_PERSIST_ENABLED: false,
  SESSION_AUTO_START_ON_ARM: false,
  CAMERA_SOURCE_ID: '',
  CAMERA_SOURCE_AUTO_FALLBACK: true,
  VEHICLE_MODE: 'drone',
})

function parseValue(key: string, raw: string | number | boolean | null): string | boolean {
  if (raw === null || raw === undefined) return CHECKBOX_KEYS.has(key) ? false : ''
  if (typeof raw === 'boolean') return raw
  const s = String(raw)
  if (CHECKBOX_KEYS.has(key)) return s === '1' || s === 'true'
  return s
}

function load(raw: Settings) {
  for (const [k, v] of Object.entries(raw)) {
    if (k in form) {
      ;(form as Record<string, string | boolean>)[k] = parseValue(k, v)
    }
  }
}

async function fetchSettings() {
  loading.value = true
  statusMessage.value = ''
  try {
    const [settingsRes, cameraRes] = await Promise.all([
      getSettings(),
      getCameraStatus().catch(() => null),
    ])
    load(settingsRes.settings as Settings)
    activeSummary.value = settingsRes.active_summary ?? ''
    providerReason.value = settingsRes.provider_reason ?? ''
    if (cameraRes?.cameras) {
      cameraOptions.value = cameraRes.cameras.map((c) => ({
        id: c.id,
        display_name: c.display_name,
        source_type: c.source_type,
      }))
    } else {
      cameraOptions.value = []
    }
  } catch (e) {
    statusMessage.value = `Failed to load: ${e instanceof Error ? e.message : 'Unknown error'}`
  } finally {
    loading.value = false
  }
}

function buildPayload(): Record<string, string | number | boolean> {
  const payload: Record<string, string | boolean | number> = {}
  for (const [k, v] of Object.entries(form)) {
    if (CHECKBOX_KEYS.has(k)) {
      payload[k] = v === true
    } else if (typeof v === 'string' && v !== '') {
      const num = Number(v)
      payload[k] = Number.isFinite(num) ? num : v
    } else if (typeof v === 'string') {
      payload[k] = v
    }
  }
  return payload
}

async function save() {
  saving.value = true
  statusMessage.value = ''
  try {
    const res = await postSettings(buildPayload())
    statusMessage.value = res.message
    if (res.active_summary) activeSummary.value = res.active_summary
    if (res.restart_required) {
      statusMessage.value += ' Some changes require app restart.'
    }
  } catch (e) {
    statusMessage.value = `Failed to save: ${e instanceof Error ? e.message : 'Unknown error'}`
  } finally {
    saving.value = false
  }
}

onMounted(fetchSettings)
</script>
