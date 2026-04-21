<template>
  <div class="page-grid">
    <article class="panel">
      <div class="panel__header">
        <div>
          <p class="section-eyebrow">Alert center</p>
          <h3>告警中心</h3>
        </div>
        <el-button @click="loadAlerts">刷新</el-button>
      </div>
      <p class="panel__helper" v-if="auth.user?.role === 'admin'">
        当前视角：{{ management.selectedUser ? `${management.selectedUser.username} 的告警` : '全部用户告警' }}
      </p>

      <el-table :data="alerts" stripe>
        <el-table-column v-if="auth.user?.role === 'admin'" label="用户" min-width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="focusUser(row.user_id, row.username)">
              {{ row.username || '--' }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="device_id" label="设备" min-width="130" />
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column label="等级" min-width="120">
          <template #default="{ row }">
            <el-tag :type="riskTagType(row.level)">{{ riskLabel(row.level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="说明" min-width="280" />
        <el-table-column label="触发规则" min-width="220">
          <template #default="{ row }">
            {{ (row.trigger_labels || row.trigger_codes)?.join('、') || '--' }}
          </template>
        </el-table-column>
        <el-table-column label="时间" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="状态" min-width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_read ? 'info' : 'warning'">{{ row.is_read ? '已读' : '未读' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="推送状态" min-width="220">
          <template #default="{ row }">
            <el-tag :type="pushStatusTagType(row.push_delivery_summary?.status)">
              {{ row.push_delivery_summary?.status_label || '未入队' }}
            </el-tag>
            <div v-if="row.push_delivery_summary?.latest_error" class="table-helper">
              {{ row.push_delivery_summary.latest_error }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="140" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.is_read" link type="primary" @click="markRead(row.id)">标记已读</el-button>
            <span v-else>已处理</span>
          </template>
        </el-table-column>
      </el-table>
    </article>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'
import { useManagementStore } from '../stores/management'
import { api } from '../utils/api'
import { formatDateTime, riskLabel, riskTagType } from '../utils/format'

const auth = useAuthStore()
const management = useManagementStore()
const alerts = ref<Array<Record<string, any>>>([])

function pushStatusTagType(status?: string) {
  if (status === 'sent') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'pending') return 'warning'
  return 'info'
}

function focusUser(userId?: number, username?: string) {
  if (!userId) return
  management.setSelectedUserId(String(userId))
  ElMessage.success(`已切换到 ${username || '该用户'} 的告警视角。`)
}

async function loadAlerts() {
  try {
    const { data } = await api.get('/alerts', {
      params: auth.user?.role === 'admin' ? management.scopeParams() : {},
    })
    alerts.value = data
  } catch {
    ElMessage.error('告警列表加载失败。')
  }
}

async function markRead(id: number) {
  try {
    await api.post(`/alerts/${id}/read`, {})
    ElMessage.success('已标记为已读。')
    await loadAlerts()
  } catch {
    ElMessage.error('告警状态更新失败。')
  }
}

onMounted(loadAlerts)
watch(() => management.selectedUserId, loadAlerts)
</script>
