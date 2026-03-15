<template>
  <div class="login-page">
    <section class="login-hero">
      <p class="login-hero__eyebrow">Atrial Fibrillation Monitoring</p>
      <h1>一个后端控制台，串起设备、解析、预警和论文演示。</h1>
      <p class="login-hero__copy">
        这个界面不替代你的移动端，而是为后端展示提供一个清晰、可讲述、可验收的操作面板。
      </p>
      <div class="login-hero__grid">
        <div>
          <strong>结构化</strong>
          <span>原始包、解析字段、风险结果统一呈现</span>
        </div>
        <div>
          <strong>即时性</strong>
          <span>适合课堂答辩和现场演示告警链路</span>
        </div>
        <div>
          <strong>可扩展</strong>
          <span>后续可继续接 App 端与 open-health 二期</span>
        </div>
      </div>
    </section>

    <section class="login-card">
      <div class="login-card__header">
        <p>控制台登录</p>
        <h2>进入 Rhythm Console</h2>
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
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功。')
    router.push((route.query.redirect as string) || '/dashboard')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.non_field_errors?.[0] || '登录失败，请检查账号密码。')
  } finally {
    loading.value = false
  }
}
</script>
