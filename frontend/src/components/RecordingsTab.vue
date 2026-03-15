<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
    <h2 class="text-base font-semibold text-slate-200 mb-2">Recordings for Current Session</h2>
    <p class="text-xs text-slate-500 mb-3">Recordings for the active flight session</p>

    <div v-if="loading" class="py-6 text-center">
      <svg class="animate-spin h-5 w-5 mx-auto text-slate-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
      </svg>
      <p class="text-sm text-slate-400 mt-2">Loading recordings…</p>
    </div>

    <div v-else-if="!recordings.length" class="py-6 text-center">
      <p class="text-slate-500 text-sm">{{ emptyMessage }}</p>
      <router-link
        v-if="!connectionStore.sessionId"
        :to="{ name: 'SessionHistory' }"
        class="mt-2 inline-block text-sm text-cyan-400 hover:text-cyan-300"
      >
        Session History
      </router-link>
    </div>

    <div v-else>
      <div class="space-y-2 max-h-64 overflow-y-auto">
        <div
          v-for="r in recordings"
          :key="r.filename"
          class="flex items-center justify-between gap-2 py-2 border-b border-slate-700/50 last:border-0"
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
            class="px-2 py-1 rounded text-xs text-red-400 hover:bg-red-900/30 shrink-0"
            @click="openDeleteModal(r.filename)"
          >
            Delete
          </button>
        </div>
      </div>
      <div v-if="connectionStore.sessionId" class="mt-2">
        <router-link
          :to="{ name: 'SessionDetail', params: { id: String(connectionStore.sessionId) } }"
          class="text-sm text-cyan-400 hover:text-cyan-300"
        >
          View full session
        </router-link>
      </div>
      <div v-if="playingFilename" class="mt-4 rounded-lg bg-black overflow-hidden max-w-md">
        <video
          ref="videoEl"
          controls
          class="w-full"
          preload="metadata"
          :src="recordingsUrl(playingFilename)"
          @ended="playingFilename = null"
        />
      </div>
    </div>

    <!-- Delete modal -->
    <div
      v-if="deleteFilename"
      class="fixed inset-0 z-50 overflow-y-auto"
      role="dialog"
      aria-modal="true"
    >
      <div class="flex min-h-screen items-center justify-center p-4">
        <div class="fixed inset-0 bg-black/60" @click="deleteFilename = null" />
        <div class="relative rounded-xl bg-slate-800 border border-slate-700 p-6 shadow-xl max-w-md w-full">
          <h3 class="text-lg font-semibold text-white">Delete recording?</h3>
          <p class="mt-2 text-sm text-slate-400 font-mono">{{ deleteFilename }}</p>
          <p class="mt-2 text-sm text-slate-500">This cannot be undone.</p>
          <div class="mt-6 flex gap-3 justify-end">
            <button
              type="button"
              class="px-4 py-2 rounded-lg bg-slate-600 hover:bg-slate-500 text-white text-sm font-medium"
              @click="deleteFilename = null"
            >
              Cancel
            </button>
            <button
              type="button"
              class="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-medium"
              :disabled="deleting"
              @click="confirmDelete"
            >
              {{ deleting ? 'Deleting…' : 'Delete' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useConnectionStore } from '@/stores/connection'
import { getRecordings, deleteRecording } from '@/api/session'
import { recordingsUrl } from '@/config'
import { fmtTsTime } from '@/utils/formatters'

const connectionStore = useConnectionStore()
const recordings = ref<{ filename: string; timestamp: string }[]>([])
const loading = ref(true)
const playingFilename = ref<string | null>(null)
const videoEl = ref<HTMLVideoElement | null>(null)
const deleteFilename = ref<string | null>(null)
const deleting = ref(false)

const emptyMessage = ref('No active session or no recordings yet')

async function fetchRecordings() {
  loading.value = true
  try {
    const res = await getRecordings(connectionStore.sessionId ?? undefined)
    recordings.value = res.recordings.map((r) => ({ filename: r.filename, timestamp: r.timestamp }))
    emptyMessage.value = connectionStore.sessionId
      ? 'No recordings yet'
      : 'No active session or no recordings yet'
  } catch {
    recordings.value = []
    emptyMessage.value = 'Failed to load recordings'
  } finally {
    loading.value = false
  }
}

function playRecording(filename: string) {
  playingFilename.value = filename
}

function openDeleteModal(filename: string) {
  deleteFilename.value = filename
}

async function confirmDelete() {
  const fn = deleteFilename.value
  if (!fn) return
  deleting.value = true
  try {
    await deleteRecording(fn)
    recordings.value = recordings.value.filter((r) => r.filename !== fn)
    if (playingFilename.value === fn) playingFilename.value = null
    deleteFilename.value = null
  } finally {
    deleting.value = false
  }
}

onMounted(fetchRecordings)

watch(() => connectionStore.sessionId, fetchRecordings)
</script>
