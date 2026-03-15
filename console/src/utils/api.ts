import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'
const TOKEN_KEY = 'yf-console-token'
const USER_KEY = 'yf-console-user'

export const api = axios.create({
  baseURL,
  timeout: 10000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('yf-console-token')
  if (token) {
    config.headers.Authorization = `Token ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)

      const currentPath = window.location.pathname + window.location.search
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`
      }
    }
    return Promise.reject(error)
  },
)
