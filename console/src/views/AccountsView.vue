<template>
  <div class="page-grid">
    <section class="split-panel">
      <article class="panel">
        <div class="panel__header">
          <div>
            <p class="section-eyebrow">Account inventory</p>
            <h3>账号概览</h3>
          </div>
          <div class="filter-row">
            <el-button @click="loadUsers">刷新</el-button>
            <el-button
              type="danger"
              plain
              :disabled="!selectedUserIds.length"
              :loading="deleting"
              @click="handleBatchDelete"
            >
              批量删除
            </el-button>
          </div>
        </div>

        <el-table :data="management.users" stripe @selection-change="handleSelectionChange">
          <el-table-column type="selection" width="48" />
          <el-table-column prop="username" label="用户名" min-width="140" />
          <el-table-column label="姓名" min-width="140">
            <template #default="{ row }">
              {{ [row.last_name, row.first_name].filter(Boolean).join('') || '--' }}
            </template>
          </el-table-column>
          <el-table-column prop="email" label="邮箱" min-width="180" />
          <el-table-column prop="device_count" label="设备数" min-width="90" />
          <el-table-column prop="measurement_count" label="测量数" min-width="90" />
          <el-table-column prop="unread_alert_count" label="未读告警" min-width="100" />
          <el-table-column label="角色" min-width="100">
            <template #default="{ row }">
              <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">{{ row.role === 'admin' ? '管理' : '普通' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="last_login_ip" label="登录 IP" min-width="140" />
          <el-table-column label="省市" min-width="180">
            <template #default="{ row }">
              {{ [row.last_login_location?.region, row.last_login_location?.city].filter(Boolean).join(' / ') || '--' }}
            </template>
          </el-table-column>
          <el-table-column label="最近活动" min-width="180">
            <template #default="{ row }">{{ formatDateTime(row.latest_activity_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" min-width="220">
            <template #default="{ row }">
              <el-button
                v-if="row.role !== 'admin'"
                link
                type="primary"
                @click="viewUser(row.id)"
              >
                查看测量
              </el-button>
              <span v-else class="panel__helper">后台账号</span>
              <el-button
                link
                type="danger"
                :disabled="row.id === auth.user?.id"
                @click="handleDelete(row.id, row.username)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </article>

      <article class="panel panel--dense">
        <div class="panel__header">
          <div>
            <p class="section-eyebrow">Create account</p>
            <h3>创建账号</h3>
          </div>
        </div>

        <el-tabs v-model="activeTab" stretch>
          <el-tab-pane label="单个创建" name="single">
            <el-form label-position="top" :model="form">
              <el-form-item label="用户名">
                <el-input v-model="form.username" />
              </el-form-item>
              <el-form-item label="密码">
                <el-input v-model="form.password" show-password type="password" />
              </el-form-item>
              <el-form-item label="邮箱">
                <el-input v-model="form.email" />
              </el-form-item>
              <el-form-item label="姓">
                <el-input v-model="form.last_name" />
              </el-form-item>
              <el-form-item label="名">
                <el-input v-model="form.first_name" />
              </el-form-item>
              <el-form-item label="角色">
                <el-select v-model="form.role">
                  <el-option label="普通用户" value="user" />
                  <el-option label="管理员" value="admin" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-switch
                  v-model="form.generate_china_location"
                  inline-prompt
                  active-text="自动生成中国 IP"
                  inactive-text="手动填写"
                />
              </el-form-item>
              <p class="panel__helper">
                开启后会自动生成中国境内公网 IP，并写入对应省市坐标，适合答辩演示与地图分布展示。
              </p>
              <el-button type="primary" :loading="submitting" @click="submitCreate">创建账号</el-button>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="批量生成" name="batch">
            <el-form label-position="top" :model="batchForm">
              <el-form-item label="数量">
                <el-input-number v-model="batchForm.count" :min="1" :max="50" />
              </el-form-item>
              <el-form-item label="用户名前缀">
                <el-input v-model="batchForm.username_prefix" placeholder="例如：patient" />
              </el-form-item>
              <el-form-item label="统一密码">
                <el-input v-model="batchForm.password" show-password type="password" />
              </el-form-item>
              <el-form-item label="角色">
                <el-select v-model="batchForm.role">
                  <el-option label="普通用户" value="user" />
                  <el-option label="管理员" value="admin" />
                </el-select>
              </el-form-item>
              <el-form-item label="邮箱域名">
                <el-input v-model="batchForm.email_domain" placeholder="例如：demo.local" />
              </el-form-item>
              <el-form-item>
                <el-switch
                  v-model="batchForm.generate_profile"
                  inline-prompt
                  active-text="自动姓名邮箱"
                  inactive-text="仅账号"
                />
              </el-form-item>
              <el-form-item>
                <el-switch
                  v-model="batchForm.generate_china_location"
                  inline-prompt
                  active-text="生成中国 IP 与定位"
                  inactive-text="不生成定位"
                />
              </el-form-item>
              <p class="panel__helper">
                批量生成会自动补齐用户名序号、邮箱、中文姓名和中国境内登录位置，用于地图、账号总览和演示联调。
              </p>
              <el-button type="primary" :loading="batchSubmitting" @click="submitBatchCreate">批量生成账号</el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { useAuthStore } from '../stores/auth'
import { useManagementStore } from '../stores/management'
import { formatDateTime } from '../utils/format'

const router = useRouter()
const auth = useAuthStore()
const management = useManagementStore()
const submitting = ref(false)
const batchSubmitting = ref(false)
const deleting = ref(false)
const activeTab = ref('single')
const selectedUserIds = ref<number[]>([])

const form = reactive({
  username: '',
  password: '',
  email: '',
  first_name: '',
  last_name: '',
  role: 'user',
  is_active: true,
  generate_china_location: true,
})

const batchForm = reactive({
  count: 10,
  username_prefix: 'patient',
  password: 'demo12345',
  role: 'user',
  is_active: true,
  generate_china_location: true,
  generate_profile: true,
  email_domain: 'demo.local',
})

async function loadUsers() {
  try {
    await management.loadUsers(true)
  } catch {
    ElMessage.error('账号列表加载失败。')
  }
}

function handleSelectionChange(rows: Array<{ id: number }>) {
  selectedUserIds.value = rows.map((row) => row.id)
}

function viewUser(userId: number) {
  management.setSelectedUserId(String(userId))
  router.push('/measurements')
}

async function submitCreate() {
  if (!form.username || !form.password) {
    ElMessage.warning('用户名和密码不能为空。')
    return
  }
  submitting.value = true
  try {
    const created = await management.createUser(form)
    ElMessage.success(`账号 ${created.username} 已创建。`)
    management.setSelectedUserId('')
    Object.assign(form, {
      username: '',
      password: '',
      email: '',
      first_name: '',
      last_name: '',
      role: 'user',
      is_active: true,
      generate_china_location: true,
    })
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.username?.[0] || '创建账号失败。')
  } finally {
    submitting.value = false
  }
}

async function submitBatchCreate() {
  if (!batchForm.count || !batchForm.username_prefix || !batchForm.password) {
    ElMessage.warning('数量、用户名前缀和密码不能为空。')
    return
  }
  batchSubmitting.value = true
  try {
    const created = await management.createUsersBatch(batchForm)
    ElMessage.success(`已批量创建 ${created.length} 个账号。`)
    management.setSelectedUserId('')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '批量创建失败。')
  } finally {
    batchSubmitting.value = false
  }
}

async function handleDelete(userId: number, username: string) {
  try {
    await ElMessageBox.confirm(`确认删除账号 ${username}？该账号关联的绑定关系和患者资料也会被移除。`, '删除账号', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  deleting.value = true
  try {
    await management.deleteUser(userId)
    if (management.selectedUserId === String(userId)) {
      management.setSelectedUserId('')
    }
    ElMessage.success(`账号 ${username} 已删除。`)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '删除账号失败。')
  } finally {
    deleting.value = false
  }
}

async function handleBatchDelete() {
  const ids = selectedUserIds.value.filter((id) => id !== auth.user?.id)
  if (!ids.length) {
    ElMessage.warning('请选择要删除的账号，且不能包含当前登录账号。')
    return
  }

  try {
    await ElMessageBox.confirm(`确认批量删除 ${ids.length} 个账号？`, '批量删除账号', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  deleting.value = true
  try {
    await management.deleteUsersBatch(ids)
    if (ids.includes(Number(management.selectedUserId))) {
      management.setSelectedUserId('')
    }
    selectedUserIds.value = []
    ElMessage.success(`已删除 ${ids.length} 个账号。`)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '批量删除失败。')
  } finally {
    deleting.value = false
  }
}

onMounted(loadUsers)
</script>
