<template>
  <div class="console-shell">
    <aside class="console-sidebar">
      <div class="brand-block">
        <p class="brand-block__eyebrow">HEARTGUARD</p>
        <h2>心脏卫士</h2>
      </div>

      <el-menu :default-active="route.path" class="console-nav" router>
        <el-menu-item v-if="auth.user?.role === 'admin'" index="/accounts">
          <span>账号管理</span>
        </el-menu-item>
        <el-menu-item v-if="auth.user?.role === 'admin'" index="/ai-settings">
          <span>AI 策略设置</span>
        </el-menu-item>
        <el-menu-item v-if="auth.user?.role === 'admin'" index="/ai-lab">
          <span>AI 评估实验室</span>
        </el-menu-item>
        <el-menu-item v-if="auth.user?.role === 'admin'" index="/dashboard">
          <span>监测态势总览</span>
        </el-menu-item>
        <el-menu-item index="/devices">
          <span>设备编排管理</span>
        </el-menu-item>
        <el-menu-item index="/measurements">
          <span>实时测量明细</span>
        </el-menu-item>
        <el-menu-item index="/alerts">
          <span>系统告警中心</span>
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
          <p class="console-topbar__eyebrow">CARDIAC HEALTH MONITORING</p>
          <h2>{{ title }}</h2>
        </div>
        <div class="console-topbar__actions">
          <el-select
            v-if="auth.user?.role === 'admin'"
            :model-value="management.selectedUserId"
            class="scope-select"
            clearable
            placeholder="查看全部用户"
            @change="handleScopeChange"
          >
            <el-option label="全部用户" value="" />
            <el-option
              v-for="item in scopeUsers"
              :key="item.id"
              :label="`${item.username} · ${item.device_count}台设备`"
              :value="String(item.id)"
            />
          </el-select>
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
import { useManagementStore } from '../stores/management'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const management = useManagementStore()
const scopeUsers = computed(() => management.users.filter((item) => item.role !== 'admin'))

const title = computed(() => {
  const map: Record<string, string> = {
    '/dashboard': '监测总览',
    '/accounts': '账号管理',
    '/ai-settings': 'AI 设置',
    '/devices': '设备编排',
    '/measurements': '测量明细',
    '/alerts': '告警中心',
  }
  return map[route.path] || '控制台'
})

function handleLogout() {
  auth.logout()
  management.reset()
  router.push('/login')
}

if (auth.user?.role === 'admin') {
  management.loadUsers().catch(() => undefined)
}

function handleScopeChange(value: string) {
  management.setSelectedUserId(value || '')
}
</script>
