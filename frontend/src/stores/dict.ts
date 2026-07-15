import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getDict } from '@/api/dicts'

export const useDictStore = defineStore('dict', () => {
  const cache = ref<Map<string, any[]>>(new Map())

  async function fetchType(type: string) {
    if (cache.value.has(type)) return cache.value.get(type)
    const res: any = await getDict(type)
    cache.value.set(type, res.items)
    return res.items
  }

  function getOptions(type: string) {
    return (cache.value.get(type) ?? []).map((i: any) => ({
      value: i.dict_key,
      label: i.dict_label,
    }))
  }

  return { cache, fetchType, getOptions }
})
