<template>
  <div class="split-layout">
    <!-- Left: Configuration Panel -->
    <div class="config-panel">
      <article class="panel">
        <div class="panel__header">
          <div>
            <p class="section-eyebrow">Strategy & Integration</p>
            <h3>AI 核心设置</h3>
          </div>
          <div class="filter-row">
            <el-button @click="loadSettings">重置</el-button>
            <el-button type="primary" :loading="saving" @click="saveSettings">部署策略</el-button>
          </div>
        </div>

        <el-form label-position="top" :model="form">
          <div class="stats-row" style="grid-template-columns: repeat(2, 1fr); margin-bottom: 2rem;">
            <div class="stat-card">
              <p class="section-eyebrow">Switch</p>
              <div class="stat-card__value" :style="{ color: form.enabled ? 'var(--success)' : 'var(--danger)' }">
                {{ form.enabled ? 'ON' : 'OFF' }}
              </div>
              <el-switch v-model="form.enabled" />
            </div>
            <div class="stat-card">
              <p class="section-eyebrow">Engine</p>
              <div class="stat-card__value" style="font-size: 2rem;">{{ form.mode }}</div>
              <el-select v-model="form.mode" size="small">
                <el-option label="DISABLED" value="disabled" />
                <el-option label="TEMPLATE" value="template" />
                <el-option label="OPENAI" value="openai_compatible" />
              </el-select>
            </div>
          </div>

          <el-form-item label="MODEL / 模型标识">
            <el-input v-model="form.model" placeholder="例如：gpt-4o-mini" />
          </el-form-item>
          
          <el-form-item label="ENDPOINT / API 基础路径">
            <el-input v-model="form.api_base_url" placeholder="https://..." />
          </el-form-item>
          
          <el-form-item label="AUTH / API 密钥">
            <el-input v-model="form.api_key" show-password type="password" placeholder="KEEP EMPTY TO REMAIN UNCHANGED" />
            <p class="panel__helper" v-if="form.has_api_key">
              [SYSTEM] 密钥已加密存储。掩码：{{ form.api_key_masked }}
            </p>
          </el-form-item>

          <el-form-item label="TEMPERATURE / 创造力系数">
            <el-slider v-model="form.temperature" :min="0" :max="1" :step="0.01" show-input />
          </el-form-item>

          <el-form-item label="SYSTEM PROMPT / 核心指令">
            <el-input
              v-model="form.system_prompt"
              type="textarea"
              :rows="8"
              placeholder="输入 AI 角色定义与临床解读规范..."
            />
          </el-form-item>
        </el-form>
      </article>
    </div>

    <!-- Right: Real-time Testing Lab -->
    <aside class="lab-panel">
      <div class="lab-panel__header">
        <p class="section-eyebrow" style="color: var(--panel)">Clinical AI Lab</p>
        <h3 style="margin: 0.5rem 0; color: var(--panel)">实时推理实验场</h3>
      </div>
      
      <div class="lab-panel__body">
        <div>
          <p class="section-eyebrow">Connection check</p>
          <div style="margin-top: 0.5rem;">
            <span v-if="testResult.ok === null" class="status-badge">READY</span>
            <span v-else-if="testResult.ok" class="status-badge status-badge--ok">STABLE</span>
            <span v-else class="status-badge status-badge--error">FAILURE</span>
          </div>
        </div>

        <div>
          <p class="section-eyebrow">Simulated Measurement Data (JSON)</p>
          <el-input
            v-model="simulatedInput"
            type="textarea"
            :rows="5"
            placeholder='{"heart_rate": 85, "hrv": 45, "risk": "low"}'
            style="margin-top: 0.5rem;"
          />
        </div>

        <el-button
          type="primary"
          style="width: 100%; height: 60px; font-size: 1.1rem;"
          :loading="testing"
          @click="testSettings"
        >
          EXECUTE INFERENCE / 执行 AI 推理
        </el-button>

        <div style="flex: 1; display: flex; flex-direction: column;">
          <p class="section-eyebrow">Inference Result / 报告生成结果</p>
          <div class="result-view" style="margin-top: 0.5rem;">
            <div v-if="!testResult.content && !testResult.error" style="color: var(--muted); text-align: center; padding-top: 4rem;">
              等待推理指令...
            </div>
            <div v-else-if="testResult.error" style="color: var(--danger)">
              [ERROR] {{ testResult.error }}
            </div>
            <div v-else>
              <p style="margin-top: 0; color: var(--accent); font-weight: 800;">[SOURCE: {{ testResult.source }}]</p>
              {{ testResult.content }}
            </div>
          </div>
        </div>
        
        <div class="panel__header" style="border-bottom: none; border-top: var(--border-weight) solid var(--ink); padding: 1rem 0 0;">
          <p class="section-eyebrow">Performance</p>
          <p style="margin: 0; font-family: monospace;">LATENCY: {{ testLatency }}ms</p>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { api } from '../utils/api'

const saving = ref(false)
const testing = ref(false)
const testLatency = ref(0)
const simulatedInput = ref('{\n  "heartRate": 112,\n  "hrv": 15,\n  "wearStatusText": "佩戴良好",\n  "measured_at": "2024-04-21T10:30:00Z"\n}')

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
    ElMessage.success('策略部署成功。')
  } catch {
    ElMessage.error('策略部署失败。')
  } finally {
    saving.value = false
  }
}

async function testSettings() {
  testing.value = true
  const startTime = Date.now()
  try {
    let testData = {}
    try {
      testData = JSON.parse(simulatedInput.value)
    } catch {
      ElMessage.error('测试数据 JSON 格式有误。')
      testing.value = false
      return
    }

    const payload = {
      enabled: form.enabled,
      mode: form.mode,
      api_base_url: form.api_base_url,
      model: form.model,
      temperature: form.temperature,
      system_prompt: form.system_prompt,
      test_data: testData,
      ...(form.api_key ? { api_key: form.api_key } : {}),
    }
    const { data } = await api.post('/ai/settings/test', payload)
    testLatency.value = Date.now() - startTime
    Object.assign(testResult, {
      ok: Boolean(data.ok),
      source: data.source || '',
      content: data.content || '',
      error: data.error || '',
      message: data.ok ? 'AI 推理成功。' : 'AI 推理异常。',
    })
    if (data.ok) ElMessage.success('AI 推理任务完成。')
    else ElMessage.warning('AI 推理返回异常。')
  } catch (err: any) {
    testLatency.value = Date.now() - startTime
    Object.assign(testResult, {
      ok: false,
      source: '',
      content: '',
      error: err?.response?.data?.error || '请求超时或配置错误。',
      message: '',
    })
    ElMessage.error('推理引擎连接失败。')
  } finally {
    testing.value = false
  }
}

onMounted(loadSettings)
</script>
