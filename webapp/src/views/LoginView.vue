<template>
  <div class="login-page">
    <div class="login-hero">
      <div class="login-hero__brand">心脏卫士</div>
      <div class="login-hero__slogan">HeartGuard · 智能房颤监测</div>
    </div>

    <div class="login-card">
      <h2 class="login-card__title">登录</h2>
      <p class="login-card__hint">使用你的账号密码登录后，连接智能戒指开始监测。</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        hide-required-asterisk
        @keyup.enter="submit"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" size="large" placeholder="请输入用户名" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            size="large"
            placeholder="请输入密码"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="submitting"
          class="login-submit"
          @click="submit"
        >
          登录
        </el-button>
      </el-form>

      <div class="login-card__foot">
        <span class="wa-muted">还没有账号？</span>
        <router-link to="/register">立即注册</router-link>
      </div>
    </div>

    <footer class="login-footer wa-muted">
      <p>仅支持 Chrome / Edge 等基于 Blink 内核的浏览器使用蓝牙连接戒指。</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  if (!formRef.value) return
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await auth.login(form.username.trim(), form.password)
    ElMessage.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/home'
    router.replace(redirect || '/home')
  } catch (err: unknown) {
    const msg =
      (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      (err instanceof Error ? err.message : '登录失败，请稍后重试')
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  padding: 0 20px 24px;
}
.login-hero {
  padding: 48px 8px 24px;
}
.login-hero__brand {
  font-size: 28px;
  font-weight: 700;
  color: var(--wa-accent);
  letter-spacing: 0.5px;
}
.login-hero__slogan {
  font-size: 13px;
  color: var(--wa-fg-muted);
  margin-top: 4px;
}
.login-card {
  background: var(--wa-surface);
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 4px 16px rgba(16, 24, 40, 0.06);
}
.login-card__title {
  margin: 0 0 4px;
  font-size: 20px;
}
.login-card__hint {
  margin: 0 0 16px;
  color: var(--wa-fg-muted);
  font-size: 13px;
}
.login-submit {
  width: 100%;
  margin-top: 4px;
}
.login-card__foot {
  margin-top: 14px;
  font-size: 13px;
}
.login-card__foot a {
  margin-left: 4px;
}
.login-footer {
  margin-top: auto;
  padding-top: 20px;
  font-size: 12px;
  text-align: center;
}
</style>
