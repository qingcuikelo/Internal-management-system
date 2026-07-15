<template>
  <div class="page">
    <!-- Filter Bar -->
    <el-card style="margin-bottom: 16px">
      <el-form :model="filters" inline>
        <el-form-item label="操作人">
          <el-input
            v-model="filters.user_id"
            placeholder="用户ID"
            clearable
            style="width: 140px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="模块">
          <el-select v-model="filters.module" placeholder="全部" clearable style="width: 140px">
            <el-option label="部门" value="department" />
            <el-option label="员工" value="employee" />
            <el-option label="工位" value="workstation" />
            <el-option label="设备" value="device" />
            <el-option label="用户" value="user" />
            <el-option label="角色" value="role" />
            <el-option label="字典" value="dict" />
            <el-option label="认证" value="auth" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作">
          <el-input
            v-model="filters.action"
            placeholder="操作类型"
            clearable
            style="width: 120px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="开始">
          <el-date-picker
            v-model="filters.start"
            type="datetime"
            placeholder="开始时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 170px"
          />
        </el-form-item>
        <el-form-item label="结束">
          <el-date-picker
            v-model="filters.end"
            type="datetime"
            placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 170px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Table -->
    <el-card>
      <el-table :data="list" v-loading="listLoading" stripe>
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="username" label="操作人" width="120" />
        <el-table-column prop="module" label="模块" width="100" />
        <el-table-column prop="action" label="操作" width="100" />
        <el-table-column prop="target_type" label="目标类型" width="100" />
        <el-table-column prop="target_id" label="目标ID" width="200" show-overflow-tooltip />
        <el-table-column label="详情" min-width="200">
          <template #default="{ row }">
            <el-popover trigger="click" placement="bottom" :width="300">
              <template #reference>
                <el-button link size="small">
                  {{ truncateDetail(row.detail) }}
                </el-button>
              </template>
              <pre style="white-space: pre-wrap; word-break: break-all; margin: 0; font-size: 12px; max-height: 300px; overflow-y: auto">{{ formatDetail(row.detail) }}</pre>
            </el-popover>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper" v-if="total > 0">
        <Pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { listLogs } from '@/api/logs'
import Pagination from '@/components/Pagination.vue'
import type { LogItem } from '@/api/logs'

// ========== Filters ==========
const filters = reactive({
  user_id: '',
  module: '',
  action: '',
  start: '',
  end: '',
})

function handleSearch() {
  currentPage.value = 1
  fetchList()
}

function handleReset() {
  filters.user_id = ''
  filters.module = ''
  filters.action = ''
  filters.start = ''
  filters.end = ''
  currentPage.value = 1
  fetchList()
}

// ========== List ==========
const list = ref<LogItem[]>([])
const listLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

async function fetchList() {
  listLoading.value = true
  try {
    const params: Record<string, any> = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (filters.user_id) params.user_id = filters.user_id
    if (filters.module) params.module = filters.module
    if (filters.action) params.action = filters.action
    if (filters.start) params.start = filters.start
    if (filters.end) params.end = filters.end

    const result = await listLogs(params)
    list.value = result.items
    total.value = result.total
  } catch {
    // handled by interceptor
  } finally {
    listLoading.value = false
  }
}

function truncateDetail(detail: any): string {
  if (!detail) return '-'
  const str = typeof detail === 'string' ? detail : JSON.stringify(detail)
  return str.length > 30 ? str.substring(0, 30) + '...' : str
}

function formatDetail(detail: any): string {
  if (!detail) return '-'
  if (typeof detail === 'string') {
    try {
      return JSON.stringify(JSON.parse(detail), null, 2)
    } catch {
      return detail
    }
  }
  return JSON.stringify(detail, null, 2)
}

// ========== Init ==========
onMounted(() => {
  fetchList()
})
</script>

<style scoped>
.page {
  padding: 16px;
}
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
