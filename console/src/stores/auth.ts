import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '../utils/api'

type UserProfile = {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_staff: boolean
  is_superuser: boolean
}

const TOKEN_KEY = 'yf-console-token'
const USER_KEY = 'yf-console-user'

export const useAuthStore = defineStore('auth', () => {
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
  }

  async function login(username: string, password: string) {
    const { data } = await api.post('/auth/login', { username, password })
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
