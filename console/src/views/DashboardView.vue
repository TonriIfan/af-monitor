<template>
  <div class="page-grid">
    <section class="hero-panel">
      <div class="hero-panel__copy">
        <p class="section-eyebrow">Management scope</p>
        <h3>{{ scopeTitle }}</h3>
        <p>{{ scopeDescription }}</p>
      </div>
      <div class="hero-panel__chips">
        <el-tag effect="plain">多账号管理</el-tag>
        <el-tag effect="plain">按账号切换数据视角</el-tag>
        <el-tag effect="plain">管理员可查看全局</el-tag>
      </div>
    </section>

    <section class="stats-row">
      <StatCard eyebrow="设备数" :value="overview.counts.devices" hint="当前已绑定设备" icon="Cpu" />
      <StatCard eyebrow="测量数" :value="overview.counts.measurements" hint="累计入库测量" icon="DataLine" />
      <StatCard eyebrow="告警数" :value="overview.counts.alerts" hint="累计风险事件" icon="Bell" />
      <StatCard eyebrow="未读告警" :value="overview.counts.unread_alerts" hint="等待处理的事件" icon="Warning" />
    </section>

    <section class="content-columns">
      <article class="panel">
        <div class="panel__header">
          <div>
            <p class="section-eyebrow">Risk distribution</p>
            <h3>风险等级分布</h3>
          </div>
        </div>
        <div class="risk-stack" v-if="overview.risk_distribution.length">
          <RiskBar
            v-for="item in overview.risk_distribution"
            :key="item.risk_level"
            :label="riskLabel(item.risk_level)"
            :total="item.total"
            :max="maxRiskTotal"
          />
        </div>
        <el-empty v-else description="暂无分布数据" />
      </article>

      <article class="panel">
        <div class="panel__header">
          <div>
            <p class="section-eyebrow">Recent alerts</p>
            <h3>最新告警</h3>
          </div>
        </div>
        <div class="timeline-list" v-if="overview.latest_alerts.length">
          <div v-for="item in overview.latest_alerts" :key="item.id" class="timeline-item">
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.device_id }} · {{ formatDateTime(item.created_at) }}</p>
            </div>
            <el-tag :type="riskTagType(item.level)">{{ riskLabel(item.level) }}</el-tag>
          </div>
        </div>
        <el-empty v-else description="暂无告警" />
      </article>
    </section>

    <article class="panel">
      <div class="panel__header">
        <div>
          <p class="section-eyebrow">Latest measurements</p>
          <h3>最新测量</h3>
        </div>
      </div>
      <el-table :data="overview.latest_measurements" stripe>
        <el-table-column prop="device_id" label="设备" min-width="140" />
        <el-table-column prop="packet_kind" label="类型" min-width="120" />
        <el-table-column label="解析结果" min-width="360">
          <template #default="{ row }">
            <pre class="json-chip">{{ JSON.stringify(row.parsed, null, 2) }}</pre>
          </template>
        </el-table-column>
        <el-table-column label="风险" min-width="120">
          <template #default="{ row }">
            <el-tag :type="riskTagType(row.risk_level)">{{ riskLabel(row.risk_level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.measured_at) }}</template>
        </el-table-column>
      </el-table>
    </article>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'

import RiskBar from '../components/RiskBar.vue'
import StatCard from '../components/StatCard.vue'
import { useAuthStore } from '../stores/auth'
import { useManagementStore } from '../stores/management'
import { api } from '../utils/api'
import { formatDateTime, riskLabel, riskTagType } from '../utils/format'

const auth = useAuthStore()
const management = useManagementStore()
const overview = reactive({
  counts: {
    devices: 0,
    measurements: 0,
    alerts: 0,
    unread_alerts: 0,
  },
  risk_distribution: [] as Array<{ risk_level: string; total: number }>,
  latest_measurements: [] as Array<Record<string, any>>,
  latest_alerts: [] as Array<Record<string, any>>,
})

const maxRiskTotal = computed(() =>
  overview.risk_distribution.reduce((max, item) => Math.max(max, item.total), 0),
)

const scopeTitle = computed(() => {
  if (!auth.user?.is_staff) return '当前账号总览'
  return management.selectedUser ? `正在查看 ${management.selectedUser.username} 的账号态势` : '正在查看全部账号态势'
})

const scopeDescription = computed(() => {
  if (!auth.user?.is_staff) return '当前页只展示你自己的设备、测量和告警数据。'
  return management.selectedUser
    ? '下方所有统计、最新测量和最新告警，都已经切换到该账号的上下文。'
    : '当前页展示所有账号汇总后的总体情况，适合管理员做全局巡检。'
})

async function loadOverview() {
  try {
    const { data } = await api.get('/dashboard/overview', {
      params: auth.user?.is_staff ? management.scopeParams() : {},
    })
    Object.assign(overview, data)
  } catch {
    ElMessage.error('总览数据加载失败。')
  }
}

onMounted(loadOverview)
watch(() => management.selectedUserId, loadOverview)
</script>
