import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useSocket } from './composables/useSocket'
import './assets/base.css'

// Global unhandled rejection handler
window.addEventListener('unhandledrejection', (e) => {
  console.error('Unhandled promise rejection:', e.reason)
})

const app = createApp(App)
app.use(createPinia())
app.use(router)

// Initialize socket on app load so stores can subscribe
useSocket()

app.mount('#app')
