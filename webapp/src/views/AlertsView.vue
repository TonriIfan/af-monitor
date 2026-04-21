<template>
  <div class="wa-page">
    <div class="wa-row-between">
      <div class="wa-page-title">告警</div>
      <el-button
        size="small"
        :disabled="!unreadItems.length"
        :loading="markingAll"
        @click="markAllRead"
      >
        全部已读
      </el-button>
    </div>

    <div v-if="loading" class="wa-card wa-empty">加载中...</div>
    <div v-else-if="!alerts.length" class="wa-card wa-empty">暂无告警，一切正常。</div>

    <div
      v-for="item in alerts"
      :key="item.id"
      class="wa-card alert"
      :class="[`alert--${item.level}`, { 'alert--read': item.status === 'read' }]"
    >
      <div class="wa-row-between">
        <div>
          <el-tag :type="levelTag(item.level)" size="small">{{ levelLabel(item.level) }}</el-tag>
          <span class="wa-muted" style="font-size: 12px; margin-left: 8px;">
            {{ formatDateTime(item.created_at) }}
          </span>
        </div>
        <el-tag v-if="item.status === 'unread'" size="small">未读</el-tag>
        <el-tag v-else type="info" size="small">已读</el-tag>
      </div>
      <div class="alert__title">{{ item.title || '异常告警' }}</div>
      <div class="alert__summary wa-muted">{{ item.message || '--' }}</div>
      <div v-if="triggerText(item)" class="alert__triggers wa-muted">
        触发：{{ triggerText(item) }}
      </div>
      <div v-if="item.device_id" class="wa-muted" style="font-size: 12px;">
        设备：<code>{{ item.device_id }}</code>
      </div>
      <div class="wa-row" style="margin-top: 10px; justify-content: flex-end;">
        <el-button v-if="item.status === 'unread'" size="small" @click="markRead(item)">标记已读</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { api } from '../utils/api'
import { formatDateTime } from '../utils/format'
import { useAlertsStore } from '../stores/alerts'

type AlertItem = {
  id: number
  title?: string
  level: 'low' | 'moderate' | 'high' | 'critical' | string
  status: 'unread' | 'read' | string
  created_at: string
  message?: string
  trigger_codes?: string[]
  trigger_labels?: string[]
  device_id?: string
}

const alerts = ref<AlertItem[]>([])
const loading = ref(false)
const markingAll = ref(false)
const alertStream = useAlertsStore()

const unreadItems = computed(() => alerts.value.filter((a) => a.status === 'unread'))

async function load() {
  loading.value = true
  try {
    const { data } = await api.get<AlertItem[]>('/alerts')
    alerts.value = Array.isArray(data) ? data : []
  } catch {
    alerts.value = []
  } finally {
    loading.value = false
  }
}

async function markRead(item: AlertItem) {
  try {
    await api.post(`/alerts/${item.id}/read`)
    item.status = 'read'
    void alertStream.loadUnreadSnapshot()
    ElMessage.success('已标记为已读')
  } catch (err: unknown) {
    const msg =
      (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      (err instanceof Error ? err.message : '操作失败')
    ElMessage.error(msg)
  }
}

async function markAllRead() {
  markingAll.value = true
  try {
    await api.post('/alerts/read-all')
    alerts.value.forEach((a) => (a.status = 'read'))
    void alertStream.loadUnreadSnapshot()
    ElMessage.success('已全部标记为已读')
  } catch (err: unknown) {
    const msg =
      (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      (err instanceof Error ? err.message : '操作失败')
    ElMessage.error(msg)
  } finally {
    markingAll.value = false
  }
}

function levelLabel(level: string) {
  return {
    low: '低',
    moderate: '中',
    high: '高',
    critical: '极高',
  }[level] || level
}

function levelTag(level: string): '' | 'success' | 'warning' | 'danger' | 'info' {
  return ({
    low: 'success',
    moderate: 'warning',
    high: 'danger',
    critical: 'danger',
  } as const)[level as 'low' | 'moderate' | 'high' | 'critical'] || 'info'
}

function triggerText(item: AlertItem) {
  const labels = item.trigger_labels?.length ? item.trigger_labels : item.trigger_codes
  return labels?.length ? labels.join('、') : ''
}

onMounted(load)
watch(
  () => alertStream.latestAlert?.id,
  (nextId, prevId) => {
    if (nextId && nextId !== prevId) {
      void load()
    }
  },
)
</script>

<style scoped>
.alert__title {
  font-weight: 600;
  margin: 8px 0 4px;
}
.alert__summary {
  font-size: 13px;
  line-height: 1.55;
  margin-bottom: 6px;
}
.alert__triggers {
  font-size: 12px;
  margin-bottom: 6px;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  word-break: break-all;
}
.alert--read {
  opacity: 0.75;
}
.alert--critical {
  border-left: 3px solid var(--wa-danger);
}
.alert--high {
  border-left: 3px solid var(--wa-danger);
}
.alert--moderate {
  border-left: 3px solid var(--wa-warning);
}
.alert--low {
  border-left: 3px solid var(--wa-success);
}
</style>
