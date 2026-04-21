<template>
  <div class="wa-page">
    <div class="wa-page-title">设备</div>

    <!-- 兼容性检查 -->
    <div v-if="!supported" class="wa-card unsupported">
      <div class="wa-card__title" style="color: var(--wa-danger);">浏览器不支持 Web Bluetooth</div>
      <p class="wa-muted" style="font-size: 13px; margin: 0;">
        当前浏览器不支持 Web Bluetooth API。请换用 Chrome / Edge / Opera 等基于 Blink 内核的浏览器，
        且确保访问的是 HTTPS 站点或 <code>localhost</code>。iOS Safari、Firefox 目前都不支持。
      </p>
    </div>

    <!-- 当前绑定 -->
    <div class="wa-card">
      <div class="wa-card__title">当前绑定</div>
      <div v-if="currentDevice" class="wa-row-between">
        <div>
          <div style="font-weight: 600;">{{ currentDevice.name || currentDevice.device_id }}</div>
          <div class="wa-muted" style="font-size: 12px;">
            设备 ID：<code>{{ currentDevice.device_id }}</code>
          </div>
        </div>
        <el-button size="small" @click="onUnbind" :loading="unbinding">解绑</el-button>
      </div>
      <div v-else class="wa-muted" style="font-size: 13px;">
        你还没有绑定任何戒指。绑定后上报的数据才能进入你的测量记录。
      </div>

      <div class="bind-form">
        <el-input
          v-model="bindForm.device_id"
          placeholder="设备 ID（例如 ring-001）"
          size="large"
          clearable
        />
        <el-input
          v-model="bindForm.alias"
          placeholder="备注名（可选，例如：我的戒指）"
          size="large"
          style="margin-top: 8px;"
        />
        <el-button
          type="primary"
          size="large"
          class="bind-form__submit"
          :loading="binding"
          @click="onBind"
        >
          绑定设备
        </el-button>
      </div>
    </div>

    <!-- 蓝牙连接 -->
    <div class="wa-card">
      <div class="wa-row-between">
        <div>
          <div class="wa-card__title">蓝牙连接</div>
          <div class="wa-muted" style="font-size: 12.5px;">
            <span :style="{ color: stateColor }">●</span>
            {{ stateLabel }}
            <span v-if="ble.device" style="margin-left: 6px;">· {{ ble.device.name }}</span>
          </div>
        </div>
        <div class="wa-row">
          <el-button
            v-if="!ble.isConnected"
            type="primary"
            :disabled="!supported || !currentDevice"
            :loading="ble.isConnecting"
            @click="onConnect"
          >
            连接戒指
          </el-button>
          <el-button v-else @click="onDisconnect">断开</el-button>
        </div>
      </div>
      <div v-if="!currentDevice" class="wa-muted" style="margin-top: 8px; font-size: 12px;">
        请先在上方绑定设备，再连接蓝牙。
      </div>

      <div v-if="ble.isConnected || ble.frameCount > 0" class="ble-stats">
        <div>
          <div class="wa-muted" style="font-size: 12px;">收包</div>
          <div class="ble-stats__value">{{ ble.frameCount }}</div>
        </div>
        <div>
          <div class="wa-muted" style="font-size: 12px;">已上报</div>
          <div class="ble-stats__value">{{ ble.uploadedCount }}</div>
        </div>
        <div>
          <div class="wa-muted" style="font-size: 12px;">最近心率</div>
          <div class="ble-stats__value">{{ ble.lastHeartRate ?? '--' }}<span class="wa-muted" style="font-size: 12px; font-weight: 400; margin-left: 2px;">bpm</span></div>
        </div>
      </div>
    </div>

    <!-- 快捷指令 -->
    <div v-if="ble.isConnected" class="wa-card">
      <div class="wa-card__title">发送指令</div>
      <div class="wa-row" style="gap: 8px;">
        <el-button size="small" @click="sendHex('00 00 10 00')">时间同步</el-button>
        <el-button size="small" @click="sendHex('00 00 12 00')">查询电量</el-button>
        <el-button size="small" @click="sendHex('00 00 31 00')">查询心率</el-button>
        <el-button size="small" @click="sendHex('00 00 32 00')">查询血氧</el-button>
      </div>
      <div class="wa-row" style="margin-top: 10px; gap: 8px;">
        <el-input v-model="customHex" placeholder="自定义 hex：00 00 10 00" size="default" />
        <el-button @click="sendHex(customHex)">发送</el-button>
      </div>
      <div class="wa-muted" style="font-size: 12px; margin-top: 6px;">
        指令格式：FrameType FrameID Cmd SubCmd [数据…]。协议详见后端 docs。
      </div>
    </div>

    <!-- 实时日志 -->
    <div class="wa-card">
      <div class="wa-row-between">
        <div class="wa-card__title">数据流（最近 {{ ble.logs.length }} 条）</div>
        <el-button
          size="small"
          :disabled="!ble.logs.length"
          @click="ble.resetStats"
        >
          清空
        </el-button>
      </div>
      <div v-if="!ble.logs.length" class="wa-empty">暂无数据，点击"连接戒指"开始采集。</div>
      <div v-else class="log-list">
        <div v-for="entry in ble.logs" :key="entry.id" class="log-item">
          <div class="wa-row-between">
            <div style="font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12.5px;">
              <span class="wa-muted">{{ formatTime(entry.time) }}</span>
              <span style="margin-left: 8px;">cmd {{ entry.cmd }}/{{ entry.sub }}</span>
            </div>
            <div>
              <el-tag v-if="entry.uploaded" type="success" size="small">已上报</el-tag>
              <el-tag v-else-if="entry.uploadError" type="info" size="small">{{ entry.uploadError }}</el-tag>
            </div>
          </div>
          <div class="log-item__hex">{{ entry.hex }}</div>
          <div v-if="entry.parsed && Object.keys(entry.parsed).length" class="log-item__parsed">
            <span v-for="(v, k) in entry.parsed" :key="k">
              <b>{{ k }}</b>: {{ v }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { api } from '../utils/api'
import { hexToBytes } from '../utils/format'
import { useBleStore } from '../stores/ble'
import { isWebBluetoothSupported } from '../utils/ble'

type DeviceItem = {
  device_id: string
  name: string
  alias?: string
}

const ble = useBleStore()
const supported = ref(isWebBluetoothSupported())
const currentDevice = ref<DeviceItem | null>(null)
const bindForm = ref({ device_id: '', alias: '' })
const binding = ref(false)
const unbinding = ref(false)
const customHex = ref('00 00 10 00')

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

function formatTime(ts: number) {
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d
    .getMinutes()
    .toString()
    .padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

async function loadCurrent() {
  try {
    const { data } = await api.get<DeviceItem>('/devices/current')
    currentDevice.value = data
    ble.setBoundDevice(data.device_id)
  } catch (err: unknown) {
    if ((err as { response?: { status?: number } })?.response?.status === 404) {
      currentDevice.value = null
      ble.setBoundDevice('')
    }
  }
}

async function onBind() {
  const deviceId = bindForm.value.device_id.trim()
  if (!deviceId) {
    ElMessage.warning('请填写设备 ID')
    return
  }
  binding.value = true
  try {
    await api.post('/devices/bind', {
      device_id: deviceId,
      alias: bindForm.value.alias.trim(),
      source: 'web-bluetooth',
    })
    ElMessage.success('绑定成功')
    bindForm.value = { device_id: '', alias: '' }
    await loadCurrent()
  } catch (err: unknown) {
    const msg =
      (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      (err instanceof Error ? err.message : '绑定失败')
    ElMessage.error(msg)
  } finally {
    binding.value = false
  }
}

async function onUnbind() {
  if (!currentDevice.value) return
  try {
    await ElMessageBox.confirm('确认解绑当前设备？解绑后该戒指上报的数据将不再归属到你。', '解绑确认', {
      type: 'warning',
      confirmButtonText: '解绑',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  unbinding.value = true
  try {
    await api.post('/devices/unbind', { device_id: currentDevice.value.device_id })
    ElMessage.success('已解绑')
    if (ble.isConnected) {
      await ble.disconnect()
    }
    await loadCurrent()
  } catch (err: unknown) {
    const msg =
      (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      (err instanceof Error ? err.message : '解绑失败')
    ElMessage.error(msg)
  } finally {
    unbinding.value = false
  }
}

async function onConnect() {
  try {
    await ble.connect()
    ElMessage.success('已连接')
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '连接失败'
    // 用户取消浏览器选择器会抛 NotFoundError；这里静默
    if (!/NotFoundError|User cancelled/i.test(msg)) {
      ElMessage.error(msg)
    }
  }
}

async function onDisconnect() {
  await ble.disconnect()
  ElMessage.info('已断开')
}

async function sendHex(text: string) {
  try {
    const bytes = hexToBytes(text)
    await ble.sendCommand(bytes)
    ElMessage.success('已发送')
  } catch (err: unknown) {
    ElMessage.error(err instanceof Error ? err.message : '发送失败')
  }
}

onMounted(async () => {
  await loadCurrent()
  await ble.ensureSubscribed()
})
</script>

<style scoped>
.unsupported {
  border: 1px solid var(--wa-danger);
  background: rgba(197, 48, 48, 0.05);
}
.bind-form {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--wa-border);
}
.bind-form__submit {
  width: 100%;
  margin-top: 10px;
}
.ble-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--wa-border);
}
.ble-stats__value {
  font-weight: 700;
  font-size: 20px;
}
.log-list {
  max-height: 360px;
  overflow: auto;
  margin-top: 8px;
}
.log-item {
  padding: 8px 0;
  border-bottom: 1px dashed var(--wa-border);
}
.log-item:last-child {
  border-bottom: none;
}
.log-item__hex {
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 12px;
  color: var(--wa-fg-muted);
  margin-top: 4px;
  word-break: break-all;
}
.log-item__parsed {
  font-size: 12px;
  margin-top: 4px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.log-item__parsed b {
  color: var(--wa-fg-muted);
  font-weight: 500;
  margin-right: 2px;
}
</style>
