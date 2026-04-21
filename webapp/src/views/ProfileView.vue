<template>
  <div class="wa-page">
    <div class="wa-page-title">我的</div>

    <div class="wa-card profile-hero">
      <el-avatar :size="56">
        <el-icon :size="32"><User /></el-icon>
      </el-avatar>
      <div>
        <div class="profile-hero__name">{{ auth.user?.username || '--' }}</div>
        <div class="wa-muted" style="font-size: 12px;">
          {{ auth.user?.role === 'admin' ? '管理员账号' : '普通用户' }}
          <span v-if="auth.user?.email"> · {{ auth.user.email }}</span>
        </div>
      </div>
    </div>

    <div class="wa-card profile-info">
      <dl class="kv">
        <dt>用户 ID</dt>
        <dd>{{ auth.user?.id ?? '--' }}</dd>
        <dt>姓名</dt>
        <dd>{{ fullName || '未填写' }}</dd>
        <dt>当前环境</dt>
        <dd>
          <el-tag size="small" :type="supported ? 'success' : 'danger'">
            {{ supported ? '支持 Web Bluetooth' : '不支持 Web Bluetooth' }}
          </el-tag>
        </dd>
      </dl>
    </div>

    <div class="wa-card">
      <div class="wa-card__title">关于</div>
      <p class="wa-muted" style="font-size: 13px; margin: 0 0 6px;">
        心脏卫士（HeartGuard）是一款面向日常心律监测的 Web 系统。本页面为用户端，
        通过 Web Bluetooth API 直接连接智能戒指；管理员请访问 Console 控制台。
      </p>
      <p class="wa-muted" style="font-size: 12px; margin: 0;">
        本系统数据仅作健康参考，不能替代医疗诊断。如出现持续不适请及时就医。
      </p>
    </div>

    <el-button
      type="danger"
      plain
      size="large"
      style="width: 100%; margin-top: 12px;"
      @click="onLogout"
    >
      退出登录
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { User } from '@element-plus/icons-vue'

import { useAuthStore } from '../stores/auth'
import { useBleStore } from '../stores/ble'
import { isWebBluetoothSupported } from '../utils/ble'

const auth = useAuthStore()
const ble = useBleStore()
const router = useRouter()

const supported = isWebBluetoothSupported()

const fullName = computed(() => {
  const u = auth.user
  if (!u) return ''
  return [u.last_name, u.first_name].filter(Boolean).join('')
})

async function onLogout() {
  try {
    await ElMessageBox.confirm('确认退出登录？', '提示', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  if (ble.isConnected) {
    await ble.disconnect().catch(() => undefined)
  }
  auth.logout()
  ElMessage.success('已退出')
  router.replace('/login')
}
</script>

<style scoped>
.profile-hero {
  display: flex;
  gap: 14px;
  align-items: center;
}
.profile-hero__name {
  font-size: 18px;
  font-weight: 600;
}
.kv {
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 8px 12px;
  font-size: 13px;
  margin: 0;
}
.kv dt {
  color: var(--wa-fg-muted);
}
.kv dd {
  margin: 0;
}
</style>
