<template>
  <div class="page-grid">
    <section class="split-panel">
      <article class="panel panel--dense">
        <div class="panel__header">
          <div>
            <p class="section-eyebrow">Bind a device</p>
            <h3>绑定新设备</h3>
          </div>
        </div>
        <el-form label-position="top" :model="form">
          <el-form-item label="设备 ID">
            <el-input v-model="form.device_id" placeholder="例如：ring-001" />
          </el-form-item>
          <el-form-item label="名称">
            <el-input v-model="form.name" placeholder="例如：智能戒指" />
          </el-form-item>
          <el-form-item label="别名">
            <el-input v-model="form.alias" placeholder="例如：受试者 A 的戒指" />
          </el-form-item>
          <el-button type="primary" :loading="submitting" @click="submitBind">绑定设备</el-button>
        </el-form>
      </article>

      <article class="panel panel--dense">
        <div class="panel__header">
          <div>
            <p class="section-eyebrow">Inventory</p>
            <h3>设备清单</h3>
          </div>
        </div>
        <p class="panel__helper" v-if="auth.user?.role === 'admin'">
          当前视角：{{ management.selectedUser ? `${management.selectedUser.username} 的设备` : '全部用户设备' }}
        </p>
        <div class="device-grid" v-if="devices.length">
          <div v-for="device in devices" :key="device.device_id" class="device-tile">
            <div class="device-tile__header">
              <strong>{{ device.name || device.device_id }}</strong>
              <el-tag type="info">{{ device.source }}</el-tag>
            </div>
            <p>{{ device.device_id }}</p>
            <div class="device-tile__meta">
              <span v-if="auth.user?.role === 'admin'">
                所属用户：
                <el-button
                  v-if="device.owner_user_id"
                  link
                  type="primary"
                  @click="focusUser(device.owner_user_id, device.owner_username)"
                >
                  {{ device.owner_username || '--' }}
                </el-button>
                <template v-else>{{ device.owner_username || '--' }}</template>
              </span>
              <span>别名：{{ device.alias || '--' }}</span>
              <span>未读告警：{{ device.unread_alerts }}</span>
              <span>最近测量：{{ formatDateTime(device.latest_measurement_at) }}</span>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无绑定设备" />
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'
import { useManagementStore } from '../stores/management'
import { api } from '../utils/api'
import { formatDateTime } from '../utils/format'

const auth = useAuthStore()
const management = useManagementStore()
const devices = ref<Array<Record<string, any>>>([])
const submitting = ref(false)
const form = reactive({
  device_id: '',
  name: '',
  alias: '',
})

function focusUser(userId?: number, username?: string) {
  if (!userId) return
  management.setSelectedUserId(String(userId))
  ElMessage.success(`已切换到 ${username || '该用户'} 的设备视角。`)
}

async function loadDevices() {
  try {
    const { data } = await api.get('/devices/', {
      params: auth.user?.role === 'admin' ? management.scopeParams() : {},
    })
    devices.value = data
  } catch {
    ElMessage.error('设备列表加载失败。')
  }
}

async function submitBind() {
  if (!form.device_id) {
    ElMessage.warning('设备 ID 不能为空。')
    return
  }
  submitting.value = true
  try {
      await api.post('/devices/bind', {
        ...form,
        ...(auth.user?.role === 'admin' ? management.scopeParams() : {}),
      })
    ElMessage.success('设备绑定成功。')
    form.device_id = ''
    form.name = ''
    form.alias = ''
    await loadDevices()
  } catch {
    ElMessage.error('设备绑定失败。')
  } finally {
    submitting.value = false
  }
}

onMounted(loadDevices)
watch(() => management.selectedUserId, loadDevices)
</script>
