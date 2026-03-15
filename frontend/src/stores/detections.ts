import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSocket } from '@/composables/useSocket'
import { getRecentDetections } from '@/api/session'
import type { Detection } from '@/types'

export const useDetectionsStore = defineStore('detections', () => {
  const detections = ref<Detection[]>([])

  const { socket } = useSocket()
  socket.on(
    'detections_update',
    (payload: { detections: Detection[]; session_id?: number | null }) => {
      const incoming = payload.detections ?? []
      const sessionEnded =
        incoming.length === 0 && payload.session_id == null
      if (sessionEnded && detections.value.length > 0) {
        return
      }
      detections.value = incoming
    }
  )

  async function fetchRecentDetections() {
    try {
      const res = await getRecentDetections()
      detections.value = res.detections ?? []
    } catch {
      detections.value = []
    }
  }

  fetchRecentDetections()

  return { detections, fetchRecentDetections }
})
