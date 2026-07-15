import client from './client'

export interface DictItem {
  dict_key: string
  dict_label: string
  sort_order: number
}

export interface DictData {
  items: DictItem[]
}

export interface DictAdminItem {
  id: string
  dict_type: string
  dict_key: string
  dict_label: string
  sort_order: number
  status: number
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
}

export function getDict(dictType: string) {
  return client.get<any, DictData>(`/dicts/${dictType}`)
}

export function listDicts(params: Record<string, any>) {
  return client.get<any, PaginatedResult<DictAdminItem>>('/dicts', { params })
}

export function createDict(data: Record<string, any>) {
  return client.post('/dicts', data)
}

export function updateDict(id: string, data: Record<string, any>) {
  return client.put(`/dicts/${id}`, data)
}

export function deleteDict(id: string) {
  return client.delete(`/dicts/${id}`)
}
