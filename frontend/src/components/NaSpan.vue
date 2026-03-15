<template>
  <span :class="{ na: result.na }">{{ result.text }}</span>
</template>

<script setup lang="ts">
import type { FmtResult } from '@/utils/formatters'

defineProps<{
  result: FmtResult
}>()
</script>
