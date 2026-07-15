import client from './client'

export interface DeptNode {
  id: string
  name: string
  parent_id: string | null
  manager_id: string | null
  manager_name?: string
  sort_order: number
  status: number
  children: DeptNode[]
}

export interface DeptItem {
  id: string
  name: string
  parent_id: string | null
  manager_id: string | null
  sort_order: number
  status: number
}

export function getTree() {
  return client.get<any, DeptNode[]>('/departments/tree')
}

export function getList() {
  return client.get<any, DeptItem[]>('/departments')
}

export function createDept(data: Partial<DeptItem>) {
  return client.post('/departments', data)
}

export function updateDept(id: string, data: Partial<DeptItem>) {
  return client.put(`/departments/${id}`, data)
}

export function deleteDept(id: string) {
  return client.delete(`/departments/${id}`)
}
