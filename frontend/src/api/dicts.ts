import client from './client'

export interface DictItem {
  dict_key: string
  dict_label: string
}

export interface DictData {
  items: DictItem[]
}

export function getDict(dictType: string) {
  return client.get<any, DictData>(`/dicts/${dictType}`)
}
