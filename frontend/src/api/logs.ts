import client from './client'

export interface LogItem {
  id: string
  user_id: string
  username: string
  module: string
  action: string
  target_type: string
  target_id: string
  detail: any
  ip: string
  created_at: string
}

export interface PaginatedResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export function listLogs(params: Record<string, any>) {
  return client.get<any, PaginatedResult<LogItem>>('/operation-logs', { params })
}
