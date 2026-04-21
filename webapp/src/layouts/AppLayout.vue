<template>
  <div class="wa-layout">
    <RouterView v-slot="{ Component }">
      <component :is="Component" />
    </RouterView>
    <nav class="wa-tabbar">
      <RouterLink
        v-for="item in tabs.slice(0, 2)"
        :key="item.name"
        :to="item.to"
        class="wa-tab"
        :class="{ 'wa-tab--active': isActive(item) }"
      >
        <el-icon :size="22">
          <component :is="item.icon" />
        </el-icon>
        <span class="wa-tab__label">{{ item.label }}</span>
      </RouterLink>

      <!-- AI Assistant (Standard Tab Style) -->
      <button
        type="button"
        class="wa-tab"
        :class="{ 'wa-tab--active': ai.isOpen }"
        @click="ai.open()"
      >
        <el-icon :size="22"><MagicStick /></el-icon>
        <span class="wa-tab__label">AI 助手</span>
      </button>

      <RouterLink
        v-for="item in tabs.slice(2)"
        :key="item.name"
        :to="item.to"
        class="wa-tab"
        :class="{ 'wa-tab--active': isActive(item) }"
      >
        <el-icon :size="22">
          <component :is="item.icon" />
        </el-icon>
        <span class="wa-tab__label">{{ item.label }}</span>
      </RouterLink>
    </nav>
    <AiChatDrawer />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { MagicStick } from '@element-plus/icons-vue'

import { useBleStore } from '../stores/ble'
import { useAiStore } from '../stores/ai'
import AiChatDrawer from '../components/AiChatDrawer.vue'

type TabItem = {
  name: string
  label: string
  to: string
  icon: string
  match: string[]
}

const tabs: TabItem[] = [
  { name: 'home', label: '首页', to: '/home', icon: 'HomeFilled', match: ['/home', '/'] },
  { name: 'device', label: '设备', to: '/device', icon: 'Connection', match: ['/device'] },
  { name: 'measurements', label: '测量', to: '/measurements', icon: 'DataLine', match: ['/measurements'] },
  { name: 'alerts', label: '告警', to: '/alerts', icon: 'Bell', match: ['/alerts'] },
  { name: 'profile', label: '我的', to: '/profile', icon: 'User', match: ['/profile'] },
]

const route = useRoute()
const ble = useBleStore()
const ai = useAiStore()

const currentPath = computed(() => route.path)

function isActive(item: TabItem) {
  return item.match.some((m) => currentPath.value === m || currentPath.value.startsWith(`${m}/`))
}

onMounted(() => {
  // 挂载即订阅 BLE 事件，避免跨页切换时丢状态
  ble.ensureSubscribed()
})
</script>

<style scoped>
.wa-layout {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
}
.wa-tabbar {
  position: fixed;
  left: 50%;
  bottom: 0;
  transform: translateX(-50%);
  width: 100%;
  max-width: 720px;
  height: var(--wa-tab-height);
  background: var(--wa-surface);
  border-top: 1px solid var(--wa-border);
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  padding-bottom: env(safe-area-inset-bottom);
  z-index: 10;
}
.wa-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  color: var(--wa-fg-muted);
  font-size: 12px;
  padding: 6px 0;
  transition: color 0.15s ease;
  background: transparent;
  border: none;
  cursor: pointer;
}
.wa-tab:hover {
  color: var(--wa-fg);
}
.wa-tab--active {
  color: var(--wa-accent);
}
.wa-tab__label {
  font-size: 11px;
  line-height: 1.2;
}
</style>
