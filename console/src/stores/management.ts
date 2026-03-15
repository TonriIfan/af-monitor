import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '../utils/api'

export type ManagedUser = {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  role: 'admin' | 'user'
  is_active: boolean
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
  device_count: number
  measurement_count: number
  alert_count: number
  unread_alert_count: number
  latest_activity_at: string | null
  date_joined: string
}

const SELECTED_SCOPE_KEY = 'yf-console-scope-user-id'

export const useManagementStore = defineStore('management', () => {
  const users = ref<ManagedUser[]>([])
  const selectedUserId = ref<string>(localStorage.getItem(SELECTED_SCOPE_KEY) || '')
  const loaded = ref(false)

  const selectedUser = computed(() =>
    users.value.find((item) => String(item.id) === selectedUserId.value) || null,
  )

  async function loadUsers(force = false) {
    if (loaded.value && !force) return users.value
    const { data } = await api.get('/auth/users')
    users.value = data
    loaded.value = true
    return data
  }

  function setSelectedUserId(value: string) {
    selectedUserId.value = value
    if (value) {
      localStorage.setItem(SELECTED_SCOPE_KEY, value)
    } else {
      localStorage.removeItem(SELECTED_SCOPE_KEY)
    }
  }

  function scopeParams() {
    return selectedUserId.value ? { user_id: selectedUserId.value } : {}
  }

  async function createUser(payload: Record<string, unknown>) {
    const { data } = await api.post('/auth/users', payload)
    await loadUsers(true)
    return data
  }

  function reset() {
    users.value = []
    loaded.value = false
    setSelectedUserId('')
  }

  return {
    users,
    loaded,
    selectedUserId,
    selectedUser,
    loadUsers,
    setSelectedUserId,
    scopeParams,
    createUser,
    reset,
  }
})
