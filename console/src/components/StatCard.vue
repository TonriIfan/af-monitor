<template>
  <article class="stat-card">
    <p class="section-eyebrow">{{ eyebrow }}</p>
    <div class="stat-card__value">{{ value }}</div>
    <p class="stat-card__hint">{{ hint }}</p>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  eyebrow: string
  value: string | number
  hint: string
  icon: string // Kept for prop compatibility but unused in template
}>()
</script>
