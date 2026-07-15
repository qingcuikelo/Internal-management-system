import client from './client'

export interface TaskStatus {
  status: string
  result: any
  error: string | null
}

export function getTaskStatus(id: string) {
  return client.get<any, TaskStatus>(`/tasks/${id}`)
}
