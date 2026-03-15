import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSocket } from '@/composables/useSocket'
import type { AircraftState } from '@/types'
import type { AppHomeSource, StateUpdatePayload } from '@/types/socket'

export const useStateStore = defineStore('state', () => {
  const lastState = ref<AircraftState | null>(null)
  const appHomeSource = ref<AppHomeSource | null>(null)

  const { socket } = useSocket()
  socket.on('state_update', (payload: StateUpdatePayload) => {
    lastState.value = payload.state
    appHomeSource.value = payload.app_home_source ?? null
  })

  return { lastState, appHomeSource }
})
