<template>
  <div class="login-page">
    <section class="login-hero">
      <p class="login-hero__eyebrow">HeartGuard Cardiac Monitoring</p>
      <h1>心脏卫士</h1>
      <p class="login-hero__copy">
        面向心脏健康监测与房颤风险筛查的后台入口，用于串联设备数据、测量结果、告警处置与演示讲解。
      </p>
      <div class="login-hero__grid">
        <div>
          <strong>数据贯通</strong>
          <span>统一查看设备上报、解析字段、风险结果与原始记录</span>
        </div>
        <div>
          <strong>响应及时</strong>
          <span>快速感知异常趋势，便于联调、演示和复盘告警链路</span>
        </div>
        <div>
          <strong>持续扩展</strong>
          <span>为后续接入 App、AI 分析和更多监测场景预留统一入口</span>
        </div>
      </div>
    </section>

    <section class="login-card">
      <div class="login-card__header">
        <p>HeartGuard 控制台</p>
        <h2>进入心脏卫士</h2>
      </div>

      <el-form :model="form" label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="例如：admin" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" show-password type="password" placeholder="请输入密码" />
        </el-form-item>
        <el-button class="login-card__submit" :loading="loading" type="primary" @click="handleLogin">
          登录控制台
        </el-button>
      </el-form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'
import { fetchLoginContext } from '../utils/loginContext'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const loading = ref(false)

const form = reactive({
  username: 'admin',
  password: 'admin123456',
})

async function handleLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码。')
    return
  }
  loading.value = true
  try {
    const loginContext = await fetchLoginContext()
    await auth.login(form.username, form.password, loginContext)
    ElMessage.success('登录成功。')
    router.push((route.query.redirect as string) || '/dashboard')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.non_field_errors?.[0] || '登录失败，请检查账号密码。')
  } finally {
    loading.value = false
  }
}
</script>
