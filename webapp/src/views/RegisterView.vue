<template>
  <div class="register-page">
    <div class="register-hero">
      <div class="register-hero__brand">心脏卫士</div>
      <div class="register-hero__slogan">HeartGuard · 智能房颤监测</div>
    </div>

    <div class="register-card">
      <h2 class="register-card__title">创建账号</h2>
      <p class="register-card__hint">注册后即可连接智能戒指，开始心率监测。</p>

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
            placeholder="请输入密码（至少8位）"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            size="large"
            placeholder="请再次输入密码"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="姓名（选填）" prop="first_name">
          <el-input v-model="form.first_name" size="large" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="手机（选填）" prop="phone">
          <el-input v-model="form.phone" size="large" placeholder="请输入手机号" />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="submitting"
          class="register-submit"
          @click="submit"
        >
          注册
        </el-button>
      </el-form>

      <div class="register-card__foot">
        <span class="wa-muted">已有账号？</span>
        <router-link to="/login">立即登录</router-link>
      </div>
    </div>

    <footer class="register-footer wa-muted">
      <p>仅支持 Chrome / Edge 等基于 Blink 内核的浏览器使用蓝牙连接戒指。</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  first_name: '',
  phone: '',
})

const validateConfirmPassword = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '用户名长度在 3 到 32 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码长度至少8位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

async function submit() {
  if (!formRef.value) return
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return

  submitting.value = true
  try {
    await auth.register({
      username: form.username.trim(),
      password: form.password,
      first_name: form.first_name.trim(),
      profile: form.phone ? { phone: form.phone.trim() } : undefined,
    })
    ElMessage.success('注册成功')
    router.replace('/home')
  } catch (err: unknown) {
    const msg =
      (err as { response?: { data?: Record<string, string[]> } })?.response?.data
        ? Object.values((err as { response?: { data?: Record<string, string[]> } }).response?.data || {}).flat()[0]
        : (err instanceof Error ? err.message : '注册失败，请稍后重试')
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  padding: 0 20px 24px;
}
.register-hero {
  padding: 48px 8px 24px;
}
.register-hero__brand {
  font-size: 28px;
  font-weight: 700;
  color: var(--wa-accent);
  letter-spacing: 0.5px;
}
.register-hero__slogan {
  font-size: 13px;
  color: var(--wa-fg-muted);
  margin-top: 4px;
}
.register-card {
  background: var(--wa-surface);
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 4px 16px rgba(16, 24, 40, 0.06);
}
.register-card__title {
  margin: 0 0 4px;
  font-size: 20px;
}
.register-card__hint {
  margin: 0 0 16px;
  color: var(--wa-fg-muted);
  font-size: 13px;
}
.register-submit {
  width: 100%;
  margin-top: 4px;
}
.register-card__foot {
  margin-top: 14px;
  font-size: 13px;
}
.register-card__foot a {
  margin-left: 4px;
}
.register-footer {
  margin-top: auto;
  padding-top: 20px;
  font-size: 12px;
  text-align: center;
}
</style>
