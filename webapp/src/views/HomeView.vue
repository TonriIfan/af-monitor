<template>
  <div class="wa-page">
    <div class="home-greeting">
      <div class="home-greeting__hello">{{ greeting }}</div>
      <div class="home-greeting__name">{{ auth.user?.username || '用户' }}</div>
    </div>

    <div class="wa-card home-hr">
      <div class="wa-row-between">
        <div>
          <div class="wa-section-title" style="margin: 0 0 4px;">Heart rate · 心率</div>
          <div class="wa-stat">
            {{ heartRate ?? '--' }}
            <span class="wa-stat__unit">bpm</span>
          </div>
          <div class="wa-muted" style="font-size: 12px;">
            <span v-if="latest?.measured_at">最近测量：{{ formatDateTime(latest.measured_at) }}</span>
            <span v-else>暂无测量数据</span>
          </div>
        </div>
        <div class="home-hr__risk">
          <el-tag :type="riskTagType(latestRisk)" size="large" round>
            {{ riskLabel(latestRisk) }}
          </el-tag>
        </div>
      </div>
    </div>

    <div class="wa-card home-ble">
      <div class="wa-row-between">
        <div>
          <div class="wa-card__title">戒指连接</div>
          <div class="wa-muted" style="font-size: 12.5px;">
            <span :style="{ color: stateColor }">●</span>
            {{ stateLabel }}
            <span v-if="ble.device" style="margin-left: 6px;">{{ ble.device.name }}</span>
          </div>
        </div>
        <RouterLink to="/device">
          <el-button type="primary" :plain="ble.isConnected">
            {{ ble.isConnected ? '管理' : '去连接' }}
          </el-button>
        </RouterLink>
      </div>

      <div v-if="ble.isConnected" class="home-ble__stats">
        <div>
          <div class="wa-muted" style="font-size: 12px;">收包</div>
          <div style="font-weight: 600;">{{ ble.frameCount }}</div>
        </div>
        <div>
          <div class="wa-muted" style="font-size: 12px;">已上报</div>
          <div style="font-weight: 600;">{{ ble.uploadedCount }}</div>
        </div>
        <div>
          <div class="wa-muted" style="font-size: 12px;">最近上报</div>
          <div style="font-weight: 600;">
            {{ ble.lastUploadedAt ? formatTimeShort(new Date(ble.lastUploadedAt).toISOString()) : '--' }}
          </div>
        </div>
      </div>
    </div>

    <div class="wa-grid">
      <RouterLink to="/alerts" class="wa-card home-quick">
        <el-icon :size="22"><Bell /></el-icon>
        <div>
          <div class="wa-muted" style="font-size: 12px;">未读告警</div>
          <div style="font-size: 22px; font-weight: 700;">{{ unreadCount }}</div>
        </div>
      </RouterLink>
      <RouterLink to="/measurements" class="wa-card home-quick">
        <el-icon :size="22"><DataLine /></el-icon>
        <div>
          <div class="wa-muted" style="font-size: 12px;">历史测量</div>
          <div style="font-size: 22px; font-weight: 700;">查看</div>
        </div>
      </RouterLink>
    </div>

    <div class="wa-section-title">健康提示</div>
    <div class="wa-card home-tips">
      <p style="margin: 0 0 6px;">佩戴戒指期间请保持手指安静、避免用力挤压。</p>
      <p style="margin: 0 0 6px;">如出现持续心悸或晕眩症状，请及时就医，本系统仅作日常参考。</p>
      <p style="margin: 0;">蓝牙连接只支持 Chrome / Edge 等浏览器，iOS Safari 暂不支持。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Bell, DataLine } from '@element-plus/icons-vue'

import { api } from '../utils/api'
import { formatDateTime, formatTimeShort, riskLabel, riskTagType } from '../utils/format'
import { useAuthStore } from '../stores/auth'
import { useBleStore } from '../stores/ble'

type LatestMeasurement = {
  id: number
  measured_at: string
  parsed?: { heartRate?: number | null }
  analysis?: { risk_level?: string | null }
}

const auth = useAuthStore()
const ble = useBleStore()

const latest = ref<LatestMeasurement | null>(null)
const unreadCount = ref(0)

const heartRate = computed<number | null>(() => {
  if (ble.lastHeartRate && ble.lastHeartRate > 0) return ble.lastHeartRate
  const hr = latest.value?.parsed?.heartRate
  return typeof hr === 'number' && hr > 0 ? hr : null
})

const latestRisk = computed(() => {
  return ble.lastRiskLevel || latest.value?.analysis?.risk_level || 'unknown'
})

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '深夜好'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const stateLabel = computed(() => {
  switch (ble.state) {
    case 'connected':
      return '已连接'
    case 'connecting':
      return '连接中...'
    case 'disconnected':
      return '已断开'
    case 'error':
      return ble.stateDetail || '连接异常'
    default:
      return '未连接'
  }
})
const stateColor = computed(() => {
  switch (ble.state) {
    case 'connected':
      return 'var(--wa-success)'
    case 'connecting':
      return 'var(--wa-warning)'
    case 'error':
      return 'var(--wa-danger)'
    default:
      return 'var(--wa-fg-muted)'
  }
})

async function loadLatest() {
  try {
    const { data } = await api.get<LatestMeasurement>('/measurements/latest')
    latest.value = data
  } catch {
    latest.value = null
  }
}

async function loadUnread() {
  try {
    const { data } = await api.get<{ unread_count?: number }>('/alerts/unread-count')
    unreadCount.value = data.unread_count ?? 0
  } catch {
    unreadCount.value = 0
  }
}

onMounted(() => {
  loadLatest()
  loadUnread()
})
</script>

<style scoped>
.home-greeting {
  padding: 4px 4px 12px;
}
.home-greeting__hello {
  color: var(--wa-fg-muted);
  font-size: 13px;
}
.home-greeting__name {
  font-size: 22px;
  font-weight: 700;
  margin-top: 2px;
}
.home-hr .wa-stat {
  font-size: 44px;
  margin: 4px 0 6px;
}
.home-hr__risk {
  padding-right: 4px;
}
.home-ble__stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--wa-border);
}
.wa-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 6px;
}
.home-quick {
  display: flex;
  align-items: center;
  gap: 10px;
  color: inherit;
}
.home-quick .el-icon {
  color: var(--wa-accent);
}
.home-ai {
  overflow: hidden;
}
.home-ai__header {
  align-items: flex-start;
  margin-bottom: 12px;
}
.home-ai__suggestions {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  margin: 0 -2px 12px;
  padding: 2px;
  scrollbar-width: none;
}
.home-ai__suggestions::-webkit-scrollbar {
  display: none;
}
.home-ai__chip {
  border: 1px solid var(--wa-border);
  background: var(--wa-surface-soft);
  color: var(--wa-fg);
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 12px;
  white-space: nowrap;
}
.home-ai__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.home-ai__reply,
.home-ai__empty,
.home-ai__error {
  margin-top: 12px;
  border-radius: 12px;
  padding: 12px 14px;
}
.home-ai__reply {
  background: linear-gradient(135deg, var(--wa-accent-soft), rgba(255, 255, 255, 0));
  border: 1px solid color-mix(in srgb, var(--wa-accent) 20%, var(--wa-border));
}
.home-ai__reply-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: var(--wa-fg-muted);
  margin-bottom: 8px;
}
.home-ai__reply-text {
  white-space: pre-wrap;
  line-height: 1.7;
}
.home-ai__empty {
  background: var(--wa-surface-soft);
  color: var(--wa-fg-muted);
  font-size: 13px;
}
.home-ai__error {
  background: color-mix(in srgb, var(--wa-danger) 8%, var(--wa-surface));
  color: var(--wa-danger);
  border: 1px solid color-mix(in srgb, var(--wa-danger) 20%, var(--wa-border));
  font-size: 13px;
}
.home-tips p {
  font-size: 13px;
  color: var(--wa-fg-muted);
}
</style>
