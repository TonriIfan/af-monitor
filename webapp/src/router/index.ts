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
      path: '/register',
      name: 'register',
      component: () => import('../views/RegisterView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('../layouts/AppLayout.vue'),
      children: [
        { path: '', redirect: '/home' },
        { path: 'home', name: 'home', component: () => import('../views/HomeView.vue') },
        { path: 'device', name: 'device', component: () => import('../views/DeviceView.vue') },
        {
          path: 'measurements',
          name: 'measurements',
          component: () => import('../views/MeasurementsView.vue'),
        },
        { path: 'alerts', name: 'alerts', component: () => import('../views/AlertsView.vue') },
        { path: 'profile', name: 'profile', component: () => import('../views/ProfileView.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/home' },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.public) {
    if (to.path === '/login' && auth.isAuthenticated) {
      return '/home'
    }
    return true
  }
  if (!auth.isAuthenticated) {
    return `/login?redirect=${encodeURIComponent(to.fullPath)}`
  }
  return true
})

export default router
