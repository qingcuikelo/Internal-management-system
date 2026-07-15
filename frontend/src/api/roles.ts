import client from './client'

export interface RoleItem {
  id: string
  name: string
  code: string
  data_scope: string
  is_builtin: number
  status: number
}

export interface PermissionGroup {
  module: string
  permissions: { code: string; name: string }[]
}

export function listRoles() {
  return client.get<any, RoleItem[]>('/roles')
}

export function getRole(id: string) {
  return client.get<any, RoleItem>(`/roles/${id}`)
}

export function createRole(data: Record<string, any>) {
  return client.post('/roles', data)
}

export function updateRole(id: string, data: Record<string, any>) {
  return client.put(`/roles/${id}`, data)
}

export function deleteRole(id: string) {
  return client.delete(`/roles/${id}`)
}

export function getRolePermissions(id: string) {
  return client.get<any, { codes: string[] }>(`/roles/${id}/permissions`)
}

export function updateRolePermissions(id: string, data: { codes: string[] }) {
  return client.put(`/roles/${id}/permissions`, data)
}

export function getAllPermissions() {
  return client.get<any, { items: PermissionGroup[] }>('/permissions')
}
