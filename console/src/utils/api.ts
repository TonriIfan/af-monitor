import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

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
