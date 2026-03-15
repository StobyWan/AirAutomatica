import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ReplayTab from './ReplayTab.vue'
import { useReplayStore } from '@/stores/replay'

vi.mock('@/api/session', () => ({
  getSessionTelemetrySamples: vi.fn().mockResolvedValue({ samples: [], session_id: 1 }),
  getSessionPath: vi.fn().mockResolvedValue({ path: [], session_id: 1 }),
  getSessionRecordings: vi.fn().mockResolvedValue({ recordings: [], session_id: 1, session_resolved: true, count: 0 }),
  getSessionFlightEvents: vi.fn().mockResolvedValue({ events: [], session_id: 1 }),
  getSessionPhaseIntervals: vi.fn().mockResolvedValue({ intervals: [], session_id: 1 }),
}))

describe('ReplayTab lazy loading', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('calls load on mount', async () => {
    const { getSessionTelemetrySamples } = await import('@/api/session')
    mount(ReplayTab, {
      props: { sessionId: 42 },
      global: { plugins: [createPinia()] },
    })
    await flushPromises()
    expect(getSessionTelemetrySamples).toHaveBeenCalledWith(42, { limit: 5000, order: 'asc' })
  })

  it('calls load when sessionId prop changes', async () => {
    const { getSessionTelemetrySamples } = await import('@/api/session')
    const wrapper = mount(ReplayTab, {
      props: { sessionId: 1 },
      global: { plugins: [createPinia()] },
    })
    await flushPromises()
    expect(getSessionTelemetrySamples).toHaveBeenCalledWith(1, expect.any(Object))
    vi.clearAllMocks()
    await wrapper.setProps({ sessionId: 2 })
    await flushPromises()
    expect(getSessionTelemetrySamples).toHaveBeenCalledWith(2, expect.any(Object))
  })

  it('shows loading state initially', async () => {
    const pinia = createPinia()
    const wrapper = mount(ReplayTab, {
      props: { sessionId: 1 },
      global: { plugins: [pinia] },
    })
    const store = useReplayStore()
    store.loading = true
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Loading')
  })

  it('shows empty state when no samples', async () => {
    const pinia = createPinia()
    const wrapper = mount(ReplayTab, {
      props: { sessionId: 1 },
      global: { plugins: [pinia] },
    })
    const store = useReplayStore()
    store.loading = false
    store.loaded = true
    store.samples = []
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('No telemetry data')
  })
})
