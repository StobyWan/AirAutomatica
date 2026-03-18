<template>
  <div>
    <div class="flex gap-4 mb-4 border-b border-white/10 pb-2">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>
    <div class="min-h-48">
      <FlightTab v-if="activeTab === 'flight'" />
      <EventsTab v-if="activeTab === 'events'" />
      <RecordingsTab v-if="activeTab === 'recordings'" />
      <AiTab v-if="activeTab === 'ai'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import FlightTab from './FlightTab.vue'
import EventsTab from './EventsTab.vue'
import RecordingsTab from './RecordingsTab.vue'
import AiTab from './AiTab.vue'

const tabs = [
  { id: 'flight', label: 'Flight' },
  { id: 'events', label: 'Events' },
  { id: 'recordings', label: 'Recordings' },
  { id: 'ai', label: 'AI' },
] as const

const activeTab = ref<(typeof tabs)[number]['id']>('flight')
</script>
