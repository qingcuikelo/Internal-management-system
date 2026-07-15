import client from './client'

export interface DeviceItem {
  id: string
  asset_code: string
  type: string
  brand: string | null
  model: string | null
  serial_number: string | null
  specs: string | null
  status: number
  employee_id: string | null
  employee_name: string | null
  employee_no: string | null
  purchase_date: string | null
  warranty_expire: string | null
  version: number
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
}

export interface DeviceHistoryItem {
  id: string
  device_id: string
  employee_id: string
  employee_name: string
  employee_no: string
  checkout_date: string
  return_date: string | null
  operator_name: string
  created_at: string
}

export function listDevices(params: Record<string, any>) {
  return client.get<any, PaginatedResult<DeviceItem>>('/devices', { params })
}

export function getDevice(id: string) {
  return client.get<any, DeviceItem>(`/devices/${id}`)
}

export function createDevice(data: Partial<DeviceItem>) {
  return client.post('/devices', data)
}

export function updateDevice(id: string, data: Partial<DeviceItem>) {
  return client.put(`/devices/${id}`, data)
}

export function checkoutDevice(id: string, data: { employee_id: string; assign_date?: string; version?: number }) {
  return client.post(`/devices/${id}/checkout`, data)
}

export function returnDevice(id: string) {
  return client.post(`/devices/${id}/return`)
}

export function repairDevice(id: string) {
  return client.post(`/devices/${id}/repair`)
}

export function scrapDevice(id: string) {
  return client.post(`/devices/${id}/scrap`)
}

export function getDeviceHistory(id: string) {
  return client.get<any, DeviceHistoryItem[]>(`/devices/${id}/history`)
}
