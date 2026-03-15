import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSocket } from '@/composables/useSocket'
import type { TrendsUpdatePayload } from '@/types'

export const useTrendsStore = defineStore('trends', () => {
  const voltage = ref<number[]>([])
  const relAlt = ref<number[]>([])
  const groundspeed = ref<number[]>([])
  const heartbeat = ref<number[]>([])

  const socket = useSocket()
  socket.on('trends_update', (payload: TrendsUpdatePayload) => {
    voltage.value = payload.voltage ?? []
    relAlt.value = payload.rel_alt ?? []
    groundspeed.value = payload.groundspeed ?? []
    heartbeat.value = payload.heartbeat ?? []
  })

  return { voltage, relAlt, groundspeed, heartbeat }
})
