<template>
  <svg
    class="animate-spin"
    :class="[sizeClass[props.size], colorClass[props.color], { 'mx-auto': props.center }]"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    aria-hidden="true"
  >
    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
    <path
      class="opacity-75"
      fill="currentColor"
      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
    />
  </svg>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    size?: 'sm' | 'md' | 'lg'
    color?: 'cyan' | 'slate'
    center?: boolean
  }>(),
  {
    size: 'md',
    color: 'cyan',
    center: false,
  }
)

const sizeClass: Record<string, string> = {
  sm: 'h-4 w-4',
  md: 'h-5 w-5',
  lg: 'h-6 w-6',
}

const colorClass: Record<string, string> = {
  cyan: 'text-cyan-500',
  slate: 'text-slate-500',
}
</script>
