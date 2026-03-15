<template>
  <nav class="flex gap-4 mb-4 border-b border-white/10 pb-2">
    <router-link
      :to="{ name: 'Dashboard' }"
      class="tab-btn"
      :class="{ active: isLive }"
    >
      Live
    </router-link>
    <router-link
      :to="{ name: 'SessionHistory' }"
      class="tab-btn"
      :class="{ active: isHistory }"
    >
      Session History
    </router-link>
    <router-link
      :to="{ name: 'Settings' }"
      class="tab-btn"
      :class="{ active: isSettings }"
    >
      Settings
    </router-link>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const isLive = computed(
  () => !route.path.includes('history') && !route.path.includes('settings')
)
const isHistory = computed(() => route.path.includes('history'))
const isSettings = computed(() => route.path.includes('settings'))
</script>
