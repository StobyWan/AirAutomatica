import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSocket } from '@/composables/useSocket'
import type { HealthUpdatePayload } from '@/types'

export const useHealthStore = defineStore('health', () => {
  const lastHealth = ref<HealthUpdatePayload | null>(null)

  const { socket } = useSocket()
  socket.on('health_update', (payload: HealthUpdatePayload) => {
    lastHealth.value = payload
  })

  function patchHealth(patch: Partial<HealthUpdatePayload>) {
    if (lastHealth.value) {
      lastHealth.value = { ...lastHealth.value, ...patch }
    } else {
      lastHealth.value = patch as HealthUpdatePayload
    }
  }

  return { lastHealth, patchHealth }
})
