<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
    <h2 class="text-base font-semibold text-slate-200 mb-2">Rover Control</h2>
    <p class="text-xs text-slate-400 mb-3">
      Use gamepad or keyboard (WASD / arrows). Steering: left stick X. Throttle: triggers or right stick Y.
    </p>
    <div class="flex items-center gap-2 text-sm flex-wrap">
      <span
        class="inline-flex h-2 w-2 rounded-full"
        :class="connected ? 'bg-green-500' : 'bg-slate-500'"
      />
      <span class="text-slate-400">{{ connected ? 'Connected' : 'Disconnected' }}</span>
      <span v-if="lastEmitted" class="text-slate-500 text-xs">
        Last: {{ lastEmitted }}
      </span>
      <button
        type="button"
        class="ml-auto px-3 py-1 rounded bg-red-600/80 hover:bg-red-600 text-white text-xs font-medium"
        @click="stop"
      >
        Stop
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSocket } from '@/composables/useSocket'
import { useHealthStore } from '@/stores/health'
import { API_BASE } from '@/config'

const { socket, connected } = useSocket()
const healthStore = useHealthStore()

const seq = ref(0)
const lastEmitted = ref('')

const vehicleMode = computed(() => healthStore.lastHealth?.vehicle_mode ?? 'rover')

async function stop() {
  try {
    await fetch(`${API_BASE}/vehicle/stop`, { method: 'POST' })
  } catch {
    // ignore
  }
}

function emitControl(payload: {
  steering: number
  throttle: number
  pan?: number
  tilt?: number
  source: string
}) {
  if (!socket?.connected) return
  seq.value += 1
  const msg = {
    timestamp: new Date().toISOString(),
    seq: seq.value,
    steering: payload.steering,
    throttle: payload.throttle,
    pan: payload.pan ?? 0,
    tilt: payload.tilt ?? 0,
    source: payload.source,
    mode: vehicleMode.value,
  }
  socket.emit('vehicle_control', msg)
  lastEmitted.value = `S:${payload.steering.toFixed(2)} T:${payload.throttle.toFixed(2)}`
}

const keys = ref<Set<string>>(new Set())
const steering = ref(0)
const throttle = ref(0)

function updateFromKeys() {
  let s = 0
  let t = 0
  if (keys.value.has('a') || keys.value.has('ArrowLeft')) s -= 1
  if (keys.value.has('d') || keys.value.has('ArrowRight')) s += 1
  if (keys.value.has('w') || keys.value.has('ArrowUp')) t += 1
  if (keys.value.has('s') || keys.value.has('ArrowDown')) t -= 1
  steering.value = Math.max(-1, Math.min(1, s))
  throttle.value = Math.max(-1, Math.min(1, t))
}

let rafId: number

function tick() {
  updateFromKeys()
  if (steering.value !== 0 || throttle.value !== 0) {
    emitControl({
      steering: steering.value,
      throttle: throttle.value,
      source: 'keyboard',
    })
  }
  rafId = requestAnimationFrame(tick)
}

function onKeyDown(e: KeyboardEvent) {
  const k = e.key.toLowerCase()
  if (['a', 's', 'd', 'w', 'arrowleft', 'arrowright', 'arrowup', 'arrowdown'].includes(k)) {
    e.preventDefault()
    keys.value.add(k)
  }
}

function onKeyUp(e: KeyboardEvent) {
  const k = e.key.toLowerCase()
  keys.value.delete(k)
}

function onGamepadConnected() {
  if (rafId) return
  rafId = requestAnimationFrame(tick)
}

function onGamepadDisconnected() {
  const pads = navigator.getGamepads()
  const anyConnected = Array.from(pads).some((p) => p !== null)
  if (!anyConnected) {
    cancelAnimationFrame(rafId)
    rafId = 0
  }
}

function pollGamepad() {
  const pads = navigator.getGamepads()
  for (const pad of pads) {
    if (!pad) continue
    const steer = pad.axes[0] ?? 0
    const stickY = pad.axes[1] ?? 0
    const throttleVal = -stickY
    if (Math.abs(steer) > 0.05 || Math.abs(throttleVal) > 0.05) {
      emitControl({
        steering: steer,
        throttle: throttleVal,
        source: 'gamepad',
      })
    }
  }
}

let gamepadInterval: ReturnType<typeof setInterval>

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  window.addEventListener('gamepadconnected', onGamepadConnected)
  window.addEventListener('gamepaddisconnected', onGamepadDisconnected)
  if (navigator.getGamepads().some((p) => p !== null)) {
    onGamepadConnected()
  }
  rafId = requestAnimationFrame(tick)
  gamepadInterval = setInterval(pollGamepad, 50)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('gamepadconnected', onGamepadConnected)
  window.removeEventListener('gamepaddisconnected', onGamepadDisconnected)
  if (rafId) cancelAnimationFrame(rafId)
  clearInterval(gamepadInterval)
})
</script>
