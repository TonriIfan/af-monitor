<template>
  <div class="page-grid">
    <article class="panel">
      <div class="panel__header">
        <div>
          <p class="section-eyebrow">AI integration</p>
          <h3>AI 设置</h3>
        </div>
        <div class="filter-row">
          <el-button @click="loadSettings">刷新</el-button>
          <el-button :loading="testing" @click="testSettings">测试可用性</el-button>
          <el-button type="primary" :loading="saving" @click="saveSettings">保存配置</el-button>
        </div>
      </div>

      <el-form label-position="top" :model="form">
        <el-form-item label="启用 AI 解读">
          <el-switch v-model="form.enabled" inline-prompt active-text="启用" inactive-text="关闭" />
        </el-form-item>
        <el-form-item label="运行模式">
          <el-select v-model="form.mode">
            <el-option label="关闭（仅保留接口）" value="disabled" />
            <el-option label="模板解读（推荐）" value="template" />
            <el-option label="外部 LLM（兼容 OpenAI）" value="openai_compatible" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名">
          <el-input v-model="form.model" placeholder="例如：gpt-5.2" />
        </el-form-item>
        <el-form-item label="API Base URL">
          <el-input v-model="form.api_base_url" placeholder="例如：https://your-llm-service.example.com/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" show-password type="password" placeholder="留空表示保持现有 Key 不变" />
          <p class="panel__helper">
            当前状态：{{ form.has_api_key ? `已配置 (${form.api_key_masked || '已隐藏'})` : '未配置' }}
          </p>
        </el-form-item>
        <el-form-item label="温度">
          <el-input-number v-model="form.temperature" :min="0" :max="1" :step="0.05" />
        </el-form-item>
        <el-form-item label="系统提示词">
          <el-input v-model="form.system_prompt" type="textarea" :rows="5" placeholder="可选，自定义 AI 健康解读提示词" />
        </el-form-item>
      </el-form>

      <div class="split-panel">
        <article class="panel panel--dense">
          <div class="panel__header">
            <div>
              <p class="section-eyebrow">Mode note</p>
              <h3>模式说明</h3>
            </div>
          </div>
          <div class="timeline-list">
            <div class="timeline-item">
              <strong>disabled</strong>
              <p>接口仍存在，但只返回模板内容，不视为启用 AI。</p>
            </div>
            <div class="timeline-item">
              <strong>template</strong>
              <p>后端直接生成面向患者的中文模板解释，不依赖外部模型。</p>
            </div>
            <div class="timeline-item">
              <strong>openai_compatible</strong>
              <p>调用兼容 OpenAI Chat Completions 的外部模型，失败时自动回退模板解释。</p>
            </div>
          </div>
        </article>

        <article class="panel panel--dense">
          <div class="panel__header">
            <div>
              <p class="section-eyebrow">Current state</p>
              <h3>当前状态</h3>
            </div>
          </div>
          <div class="timeline-list">
            <div class="timeline-item">
              <strong>启用状态</strong>
              <p>{{ form.enabled ? '已启用' : '未启用' }}</p>
            </div>
            <div class="timeline-item">
              <strong>运行模式</strong>
              <p>{{ form.mode }}</p>
            </div>
            <div class="timeline-item">
              <strong>最近更新时间</strong>
              <p>{{ formatDateTime(form.updated_at) }}</p>
            </div>
          </div>
        </article>
      </div>

      <article class="panel panel--dense">
        <div class="panel__header">
          <div>
            <p class="section-eyebrow">AI test</p>
            <h3>测试结果</h3>
          </div>
        </div>
        <div class="timeline-list">
          <div class="timeline-item">
            <strong>状态</strong>
            <p>{{ testResult.ok === null ? '未测试' : testResult.ok ? '可用' : '不可用' }}</p>
          </div>
          <div class="timeline-item">
            <strong>来源</strong>
            <p>{{ testResult.source || '--' }}</p>
          </div>
          <div class="timeline-item">
            <strong>说明</strong>
            <p>{{ testResult.error || testResult.message || '点击“测试可用性”后显示结果。' }}</p>
          </div>
        </div>
        <el-input
          v-if="testResult.content"
          :model-value="testResult.content"
          type="textarea"
          :rows="12"
          readonly
        />
      </article>
    </article>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { api } from '../utils/api'
import { formatDateTime } from '../utils/format'

const saving = ref(false)
const testing = ref(false)
const form = reactive({
  enabled: false,
  mode: 'template',
  api_base_url: '',
  api_key: '',
  api_key_masked: '',
  has_api_key: false,
  model: 'gpt-4o-mini',
  temperature: 0.2,
  system_prompt: '',
  updated_at: '',
})
const testResult = reactive({
  ok: null as null | boolean,
  source: '',
  content: '',
  error: '',
  message: '',
})

async function loadSettings() {
  try {
    const { data } = await api.get('/ai/settings')
    Object.assign(form, data, { api_key: '' })
  } catch {
    ElMessage.error('AI 设置加载失败。')
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const payload = {
      enabled: form.enabled,
      mode: form.mode,
      api_base_url: form.api_base_url,
      model: form.model,
      temperature: form.temperature,
      system_prompt: form.system_prompt,
      ...(form.api_key ? { api_key: form.api_key } : {}),
    }
    const { data } = await api.put('/ai/settings', payload)
    Object.assign(form, data, { api_key: '' })
    ElMessage.success('AI 设置已保存。')
  } catch {
    ElMessage.error('AI 设置保存失败。')
  } finally {
    saving.value = false
  }
}

async function testSettings() {
  testing.value = true
  try {
    const payload = {
      enabled: form.enabled,
      mode: form.mode,
      api_base_url: form.api_base_url,
      model: form.model,
      temperature: form.temperature,
      system_prompt: form.system_prompt,
      ...(form.api_key ? { api_key: form.api_key } : {}),
    }
    const { data } = await api.post('/ai/settings/test', payload)
    Object.assign(testResult, {
      ok: Boolean(data.ok),
      source: data.source || '',
      content: data.content || '',
      error: data.error || '',
      message: data.ok ? 'AI 测试通过。' : 'AI 测试未通过。',
    })
    ElMessage.success(data.ok ? 'AI 测试通过。' : 'AI 测试完成。')
  } catch {
    Object.assign(testResult, {
      ok: false,
      source: '',
      content: '',
      error: 'AI 测试请求失败。',
      message: '',
    })
    ElMessage.error('AI 测试失败。')
  } finally {
    testing.value = false
  }
}

onMounted(loadSettings)
</script>
