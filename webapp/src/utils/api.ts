import axios from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

export const TOKEN_KEY = 'yf-webapp-token'
export const USER_KEY = 'yf-webapp-user'
export const SESSION_VERSION_KEY = 'yf-webapp-session-version'
export const SESSION_VERSION = '1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
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
