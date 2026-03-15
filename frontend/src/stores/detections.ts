import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSocket } from '@/composables/useSocket'
import type { Detection } from '@/types'

export const useDetectionsStore = defineStore('detections', () => {
  const detections = ref<Detection[]>([])

  const socket = useSocket()
  socket.on('detections_update', (payload: { detections: Detection[] }) => {
    detections.value = payload.detections ?? []
  })

  return { detections }
})
