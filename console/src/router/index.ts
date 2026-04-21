import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('../layouts/ConsoleLayout.vue'),
      children: [
        { path: '', redirect: '/measurements' },
        { path: 'accounts', name: 'accounts', component: () => import('../views/AccountsView.vue') },
        { path: 'ai-settings', name: 'ai-settings', component: () => import('../views/AiSettingsView.vue') },
        { path: 'dashboard', name: 'dashboard', component: () => import('../views/DashboardView.vue') },
        { path: 'packet-test', name: 'packet-test', component: () => import('../views/PacketTestView.vue') },
        { path: 'devices', name: 'devices', component: () => import('../views/DevicesView.vue') },
        { path: 'measurements', name: 'measurements', component: () => import('../views/MeasurementsView.vue') },
        { path: 'alerts', name: 'alerts', component: () => import('../views/AlertsView.vue') },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.public) {
    if (to.path === '/login' && auth.isAuthenticated) {
      return auth.user?.role === 'admin' ? '/dashboard' : '/measurements'
    }
    return true
  }
  if (!auth.isAuthenticated) {
    return `/login?redirect=${encodeURIComponent(to.fullPath)}`
  }
  if (to.path === '/dashboard' && auth.user?.role !== 'admin') {
    return '/measurements'
  }
  if (to.path === '/packet-test' && auth.user?.role !== 'admin') {
    return '/measurements'
  }
  if (to.path === '/ai-settings' && auth.user?.role !== 'admin') {
    return '/measurements'
  }
  if (to.path === '/ai-lab' && auth.user?.role !== 'admin') {
    return '/measurements'
  }
  if (to.path === '/accounts' && auth.user?.role !== 'admin') {
    return '/measurements'
  }
  return true
})

export default router
