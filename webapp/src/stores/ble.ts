import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '../utils/api'
import { bytesToHex } from '../utils/format'
import { ringBle, type BleState, type RingDeviceInfo } from '../utils/ble'

export type FrameLogEntry = {
  id: number
  time: number
  hex: string
  length: number
  cmd: string
  sub: string
  uploaded: boolean
  uploadError?: string
  parsed?: Record<string, unknown> | null
  riskLevel?: string | null
}

const MAX_LOG_ENTRIES = 60
// 节流：单次测量推送通常秒级，跟小程序一致给 800ms 去重窗。
const UPLOAD_THROTTLE_MS = 800

export const useBleStore = defineStore('ble', () => {
  const state = ref<BleState>('idle')
  const stateDetail = ref<string>('')
  const device = ref<RingDeviceInfo | null>(null)
  const deviceBoundId = ref<string>('')
  const frameCount = ref(0)
  const uploadedCount = ref(0)
  const lastUploadedAt = ref<number>(0)
  const lastRiskLevel = ref<string | null>(null)
  const lastHeartRate = ref<number | null>(null)
  const logs = ref<FrameLogEntry[]>([])

  let logSeq = 0
  let lastUploadTs = 0
  let unsubFrame: (() => void) | null = null
  let unsubState: (() => void) | null = null

  const isConnected = computed(() => state.value === 'connected')
  const isConnecting = computed(() => state.value === 'connecting')

  function setBoundDevice(id: string) {
    deviceBoundId.value = id
  }

  function resetStats() {
    frameCount.value = 0
    uploadedCount.value = 0
    lastUploadedAt.value = 0
    lastRiskLevel.value = null
    lastHeartRate.value = null
    logs.value = []
    logSeq = 0
    lastUploadTs = 0
  }

  function pushLog(entry: FrameLogEntry) {
    logs.value.unshift(entry)
    if (logs.value.length > MAX_LOG_ENTRIES) {
      logs.value.length = MAX_LOG_ENTRIES
    }
  }

  async function ensureSubscribed() {
    if (unsubFrame && unsubState) return
    unsubState = ringBle.onStateChange((next, detail) => {
      state.value = next
      stateDetail.value = detail || ''
      device.value = ringBle.getDevice()
      if (next === 'disconnected' || next === 'error' || next === 'idle') {
        // 保留已有统计；断开不清零，便于用户查看最后状态
      }
    })
    unsubFrame = ringBle.onFrame(async (frame) => {
      frameCount.value += 1
      const now = Date.now()
      const hex = bytesToHex(frame)
      const cmd = frame[2] !== undefined ? `0x${frame[2].toString(16).padStart(2, '0').toUpperCase()}` : '?'
      const sub = frame[3] !== undefined ? `0x${frame[3].toString(16).padStart(2, '0').toUpperCase()}` : '?'
      const entry: FrameLogEntry = {
        id: ++logSeq,
        time: now,
        hex,
        length: frame.length,
        cmd,
        sub,
        uploaded: false,
      }
      pushLog(entry)

      // 节流上报：同一 800ms 窗口内只上报一次，避免短时间打爆后端
      if (!deviceBoundId.value) {
        entry.uploadError = '未绑定设备，跳过上报'
        return
      }
      if (now - lastUploadTs < UPLOAD_THROTTLE_MS) {
        entry.uploadError = '节流跳过'
        return
      }
      lastUploadTs = now

      try {
        const { data } = await api.post('/packets', {
          device_id: deviceBoundId.value,
          client_time: new Date(now).toISOString(),
          source: 'web-bluetooth',
          payload: {
            frame_hex: hex,
            frame_bytes: Array.from(frame),
          },
        })
        entry.uploaded = true
        entry.parsed = (data?.parsed ?? null) as Record<string, unknown> | null
        entry.riskLevel = data?.analysis?.risk_level ?? null
        uploadedCount.value += 1
        lastUploadedAt.value = now
        if (entry.riskLevel) {
          lastRiskLevel.value = entry.riskLevel
        }
        const hr = (entry.parsed as { heartRate?: number } | null)?.heartRate
        if (typeof hr === 'number' && hr > 0) {
          lastHeartRate.value = hr
        }
      } catch (err) {
        entry.uploaded = false
        entry.uploadError =
          err instanceof Error ? err.message : typeof err === 'string' ? err : '上报失败'
      }
    })
  }

  async function connect(): Promise<void> {
    await ensureSubscribed()
    await ringBle.connect()
  }

  async function disconnect(): Promise<void> {
    await ringBle.disconnect()
  }

  async function sendCommand(frame: Uint8Array): Promise<void> {
    await ringBle.write(frame)
  }

  return {
    state,
    stateDetail,
    device,
    deviceBoundId,
    frameCount,
    uploadedCount,
    lastUploadedAt,
    lastRiskLevel,
    lastHeartRate,
    logs,
    isConnected,
    isConnecting,
    setBoundDevice,
    resetStats,
    connect,
    disconnect,
    sendCommand,
    ensureSubscribed,
  }
})
