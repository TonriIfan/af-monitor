<template>
  <div class="console-shell">
    <aside class="console-sidebar">
      <div class="brand-block">
        <p class="brand-block__eyebrow">YF MONITOR</p>
        <h1>Rhythm Console</h1>
        <p class="brand-block__copy">面向毕设演示的一体化监测后台，聚焦设备、告警与节律趋势。</p>
      </div>

      <el-menu :default-active="route.path" class="console-nav" router>
        <el-menu-item index="/dashboard">
          <el-icon><DataBoard /></el-icon>
          <span>总览</span>
        </el-menu-item>
        <el-menu-item index="/devices">
          <el-icon><Cpu /></el-icon>
          <span>设备</span>
        </el-menu-item>
        <el-menu-item index="/measurements">
          <el-icon><TrendCharts /></el-icon>
          <span>测量</span>
        </el-menu-item>
        <el-menu-item index="/alerts">
          <el-icon><Bell /></el-icon>
          <span>告警</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div>
          <p class="sidebar-footer__label">当前用户</p>
          <strong>{{ auth.user?.username }}</strong>
        </div>
        <el-button text @click="handleLogout">退出</el-button>
      </div>
    </aside>

    <main class="console-main">
      <header class="console-topbar">
        <div>
          <p class="console-topbar__eyebrow">AF RISK SCREENING</p>
          <h2>{{ title }}</h2>
        </div>
        <div class="console-topbar__actions">
          <el-tag type="warning" effect="dark">原始 JSON 保持不变</el-tag>
        </div>
      </header>

      <section class="console-content">
        <RouterView />
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const title = computed(() => {
  const map: Record<string, string> = {
    '/dashboard': '监测总览',
    '/devices': '设备编排',
    '/measurements': '测量明细',
    '/alerts': '告警中心',
  }
  return map[route.path] || '控制台'
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>
