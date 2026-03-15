import { ref } from 'vue'
import { io } from 'socket.io-client'

// Socket.io is served at root /socket.io, not under the SPA base path
let socket: ReturnType<typeof io> | null = null
const connected = ref(false)

export function useSocket() {
  if (!socket) {
    socket = io()
    connected.value = socket.connected
    socket.on('connect', () => {
      connected.value = true
    })
    socket.on('disconnect', () => {
      connected.value = false
    })
    socket.on('connect_error', () => {
      connected.value = false
    })
  }
  return { socket, connected }
}
