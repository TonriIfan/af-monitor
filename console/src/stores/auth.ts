import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '../utils/api'
import type { LoginContext } from '../utils/loginContext'

type UserProfile = {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  role: 'admin' | 'user'
  is_staff: boolean
  is_superuser: boolean
  last_login_ip: string | null
  last_login_location: {
    country: string
    region: string
    city: string
    latitude: number | null
    longitude: number | null
    label: string
    resolved: boolean
  }
}

const TOKEN_KEY = 'yf-console-token'
const USER_KEY = 'yf-console-user'
const SESSION_VERSION_KEY = 'yf-console-session-version'
const SESSION_VERSION = '2'

export const useAuthStore = defineStore('auth', () => {
  if (localStorage.getItem(SESSION_VERSION_KEY) !== SESSION_VERSION) {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.setItem(SESSION_VERSION_KEY, SESSION_VERSION)
  }

  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref<UserProfile | null>(
    localStorage.getItem(USER_KEY) ? JSON.parse(localStorage.getItem(USER_KEY) as string) : null,
  )

  const isAuthenticated = computed(() => Boolean(token.value))

  function persistSession(nextToken: string, nextUser: UserProfile) {
    token.value = nextToken
    user.value = nextUser
    localStorage.setItem(TOKEN_KEY, nextToken)
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser))
    localStorage.setItem(SESSION_VERSION_KEY, SESSION_VERSION)
  }

  async function login(username: string, password: string, loginContext?: LoginContext | null) {
    const { data } = await api.post('/auth/console-login', {
      username,
      password,
      ...(loginContext ? { login_context: loginContext } : {}),
    })
    persistSession(data.token, data.user)
    return data
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    logout,
  }
})
