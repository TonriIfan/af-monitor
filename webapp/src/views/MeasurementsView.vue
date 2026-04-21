<template>
  <div class="wa-page">
    <div class="wa-page-title">测量记录</div>

    <div class="wa-card">
      <div class="wa-row-between">
        <div>
          <div class="wa-card__title">最近 7 天心率趋势</div>
          <div class="wa-muted" style="font-size: 12px;">共 {{ chartPointCount }} 条测量</div>
        </div>
        <el-button size="small" :loading="loadingChart" @click="loadChart">刷新</el-button>
      </div>
      <div ref="chartRef" class="chart" />
      <div v-if="!loadingChart && chartPointCount === 0" class="wa-empty">
        暂无测量数据。到“设备”页面连接戒指后开始采集。
      </div>
    </div>

    <div class="wa-row-between" style="margin: 10px 0 6px;">
      <div class="wa-section-title" style="margin: 0;">测量列表</div>
      <el-button size="small" :loading="loading" @click="loadMeasurements">刷新</el-button>
    </div>

    <div v-if="!loading && !measurements.length" class="wa-card wa-empty">
      暂无记录。
    </div>

    <div v-for="m in measurements" :key="m.id" class="wa-card measurement">
      <div class="wa-row-between">
        <div>
          <div class="measurement__hr">
            <span v-if="m.parsed?.heartRate">{{ m.parsed.heartRate }}<span class="measurement__unit">次/分钟</span></span>
            <span v-else-if="m.parsed?.oxygen">{{ m.parsed.oxygen }}<span class="measurement__unit">%</span></span>
            <span v-else class="wa-muted" style="font-size: 16px;">{{ packetKindLabel(m.packet_kind) }}</span>
          </div>
          <div class="wa-muted" style="font-size: 12px;">
            {{ formatDateTime(m.measured_at) }}
          </div>
        </div>
        <el-tag :type="riskTagType(m.analysis?.risk_level)">
          {{ riskLabel(m.analysis?.risk_level) }}
        </el-tag>
      </div>
      <div v-if="m.analysis?.summary" class="measurement__summary wa-muted">
        {{ m.analysis.summary }}
      </div>
      <div v-if="m.parsed" class="measurement__fields">
        <span v-if="m.parsed.heartRate != null"><b>心率</b> {{ m.parsed.heartRate }} 次/分钟</span>
        <span v-if="m.parsed.hrv != null"><b>心率变异性</b> {{ m.parsed.hrv }}</span>
        <span v-if="m.parsed.oxygen != null"><b>血氧饱和度</b> {{ m.parsed.oxygen }}%</span>
        <span v-if="m.parsed.temperature != null"><b>体表温度</b> {{ m.parsed.temperature }}℃</span>
        <span v-if="m.parsed.wearStatusText"><b>佩戴状态</b> {{ m.parsed.wearStatusText }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

import { api } from '../utils/api'
import { formatDateTime, riskLabel, riskTagType } from '../utils/format'

echarts.use([LineChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer])

type MeasurementItem = {
  id: number
  device_id: string
  measured_at: string
  packet_kind: string
  parsed?: {
    heartRate?: number | null
    hrv?: number | null
    oxygen?: number | null
    temperature?: number | null
    wearStatusText?: string | null
  }
  analysis?: {
    risk_level?: string | null
    summary?: string | null
  } | null
}

type ChartResponse = {
  metric: string
  range: string
  points?: Array<{ time?: string; value?: number; measured_at?: string }>
}

const measurements = ref<MeasurementItem[]>([])
const loading = ref(false)
const loadingChart = ref(false)
const chartRef = ref<HTMLDivElement | null>(null)
const chartPointCount = ref(0)
let chart: echarts.ECharts | null = null

async function loadMeasurements() {
  loading.value = true
  try {
    const { data } = await api.get<MeasurementItem[]>('/measurements')
    const arr = Array.isArray(data) ? data : []
    measurements.value = arr.slice(0, 60)
  } catch {
    measurements.value = []
  } finally {
    loading.value = false
  }
}

async function loadChart() {
  loadingChart.value = true
  try {
    const { data } = await api.get<ChartResponse>('/measurements/chart', {
      // 后端接受 snake_case 的 metric 名：heart_rate / oxygen / temperature
      params: { metric: 'heart_rate', range: '7d' },
    })
    const points = data.points ?? []
    chartPointCount.value = points.length
    renderChart(points)
  } catch {
    chartPointCount.value = 0
    renderChart([])
  } finally {
    loadingChart.value = false
  }
}

function renderChart(points: Array<{ time?: string; value?: number; measured_at?: string }>) {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  const items = points
    .map((p) => ({ t: p.time || p.measured_at || '', v: p.value }))
    .filter((p) => p.t && typeof p.v === 'number')
  chart.setOption({
    grid: { left: 36, right: 10, top: 24, bottom: 24 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'time',
      axisLabel: { fontSize: 11, color: '#9ca3af' },
      axisLine: { lineStyle: { color: '#d1d5db' } },
    },
    yAxis: {
      type: 'value',
      name: '次/分钟',
      nameTextStyle: { color: '#9ca3af', fontSize: 11 },
      axisLabel: { fontSize: 11, color: '#9ca3af' },
      splitLine: { lineStyle: { color: 'rgba(156,163,175,0.18)' } },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        showSymbol: false,
        itemStyle: { color: '#2b6cb0' },
        lineStyle: { color: '#2b6cb0', width: 2 },
        areaStyle: { color: 'rgba(43, 108, 176, 0.12)' },
        data: items.map((p) => [p.t, p.v]),
      },
    ],
  })
}

function packetKindLabel(kind: string) {
  const map: Record<string, string> = {
    heart_rate: '心率测量',
    blood_oxygen: '血氧测量',
    blood_oxygen_complete: '血氧采集完成',
    temperature: '体温测量',
    battery: '电量信息',
    battery_state: '充电状态',
    time_sync: '时间同步',
    device_time: '设备时间',
    unsupported: '暂不支持的数据',
    invalid: '无效数据',
    unknown: '未知数据',
  }
  return map[kind] || kind || '--'
}

const handleResize = () => chart?.resize()

onMounted(async () => {
  await loadMeasurements()
  await nextTick()
  await loadChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})

</script>

<style scoped>
.chart {
  width: 100%;
  height: 220px;
  margin-top: 10px;
}
.measurement__hr {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.1;
}
.measurement__unit {
  font-size: 13px;
  color: var(--wa-fg-muted);
  font-weight: 500;
  margin-left: 4px;
}
.measurement__summary {
  font-size: 12.5px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--wa-border);
}
.measurement__fields {
  margin-top: 6px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12.5px;
}
.measurement__fields b {
  color: var(--wa-fg-muted);
  font-weight: 500;
  margin-right: 2px;
}
</style>
