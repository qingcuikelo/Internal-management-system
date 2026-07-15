import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      { path: '', name: 'Dashboard', component: () => import('@/views/dashboard/Index.vue') },
      { path: 'departments', name: 'Departments', component: () => import('@/views/departments/Index.vue'), meta: { permission: 'department:view' } },
      { path: 'employees', name: 'Employees', component: () => import('@/views/employees/Index.vue'), meta: { permission: 'employee:view' } },
      { path: 'employees/:id', name: 'EmployeeDetail', component: () => import('@/views/employees/Detail.vue'), meta: { permission: 'employee:view' } },
      { path: 'workstations', name: 'Workstations', component: () => import('@/views/workstations/Index.vue'), meta: { permission: 'workstation:view' } },
      { path: 'workstations/:id', name: 'WorkstationDetail', component: () => import('@/views/workstations/Detail.vue'), meta: { permission: 'workstation:view' } },
      { path: 'devices', name: 'Devices', component: () => import('@/views/devices/Index.vue'), meta: { permission: 'device:view' } },
      { path: 'devices/:id', name: 'DeviceDetail', component: () => import('@/views/devices/Detail.vue'), meta: { permission: 'device:view' } },
      { path: 'system/users', name: 'SystemUsers', component: () => import('@/views/system/Users.vue'), meta: { permission: 'system:user' } },
      { path: 'system/roles', name: 'SystemRoles', component: () => import('@/views/system/Roles.vue'), meta: { permission: 'system:role' } },
      { path: 'system/dicts', name: 'SystemDicts', component: () => import('@/views/system/Dicts.vue'), meta: { permission: 'system:dict' } },
      { path: 'system/logs', name: 'SystemLogs', component: () => import('@/views/system/Logs.vue'), meta: { permission: 'system:log' } },
      { path: 'reports', name: 'Reports', component: () => import('@/views/reports/Index.vue'), meta: { permission: 'report:view' } },
      { path: '403', name: 'Forbidden', component: () => import('@/views/Forbidden.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

// Auth guard
import { useAuthStore } from '@/stores/auth'

router.beforeEach(async (to, _from, next) => {
  const auth = useAuthStore()

  // Login page: redirect to home if already logged in
  if (to.meta.guest) {
    if (auth.isLoggedIn) return next('/')
    return next()
  }

  // Protected pages: redirect to login if not authenticated
  if (!auth.isLoggedIn) return next('/login')

  // Fetch user info on first load
  if (!auth.user) {
    try {
      await auth.fetchUser()
    } catch {
      auth.clearAuth()
      return next('/login')
    }
  }

  // Permission check
  const perm = to.meta.permission as string | undefined
  if (perm && !auth.hasPermission(perm)) return next('/403')

  next()
})

export default router
