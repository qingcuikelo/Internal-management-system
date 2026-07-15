<template>
  <el-tag :type="tagType" size="small">
    {{ label }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status: number
  type: 'workstation' | 'device' | 'employee' | 'user'
}>()

const statusMap: Record<string, Record<number, { type: string; label: string }>> = {
  workstation: {
    1: { type: 'info', label: '闲置' },
    2: { type: 'success', label: '占用' },
    3: { type: 'warning', label: '预留' },
    4: { type: 'danger', label: '禁用' },
  },
  device: {
    1: { type: 'info', label: '在库' },
    2: { type: 'success', label: '使用中' },
    3: { type: 'warning', label: '维修' },
    4: { type: 'danger', label: '报废' },
  },
  employee: {
    1: { type: 'success', label: '在职' },
    0: { type: 'danger', label: '离职' },
  },
  user: {
    1: { type: 'success', label: '启用' },
    0: { type: 'danger', label: '禁用' },
  },
}

const tagType = computed(() => statusMap[props.type]?.[props.status]?.type ?? 'info')
const label = computed(() => statusMap[props.type]?.[props.status]?.label ?? '未知')
</script>
