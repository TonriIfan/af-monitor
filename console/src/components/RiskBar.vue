<template>
  <div class="risk-bar">
    <div class="risk-bar__meta">
      <span>{{ label }}</span>
      <strong>{{ total }}</strong>
    </div>
    <div class="risk-bar__track">
      <div class="risk-bar__fill" :style="{ width: `${width}%` }"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  total: number
  max: number
}>()

const width = computed(() => {
  if (!props.max) return 0
  return Math.max(8, (props.total / props.max) * 100)
})
</script>
