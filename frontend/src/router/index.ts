import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const NotFound = { template: '<div class="p-8 text-center text-gray-500">403 Forbidden</div>' }

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      component: () => import('../views/Login.vue'),
    },
    {
      path: '/dashboard',
      component: () => import('../views/Dashboard.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/strategy',
      component: () => import('../views/StrategyLab.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/admin',
      // Component is resolved dynamically at navigation time.
      // Non-admin users get a lightweight stub - the AdminConfig chunk is never fetched.
      component: () => {
        const auth = useAuthStore()
        if (!auth.isAdmin) {
          return Promise.resolve(NotFound)
        }
        return import('../views/AdminConfig.vue')
      },
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/',
      redirect: '/dashboard',
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return '/login'
  }

  // Non-admin users are redirected before the admin component ever loads
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return '/dashboard'
  }
})

export default router
