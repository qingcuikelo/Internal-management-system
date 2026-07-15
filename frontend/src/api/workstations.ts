import client from './client'

export interface WorkstationItem {
  id: string
  code: string
  location: string | null
  type: string
  status: number
  employee_id: string | null
  employee_name: string | null
  employee_no: string | null
  version: number
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
}

export interface WorkstationHistoryItem {
  id: string
  workstation_id: string
  employee_id: string
  employee_name: string
  employee_no: string
  start_date: string
  end_date: string | null
  operator_name: string
  created_at: string
}

export interface BatchReleaseResult {
  success_count: number
}

export function listWorkstations(params: Record<string, any>) {
  return client.get<any, PaginatedResult<WorkstationItem>>('/workstations', { params })
}

export function getWorkstation(id: string) {
  return client.get<any, WorkstationItem>(`/workstations/${id}`)
}

export function createWorkstation(data: Partial<WorkstationItem>) {
  return client.post('/workstations', data)
}

export function updateWorkstation(id: string, data: Partial<WorkstationItem>) {
  return client.put(`/workstations/${id}`, data)
}

export function assignWorkstation(id: string, data: { employee_id: string; assign_date?: string; version?: number }) {
  return client.post(`/workstations/${id}/assign`, data)
}

export function releaseWorkstation(id: string) {
  return client.post(`/workstations/${id}/release`)
}

export function batchReleaseWorkstations(data: { ids: string[] }) {
  return client.post<any, BatchReleaseResult>('/workstations/batch-release', data)
}

export function updateWorkstationStatus(id: string, data: { status: number }) {
  return client.patch(`/workstations/${id}/status`, data)
}

export function getWorkstationHistory(id: string) {
  return client.get<any, WorkstationHistoryItem[]>(`/workstations/${id}/history`)
}
