<template>
  <div class="china-map-shell">
    <div ref="chartRef" class="china-map-canvas" />
    <div class="china-map-caption">
      <span>地理位置来自 ipapi.co</span>
      <span>中国底图来自阿里 GeoAtlas</span>
    </div>
    <!-- <div v-if="message" class="china-map-empty">
      <strong>{{ message }}</strong>
      <span>只有公网 IP 才会展示定位，局域网和 127.0.0.1 不会落点。</span>
    </div> -->
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

type LoginLocation = {
  country: string
  region: string
  city: string
  latitude: number | null
  longitude: number | null
  label: string
  resolved: boolean
}

type UserSummary = {
  id: number
  username: string
  role: string
  last_login_ip: string | null
  last_login_location?: LoginLocation
  device_count: number
  measurement_count: number
  unread_alert_count: number
}

const props = defineProps<{
  users: UserSummary[]
}>()

const MAP_NAME = 'yf-monitor-china'
const MAP_URL = 'https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json'

const chartRef = ref<HTMLDivElement | null>(null)
const message = ref('')
const locatedUsers = computed(() =>
  props.users.filter(
    (user) =>
      user.last_login_location?.resolved &&
      user.last_login_location.latitude !== null &&
      user.last_login_location.longitude !== null,
  ),
)

let chart: echarts.ECharts | null = null
let mapReady = false
let resizeObserver: ResizeObserver | null = null

async function ensureMapLoaded() {
  if (mapReady) return
  const response = await fetch(MAP_URL)
  if (!response.ok) {
    throw new Error('map-load-failed')
  }
  const geoJson = await response.json()
  echarts.registerMap(MAP_NAME, geoJson)
  mapReady = true
}

function seriesData() {
  return locatedUsers.value.map((user) => ({
    name: user.username,
    value: [
      user.last_login_location!.longitude,
      user.last_login_location!.latitude,
      Math.max(user.unread_alert_count, 1),
    ],
    ip: user.last_login_ip || '--',
    locationLabel: user.last_login_location?.label || '未解析',
    deviceCount: user.device_count,
    measurementCount: user.measurement_count,
    alertCount: user.unread_alert_count,
  }))
}

async function renderChart() {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  try {
    await ensureMapLoaded()
    const dots = seriesData()
    message.value = dots.length ? '' : '当前没有可展示的公网登录位置'

    chart.setOption(
      {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'item',
          formatter: (params: any) => {
            const data = params.data
            if (!data) return ''
            return [
              `<strong>${data.name}</strong>`,
              `位置：${data.locationLabel}`,
              `IP：${data.ip}`,
              `设备：${data.deviceCount}`,
              `测量：${data.measurementCount}`,
              `未读告警：${data.alertCount}`,
            ].join('<br />')
          },
        },
        geo: {
          map: MAP_NAME,
          roam: true,
          zoom: 1.12,
          itemStyle: {
            areaColor: '#f6dfca',
            borderColor: '#9e5f3f',
            borderWidth: 1.1,
          },
          emphasis: {
            itemStyle: {
              areaColor: '#efc49f',
            },
          },
          select: {
            disabled: true,
          },
        },
        series: [
          {
            type: 'effectScatter',
            coordinateSystem: 'geo',
            rippleEffect: {
              scale: 5,
              brushType: 'stroke',
            },
            symbolSize: (value: number[]) => Math.min(18, 10 + value[2] * 2),
            itemStyle: {
              color: '#b5482d',
              shadowBlur: 20,
              shadowColor: 'rgba(181, 72, 45, 0.35)',
            },
            label: {
              show: true,
              position: 'right',
              formatter: '{b}',
              color: '#5e2b1f',
              fontWeight: 700,
              fontSize: 12,
            },
            data: dots,
          },
        ],
      },
      true,
    )
  } catch {
    message.value = '中国地图底图加载失败'
    chart?.clear()
  }
}

onMounted(() => {
  renderChart()
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => {
      chart?.resize()
    })
    resizeObserver.observe(chartRef.value)
  }
})

watch(
  () => props.users,
  () => {
    renderChart()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
  chart = null
})
</script>
