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
          @change="sessionsStore.setFilters()"
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
          @change="sessionsStore.setFilters()"
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
        @click="sessionsStore.clearFilters()"
      >
        Clear filters
      </button>
      <span class="text-xs text-slate-500 ml-auto">{{ resultCountText }}</span>
    </div>

    <div v-if="sessionsStore.loading" class="flex items-center gap-2 py-6">
      <BaseSpinner />
      <span class="text-sm text-slate-400">Loading…</span>
    </div>

    <div v-else-if="sessionsStore.sessions.length" class="flex flex-col gap-2">
      <router-link
        v-for="s in sessionsStore.sessions"
        :key="s.id"
        :to="{ name: 'SessionDetail', params: { id: String(s.id) } }"
        class="session-row grid grid-cols-[auto_1fr_auto] gap-3 items-start p-4 rounded-lg border border-slate-700 bg-slate-800/50 hover:bg-slate-800/80 transition-colors"
      >
        <span class="font-semibold text-cyan-400 font-mono">#{{ s.id }}</span>
        <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-400 min-w-0">
          <span>{{ fmtTs(s.started_at) }}</span>
          <span v-if="s.ended_at">– {{ fmtTs(s.ended_at) }}</span>
          <span>{{ labelAutopilot(s) }}</span>
          <span>{{ labelMode(s) }}</span>
          <span v-if="getDetectionCount(s) != null">
            {{ getDetectionCount(s) }} detections
          </span>
        </div>
        <span
          v-if="sessionsStore.currentSessionId === s.id"
          class="px-2 py-0.5 rounded text-xs font-medium bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 shrink-0"
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { fmtTs, labelAutopilot, labelMode } from '@/utils/formatters'

const sessionsStore = useSessionsStore()

const resultCountText = computed(() => {
  const n = sessionsStore.sessions.length
  return n === 0 ? 'No results' : `${n} session${n === 1 ? '' : 's'}`
})

function getDetectionCount(s: Record<string, unknown>): number | null {
  const v = s.detection_count
  return typeof v === 'number' ? v : null
}

onMounted(() => {
  sessionsStore.setFilters()
})
</script>
