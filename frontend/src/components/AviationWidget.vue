<template>
  <div class="flex flex-wrap gap-4">
    <!-- Attitude -->
    <div class="rounded-lg border border-slate-600/80 bg-slate-800/60 p-4 flex-1 min-w-[152px]">
      <h3 class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-3">Attitude</h3>
      <div class="relative w-32 h-32 mx-auto rounded-full overflow-hidden border-2 border-slate-600/80 bg-slate-900/90 shrink-0 shadow-inner">
        <div
          v-if="!hasAttitude"
          class="absolute inset-0 flex items-center justify-center text-slate-500 text-xs"
        >
          Unavailable
        </div>
        <template v-else>
          <div
            class="absolute left-0 right-0 h-1/2 bg-gradient-to-b from-sky-600/90 to-sky-700/80 transition-all duration-100"
            :style="horizonSkyStyle"
          />
          <div
            class="absolute left-0 right-0 bottom-0 h-1/2 bg-gradient-to-t from-amber-800/90 to-amber-900/80 transition-all duration-100"
            :style="horizonEarthStyle"
          />
          <div
            class="absolute left-0 right-0 h-0.5 bg-white/90 transition-all duration-100"
            :style="horizonLineStyle"
          />
          <div
            class="absolute left-1/2 top-1/2 w-16 h-4 -ml-8 -mt-2 border-2 border-cyan-400 rounded-sm transition-transform duration-100"
            :style="planeStyle"
          />
        </template>
      </div>
      <div class="mt-2 text-center text-sm font-mono font-medium text-slate-300 tabular-nums">
        {{ attitudeValues }}
      </div>
    </div>

    <!-- Home -->
    <div class="rounded-lg border border-slate-600/80 bg-slate-800/60 p-4 flex-1 min-w-[152px]">
      <h3 class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-3">Home</h3>
      <div v-if="!hasHome" class="text-center text-slate-500 text-xs py-6">
        Position or home unavailable
      </div>
      <div v-else class="flex flex-col items-center gap-2">
        <div class="relative w-32 h-32 mx-auto rounded-full border-2 border-slate-600/80 bg-slate-900/90 flex items-center justify-center shrink-0 shadow-inner">
          <span class="absolute -top-0.5 left-1/2 -translate-x-1/2 text-[10px] font-semibold text-slate-500">N</span>
          <div
            class="absolute inset-0 flex items-center justify-center pointer-events-none transition-transform duration-150"
            :style="{ transform: `rotate(${homeBearing}deg)` }"
          >
            <svg class="w-10 h-10 text-emerald-400" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L4 22h4l4-8 4 8h4L12 2z" />
            </svg>
          </div>
        </div>
        <div class="text-center text-sm font-mono font-medium text-slate-200 tabular-nums">
          {{ homeBearing.toFixed(0) }}° {{ formatDistance(homeDistanceM) }}
        </div>
      </div>
    </div>

    <!-- Altitude -->
    <div class="rounded-lg border border-slate-600/80 bg-slate-800/60 p-4 flex-1 min-w-[120px]">
      <h3 class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-3">Altitude</h3>
      <div v-if="!hasAltitude" class="text-center text-slate-500 text-xs py-6">Unavailable</div>
      <div v-else class="space-y-2 text-sm">
        <div class="flex justify-between items-center gap-2">
          <span class="text-slate-500 text-xs">Above home</span>
          <span class="font-mono font-medium text-slate-200 tabular-nums">{{ formatMeters(relAlt) }}</span>
        </div>
        <div class="flex justify-between items-center gap-2">
          <span class="text-slate-500 text-xs">Climb</span>
          <span class="font-mono font-medium text-slate-200 tabular-nums">{{ formatClimb(climbRate) }}</span>
        </div>
      </div>
    </div>

    <!-- Speed -->
    <div class="rounded-lg border border-slate-600/80 bg-slate-800/60 p-4 flex-1 min-w-[100px]">
      <h3 class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-3">Speed</h3>
      <div class="text-center">
        <div class="font-mono text-lg font-medium text-slate-200 tabular-nums">{{ speedValue }}</div>
        <div class="text-xs text-slate-500 mt-0.5">{{ speedLabel }}</div>
      </div>
    </div>

    <!-- Power -->
    <div class="rounded-lg border border-slate-600/80 bg-slate-800/60 p-4 flex-1 min-w-[100px]">
      <h3 class="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-3">Power</h3>
      <div class="space-y-2 text-sm">
        <div class="flex justify-between items-center gap-2">
          <span class="text-slate-500 text-xs">Voltage</span>
          <span class="font-mono font-medium text-slate-200 tabular-nums">{{ formatVolts(voltage) }}</span>
        </div>
        <div class="flex justify-between items-center gap-2">
          <span class="text-slate-500 text-xs">Current</span>
          <span class="font-mono font-medium text-slate-200 tabular-nums">{{ formatAmps(current) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStateStore } from '@/stores/state'
import { useTelemetryPathStore } from '@/stores/telemetryPath'
import { formatDistance, formatMetersOrKm } from '@/utils/formatters'

const stateStore = useStateStore()
const pathStore = useTelemetryPathStore()

const rollRad = computed(() => stateStore.lastState?.roll_rad ?? null)
const pitchRad = computed(() => stateStore.lastState?.pitch_rad ?? null)
const relAlt = computed(() => stateStore.lastState?.rel_alt_m ?? null)
const climbRate = computed(() => stateStore.lastState?.climb_rate_m_s ?? null)
const voltage = computed(() => stateStore.lastState?.voltage_v ?? null)
const current = computed(() => stateStore.lastState?.current_a ?? null)

const hasAttitude = computed(() => rollRad.value != null || pitchRad.value != null)
const hasAltitude = computed(() => relAlt.value != null || climbRate.value != null)

const rollDeg = computed(() => (rollRad.value != null ? (rollRad.value * 180) / Math.PI : 0))
const pitchDeg = computed(() => (pitchRad.value != null ? (pitchRad.value * 180) / Math.PI : 0))

const horizonSkyStyle = computed(() => {
  const p = pitchDeg.value
  const offset = Math.max(-50, Math.min(50, p * 2))
  return { transform: `translateY(${offset}%)` }
})
const horizonEarthStyle = computed(() => {
  const p = pitchDeg.value
  const offset = Math.max(-50, Math.min(50, p * 2))
  return { transform: `translateY(${-offset}%)` }
})
const horizonLineStyle = computed(() => {
  const p = pitchDeg.value
  const top = 50 + Math.max(-25, Math.min(25, p * 2))
  return { top: `${top}%`, transform: 'translateY(-50%)' }
})
const planeStyle = computed(() => {
  const r = rollDeg.value
  return { transform: `translate(-50%, -50%) rotate(${r}deg)` }
})

const attitudeValues = computed(() => {
  const r = rollRad.value
  const p = pitchRad.value
  if (r == null && p == null) return '—'
  const parts: string[] = []
  if (r != null) parts.push(`R ${((r * 180) / Math.PI).toFixed(1)}°`)
  if (p != null) parts.push(`P ${((p * 180) / Math.PI).toFixed(1)}°`)
  return parts.join(' · ')
})

const homePosition = computed(() => {
  const s = stateStore.lastState
  if (s?.home_lat != null && s?.home_lon != null) {
    return { lat: s.home_lat, lon: s.home_lon }
  }
  return null
})

const homeDistanceM = computed(() => {
  const current = pathStore.currentPosition
  const home = homePosition.value
  if (!current?.lat || !current?.lon || !home?.lat || !home?.lon) return null
  const R = 6371000
  const dLat = ((home.lat - current.lat) * Math.PI) / 180
  const dLon = ((home.lon - current.lon) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((current.lat * Math.PI) / 180) *
      Math.cos((home.lat * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
})

const homeBearing = computed(() => {
  const current = pathStore.currentPosition
  const home = homePosition.value
  if (!current?.lat || !current?.lon || !home?.lat || !home?.lon) return 0
  const dLon = ((home.lon - current.lon) * Math.PI) / 180
  const y = Math.sin(dLon) * Math.cos((home.lat * Math.PI) / 180)
  const x =
    Math.cos((current.lat * Math.PI) / 180) * Math.sin((home.lat * Math.PI) / 180) -
    Math.sin((current.lat * Math.PI) / 180) *
      Math.cos((home.lat * Math.PI) / 180) *
      Math.cos(dLon)
  let brg = (Math.atan2(y, x) * 180) / Math.PI
  return (brg + 360) % 360
})

const hasHome = computed(() => homeDistanceM.value != null)

const speedValue = computed(() => {
  const spd = stateStore.lastState?.airspeed_m_s ?? stateStore.lastState?.groundspeed_m_s
  if (spd == null || !Number.isFinite(spd)) return '—'
  return spd.toFixed(1)
})

const speedLabel = computed(() => {
  const air = stateStore.lastState?.airspeed_m_s
  return air != null ? 'm/s (air)' : 'm/s (ground)'
})

function formatMeters(m: number | null): string {
  if (m == null || !Number.isFinite(m)) return '—'
  return formatMetersOrKm(m)
}

function formatClimb(m: number | null): string {
  if (m == null || !Number.isFinite(m)) return '—'
  const s = m.toFixed(1)
  return m >= 0 ? `+${s} m/s` : `${s} m/s`
}

function formatVolts(v: number | null): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toFixed(2) + ' V'
}

function formatAmps(a: number | null): string {
  if (a == null || !Number.isFinite(a)) return '—'
  return a.toFixed(2) + ' A'
}
</script>
