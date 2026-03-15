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
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', name: 'dashboard', component: () => import('../views/DashboardView.vue') },
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
      return '/dashboard'
    }
    return true
  }
  if (!auth.isAuthenticated) {
    return `/login?redirect=${encodeURIComponent(to.fullPath)}`
  }
  return true
})

export default router
