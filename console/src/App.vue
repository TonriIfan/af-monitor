<template>
  <div class="app-shell">
    <main class="app-view">
      <RouterView />
    </main>
    <footer class="app-footer">
      <p>
        <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">
          蜀ICP备2025174048号-2
        </a>
      </p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>
