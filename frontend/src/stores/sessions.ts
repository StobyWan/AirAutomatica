import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSocket } from '@/composables/useSocket'
import { getSessions } from '@/api/session'
import { normalizeSession } from '@/api/session'
import type { SessionSummary } from '@/types'
import { ApiError } from '@/api/client'

export const useSessionsStore = defineStore('sessions', () => {
  const sessions = ref<SessionSummary[]>([])
  const currentSessionId = ref<number | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const socket = useSocket()
  socket.on('connect', () => {
    fetchSessions()
  })
  socket.on(
    'sessions_update',
    (payload: { sessions: SessionSummary[]; current_session_id?: number }) => {
      sessions.value = (payload.sessions ?? []).map(normalizeSession)
      currentSessionId.value = payload.current_session_id ?? null
    }
  )

  async function fetchSessions(params?: {
    autopilot?: string
    connection_mode?: string
  }) {
    loading.value = true
    error.value = null
    try {
      const res = await getSessions(params)
      sessions.value = (res.sessions ?? []).map(normalizeSession)
      currentSessionId.value = res.current_session_id ?? null
      return res
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e)
      error.value = msg
      throw e
    } finally {
      loading.value = false
    }
  }

  function clearError() {
    error.value = null
  }

  return {
    sessions,
    currentSessionId,
    loading,
    error,
    fetchSessions,
    clearError,
  }
})
