import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSocket } from '@/composables/useSocket'
import { getSessions } from '@/api/session'
import { normalizeSession } from '@/api/session'
import type { SessionSummary } from '@/types'
import { ApiError } from '@/api/client'

export interface SessionFilters {
  autopilot: string
  connection_mode: string
}

export const useSessionsStore = defineStore('sessions', () => {
  const sessions = ref<SessionSummary[]>([])
  const total = ref(0)
  const currentSessionId = ref<number | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const filters = ref<SessionFilters>({ autopilot: '', connection_mode: '' })

  const { socket } = useSocket()
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
    limit?: number
    offset?: number
  }) {
    loading.value = true
    error.value = null
    try {
      const res = await getSessions(params)
      sessions.value = (res.sessions ?? []).map(normalizeSession)
      total.value = res.total ?? 0
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

  function setFilters(updates?: {
    autopilot?: string
    connection_mode?: string
    limit?: number
    offset?: number
  }) {
    if (updates?.autopilot !== undefined) filters.value.autopilot = updates.autopilot
    if (updates?.connection_mode !== undefined) filters.value.connection_mode = updates.connection_mode
    const params: {
      autopilot?: string
      connection_mode?: string
      limit?: number
      offset?: number
    } = {}
    if (filters.value.autopilot) params.autopilot = filters.value.autopilot
    if (filters.value.connection_mode) params.connection_mode = filters.value.connection_mode
    if (updates?.limit != null) params.limit = updates.limit
    if (updates?.offset != null) params.offset = updates.offset
    return fetchSessions(params)
  }

  function clearFilters(opts?: { limit?: number; offset?: number }) {
    filters.value = { autopilot: '', connection_mode: '' }
    return fetchSessions(opts)
  }

  return {
    sessions,
    total,
    currentSessionId,
    loading,
    error,
    filters,
    fetchSessions,
    clearError,
    setFilters,
    clearFilters,
  }
})
