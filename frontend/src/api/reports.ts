import client from './client'

export interface EmployeeAssets {
  workstation: Record<string, any> | null
  devices: Record<string, any>[]
}

export interface IdleAssets {
  idle_workstations: number | null
  idle_devices: number | null
}

export interface DeviceByDeptItem {
  department_id: string
  department_name: string
  count: number
}

export interface WarrantyExpiringItem {
  id: string
  asset_code: string
  type: string
  brand: string | null
  model: string | null
  current_employee_id: string | null
  warranty_expire: string
}

export function getEmployeeAssets(employeeId: string) {
  return client.get<any, EmployeeAssets>('/reports/employee-assets', {
    params: { employee_id: employeeId },
  })
}

export function getIdleAssets() {
  return client.get<any, IdleAssets>('/reports/idle-assets')
}

export function getDeviceByDepartment(departmentId?: string) {
  const params: Record<string, any> = {}
  if (departmentId) params.department_id = departmentId
  return client.get<any, { items: DeviceByDeptItem[] }>('/reports/device-by-department', { params })
}

export function getWarrantyExpiring(days: number = 30) {
  return client.get<any, { items: WarrantyExpiringItem[] }>('/reports/warranty-expiring', {
    params: { days },
  })
}
