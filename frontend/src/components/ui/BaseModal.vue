<template>
  <div
    v-if="modelValue"
    class="fixed inset-0 z-50 overflow-y-auto"
    role="dialog"
    aria-modal="true"
  >
    <div class="flex min-h-screen items-center justify-center p-4">
      <div
        class="fixed inset-0 bg-black/60"
        aria-hidden="true"
        @click="$emit('update:modelValue', false)"
      />
      <div
        class="relative rounded-xl bg-slate-800 border border-slate-700 p-6 shadow-xl w-full"
        :class="sizeClass"
      >
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    modelValue: boolean
    size?: 'sm' | 'md'
  }>(),
  { size: 'md' }
)

defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const sizeClass = props.size === 'sm' ? 'max-w-sm' : 'max-w-md'
</script>
