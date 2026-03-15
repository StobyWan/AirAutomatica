import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSocket } from '@/composables/useSocket'
import type { AircraftState } from '@/types'

export const useStateStore = defineStore('state', () => {
  const lastState = ref<AircraftState | null>(null)

  const { socket } = useSocket()
  socket.on('state_update', (payload: { state: AircraftState }) => {
    lastState.value = payload.state
  })

  return { lastState }
})
