<template>
  <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
    <div
      v-for="s in series"
      :key="s.label"
      class="flex flex-col gap-0.5"
    >
      <span class="text-xs text-muted">{{ s.label }}</span>
      <svg
        v-if="!s.empty"
        class="sparkline w-full h-8"
        viewBox="0 0 140 32"
        preserveAspectRatio="none"
      >
        <polyline
          fill="none"
          stroke="#3b82f6"
          stroke-width="1"
          :points="s.points"
        />
      </svg>
      <div v-else class="text-muted text-xs">—</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTrendsStore } from '@/stores/trends'
import { renderTrends } from '@/utils/sparklines'

const trendsStore = useTrendsStore()

const series = computed(() =>
  renderTrends(
    trendsStore.voltage,
    trendsStore.relAlt,
    trendsStore.groundspeed,
    trendsStore.heartbeat
  )
)
</script>

<style scoped>
.sparkline {
  height: 36px;
}
</style>
