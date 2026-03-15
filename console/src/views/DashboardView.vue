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
      <article class="panel" v-if="auth.user?.role === 'admin'">
        <div class="panel__header">
          <div>
            <p class="section-eyebrow">Account overview</p>
            <h3>账号总览</h3>
          </div>
        </div>
        <p class="panel__helper">地图会根据最近登录 IP 的地理信息落点，统计用户在全国范围内的分布。</p>
        <div class="account-overview-layout">
          <ChinaLoginMap :users="overview.user_summaries" />
          <div class="account-overview-table">
            <el-table :data="provinceDistribution" stripe>
              <el-table-column prop="province" label="省级行政区" min-width="160" />
              <el-table-column prop="user_count" label="用户数" min-width="90" />
              <el-table-column prop="admin_count" label="管理员" min-width="90" />
              <el-table-column prop="device_count" label="设备数" min-width="90" />
              <el-table-column prop="measurement_count" label="测量数" min-width="100" />
              <el-table-column prop="unread_alert_count" label="未读告警" min-width="100" />
            </el-table>
          </div>
        </div>
      </article>

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

import ChinaLoginMap from '../components/ChinaLoginMap.vue'
import RiskBar from '../components/RiskBar.vue'
import StatCard from '../components/StatCard.vue'
import { useAuthStore } from '../stores/auth'
import { type ManagedUser, useManagementStore } from '../stores/management'
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
  user_summaries: [] as ManagedUser[],
  risk_distribution: [] as Array<{ risk_level: string; total: number }>,
  latest_measurements: [] as Array<Record<string, any>>,
  latest_alerts: [] as Array<Record<string, any>>,
})

const maxRiskTotal = computed(() =>
  overview.risk_distribution.reduce((max, item) => Math.max(max, item.total), 0),
)

const provinceAliases: Record<string, string> = {
  Beijing: '北京市',
  Tianjin: '天津市',
  Shanghai: '上海市',
  Chongqing: '重庆市',
  Hebei: '河北省',
  Shanxi: '山西省',
  'Inner Mongolia': '内蒙古自治区',
  Liaoning: '辽宁省',
  Jilin: '吉林省',
  Heilongjiang: '黑龙江省',
  Jiangsu: '江苏省',
  Zhejiang: '浙江省',
  Anhui: '安徽省',
  Fujian: '福建省',
  Jiangxi: '江西省',
  Shandong: '山东省',
  Henan: '河南省',
  Hubei: '湖北省',
  Hunan: '湖南省',
  Guangdong: '广东省',
  Guangxi: '广西壮族自治区',
  Hainan: '海南省',
  Sichuan: '四川省',
  Guizhou: '贵州省',
  Yunnan: '云南省',
  Xizang: '西藏自治区',
  Tibet: '西藏自治区',
  Shaanxi: '陕西省',
  Gansu: '甘肃省',
  Qinghai: '青海省',
  Ningxia: '宁夏回族自治区',
  Xinjiang: '新疆维吾尔自治区',
  HongKong: '香港特别行政区',
  'Hong Kong': '香港特别行政区',
  Macau: '澳门特别行政区',
  Taiwan: '台湾省',
}

function normalizeProvince(region?: string, country?: string) {
  const raw = (region || '').trim()
  if (!raw) {
    return country === 'China' || country === '中国' ? '境内未识别' : '未解析'
  }
  if (provinceAliases[raw]) return provinceAliases[raw]
  if (raw.endsWith('省') || raw.endsWith('市') || raw.endsWith('自治区') || raw.endsWith('特别行政区')) {
    return raw
  }
  return raw
}

const provinceDistribution = computed(() => {
  const grouped = new Map<
    string,
    {
      province: string
      user_count: number
      admin_count: number
      device_count: number
      measurement_count: number
      unread_alert_count: number
    }
  >()

  for (const user of overview.user_summaries) {
    const province = normalizeProvince(user.last_login_location?.region, user.last_login_location?.country)
    const entry = grouped.get(province) || {
      province,
      user_count: 0,
      admin_count: 0,
      device_count: 0,
      measurement_count: 0,
      unread_alert_count: 0,
    }
    entry.user_count += 1
    entry.admin_count += user.role === 'admin' ? 1 : 0
    entry.device_count += user.device_count
    entry.measurement_count += user.measurement_count
    entry.unread_alert_count += user.unread_alert_count
    grouped.set(province, entry)
  }

  return Array.from(grouped.values()).sort((a, b) => {
    if (b.user_count !== a.user_count) return b.user_count - a.user_count
    return a.province.localeCompare(b.province, 'zh-CN')
  })
})

const scopeTitle = computed(() => {
  if (auth.user?.role !== 'admin') return '当前账号总览'
  return management.selectedUser ? `正在查看 ${management.selectedUser.username} 的账号态势` : '正在查看全部账号态势'
})

const scopeDescription = computed(() => {
  if (auth.user?.role !== 'admin') return '当前页只展示你自己的设备、测量和告警数据。'
  return management.selectedUser
    ? '下方所有统计、最新测量和最新告警，都已经切换到该账号的上下文。'
    : '当前页展示所有账号汇总后的总体情况，适合管理员做全局巡检。'
})

async function loadOverview() {
  try {
    const { data } = await api.get('/dashboard/overview', {
      params: auth.user?.role === 'admin' ? management.scopeParams() : {},
    })
    Object.assign(overview, data)
  } catch {
    ElMessage.error('总览数据加载失败。')
  }
}

onMounted(loadOverview)
watch(() => management.selectedUserId, loadOverview)
</script>
