<template>
  <article class="stat-card">
    <div class="stat-card__header">
      <p>{{ eyebrow }}</p>
      <el-icon><component :is="icon" /></el-icon>
    </div>
    <div class="stat-card__value">{{ value }}</div>
    <p class="stat-card__hint">{{ hint }}</p>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  eyebrow: string
  value: string | number
  hint: string
  icon: string
}>()
</script>
