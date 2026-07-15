<template>
  <el-pagination
    v-model:current-page="modelCurrentPage"
    v-model:page-size="modelPageSize"
    :total="total"
    :page-sizes="pageSizes"
    layout="total, sizes, prev, pager, next, jumper"
    background
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  currentPage: number
  pageSize: number
  total: number
  pageSizes?: number[]
}>()

const emit = defineEmits<{
  (e: 'update:currentPage', val: number): void
  (e: 'update:pageSize', val: number): void
}>()

const modelCurrentPage = computed({
  get: () => props.currentPage,
  set: (val) => emit('update:currentPage', val),
})

const modelPageSize = computed({
  get: () => props.pageSize,
  set: (val) => {
    emit('update:pageSize', val)
    emit('update:currentPage', 1)
  },
})

const defaultSizes = [10, 20, 50, 100]
const pageSizes = computed(() => props.pageSizes ?? defaultSizes)
</script>
