import { useAuthStore } from '@/stores/auth'

export function hasPermission(code: string): boolean {
  return useAuthStore().hasPermission(code)
}
