<template>
  <div class="flex flex-wrap items-center gap-2 py-2 px-3 rounded-lg border border-slate-700 bg-slate-800/50 mb-4">
    <span class="text-xs font-semibold text-slate-500 uppercase tracking-wider mr-1">Telemetry</span>
    <span class="chip" :class="chipClass(altNa)">Alt {{ altText }}</span>
    <span class="chip" :class="chipClass(altNa)">Spd {{ spdText }}</span>
    <span class="chip" :class="chipClass(voltageNa)">V {{ voltageText }}</span>
    <span class="chip" :class="chipClass(gpsNa)">GPS {{ gpsText }}</span>
    <span class="chip" :class="chipClass(hdgNa)">Hdg {{ hdgText }}</span>
    <span class="chip" :class="chipClass(linkNa)">Link {{ linkText }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStateStore } from '@/stores/state'
import { formatVolts, formatDistance } from '@/utils/formatters'

const stateStore = useStateStore()

const altText = computed(() => {
  const v = stateStore.lastState?.rel_alt_m
  if (v == null || (typeof v === 'number' && Number.isNaN(v))) return '—'
  return formatDistance(v)
})
const altNa = computed(() => !stateStore.lastState?.rel_alt_m)

const spdText = computed(() => {
  const v = stateStore.lastState?.groundspeed_m_s
  if (v == null || (typeof v === 'number' && Number.isNaN(v))) return '—'
  return v.toFixed(1) + ' m/s'
})
const spdNa = computed(() => stateStore.lastState?.groundspeed_m_s == null)

const voltageText = computed(() => {
  const v = stateStore.lastState?.voltage_v
  return formatVolts(v)
})
const voltageNa = computed(() => stateStore.lastState?.voltage_v == null)

const gpsText = computed(() => {
  const sats = stateStore.lastState?.satellites_visible
  if (sats == null) return '—'
  return String(sats)
})
const gpsNa = computed(() => stateStore.lastState?.satellites_visible == null)

const hdgText = computed(() => {
  const v = stateStore.lastState?.heading_deg
  if (v == null || (typeof v === 'number' && Number.isNaN(v))) return '—'
  return v.toFixed(0)
})
const hdgNa = computed(() => stateStore.lastState?.heading_deg == null)

const linkText = computed(() =>
  stateStore.lastState?.connected ? 'OK' : '—'
)
const linkNa = computed(() => !stateStore.lastState?.connected)

function chipClass(na: boolean): string {
  return na ? 'chip-err' : 'chip-ok'
}
</script>

<style scoped>
.chip {
  @apply inline-block px-2 py-0.5 rounded text-xs font-mono;
}
.chip-ok {
  @apply bg-slate-700/50 text-slate-300 border border-slate-600/50;
}
.chip-err {
  @apply bg-slate-700/50 text-slate-500 border border-slate-600/50;
}
</style>
