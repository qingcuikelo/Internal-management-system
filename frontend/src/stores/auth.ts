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
