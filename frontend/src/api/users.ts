import client from './client'

export interface UserItem {
  id: string
  username: string
  role_id: string
  role_code: string
  role_name: string
  employee_id: string | null
  employee_name: string | null
  status: number
  last_login_at: string | null
  created_at: string
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
}

export function listUsers(params: Record<string, any>) {
  return client.get<any, PaginatedResult<UserItem>>('/users', { params })
}

export function getUser(id: string) {
  return client.get<any, UserItem>(`/users/${id}`)
}

export function createUser(data: Record<string, any>) {
  return client.post('/users', data)
}

export function updateUser(id: string, data: Record<string, any>) {
  return client.put(`/users/${id}`, data)
}

export function deleteUser(id: string) {
  return client.delete(`/users/${id}`)
}

export function updateUserStatus(id: string, data: { status: number }) {
  return client.patch(`/users/${id}/status`, data)
}

export function resetPassword(id: string, data: { new_password: string }) {
  return client.post(`/users/${id}/reset-password`, data)
}
