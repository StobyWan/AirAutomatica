<template>
  <div class="card">
    <h2>Events</h2>
    <div
      v-if="eventsStore.events.length"
      class="max-h-64 overflow-y-auto space-y-1"
    >
      <div
        v-for="(e, i) in eventsStore.events"
        :key="i"
        class="event-item py-1.5 border-b border-white/10 text-sm last:border-0"
      >
        {{ e.name }} — {{ fmtTs(e.started_at) }}
      </div>
    </div>
    <p v-else class="text-muted text-sm">No events</p>
  </div>
</template>

<script setup lang="ts">
import { useEventsStore } from '@/stores/events'
import { fmtTs } from '@/utils/formatters'

const eventsStore = useEventsStore()
</script>
