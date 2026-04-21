import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api, TOKEN_KEY, USER_KEY, SESSION_VERSION_KEY, SESSION_VERSION } from '../utils/api'
import { useAiStore } from './ai'

export type UserProfile = {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  role: 'admin' | 'user'
  is_staff: boolean
  is_superuser: boolean
}

export const useAuthStore = defineStore('auth', () => {
  if (localStorage.getItem(SESSION_VERSION_KEY) !== SESSION_VERSION) {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.setItem(SESSION_VERSION_KEY, SESSION_VERSION)
  }

  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref<UserProfile | null>(
    localStorage.getItem(USER_KEY) ? (JSON.parse(localStorage.getItem(USER_KEY) as string) as UserProfile) : null,
  )

  const isAuthenticated = computed(() => Boolean(token.value))

  function persistSession(nextToken: string, nextUser: UserProfile) {
    token.value = nextToken
    user.value = nextUser
    localStorage.setItem(TOKEN_KEY, nextToken)
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser))
    localStorage.setItem(SESSION_VERSION_KEY, SESSION_VERSION)
  }

  async function login(username: string, password: string) {
    const { data } = await api.post('/auth/login', { username, password })
    persistSession(data.token, data.user)
    return data
  }

  async function register(payload: {
    username: string
    password: string
    first_name?: string
    profile?: { phone?: string; full_name?: string; age?: number; sex?: string; notes?: string }
  }) {
    const { data } = await api.post('/auth/register', payload)
    persistSession(data.token, data.user)
    return data
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    try {
      useAiStore().reset()
    } catch {
      // Pinia 未初始化时忽略（例如在 SSR 场景或 store 尚未挂载）
    }
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    register,
    logout,
  }
})
