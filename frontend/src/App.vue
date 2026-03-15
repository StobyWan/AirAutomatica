<template>
  <div class="min-h-screen bg-bg text-[var(--text)] font-sans">
    <ErrorBoundary>
      <RouterView />
    </ErrorBoundary>
  </div>
</template>

<script setup lang="ts">
import ErrorBoundary from '@/components/ErrorBoundary.vue'
</script>
