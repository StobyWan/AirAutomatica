<template>
  <component
    :is="tag"
    :type="tag === 'button' ? 'button' : undefined"
    :class="buttonClass"
    :disabled="disabled"
    v-bind="$attrs"
  >
    <slot />
  </component>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
    size?: 'sm' | 'md'
    disabled?: boolean
    tag?: 'button' | 'a'
  }>(),
  {
    variant: 'secondary',
    size: 'md',
    disabled: false,
    tag: 'button',
  }
)

const baseClass = 'rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed'

const variantClass: Record<string, string> = {
  primary: 'bg-cyan-600 hover:bg-cyan-500 text-white',
  secondary: 'bg-slate-600 hover:bg-slate-500 text-white',
  danger: 'bg-red-600 hover:bg-red-500 text-white',
  ghost: 'bg-transparent hover:bg-slate-600/50 text-slate-200',
}

const sizeClass: Record<string, string> = {
  sm: 'px-2 py-1 text-xs',
  md: 'px-4 py-2 text-sm',
}

const buttonClass = computed(
  () => `${baseClass} ${variantClass[props.variant]} ${sizeClass[props.size]}`
)
</script>
