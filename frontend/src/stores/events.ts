import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSocket } from '@/composables/useSocket'
import type { Event } from '@/types'

export const useEventsStore = defineStore('events', () => {
  const events = ref<Event[]>([])

  const socket = useSocket()
  socket.on('events_update', (payload: { events: Event[] }) => {
    events.value = payload.events ?? []
  })

  return { events }
})
