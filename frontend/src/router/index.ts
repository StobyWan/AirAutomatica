import { createRouter, createWebHistory } from 'vue-router'

const basePath = (import.meta.env.VITE_BASE_PATH || '').replace(/\/$/, '')
const base = basePath ? basePath + '/' : '/'

// When served at /dashboard, root path '' shows Dashboard. When at /, we have / and /dashboard.
const routes =
  basePath === ''
    ? [
        {
          path: '/',
          name: 'Landing',
          component: () => import('@/views/LandingView.vue'),
        },
        {
          path: '/dashboard',
          component: () => import('@/views/DashboardView.vue'),
          children: [
            {
              path: '',
              name: 'Dashboard',
              component: () => import('@/views/DashboardLiveView.vue'),
            },
            {
              path: 'history',
              name: 'SessionHistory',
              component: () => import('@/views/SessionHistoryView.vue'),
            },
            {
              path: 'settings',
              name: 'Settings',
              component: () => import('@/views/SettingsView.vue'),
            },
          ],
        },
        {
          path: '/dashboard/sessions/:id',
          name: 'SessionDetail',
          component: () => import('@/views/SessionDetailView.vue'),
        },
      ]
    : [
        {
          path: '',
          component: () => import('@/views/DashboardView.vue'),
          children: [
            {
              path: '',
              name: 'Dashboard',
              component: () => import('@/views/DashboardLiveView.vue'),
            },
            {
              path: 'history',
              name: 'SessionHistory',
              component: () => import('@/views/SessionHistoryView.vue'),
            },
            {
              path: 'settings',
              name: 'Settings',
              component: () => import('@/views/SettingsView.vue'),
            },
          ],
        },
        {
          path: 'sessions/:id',
          name: 'SessionDetail',
          component: () => import('@/views/SessionDetailView.vue'),
        },
      ]

const router = createRouter({
  history: createWebHistory(base),
  routes,
})

export default router
