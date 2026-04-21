<template>
  <el-drawer
    v-model="ai.isOpen"
    direction="btt"
    size="85%"
    :with-header="false"
    class="ai-chat-drawer"
  >
    <div class="chat-container">
      <div class="chat-header">
        <div class="chat-header__title">AI 健康助手</div>
        <div class="chat-header__actions">
          <el-button
            v-if="ai.messages.length > 1"
            text
            size="small"
            :disabled="ai.isAsking"
            @click="ai.clearHistory()"
          >
            清空对话
          </el-button>
          <el-button icon="Close" circle @click="ai.close()" />
        </div>
      </div>

      <div ref="scrollRef" class="chat-body">
        <div
          v-for="(msg, index) in ai.messages"
          :key="index"
          class="chat-msg"
          :class="[`chat-msg--${msg.role}`]"
        >
          <div class="chat-msg__avatar">
            <el-icon v-if="msg.role === 'assistant'"><Avatar /></el-icon>
            <el-icon v-else><User /></el-icon>
          </div>
          <div class="chat-msg__content">
            <div v-if="resolveMeta(msg)" class="chat-msg__meta">
              {{ resolveMeta(msg) }}
            </div>
            <div
              v-if="msg.role === 'assistant' && !msg.error"
              class="chat-msg__text chat-msg__markdown"
              v-html="renderMarkdown(msg.content)"
            />
            <div v-else class="chat-msg__text" :class="{ 'chat-msg__text--error': msg.error }">
              {{ msg.content }}
            </div>
            <div class="chat-msg__time">{{ formatTime(msg.time) }}</div>
          </div>
        </div>
        <div v-if="ai.isAsking" class="chat-msg chat-msg--assistant">
          <div class="chat-msg__avatar"><el-icon><Avatar /></el-icon></div>
          <div class="chat-msg__content">
            <div class="chat-msg__text chat-msg__loading">
              <span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-footer">
        <div class="chat-suggestions">
          <button
            v-for="item in suggestions"
            :key="item"
            type="button"
            class="chat-suggestion-chip"
            :disabled="ai.isAsking"
            @click="handleSuggestion(item)"
          >
            {{ item }}
          </button>
        </div>
        <div class="chat-input-row">
          <el-input
            v-model="input"
            placeholder="输入您的问题..."
            :disabled="ai.isAsking"
            @keydown.enter="handleEnter"
            @compositionstart="composing = true"
            @compositionend="composing = false"
          >
            <template #append>
              <el-button :loading="ai.isAsking" :disabled="!canSend" @click="handleSend">
                发送
              </el-button>
            </template>
          </el-input>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Avatar, User } from '@element-plus/icons-vue'

import { useAiStore, type ChatMessage } from '../stores/ai'
import { renderMarkdown } from '../utils/markdown'

const ai = useAiStore()
const input = ref('')
const scrollRef = ref<HTMLElement | null>(null)
const composing = ref(false)

const suggestions = [
  '分析我现在的风险',
  '心率过高怎么办？',
  '给出健康建议',
]

const canSend = computed(() => !ai.isAsking && input.value.trim().length > 0)

function formatTime(date: Date) {
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function resolveMeta(msg: ChatMessage) {
  if (msg.error || msg.role !== 'assistant') return ''
  if (msg.source === 'llm') {
    return msg.model ? `AI 深度解读 · ${msg.model}` : 'AI 深度解读'
  }
  if (msg.source === 'template_fallback') {
    return '模板解读（AI 暂不可用）'
  }
  if (msg.source === 'template') {
    return '模板解读'
  }
  return ''
}

async function handleSend() {
  if (!canSend.value) return
  const text = input.value.trim()
  input.value = ''
  await ai.sendMessage(text)
}

function handleEnter(event: KeyboardEvent) {
  if (composing.value || event.isComposing) return
  event.preventDefault()
  handleSend()
}

function handleSuggestion(item: string) {
  if (ai.isAsking) return
  ai.sendMessage(item)
}

async function scrollToBottom() {
  await nextTick()
  if (scrollRef.value) {
    scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  }
}

watch(
  () => [ai.messages.length, ai.isAsking] as const,
  () => {
    scrollToBottom()
  },
)

watch(
  () => ai.isOpen,
  (open) => {
    if (open) scrollToBottom()
  },
)
</script>

<style>
/* Global style to target drawer content specifically */
.ai-chat-drawer .el-drawer__body {
  padding: 0;
  overflow: hidden;
}
</style>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--wa-bg);
}
.chat-header {
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--wa-border);
  background: var(--wa-surface);
}
.chat-header__title {
  font-weight: 700;
  font-size: 16px;
}
.chat-header__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.chat-msg {
  display: flex;
  gap: 10px;
  max-width: 90%;
}
.chat-msg--user {
  flex-direction: row-reverse;
  align-self: flex-end;
}
.chat-msg__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--wa-surface-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid var(--wa-border);
}
.chat-msg--user .chat-msg__avatar {
  background: var(--wa-accent);
  color: white;
}
.chat-msg__content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1 1 auto;
}
.chat-msg--user .chat-msg__content {
  align-items: flex-end;
}
.chat-msg__text {
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.6;
  background: var(--wa-surface);
  border: 1px solid var(--wa-border);
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}
.chat-msg--assistant .chat-msg__text {
  border-top-left-radius: 2px;
}
.chat-msg--user .chat-msg__text {
  background: var(--wa-accent);
  color: white;
  border: none;
  border-top-right-radius: 2px;
}
.chat-msg__text--error {
  color: var(--wa-danger);
}
.chat-msg__markdown :deep(p) {
  margin: 0 0 8px;
}
.chat-msg__markdown :deep(p:last-child) {
  margin-bottom: 0;
}
.chat-msg__markdown :deep(h1),
.chat-msg__markdown :deep(h2),
.chat-msg__markdown :deep(h3),
.chat-msg__markdown :deep(h4) {
  margin: 4px 0 8px;
  font-size: 15px;
  line-height: 1.45;
}
.chat-msg__markdown :deep(ul),
.chat-msg__markdown :deep(ol) {
  margin: 4px 0 8px;
  padding-left: 18px;
}
.chat-msg__markdown :deep(li + li) {
  margin-top: 4px;
}
.chat-msg__markdown :deep(blockquote) {
  margin: 6px 0;
  padding: 6px 10px;
  border-left: 3px solid var(--wa-accent);
  background: var(--wa-accent-soft);
  color: var(--wa-fg-muted);
}
.chat-msg__markdown :deep(code) {
  padding: 1px 5px;
  border-radius: 5px;
  background: var(--wa-surface-soft);
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 0.92em;
}
.chat-msg__markdown :deep(pre) {
  margin: 6px 0;
  padding: 10px;
  border-radius: 10px;
  background: var(--wa-surface-soft);
  overflow-x: auto;
}
.chat-msg__markdown :deep(pre code) {
  padding: 0;
  background: transparent;
}
.chat-msg__markdown :deep(a) {
  color: var(--wa-accent);
  text-decoration: underline;
  text-underline-offset: 3px;
}
.chat-msg__meta {
  font-size: 11px;
  color: var(--wa-fg-muted);
}
.chat-msg__time {
  font-size: 10px;
  color: var(--wa-fg-muted);
}
.chat-footer {
  padding: 12px;
  background: var(--wa-surface);
  border-top: 1px solid var(--wa-border);
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}
.chat-suggestions {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  margin-bottom: 12px;
  scrollbar-width: none;
}
.chat-suggestions::-webkit-scrollbar { display: none; }
.chat-suggestion-chip {
  padding: 6px 12px;
  background: var(--wa-surface-soft);
  border: 1px solid var(--wa-border);
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
  color: var(--wa-fg);
  cursor: pointer;
  transition: opacity 0.15s ease;
}
.chat-suggestion-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.chat-msg__loading .dot {
  animation: dot-fade 1.4s infinite;
  opacity: 0;
}
.chat-msg__loading .dot:nth-child(2) { animation-delay: 0.2s; }
.chat-msg__loading .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-fade {
  0% { opacity: 0; }
  50% { opacity: 1; }
  100% { opacity: 0; }
}
</style>
