<template>
  <div v-if="error" class="min-h-[200px] flex flex-col items-center justify-center p-8">
    <div class="rounded-xl bg-red-950/30 border border-red-900/50 p-6 max-w-md text-center">
      <h2 class="text-lg font-semibold text-red-200 mb-2">Something went wrong</h2>
      <p class="text-sm text-red-200/90 mb-4">{{ error.message }}</p>
      <button
        type="button"
        class="px-4 py-2 rounded-lg bg-slate-600 hover:bg-slate-500 text-white text-sm font-medium"
        @click="retry"
      >
        Try again
      </button>
    </div>
  </div>
  <template v-else>
    <slot />
  </template>
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'

const error = ref<Error | null>(null)

onErrorCaptured((err) => {
  error.value = err instanceof Error ? err : new Error(String(err))
  return false
})

function retry() {
  error.value = null
}
</script>
