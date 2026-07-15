# Slice 6: Frontend SPA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-grade Vue3+TS+Pinia+Element Plus frontend SPA with login/auth, RBAC menu+routing, and full CRUD pages for all 5 backend domains plus reports.

**Architecture:** Vite project scaffolded under `frontend/`. Axios client with token-refresh interceptor. Pinia auth store. Vue Router with `beforeEach` guard checking permissions. Element Plus with Chinese locale. Pages organized by domain under `views/`. API layer in `api/` mirroring backend routes. Stores in `stores/`. Reusable pagination/status-tag components.

**Tech Stack:** Vue 3.4+, vue-router 4.3+, Pinia 2.1+, Axios 1.7+, Element Plus 2.8+, @element-plus/icons-vue, TypeScript, Vite 5.

## Global Constraints

- All frontend code under `frontend/` directory at repo root. Run `npm` from there.
- Use Element Plus Chinese locale. Style: clean business admin, consistent spacing, no custom themes — default Element Plus theme.
- API base: `/api/v1` (Vite dev proxy to `http://localhost:8000`). All API calls go through the Axios client.
- Token storage: localStorage keys `access_token` and `refresh_token`.
- Route permissions via `meta.permission` string. Guard checks `authStore.permissions.has(route.meta.permission)`.
- `npm run build` must succeed with 0 errors.
- No frontend tests in this slice (deferred). Verification by build success + visual check.
- Follow Vue3 Composition API (`<script setup lang="ts">`) consistently.

---

### Task 1: Scaffold + Auth + Layout + Router Foundation

**Files:** ~15 files creating the entire project skeleton, auth flow, and navigation framework.

**Goal:** A working login flow + sidebar layout + protected routing. After this task, you can login, see a sidebar with menu items filtered by role, and navigate between placeholder pages.

- [ ] **Step 1: Scaffold Vite project**

```bash
cd e:/it/claude_code/ai_projects/Internal-management-system
npm create vite@latest frontend -- --template vue-ts
cd frontend
npm install
npm install vue-router@4 pinia@2 axios@1 element-plus@2 @element-plus/icons-vue
```

- [ ] **Step 2: Configure vite.config.ts**

Edit `frontend/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
```

- [ ] **Step 3: Create src/main.ts**

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.mount('#app')
```

- [ ] **Step 4: Create src/api/client.ts (Axios with interceptors)**

```typescript
import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({ baseURL: '/api/v1' })

// Request: attach token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Response: unwrap envelope, refresh on 401
let isRefreshing = false
let failedQueue: Array<{ resolve: Function; reject: Function }> = []

function processQueue(error: any, token: string | null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else resolve(token)
  })
  failedQueue = []
}

client.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body.code === 0) return body.data
    if (body.code === 1001) {
      // Will be handled in error interceptor logic below — actually this path
      // is when the server returns 200 with code=1001, which our backend doesn't do
      // (it returns 401 HTTP status). Fall through.
    }
    return Promise.reject(new Error(body.message || 'Request failed'))
  },
  async (error) => {
    const originalRequest = error.config
    const status = error.response?.status
    const body = error.response?.data

    // Handle 401: try refresh
    if (status === 401 && body?.code === 1001 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return client(originalRequest)
        })
      }
      originalRequest._retry = true
      isRefreshing = true
      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        isRefreshing = false
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(error)
      }
      try {
        const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
        const newToken = data.data.access_token
        const newRefresh = data.data.refresh_token
        localStorage.setItem('access_token', newToken)
        localStorage.setItem('refresh_token', newRefresh)
        processQueue(null, newToken)
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return client(originalRequest)
      } catch (e) {
        processQueue(e, null)
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(e)
      } finally {
        isRefreshing = false
      }
    }

    // Show error message for non-401 errors
    if (status !== 401) {
      ElMessage.error(body?.message || error.message || 'Network error')
    }
    return Promise.reject(error)
  },
)

export default client
```

- [ ] **Step 5: Create API modules (auth.ts, plus stub files)**

Create `src/api/auth.ts`:
```typescript
import client from './client'

export function login(username: string, password: string) {
  return client.post('/auth/login', { username, password })
}
export function refresh(refreshToken: string) {
  return client.post('/auth/refresh', { refresh_token: refreshToken })
}
export function logout() {
  return client.post('/auth/logout')
}
export function me() {
  return client.get('/auth/me')
}
```

Create stub files `src/api/departments.ts`, `employees.ts`, `workstations.ts`, `devices.ts`, `users.ts`, `roles.ts`, `dicts.ts`, `reports.ts`, `tasks.ts` — each with a comment `// TODO: implement in later tasks`.

- [ ] **Step 6: Create auth store**

Create `src/stores/auth.ts`:
```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '@/api/auth'
import router from '@/router'

interface UserInfo {
  id: string; username: string; role: string;
  employee_id: string | null; permissions: string[];
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const user = ref<UserInfo | null>(null)
  const permissions = computed(() => new Set(user.value?.permissions ?? []))

  const isLoggedIn = computed(() => !!token.value)

  function hasPermission(code: string): boolean {
    return permissions.value.has(code)
  }

  async function login(username: string, password: string) {
    const data: any = await authApi.login(username, password)
    token.value = data.access_token
    refreshToken.value = data.refresh_token
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    await fetchUser()
  }

  async function fetchUser() {
    const data: any = await authApi.me()
    user.value = data
  }

  async function doLogout() {
    try { await authApi.logout() } catch {}
    clearAuth()
    router.push('/login')
  }

  function clearAuth() {
    token.value = null
    refreshToken.value = null
    user.value = null
    localStorage.clear()
  }

  return { token, refreshToken, user, permissions, isLoggedIn, hasPermission, login, fetchUser, doLogout, clearAuth }
})
```

- [ ] **Step 7: Create router**

Create `src/router/index.ts`:
```typescript
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
```

- [ ] **Step 8: Create MainLayout with sidebar**

Create `src/layouts/MainLayout.vue`:
```vue
<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar">
      <div class="logo">{{ collapsed ? 'IMS' : '企业内部管理系统' }}</div>
      <el-menu
        :default-active="route.path"
        :collapse="collapsed"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </el-menu-item>

        <template v-for="item in visibleMenus" :key="item.index">
          <el-sub-menu v-if="item.children" :index="item.index">
            <template #title>
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </template>
            <el-menu-item v-for="child in item.children" :key="child.index" :index="child.index">
              {{ child.title }}
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.index">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-button @click="collapsed = !collapsed" :icon="collapsed ? Expand : Fold" text />
        </div>
        <div class="header-right">
          <span class="user-info">{{ auth.user?.username }} ({{ auth.user?.role }})</span>
          <el-button @click="auth.doLogout()" text type="danger">退出</el-button>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { HomeFilled, Expand, Fold, OfficeBuilding, User, Monitor, Cpu, Setting, DataAnalysis } from '@element-plus/icons-vue'

const route = useRoute()
const auth = useAuthStore()
const collapsed = ref(false)

interface MenuItem {
  index: string
  title: string
  icon: any
  permission?: string
  children?: { index: string; title: string; permission?: string }[]
}

const allMenus: MenuItem[] = [
  { index: '/departments', title: '部门管理', icon: OfficeBuilding, permission: 'department:view' },
  {
    index: 'employees-group', title: '员工管理', icon: User,
    children: [
      { index: '/employees', title: '员工列表', permission: 'employee:view' },
    ],
  },
  { index: '/workstations', title: '工位管理', icon: Monitor, permission: 'workstation:view' },
  { index: '/devices', title: '设备管理', icon: Cpu, permission: 'device:view' },
  { index: '/reports', title: '报表', icon: DataAnalysis, permission: 'report:view' },
  {
    index: 'system-group', title: '系统管理', icon: Setting,
    children: [
      { index: '/system/users', title: '账号管理', permission: 'system:user' },
      { index: '/system/roles', title: '角色权限', permission: 'system:role' },
      { index: '/system/dicts', title: '数据字典', permission: 'system:dict' },
      { index: '/system/logs', title: '操作日志', permission: 'system:log' },
    ],
  },
]

const visibleMenus = computed(() => {
  return allMenus
    .map((item) => {
      if (item.children) {
        const visible = item.children.filter((c) => auth.hasPermission(c.permission!))
        if (visible.length === 0) return null
        return { ...item, children: visible }
      }
      if (item.permission && !auth.hasPermission(item.permission)) return null
      return item
    })
    .filter(Boolean) as MenuItem[]
})
</script>

<style scoped>
.layout { height: 100vh; }
.sidebar { background-color: #304156; overflow-y: auto; }
.logo { height: 60px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; font-weight: bold; white-space: nowrap; overflow: hidden; }
.header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e6e6e6; background: #fff; height: 60px; }
.header-left, .header-right { display: flex; align-items: center; gap: 12px; }
.user-info { color: #606266; }
.el-menu { border-right: none; }
.el-main { background: #f0f2f5; padding: 20px; }
</style>
```

- [ ] **Step 9: Create Login view**

Create `src/views/Login.vue`:
```vue
<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2>企业内部管理系统</h2>
      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" prefix-icon="Lock" show-password @keyup.enter="handleLogin" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleLogin" style="width: 100%">登录</el-button>
        </el-form-item>
        <p v-if="error" class="error">{{ error }}</p>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const router = useRouter()
const auth = useAuthStore()

async function handleLogin() {
  if (!username.value || !password.value) return
  loading.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch (e: any) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { display: flex; align-items: center; justify-content: center; height: 100vh; background: #f0f2f5; }
.login-card { width: 400px; }
.login-card h2 { text-align: center; margin-bottom: 24px; }
.error { color: var(--el-color-danger); text-align: center; }
</style>
```

- [ ] **Step 10: Create placeholder pages**

Create minimal Vue SFCs for: `views/dashboard/Index.vue`, `views/Forbidden.vue`, `views/departments/Index.vue`, `views/employees/Index.vue`, `views/employees/Detail.vue`, `views/workstations/Index.vue`, `views/workstations/Detail.vue`, `views/devices/Index.vue`, `views/devices/Detail.vue`, `views/system/Users.vue`, `views/system/Roles.vue`, `views/system/Dicts.vue`, `views/system/Logs.vue`, `views/reports/Index.vue`. Each has a `<template><div>Page Name</div></template>`.

Update `App.vue` to `<router-view />`.

- [ ] **Step 11: Verify build**

Run `cd frontend && npm run build`. Fix any TypeScript errors. The build must succeed.

- [ ] **Step 12: Commit**

```bash
cd e:/it/claude_code/ai_projects/Internal-management-system
git add frontend/
git commit -m "feat(frontend): Vite+Vue3 scaffold, auth flow, sidebar layout, router with permission guards"
```

---

### Task 2: Department + Employee Pages

**Files:** Modify `src/api/departments.ts`, `src/api/employees.ts`, `src/views/departments/Index.vue`, `src/views/employees/Index.vue`, `src/views/employees/Detail.vue`, `src/components/Pagination.vue`.

**Goal:** Fully functional department tree with CRUD dialogs, and employee list with filters/pagination/CRUD/resign/import-export.

- [ ] **Step 1: Implement departments API**

Implement `src/api/departments.ts`:
```typescript
import client from './client'

export function getTree() { return client.get('/departments/tree') }
export function getList() { return client.get('/departments') }
export function createDept(data: any) { return client.post('/departments', data) }
export function updateDept(id: string, data: any) { return client.put(`/departments/${id}`, data) }
export function deleteDept(id: string) { return client.delete(`/departments/${id}`) }
```

- [ ] **Step 2: Implement departments page**

Build a full department tree view with:
- `el-tree` with `node-key="id"`, `default-expand-all`
- Node label shows department name + status tag
- Hover shows edit/delete/add-child buttons (render via scoped slot)
- `el-dialog` for create/edit form (name, parent select-tree, manager, sort_order, status)
- Delete confirmation dialog, handle 3002 errors with specific message

- [ ] **Step 3: Implement employees API**

```typescript
import client from './client'

export function listEmployees(params: any) { return client.get('/employees', { params }) }
export function getEmployee(id: string) { return client.get(`/employees/${id}`) }
export function createEmployee(data: any) { return client.post('/employees', data) }
export function updateEmployee(id: string, data: any) { return client.put(`/employees/${id}`, data) }
export function deleteEmployee(id: string) { return client.delete(`/employees/${id}`) }
export function resignEmployee(id: string, data: any) { return client.post(`/employees/${id}/resign`, data) }
export function batchDepartment(data: any) { return client.patch('/employees/batch-department', data) }
export function importEmployees(file: File) { const fd = new FormData(); fd.append('file', file); return client.post('/employees/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } }) }
export function exportEmployees(data: any) { return client.post('/employees/export', data) }
```

- [ ] **Step 4: Implement employees list page**

Full employee list with:
- Filter bar: keyword input, department select, status select, search/reset buttons
- `el-table` with columns: 工号, 姓名, 部门, 职位, 性别, 状态, 操作(查看/编辑/删除/离职)
- Pagination component
- Batch department change: select rows + target department dropdown
- Import button → upload Excel dialog → task polling → result summary
- Export button → post filter → wait task → download link
- `el-dialog` for create/edit (employee form with validation)
- Delete confirmation
- Resign: confirmation dialog → show result (released workstations, returned devices, account disabled)

- [ ] **Step 5: Implement employee detail page**

Display employee info + current workstation + current devices. Route `/employees/:id`.

- [ ] **Step 6: Create Pagination component**

Create `src/components/Pagination.vue` wrapping `el-pagination` with v-model:current-page and v-model:page-size, emitting update events.

- [ ] **Step 7: Build + commit**

```bash
cd frontend && npm run build
git add frontend/src/api/departments.ts frontend/src/api/employees.ts frontend/src/views/departments/ frontend/src/views/employees/ frontend/src/components/Pagination.vue
git commit -m "feat(frontend): department tree + employee CRUD, import/export, resign"
```

---

### Task 3: Workstation + Device Pages

**Files:** Modify `src/api/workstations.ts`, `src/api/devices.ts`, workstation views, device views.

**Goal:** Full workstation and device management pages — lists with filters, detail/history, all state transitions (assign/release/checkout/return/repair/scrap) with optimistic lock handling.

- [ ] **Step 1: Implement workstation API + list page**
- **API**: list, get, create, update, assign, release, batchRelease, setStatus, getHistory
- **List**: filter by code/location/type/status/employee, table with actions
- **Detail**: full info + assign dialog (employee select, date, version) + 3001 conflict handling + history timeline
- **Status management**: reserve/disable buttons, batch release button

- [ ] **Step 2: Implement device API + pages**
- **API**: list, get, create, update, checkout, return, repair, scrap, getHistory
- **List**: filter by asset_code/type/status/employee, table with actions
- **Detail**: full info + checkout dialog (employee, date, version) + return/repair/scrap buttons + 3001/3007 error handling + history
- **Create (register)**: form with asset_code, type, brand, model, serial, specs, purchase_date, warranty_expire

- [ ] **Step 3: Add StatusTag component**

Create `src/components/StatusTag.vue` — maps backend status integers to `el-tag` with appropriate `type` (success/warning/danger/info) using dict or constant lookups.

- [ ] **Step 4: Build + commit**

```bash
cd frontend && npm run build
git add frontend/src/api/workstations.ts frontend/src/api/devices.ts frontend/src/views/workstations/ frontend/src/views/devices/ frontend/src/components/StatusTag.vue
git commit -m "feat(frontend): workstation + device pages with state transitions"
```

---

### Task 4: System Management + Reports Pages

**Files:** Modify `src/api/users.ts`, `roles.ts`, `dicts.ts`, `reports.ts`, `tasks.ts`, system views, reports view.

**Goal:** All system management pages (super_admin only) + reports page. Dicts with type cache. Roles with permission checkbox matrix.

- [ ] **Step 1: Implement system management pages**
- **Users** (`system/Users.vue`): table with filters (username/role/status), create dialog (role+employee+password), edit, delete, enable/disable toggle, reset password dialog.
- **Roles** (`system/Roles.vue`): role list, create/edit dialogs, delete guard, permission assignment dialog (`el-checkbox-group` grouped by module, overwrite submit). Show `is_builtin` badge.
- **Dicts** (`system/Dicts.vue`): left panel (type list), right panel (items of selected type, editable table with add/delete/save).
- **Logs** (`system/Logs.vue`): `el-table` with filters (user/module/action start/end date), read-only, paginated.

- [ ] **Step 2: Implement reports page**

`views/reports/Index.vue` with 4 `el-tab-pane`s:
- **员工资产概览**: employee select → display workstation + devices cards
- **闲置资产**: two stat cards (idle workstations, idle devices). dept_manager gets "—" dash
- **部门设备统计**: table of dept + device count
- **保修到期**: days input + table of expiring devices sorted by warranty date

- [ ] **Step 3: Implement dict store**

Create `src/stores/dict.ts`:
```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getByType } from '@/api/dicts'

export const useDictStore = defineStore('dict', () => {
  const cache = ref<Map<string, any[]>>(new Map())

  async function fetchType(type: string) {
    if (cache.value.has(type)) return cache.value.get(type)
    const res: any = await getByType(type)
    cache.value.set(type, res.items)
    return res.items
  }

  function getOptions(type: string) {
    return (cache.value.get(type) ?? []).map((i: any) => ({ value: i.dict_key, label: i.dict_label }))
  }

  return { cache, fetchType, getOptions }
})
```

- [ ] **Step 4: Implement remaining API modules**

Fill in `api/dicts.ts`, `api/users.ts`, `api/roles.ts`, `api/reports.ts`, `api/tasks.ts` — each mirroring the backend endpoints.

- [ ] **Step 5: Build + commit**

```bash
cd frontend && npm run build
git add frontend/src/ views/system/ views/reports/ stores/dict.ts api/
git commit -m "feat(frontend): system management + reports pages, dict cache store"
```

---

### Task 5: Integration, Polish, Build Green

**Files:** Cross-cutting fixes, CSS polish, `utils/`, final build verification.

**Goal:** `npm run build` succeeds with 0 errors/warnings. Polish any rough UI edges. Ensure all pages are discoverable via sidebar and functional with real backend data.

- [ ] **Step 1: Add utils**

Create `src/utils/permission.ts`:
```typescript
import { useAuthStore } from '@/stores/auth'
export function hasPermission(code: string): boolean {
  return useAuthStore().hasPermission(code)
}
```

Create `src/utils/format.ts`:
```typescript
export const genderLabel: Record<number, string> = { 0: '未知', 1: '男', 2: '女' }
export function formatDate(d: string | null) { if (!d) return ''; return new Date(d).toLocaleDateString('zh-CN') }
export function formatDateTime(d: string | null) { if (!d) return ''; return new Date(d).toLocaleString('zh-CN') }
```

- [ ] **Step 2: Consistency sweep**

- Ensure all API error paths show user-friendly messages (the Axios interceptor handles most; catch blocks should handle specific 3001/3007/3002 messages).
- All tables have loading states, empty states (`el-empty`), and error states.
- All forms have validation rules (required fields, format checks).
- Optimistic lock: assign/checkout forms carry `version`; on 3001 error, show "已被占用，请刷新后重试" and allow re-fetch.
- All dialogs have confirm/cancel buttons with proper loading states.

- [ ] **Step 3: Final build**

```bash
cd frontend && npm run build
```

Fix any TS errors or build warnings. The `dist/` directory should be created.

- [ ] **Step 4: Commit**

```bash
cd frontend && git add -A
git commit -m "chore(frontend): utils, polish, final build green"
```

---

## Self-Review Notes (author)

- **Frontend is a greenfield project** — Task 1 scaffolds from scratch. Subagents must run `npm create vite` and install deps before writing code.
- **No frontend test framework** by design (deferred). Build success is the gate.
- **API types**: This plan doesn't define TypeScript interfaces for API responses — subagents should derive shapes from the backend schema docs and use `any` where needed for speed.
- **Pattern consistency**: All pages use `<script setup lang="ts">`, Composition API, `el-table` + `el-pagination` for lists, `el-dialog` + `el-form` for create/edit.
- **Permission guard**: The `beforeEach` guard is the single enforcement point; menu visibility is cosmetic (backend also enforces).
