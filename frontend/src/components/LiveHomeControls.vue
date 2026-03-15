<template>
  <div class="rounded-lg border border-slate-700 bg-slate-800/50 p-3">
    <div class="flex flex-wrap items-center gap-2 text-sm">
      <span class="text-slate-400">Live home:</span>
      <button
        type="button"
        class="px-2 py-1 rounded bg-slate-600 hover:bg-slate-500 text-white text-xs disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="!hasCurrentPosition"
        @click="useCurrent"
      >
        Use current position
      </button>
      <button
        type="button"
        class="px-2 py-1 rounded bg-slate-600 hover:bg-slate-500 text-white text-xs"
        @click="showModal = true"
      >
        Enter coordinates…
      </button>
      <button
        v-if="appHomeSource === 'manual_live'"
        type="button"
        class="px-2 py-1 rounded bg-slate-600 hover:bg-slate-500 text-white text-xs"
        @click="clearOverride"
      >
        Clear override
      </button>
      <span v-if="error" class="text-red-400 text-xs">{{ error }}</span>
    </div>

    <BaseModal v-model="showModal" size="sm">
      <h3 class="text-lg font-medium text-white mb-3">Override home for live</h3>
      <p class="text-xs text-slate-500 mb-3">
        Affects distance, bearing, and map. Does not change the flight controller's RTL home.
      </p>
      <div class="space-y-2 mb-4">
        <label class="block text-sm text-slate-400">Latitude</label>
        <input
          v-model.number="modalLat"
          type="number"
          step="any"
          min="-90"
          max="90"
          class="w-full rounded-lg bg-slate-700 text-white px-3 py-2 border border-slate-600"
          placeholder="e.g. 37.6213"
        />
        <label class="block text-sm text-slate-400">Longitude</label>
        <input
          v-model.number="modalLon"
          type="number"
          step="any"
          min="-180"
          max="180"
          class="w-full rounded-lg bg-slate-700 text-white px-3 py-2 border border-slate-600"
          placeholder="e.g. -122.379"
        />
      </div>
      <div class="flex gap-2 justify-end">
        <BaseButton variant="secondary" size="sm" @click="showModal = false">
          Cancel
        </BaseButton>
        <BaseButton variant="primary" size="sm" @click="applyCoordinates">
          Apply
        </BaseButton>
      </div>
    </BaseModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useTelemetryPathStore } from '@/stores/telemetryPath'
import { useStateStore } from '@/stores/state'
import { setLiveHome } from '@/api/live'
import { ApiError } from '@/api/client'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const pathStore = useTelemetryPathStore()
const stateStore = useStateStore()
const { currentPosition } = storeToRefs(pathStore)
const { appHomeSource } = storeToRefs(stateStore)

const showModal = ref(false)
const modalLat = ref<number | ''>('')
const modalLon = ref<number | ''>('')
const error = ref('')

const hasCurrentPosition = computed(
  () =>
    currentPosition.value?.lat != null &&
    currentPosition.value?.lon != null &&
    Number.isFinite(currentPosition.value.lat) &&
    Number.isFinite(currentPosition.value.lon)
)

function clearError() {
  error.value = ''
}

async function useCurrent() {
  if (!hasCurrentPosition.value) return
  clearError()
  try {
    await setLiveHome({ use_current: true })
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Failed to set home'
  }
}

async function clearOverride() {
  clearError()
  try {
    await setLiveHome({ clear: true })
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Failed to clear override'
  }
}

async function applyCoordinates() {
  const lat = modalLat.value
  const lon = modalLon.value
  if (
    typeof lat !== 'number' ||
    typeof lon !== 'number' ||
    !Number.isFinite(lat) ||
    !Number.isFinite(lon)
  ) {
    error.value = 'Enter valid latitude and longitude'
    return
  }
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
    error.value = 'Latitude must be -90 to 90, longitude -180 to 180'
    return
  }
  clearError()
  try {
    await setLiveHome({ lat, lon })
    showModal.value = false
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Failed to set home'
  }
}
</script>
