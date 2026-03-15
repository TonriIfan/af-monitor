<template>
  <div class="page-grid">
    <section class="split-panel">
      <article class="panel">
        <div class="panel__header">
          <div>
            <p class="section-eyebrow">Account inventory</p>
            <h3>账号概览</h3>
          </div>
          <el-button @click="loadUsers">刷新</el-button>
        </div>

        <el-table :data="management.users" stripe>
          <el-table-column prop="username" label="用户名" min-width="140" />
          <el-table-column label="姓名" min-width="140">
            <template #default="{ row }">
              {{ [row.first_name, row.last_name].filter(Boolean).join(' ') || '--' }}
            </template>
          </el-table-column>
          <el-table-column prop="email" label="邮箱" min-width="180" />
          <el-table-column prop="device_count" label="设备数" min-width="90" />
          <el-table-column prop="measurement_count" label="测量数" min-width="90" />
          <el-table-column prop="unread_alert_count" label="未读告警" min-width="100" />
          <el-table-column label="角色" min-width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_staff ? 'danger' : 'info'">{{ row.is_staff ? '管理' : '普通' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="最近活动" min-width="180">
            <template #default="{ row }">{{ formatDateTime(row.latest_activity_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" min-width="150">
            <template #default="{ row }">
              <el-button link type="primary" @click="viewUser(row.id)">查看该账号</el-button>
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
          <el-form-item label="名">
            <el-input v-model="form.first_name" />
          </el-form-item>
          <el-form-item label="姓">
            <el-input v-model="form.last_name" />
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="form.is_staff">创建为管理员</el-checkbox>
          </el-form-item>
          <el-button type="primary" :loading="submitting" @click="submitCreate">创建账号</el-button>
        </el-form>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useManagementStore } from '../stores/management'
import { formatDateTime } from '../utils/format'

const router = useRouter()
const management = useManagementStore()
const submitting = ref(false)

const form = reactive({
  username: '',
  password: '',
  email: '',
  first_name: '',
  last_name: '',
  is_staff: false,
  is_active: true,
})

async function loadUsers() {
  try {
    await management.loadUsers(true)
  } catch {
    ElMessage.error('账号列表加载失败。')
  }
}

function viewUser(userId: number) {
  management.setSelectedUserId(String(userId))
  router.push('/dashboard')
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
    Object.assign(form, {
      username: '',
      password: '',
      email: '',
      first_name: '',
      last_name: '',
      is_staff: false,
      is_active: true,
    })
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.username?.[0] || '创建账号失败。')
  } finally {
    submitting.value = false
  }
}

onMounted(loadUsers)
</script>
