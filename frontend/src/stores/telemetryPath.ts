import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSocket } from '@/composables/useSocket'
import type { TelemetryPathUpdatePayload, PathPoint } from '@/types'

export const useTelemetryPathStore = defineStore('telemetryPath', () => {
  const path = ref<PathPoint[]>([])
  const currentPosition = ref<PathPoint | null>(null)
  const detections = ref<PathPoint[]>([])
  const sessionId = ref<number | null>(null)

  const { socket } = useSocket()
  socket.on(
    'telemetry_path_update',
    (payload: TelemetryPathUpdatePayload) => {
      path.value = payload.path ?? []
      currentPosition.value = payload.current_position ?? null
      detections.value = payload.detections ?? []
      sessionId.value = payload.session_id ?? null
    }
  )

  return { path, currentPosition, detections, sessionId }
})
