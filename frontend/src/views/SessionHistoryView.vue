<template>
  <div class="p-4">
    <h1 class="text-2xl font-bold text-slate-100 tracking-tight mb-4">Session History</h1>

    <div class="flex flex-wrap items-center gap-3 mb-4">
      <div class="flex items-center gap-2">
        <label for="sessions-filter-autopilot" class="text-xs text-slate-400">Autopilot</label>
        <select
          id="sessions-filter-autopilot"
          v-model="sessionsStore.filters.autopilot"
          class="px-2 py-1 rounded bg-slate-700/50 border border-slate-600 text-sm text-slate-200"
          @change="onFilterChange"
        >
          <option value="">All</option>
          <option value="ardupilot">ArduPilot</option>
          <option value="inav">iNav</option>
          <option value="generic">Generic</option>
        </select>
      </div>
      <div class="flex items-center gap-2">
        <label for="sessions-filter-mode" class="text-xs text-slate-400">Mode</label>
        <select
          id="sessions-filter-mode"
          v-model="sessionsStore.filters.connection_mode"
          class="px-2 py-1 rounded bg-slate-700/50 border border-slate-600 text-sm text-slate-200"
          @change="onFilterChange"
        >
          <option value="">All</option>
          <option value="mock">Mock</option>
          <option value="ardupilot">ArduPilot</option>
          <option value="inav">iNav</option>
        </select>
      </div>
      <button
        type="button"
        class="px-2 py-1 rounded text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-600/50 transition-colors"
        @click="page = 1; sessionsStore.clearFilters({ limit: pageSize, offset: 0 })"
      >
        Clear filters
      </button>
      <span class="text-xs text-slate-500 ml-auto">{{ resultCountText }}</span>
    </div>

    <div v-if="sessionsStore.loading" class="flex items-center gap-2 py-6">
      <BaseSpinner />
      <span class="text-sm text-slate-400">Loading…</span>
    </div>

    <div v-else-if="sessionsStore.sessions.length" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      <router-link
        v-for="s in sessionsStore.sessions"
        :key="s.id"
        :to="{ name: 'SessionDetail', params: { id: String(s.id) } }"
        class="block p-4 rounded-lg border border-slate-700 bg-slate-800/50 hover:bg-slate-800/80 transition-colors"
      >
        <div class="font-semibold text-cyan-400 font-mono text-lg">#{{ s.id }}</div>
        <div class="text-sm text-slate-400 mt-1">
          {{ fmtTs(s.started_at) }}
          <span v-if="s.ended_at"> – {{ fmtTs(s.ended_at) }}</span>
        </div>
        <div class="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-500 mt-2">
          <span>{{ labelAutopilot(s) }}</span>
          <span>{{ labelMode(s) }}</span>
          <span v-if="getDetectionCount(s) != null">
            {{ getDetectionCount(s) }} detections
          </span>
        </div>
        <span
          v-if="sessionsStore.currentSessionId === s.id"
          class="inline-block mt-2 px-2 py-0.5 rounded text-xs font-medium bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
        >
          Current
        </span>
      </router-link>
    </div>

    <div v-else class="py-6 text-center">
      <p class="text-slate-500 text-sm">No sessions</p>
      <router-link
        :to="{ name: 'Dashboard' }"
        class="mt-2 inline-block text-sm text-cyan-400 hover:text-cyan-300"
      >
        Go to Live to start a session
      </router-link>
    </div>

    <div
      v-if="sessionsStore.sessions.length && totalPages > 1"
      class="flex items-center justify-center gap-4 mt-6"
    >
      <button
        type="button"
        class="px-3 py-1.5 rounded text-sm text-slate-300 hover:text-slate-100 hover:bg-slate-600/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        :disabled="page <= 1"
        @click="goToPage(page - 1)"
      >
        Prev
      </button>
      <span class="text-sm text-slate-400">Page {{ page }} of {{ totalPages }}</span>
      <button
        type="button"
        class="px-3 py-1.5 rounded text-sm text-slate-300 hover:text-slate-100 hover:bg-slate-600/50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        :disabled="page >= totalPages"
        @click="goToPage(page + 1)"
      >
        Next
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { fmtTs, labelAutopilot, labelMode } from '@/utils/formatters'

const sessionsStore = useSessionsStore()
const page = ref(1)
const pageSize = 12

const totalPages = computed(() =>
  Math.max(1, Math.ceil(sessionsStore.total / pageSize))
)

const resultCountText = computed(() => {
  const total = sessionsStore.total
  if (total === 0) return 'No results'
  const start = (page.value - 1) * pageSize + 1
  const end = Math.min((page.value - 1) * pageSize + sessionsStore.sessions.length, total)
  return `${start}–${end} of ${total} session${total === 1 ? '' : 's'}`
})

function getDetectionCount(s: Record<string, unknown>): number | null {
  const v = s.detection_count
  return typeof v === 'number' ? v : null
}

function fetchPage() {
  sessionsStore.setFilters({
    limit: pageSize,
    offset: (page.value - 1) * pageSize,
  })
}

function goToPage(p: number) {
  page.value = p
  fetchPage()
}

function onFilterChange() {
  page.value = 1
  sessionsStore.setFilters({
    limit: pageSize,
    offset: 0,
  })
}

onMounted(() => {
  fetchPage()
})
</script>
