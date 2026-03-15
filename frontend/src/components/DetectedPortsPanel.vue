<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4 min-w-0">
    <h3 class="text-muted text-xs font-semibold uppercase tracking-wide mb-3">
      Detected Ports
    </h3>

    <div v-if="portsLoading" class="flex items-center gap-2 py-4 text-muted text-sm">
      <BaseSpinner size="sm" color="slate" />
      <span>Scanning ports…</span>
    </div>

    <div
      v-else-if="portsError"
      class="py-4 text-sm"
    >
      <p class="text-disconnected mb-2">{{ portsError }}</p>
      <button
        type="button"
        class="text-connecting hover:underline text-sm"
        @click="$emit('retry')"
      >
        Retry
      </button>
    </div>

    <div
      v-else-if="!ports.length"
      class="py-4 text-muted text-sm"
    >
      No ports detected
    </div>

    <ul v-else class="space-y-2">
      <li
        v-for="port in ports"
        :key="port.path"
        class="port-row rounded-lg border p-3 text-sm transition-colors"
        :class="port.mavlink_active ? 'port-active' : 'port-neutral'"
      >
        <div class="font-medium text-[var(--text)] truncate" :title="port.path">
          {{ port.path }}
        </div>
        <div class="mt-1 flex items-center gap-2">
          <span
            class="status-badge text-xs font-medium px-2 py-0.5 rounded"
            :class="port.mavlink_active ? 'badge-active' : 'badge-neutral'"
          >
            {{ port.mavlink_active ? 'Active' : 'Available' }}
          </span>
          <span v-if="port.autopilot" class="text-muted text-xs">
            {{ port.autopilot }}
          </span>
          <span v-else-if="port.mavlink_active && port.baud" class="text-muted text-xs">
            {{ port.baud }} baud
          </span>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import type { PortInfo } from '@/types'

defineProps<{
  ports: PortInfo[]
  portsLoading: boolean
  portsError: string | null
}>()

defineEmits<{
  retry: []
}>()
</script>

<style scoped>
.port-row {
  border-color: rgba(71, 85, 105, 0.5);
}

.port-active {
  border-left: 4px solid var(--connected);
  background: rgba(34, 197, 94, 0.08);
}

.port-neutral {
  border-left: 4px solid transparent;
  background: rgba(30, 41, 59, 0.4);
}

.badge-active {
  background: rgba(34, 197, 94, 0.2);
  color: var(--connected);
}

.badge-neutral {
  background: rgba(148, 163, 184, 0.15);
  color: var(--muted);
}
</style>
