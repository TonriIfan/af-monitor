<template>
  <div class="page-grid">
    <article class="panel">
      <div class="panel__header">
        <div>
          <p class="section-eyebrow">Measurement stream</p>
          <h3>测量查询</h3>
        </div>
        <div class="filter-row">
          <el-input v-model="filters.device_id" clearable placeholder="设备 ID" />
          <el-button type="primary" @click="loadMeasurements">筛选</el-button>
        </div>
      </div>
      <p class="panel__helper" v-if="auth.user?.role === 'admin'">
        当前视角：{{ management.selectedUser ? `${management.selectedUser.username} 的测量数据` : '全部账号测量数据' }}
      </p>

      <el-table :data="measurements" stripe>
        <el-table-column v-if="auth.user?.role === 'admin'" label="账号" min-width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="focusUser(row.user_id, row.username)">
              {{ row.username || '--' }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="device_id" label="设备" min-width="130" />
        <el-table-column prop="packet_kind" label="类型" min-width="120" />
        <el-table-column label="风险" min-width="120">
          <template #default="{ row }">
            <el-tag :type="riskTagType(row.analysis?.risk_level)">
              {{ riskLabel(row.analysis?.risk_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="解析结果" min-width="360">
          <template #default="{ row }">
            <pre class="json-chip">{{ JSON.stringify(row.parsed, null, 2) }}</pre>
          </template>
        </el-table-column>
        <el-table-column label="原始包" min-width="360">
          <template #default="{ row }">
            <pre class="json-chip">{{ JSON.stringify(row.raw_payload?.payload, null, 2) }}</pre>
          </template>
        </el-table-column>
        <el-table-column label="时间" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.measured_at) }}</template>
        </el-table-column>
      </el-table>
    </article>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'
import { useManagementStore } from '../stores/management'
import { api } from '../utils/api'
import { formatDateTime, riskLabel, riskTagType } from '../utils/format'

const auth = useAuthStore()
const management = useManagementStore()
const filters = reactive({
  device_id: '',
})
const measurements = ref<Array<Record<string, any>>>([])

function focusUser(userId?: number, username?: string) {
  if (!userId) return
  management.setSelectedUserId(String(userId))
  ElMessage.success(`已切换到 ${username || '该账号'} 的测量视角。`)
}

async function loadMeasurements() {
  try {
    const { data } = await api.get('/measurements', {
      params: {
        ...(auth.user?.role === 'admin' ? management.scopeParams() : {}),
        device_id: filters.device_id || undefined,
      },
    })
    measurements.value = data
  } catch {
    ElMessage.error('测量数据加载失败。')
  }
}

onMounted(loadMeasurements)
watch(() => management.selectedUserId, loadMeasurements)
</script>
