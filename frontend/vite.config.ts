import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'

const basePath = process.env.VITE_BASE_PATH || ''
const base = basePath ? basePath.replace(/\/$/, '') + '/' : '/'
const apiPort = process.env.VITE_API_PORT || process.env.API_PORT || '8000'
const apiTarget = `http://localhost:${apiPort}`

export default defineConfig({
  plugins: [vue()],
  base,
  define: {
    'import.meta.env.VITE_API_PORT': JSON.stringify(apiPort),
  },
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      '/connection': { target: apiTarget, changeOrigin: true },
      '/session': { target: apiTarget, changeOrigin: true },
      '/sessions': { target: apiTarget, changeOrigin: true },
      '/camera': { target: apiTarget, changeOrigin: true },
      '/recordings': { target: apiTarget, changeOrigin: true },
      '/recent-events': { target: apiTarget, changeOrigin: true },
      '/settings': { target: apiTarget, changeOrigin: true },
      '/ai': { target: apiTarget, changeOrigin: true },
      '/api': { target: apiTarget, changeOrigin: true },
      '/live': { target: apiTarget, changeOrigin: true },
      '/vehicle': { target: apiTarget, changeOrigin: true },
      '/health': { target: apiTarget, changeOrigin: true },
      '/static': { target: apiTarget, changeOrigin: true },
      '/socket.io': { target: apiTarget, ws: true },
    },
  },
})
