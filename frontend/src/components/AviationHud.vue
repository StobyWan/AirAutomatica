<template>
  <div class="absolute inset-0 pointer-events-none">
    <!-- ATTITUDE – top right -->
    <div
      class="absolute top-3 right-4 w-[104px] min-w-[104px] max-w-[104px] rounded-lg border border-slate-600/80 bg-slate-900/85 backdrop-blur-sm p-2 shadow-lg flex flex-col items-center"
    >
      <div class="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1 w-full text-center">Attitude</div>
      <div class="relative w-20 h-20 rounded-full overflow-hidden border border-slate-600 bg-slate-900/80 shrink-0">
        <div
          v-if="!hasAttitude"
          class="absolute inset-0 flex items-center justify-center text-slate-500 text-[10px]"
        >
          —
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
            class="absolute left-1/2 top-1/2 w-12 h-3 -ml-6 -mt-1.5 border-2 border-cyan-400 rounded-sm transition-transform duration-100"
            :style="planeStyle"
          />
        </template>
      </div>
      <div class="mt-1 text-center text-[10px] text-slate-500 font-mono w-full truncate">{{ attitudeText }}</div>
    </div>

    <!-- HEADING above HOME – bottom right stack, same width as Attitude right margin -->
    <div class="absolute bottom-3 right-4 flex flex-col items-center gap-2">
      <div
        class="w-[80px] min-w-[80px] max-w-[80px] rounded-lg border border-slate-600/80 bg-slate-900/85 backdrop-blur-sm p-1.5 shadow-lg flex flex-col items-center"
      >
        <div class="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1 w-full text-center">Heading</div>
        <div
          v-if="!hasHeading"
          class="w-14 h-14 shrink-0 rounded-full border border-slate-600 bg-slate-900/80 flex items-center justify-center text-slate-500 text-[9px]"
        >
          —
        </div>
        <div v-else class="flex flex-col items-center gap-0.5 w-full">
          <div class="relative w-14 h-14 rounded-full border border-slate-600 bg-slate-900/80 flex items-center justify-center shadow-inner">
            <span class="absolute -top-0.5 left-1/2 -translate-x-1/2 text-[8px] font-semibold text-slate-500">N</span>
            <div
              class="absolute inset-0 flex items-center justify-center pointer-events-none transition-transform duration-150"
              :style="{ transform: `rotate(${headingDeg}deg)` }"
            >
              <svg class="w-7 h-7 text-cyan-400 drop-shadow-sm" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2L4 22h4l4-8 4 8h4L12 2z" />
              </svg>
            </div>
          </div>
          <div class="text-center font-mono text-[9px] text-slate-300 tabular-nums">{{ headingText }}</div>
        </div>
      </div>

      <div
        class="w-[80px] min-w-[80px] max-w-[80px] rounded-lg border border-slate-600/80 bg-slate-900/85 backdrop-blur-sm p-1.5 shadow-lg flex flex-col items-center"
      >
        <div class="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1 w-full text-center">Home</div>
        <div v-if="!hasHome" class="w-14 h-14 shrink-0 rounded-full border border-slate-600 bg-slate-900/80 flex items-center justify-center text-slate-500 text-[9px]">
          —
        </div>
        <div v-else class="flex flex-col items-center gap-0.5">
          <div class="relative w-14 h-14 rounded-full border border-slate-600 bg-slate-900/80 flex items-center justify-center">
            <span class="absolute -top-0.5 left-1/2 -translate-x-1/2 text-[8px] font-semibold text-slate-500">N</span>
            <div
              class="absolute inset-0 flex items-center justify-center pointer-events-none transition-transform duration-150"
              :style="{ transform: `rotate(${homeBearing}deg)` }"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24">
                <polygon points="12,4 20,20 4,20" fill="#22c55e" stroke="#166534" stroke-width="1" />
              </svg>
            </div>
          </div>
          <div class="text-center w-full min-w-0">
            <div class="font-mono text-[9px] text-slate-300 truncate">{{ formatDistance(homeDistanceM) }}</div>
            <div class="text-[8px] text-slate-500">{{ homeBearing != null ? homeBearing.toFixed(0) + '°' : '—' }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ALTITUDE, SPEED, POWER – bottom left; two rows on mobile (<978px), fixed left -->
    <div
      class="absolute bottom-3 left-4 w-fit max-w-[calc(100%-7rem)] max-[978px]:max-w-[calc(100%-6rem)] rounded-lg border border-slate-600/80 bg-slate-900/85 backdrop-blur-sm px-3 py-2 shadow-lg"
    >
      <div
        class="flex flex-col max-[978px]:items-start max-[978px]:gap-y-1.5 min-[979px]:flex-row min-[979px]:items-center min-[979px]:gap-x-3 text-[10px]"
      >
        <div class="flex items-baseline gap-x-1.5 shrink-0">
          <span class="text-slate-500 uppercase tracking-wider">ALT</span>
          <span class="font-mono text-slate-200 tabular-nums">{{ altitudeText }}</span>
        </div>
        <span class="text-slate-600 shrink-0 max-[978px]:hidden">·</span>
        <div class="flex items-center gap-x-3 shrink-0">
          <div class="flex items-baseline gap-x-1.5 shrink-0">
            <span class="text-slate-500 uppercase tracking-wider">SPD</span>
            <span class="font-mono text-slate-200 tabular-nums">{{ speedText }}</span>
          </div>
          <span class="text-slate-600 shrink-0">·</span>
          <div class="flex items-baseline gap-x-1.5 shrink-0">
            <span class="text-slate-500 uppercase tracking-wider">PWR</span>
            <span class="font-mono text-slate-200 tabular-nums">{{ powerText }}</span>
          </div>
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

/** Path store updates are throttled; state_update has lat/lon every tick. */
const navCurrentLatLon = computed((): { lat: number; lon: number } | null => {
  const c = pathStore.currentPosition
  if (
    c?.lat != null &&
    c?.lon != null &&
    Number.isFinite(c.lat) &&
    Number.isFinite(c.lon)
  ) {
    return { lat: c.lat, lon: c.lon }
  }
  const s = stateStore.lastState
  if (
    s?.lat != null &&
    s?.lon != null &&
    Number.isFinite(s.lat) &&
    Number.isFinite(s.lon)
  ) {
    return { lat: s.lat, lon: s.lon }
  }
  return null
})

const rollRad = computed(() => stateStore.lastState?.roll_rad ?? null)
const pitchRad = computed(() => stateStore.lastState?.pitch_rad ?? null)
const relAlt = computed(() => stateStore.lastState?.rel_alt_m ?? null)
const climbRate = computed(() => stateStore.lastState?.climb_rate_m_s ?? null)
const voltage = computed(() => stateStore.lastState?.voltage_v ?? null)
const current = computed(() => stateStore.lastState?.current_a ?? null)

const hasAttitude = computed(() => rollRad.value != null || pitchRad.value != null)
const hasHome = computed(() => homeDistanceM.value != null)

const headingDeg = computed(() => {
  const h = stateStore.lastState?.heading_deg
  if (h == null || !Number.isFinite(h)) return 0
  return h
})

const hasHeading = computed(() => {
  const h = stateStore.lastState?.heading_deg
  return h != null && Number.isFinite(h)
})

const headingText = computed(() => {
  const h = stateStore.lastState?.heading_deg
  if (h == null || !Number.isFinite(h)) return '—'
  return `${Math.round(h)}°`
})

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

const homePosition = computed(() => {
  const s = stateStore.lastState
  if (s?.home_lat != null && s?.home_lon != null) {
    return { lat: s.home_lat, lon: s.home_lon }
  }
  return null
})

const homeDistanceM = computed(() => {
  const cur = navCurrentLatLon.value
  const home = homePosition.value
  if (
    !cur ||
    !home ||
    home.lat == null ||
    home.lon == null ||
    !Number.isFinite(home.lat) ||
    !Number.isFinite(home.lon)
  ) {
    return null
  }
  const R = 6371000
  const dLat = ((home.lat - cur.lat) * Math.PI) / 180
  const dLon = ((home.lon - cur.lon) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((cur.lat * Math.PI) / 180) *
      Math.cos((home.lat * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
})

const homeBearing = computed(() => {
  const cur = navCurrentLatLon.value
  const home = homePosition.value
  if (
    !cur ||
    !home ||
    home.lat == null ||
    home.lon == null ||
    !Number.isFinite(home.lat) ||
    !Number.isFinite(home.lon)
  ) {
    return null
  }
  const dLon = ((home.lon - cur.lon) * Math.PI) / 180
  const y = Math.sin(dLon) * Math.cos((home.lat * Math.PI) / 180)
  const x =
    Math.cos((cur.lat * Math.PI) / 180) * Math.sin((home.lat * Math.PI) / 180) -
    Math.sin((cur.lat * Math.PI) / 180) *
      Math.cos((home.lat * Math.PI) / 180) *
      Math.cos(dLon)
  let brg = (Math.atan2(y, x) * 180) / Math.PI
  return (brg + 360) % 360
})

const attitudeText = computed(() => {
  const r = rollRad.value
  const p = pitchRad.value
  if (r == null && p == null) return '—'
  const parts: string[] = []
  if (r != null) parts.push(`R ${((r * 180) / Math.PI).toFixed(1)}°`)
  if (p != null) parts.push(`P ${((p * 180) / Math.PI).toFixed(1)}°`)
  return parts.join(' · ')
})

const altitudeText = computed(() => {
  const alt = relAlt.value
  const climb = climbRate.value
  if (alt == null && climb == null) return '—'
  const parts: string[] = []
  if (alt != null) parts.push(`Above home ${formatMetersOrKm(alt)}`)
  if (climb != null) {
    const s = climb.toFixed(1)
    parts.push(`Climb ${climb >= 0 ? '+' : ''}${s} m/s`)
  }
  return parts.join(' ')
})

const speedText = computed(() => {
  const spd = stateStore.lastState?.airspeed_m_s ?? stateStore.lastState?.groundspeed_m_s
  if (spd == null || !Number.isFinite(spd)) return '—'
  const label = stateStore.lastState?.airspeed_m_s != null ? '(air)' : '(ground)'
  return `${spd.toFixed(1)} m/s ${label}`
})

const powerText = computed(() => {
  const v = voltage.value
  const a = current.value
  if (v == null && a == null) return '—'
  const parts: string[] = []
  if (v != null) parts.push(`${v.toFixed(2)} V`)
  if (a != null) parts.push(`${a.toFixed(2)} A`)
  return parts.join(' ')
})
</script>
