export const genderLabel: Record<number, string> = { 0: '未知', 1: '男', 2: '女' }

export function formatDate(d: string | null): string {
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN')
}

export function formatDateTime(d: string | null): string {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-CN')
}
