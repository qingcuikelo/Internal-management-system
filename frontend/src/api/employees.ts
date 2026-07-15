import client from './client'

export interface EmployeeItem {
  id: string
  employee_no: string
  name: string
  gender: number
  department_id: string | null
  department_name: string | null
  position: string | null
  phone: string | null
  email: string | null
  direct_supervisor_id: string | null
  supervisor_name: string | null
  hire_date: string | null
  resign_date: string | null
  status: number
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
}

export interface ResignResult {
  released_workstations: number
  returned_devices: number
  account_disabled: boolean
}

export function listEmployees(params: Record<string, any>) {
  return client.get<any, PaginatedResult<EmployeeItem>>('/employees', { params })
}

export function getEmployee(id: string) {
  return client.get<any, EmployeeItem>(`/employees/${id}`)
}

export function createEmployee(data: Partial<EmployeeItem>) {
  return client.post('/employees', data)
}

export function updateEmployee(id: string, data: Partial<EmployeeItem>) {
  return client.put(`/employees/${id}`, data)
}

export function deleteEmployee(id: string) {
  return client.delete(`/employees/${id}`)
}

export function resignEmployee(id: string, data: { resign_date: string }) {
  return client.post<any, ResignResult>(`/employees/${id}/resign`, data)
}

export function batchDepartment(data: { employee_ids: string[]; department_id: string }) {
  return client.patch('/employees/batch-department', data)
}

export function importEmployees(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return client.post<any, { task_id: string }>('/employees/import', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function exportEmployees(data: Record<string, any>) {
  return client.post<any, { task_id: string }>('/employees/export', data)
}
