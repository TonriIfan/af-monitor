<template>
  <div class="split-layout simulator-layout">
    <div class="config-panel">
      <article class="panel">
        <div class="panel__header">
          <div>
            <p class="section-eyebrow">Packet simulator</p>
            <h3>用户数据模拟测试</h3>
          </div>
          <div class="filter-row">
            <el-button @click="resetScenario">重置场景</el-button>
            <el-button type="primary" :loading="submitting" @click="submitPacket">发送测试包</el-button>
          </div>
        </div>

        <p class="panel__helper">
          该页面使用后台管理员 token 调用正式包入库接口，数据会写入所选用户的测量、分析和告警链路。
        </p>

        <el-form label-position="top" :model="form">
          <el-form-item label="目标用户">
            <el-select
              v-model="form.userId"
              filterable
              placeholder="选择要模拟上报的用户"
              style="width: 100%;"
              @change="handleUserChange"
            >
              <el-option
                v-for="item in targetUsers"
                :key="item.id"
                :label="`${item.username} · ${item.device_count}台设备 · ${item.measurement_count}条测量`"
                :value="String(item.id)"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="测试设备 ID">
            <el-input v-model="form.deviceId" placeholder="例如：sim-ring-1" />
          </el-form-item>

          <div class="stats-row simulator-scenario-row">
            <div class="stat-card">
              <p class="section-eyebrow">Scenario</p>
              <div class="stat-card__value simulator-scenario-value">{{ activeScenarioLabel }}</div>
              <el-select v-model="form.scenario" size="small">
                <el-option
                  v-for="item in scenarioOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </div>
            <div class="stat-card">
              <p class="section-eyebrow">Target</p>
              <div class="stat-card__value simulator-scenario-value">{{ selectedUserLabel }}</div>
              <p class="stat-card__hint">source: console-simulator</p>
            </div>
          </div>

          <template v-if="form.scenario !== 'custom'">
            <div class="simulator-metrics">
              <el-form-item label="心率 BPM">
                <el-input-number v-model="form.heartRate" :min="30" :max="220" />
              </el-form-item>
              <el-form-item label="HRV">
                <el-input-number v-model="form.hrv" :min="0" :max="255" />
              </el-form-item>
              <el-form-item label="压力值">
                <el-input-number v-model="form.stress" :min="0" :max="100" />
              </el-form-item>
              <el-form-item label="血氧">
                <el-input-number v-model="form.oxygen" :min="70" :max="100" />
              </el-form-item>
              <el-form-item label="体温">
                <el-input-number v-model="form.temperature" :min="34" :max="42" :step="0.01" />
              </el-form-item>
            </div>
          </template>

          <el-form-item v-else label="自定义 frame_hex">
            <el-input
              v-model="form.customFrameHex"
              type="textarea"
              :rows="5"
              placeholder="00 00 31 00 03 78 28 55 8E 0E"
            />
          </el-form-item>

          <el-alert
            show-icon
            :closable="false"
            title="连续异常测试会发送 5 条间隔 1 分钟的样本，用于满足结构化 ML 的最小样本数并触发时间窗分析。"
            type="warning"
          />

          <div class="simulator-action-row">
            <el-button type="primary" :loading="submitting" @click="submitPacket">
              发送一条
            </el-button>
            <el-button :loading="batching" @click="submitBurst">
              连续发送 5 条样本
            </el-button>
            <el-button text @click="openMeasurements">
              查看测量明细
            </el-button>
          </div>
        </el-form>
      </article>
    </div>

    <aside class="lab-panel">
      <div class="lab-panel__header">
        <p class="section-eyebrow" style="color: var(--panel)">Live payload</p>
        <h3 style="margin: 0.5rem 0; color: var(--panel)">测试注入台</h3>
      </div>

      <div class="lab-panel__body">
        <div>
          <p class="section-eyebrow">Status</p>
          <div style="margin-top: 0.5rem;">
            <span v-if="!lastResult" class="status-badge">READY</span>
            <span v-else class="status-badge status-badge--ok">CREATED</span>
          </div>
        </div>

        <div>
          <p class="section-eyebrow">Request preview</p>
          <pre class="result-view simulator-preview">{{ JSON.stringify(requestPreview, null, 2) }}</pre>
        </div>

        <div style="flex: 1; display: flex; flex-direction: column;">
          <p class="section-eyebrow">Latest response</p>
          <div class="result-view" style="margin-top: 0.5rem;">
            <div v-if="!lastResult" style="color: var(--muted); text-align: center; padding-top: 4rem;">
              等待测试数据写入...
            </div>
            <pre v-else class="simulator-response">{{ JSON.stringify(lastResult, null, 2) }}</pre>
          </div>
        </div>

        <div>
          <p class="section-eyebrow">Send log</p>
          <div v-if="logs.length" class="simulator-log">
            <div v-for="item in logs" :key="item.id" class="simulator-log__item">
              <strong>{{ item.status }}</strong>
              <span>{{ item.at }} · {{ item.deviceId }} · {{ item.summary }}</span>
            </div>
          </div>
          <p v-else class="panel__helper">暂无发送记录。</p>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useManagementStore } from '../stores/management'
import type { ManagedUser } from '../stores/management'
import { api } from '../utils/api'

type ScenarioKey = 'normal' | 'tachycardia' | 'bradycardia' | 'low_oxygen' | 'fever' | 'custom'

type TestLog = {
  id: number
  at: string
  status: string
  deviceId: string
  summary: string
}

const router = useRouter()
const management = useManagementStore()
const submitting = ref(false)
const batching = ref(false)
const lastResult = ref<Record<string, any> | null>(null)
const logs = ref<TestLog[]>([])

const scenarioOptions: Array<{ label: string; value: ScenarioKey }> = [
  { label: '正常心率', value: 'normal' },
  { label: '高心率风险', value: 'tachycardia' },
  { label: '低心率观察', value: 'bradycardia' },
  { label: '低血氧风险', value: 'low_oxygen' },
  { label: '发热观察', value: 'fever' },
  { label: '自定义原始帧', value: 'custom' },
]

const scenarioDefaults: Record<Exclude<ScenarioKey, 'custom'>, {
  heartRate: number
  hrv: number
  stress: number
  oxygen: number
  temperature: number
}> = {
  normal: { heartRate: 76, hrv: 22, stress: 26, oxygen: 98, temperature: 36.6 },
  tachycardia: { heartRate: 124, hrv: 42, stress: 85, oxygen: 97, temperature: 37.1 },
  bradycardia: { heartRate: 44, hrv: 18, stress: 30, oxygen: 97, temperature: 36.4 },
  low_oxygen: { heartRate: 112, hrv: 36, stress: 70, oxygen: 91, temperature: 36.9 },
  fever: { heartRate: 104, hrv: 32, stress: 62, oxygen: 96, temperature: 38.2 },
}

const form = reactive({
  userId: '',
  deviceId: '',
  scenario: 'tachycardia' as ScenarioKey,
  heartRate: 124,
  hrv: 42,
  stress: 85,
  oxygen: 97,
  temperature: 37.1,
  customFrameHex: '00 00 31 00 03 78 28 55 8E 0E',
})

const targetUsers = computed(() => management.users.filter((item) => item.role !== 'admin'))
const selectedUser = computed(() => targetUsers.value.find((item) => String(item.id) === form.userId) || null)
const selectedUserLabel = computed(() => selectedUser.value?.username || '未选择')
const activeScenarioLabel = computed(() => scenarioOptions.find((item) => item.value === form.scenario)?.label || '--')
const frameHex = computed(() => buildFrameHex())
const requestPreview = computed(() => ({
  user_id: form.userId ? Number(form.userId) : null,
  device_id: form.deviceId || defaultDeviceId(form.userId),
  client_time: new Date().toISOString(),
  source: 'console-simulator',
  payload: {
    frame_hex: frameHex.value,
  },
}))

function defaultDeviceId(userId: string) {
  return userId ? `sim-ring-${userId}` : 'sim-ring'
}

function toByte(value: number) {
  return Math.max(0, Math.min(255, Math.round(value)))
}

function toHex(value: number) {
  return toByte(value).toString(16).padStart(2, '0').toUpperCase()
}

function temperatureHexParts(value: number) {
  const raw = Math.max(0, Math.round(value * 100))
  return `${toHex(raw & 0xFF)} ${toHex((raw >> 8) & 0xFF)}`
}

function normalizeFrameHex(value: string) {
  return value.trim().replace(/\s+/g, ' ').toUpperCase()
}

function buildHeartRateFrame(heartRate: number, hrv: number, stress: number, temperature: number) {
  return `00 00 31 00 03 ${toHex(heartRate)} ${toHex(hrv)} ${toHex(stress)} ${temperatureHexParts(temperature)}`
}

function buildOxygenFrame(heartRate: number, oxygen: number, temperature: number) {
  return `00 00 32 00 03 ${toHex(heartRate)} ${toHex(oxygen)} ${temperatureHexParts(temperature)}`
}

function buildFrameHex() {
  if (form.scenario === 'custom') {
    return normalizeFrameHex(form.customFrameHex)
  }
  if (form.scenario === 'low_oxygen') {
    return buildOxygenFrame(form.heartRate, form.oxygen, form.temperature)
  }
  return buildHeartRateFrame(form.heartRate, form.hrv, form.stress, form.temperature)
}

function applyScenarioDefaults(scenario: ScenarioKey) {
  if (scenario === 'custom') return
  Object.assign(form, scenarioDefaults[scenario])
}

function resetScenario() {
  applyScenarioDefaults(form.scenario)
  ElMessage.success('测试场景已重置。')
}

function handleUserChange(value: string) {
  if (!value) return
  management.setSelectedUserId(value)
  if (!form.deviceId || form.deviceId.startsWith('sim-ring-')) {
    form.deviceId = defaultDeviceId(value)
  }
}

function validatePayload() {
  if (!form.userId) {
    ElMessage.warning('请先选择目标用户。')
    return false
  }
  if (!form.deviceId.trim()) {
    ElMessage.warning('测试设备 ID 不能为空。')
    return false
  }
  if (!/^([0-9A-F]{2})(\s+[0-9A-F]{2})*$/.test(frameHex.value)) {
    ElMessage.warning('frame_hex 需要使用空格分隔的两位十六进制字节。')
    return false
  }
  return true
}

function buildRequest(clientTime = new Date(), frame = frameHex.value) {
  return {
    user_id: Number(form.userId),
    device_id: form.deviceId.trim(),
    client_time: clientTime.toISOString(),
    source: 'console-simulator',
    payload: {
      frame_hex: frame,
    },
  }
}

function pushLog(data: Record<string, any>) {
  logs.value.unshift({
    id: Date.now(),
    at: new Date().toLocaleTimeString(),
    status: data.analysis?.risk_level || data.packet_kind || 'created',
    deviceId: data.device_id || form.deviceId,
    summary: data.analysis?.summary || '测试包已写入',
  })
  logs.value = logs.value.slice(0, 6)
}

async function submitPacket() {
  if (!validatePayload()) return
  submitting.value = true
  try {
    const { data } = await api.post('/packets', buildRequest())
    lastResult.value = data
    pushLog(data)
    await management.loadUsers(true)
    ElMessage.success('测试数据已写入。')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '测试数据发送失败。')
  } finally {
    submitting.value = false
  }
}

async function submitBurst() {
  if (!validatePayload()) return
  batching.value = true
  try {
    let latest: Record<string, any> | null = null
    for (let index = 0; index < 5; index += 1) {
      const frame = buildHeartRateFrame(112 + index * 4, 34 + index * 2, 78 + index, form.temperature)
      const { data } = await api.post('/packets', buildRequest(new Date(Date.now() + index * 60 * 1000), frame))
      latest = data
      pushLog(data)
    }
    lastResult.value = latest
    await management.loadUsers(true)
    ElMessage.success('5 条连续测试样本已写入。')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '连续测试发送失败。')
  } finally {
    batching.value = false
  }
}

function openMeasurements() {
  if (form.userId) {
    management.setSelectedUserId(form.userId)
  }
  router.push('/measurements')
}

async function initialize() {
  const users = await management.loadUsers() as ManagedUser[]
  const preferredUserId =
    management.selectedUserId || String(users.find((item: ManagedUser) => item.role !== 'admin')?.id || '')
  if (preferredUserId) {
    form.userId = preferredUserId
    form.deviceId = defaultDeviceId(preferredUserId)
    management.setSelectedUserId(preferredUserId)
  }
}

watch(() => form.scenario, applyScenarioDefaults)
watch(
  () => management.selectedUserId,
  (value) => {
    if (value && value !== form.userId) {
      form.userId = value
      if (!form.deviceId || form.deviceId.startsWith('sim-ring-')) {
        form.deviceId = defaultDeviceId(value)
      }
    }
  },
)

onMounted(() => {
  initialize().catch(() => {
    ElMessage.error('用户列表加载失败。')
  })
})
</script>
