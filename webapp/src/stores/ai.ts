import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '../utils/api'

export type ChatMessage = {
  role: 'user' | 'assistant' | 'system'
  content: string
  source?: string
  model?: string
  error?: boolean
  time: Date
}

const HISTORY_WINDOW = 12

export const useAiStore = defineStore('ai', () => {
  const isOpen = ref(false)
  const messages = ref<ChatMessage[]>([])
  const isAsking = ref(false)

  function pushGreeting() {
    messages.value.push({
      role: 'assistant',
      content:
        '你好！我是你的 AI 健康助手。我可以根据你的心脏监测数据提供专业的健康建议。你可以问我："我现在的风险高吗？"或者"接下来的建议是什么？"',
      time: new Date(),
    })
  }

  function open() {
    isOpen.value = true
    if (messages.value.length === 0) {
      pushGreeting()
    }
  }

  function close() {
    isOpen.value = false
  }

  function buildHistoryPayload() {
    return messages.value
      .filter((msg) => !msg.error && (msg.role === 'user' || msg.role === 'assistant'))
      .slice(-HISTORY_WINDOW)
      .map((msg) => ({ role: msg.role, content: msg.content }))
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim()
    if (!trimmed || isAsking.value) return

    const userMsg: ChatMessage = {
      role: 'user',
      content: trimmed,
      time: new Date(),
    }
    messages.value.push(userMsg)

    const history = buildHistoryPayload().slice(0, -1)

    isAsking.value = true
    try {
      const { data } = await api.post('/ai/chat', {
        message: trimmed,
        history,
      })
      messages.value.push({
        role: 'assistant',
        content: data.content || '未返回有效解读。',
        source: data.source,
        model: data.source === 'llm' ? data.model : undefined,
        time: new Date(),
      })
    } catch (err: any) {
      messages.value.push({
        role: 'assistant',
        content: err?.response?.data?.detail || '抱歉，AI 助手暂时无法响应，请稍后再试。',
        error: true,
        time: new Date(),
      })
    } finally {
      isAsking.value = false
    }
  }

  function clearHistory() {
    messages.value = []
    if (isOpen.value) {
      pushGreeting()
    }
  }

  function reset() {
    isOpen.value = false
    isAsking.value = false
    messages.value = []
  }

  return {
    isOpen,
    messages,
    isAsking,
    open,
    close,
    sendMessage,
    clearHistory,
    reset,
  }
})
