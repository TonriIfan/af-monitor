import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { API_BASE_URL, TOKEN_KEY, api } from '../utils/api'

type RealtimeAlert = {
  id: number
  title?: string
  level?: string
  status?: string
  created_at?: string
  message?: string
  trigger_codes?: string[]
  trigger_labels?: string[]
  device_id?: string
}

type AlertStatePayload = {
  unread_count?: number
  latest_alert?: RealtimeAlert | null
}

const RECONNECT_DELAY_MS = 3000

export const useAlertsStore = defineStore('alerts', () => {
  const unreadCount = ref(0)
  const latestAlert = ref<RealtimeAlert | null>(null)
  const isConnected = ref(false)
  const lastError = ref('')

  const hasUnread = computed(() => unreadCount.value > 0)

  let controller: AbortController | null = null
  let reconnectTimer: number | null = null
  let connecting = false
  let shouldReconnect = true

  function applyAlertState(payload: AlertStatePayload) {
    unreadCount.value = payload.unread_count ?? 0
    latestAlert.value = payload.latest_alert || null
  }

  function clearReconnectTimer() {
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function parseEventBlock(block: string) {
    const lines = block
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
    let eventName = 'message'
    let dataText = ''
    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataText += line.slice(5).trim()
      }
    }
    if (!dataText) return
    try {
      const payload = JSON.parse(dataText) as AlertStatePayload
      if (eventName === 'alert_state') {
        applyAlertState(payload)
      }
    } catch {
      lastError.value = '实时告警解析失败'
    }
  }

  function scheduleReconnect() {
    if (!shouldReconnect || reconnectTimer !== null) return
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      void ensureConnected()
    }, RECONNECT_DELAY_MS)
  }

  async function loadUnreadSnapshot() {
    try {
      const { data } = await api.get<{ unread_count?: number }>('/alerts/unread-count')
      unreadCount.value = data.unread_count ?? 0
    } catch {
      unreadCount.value = 0
    }
  }

  async function ensureConnected() {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token || controller || connecting) return

    clearReconnectTimer()
    shouldReconnect = true
    connecting = true
    lastError.value = ''
    controller = new AbortController()

    try {
      const response = await fetch(`${API_BASE_URL}/alerts/events`, {
        headers: {
          Authorization: `Token ${token}`,
          Accept: 'text/event-stream',
        },
        signal: controller.signal,
      })
      if (!response.ok || !response.body) {
        throw new Error(`SSE_${response.status}`)
      }

      isConnected.value = true
      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() || ''
        for (const block of blocks) {
          if (block.trim()) {
            parseEventBlock(block)
          }
        }
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        lastError.value = '实时告警连接中断'
      }
    } finally {
      connecting = false
      controller = null
      isConnected.value = false
      if (shouldReconnect) {
        scheduleReconnect()
      }
    }
  }

  function disconnect() {
    shouldReconnect = false
    clearReconnectTimer()
    controller?.abort()
    controller = null
    connecting = false
    isConnected.value = false
  }

  return {
    unreadCount,
    latestAlert,
    isConnected,
    lastError,
    hasUnread,
    applyAlertState,
    loadUnreadSnapshot,
    ensureConnected,
    disconnect,
  }
})
