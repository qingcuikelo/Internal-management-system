<template>
  <div class="workstation-detail-page" v-loading="loading">
    <!-- Info Card -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div class="card-header">
          <span>工位信息</span>
          <el-button @click="goBack">返回列表</el-button>
        </div>
      </template>

      <el-descriptions v-if="workstation" :column="2" border>
        <el-descriptions-item label="编号">{{ workstation.code }}</el-descriptions-item>
        <el-descriptions-item label="位置">{{ workstation.location || '-' }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ workstation.type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <StatusTag :status="workstation.status" type="workstation" />
        </el-descriptions-item>
        <el-descriptions-item label="占用人">
          {{ workstation.employee_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="备注">{{ workstation.notes || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ workstation.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ workstation.updated_at }}</el-descriptions-item>
      </el-descriptions>
      <el-empty v-else-if="!loading" description="未找到工位信息" />
    </el-card>

    <!-- Assign / Release section -->
    <el-card v-if="workstation" style="margin-bottom: 16px">
      <template #header>
        <span>{{ workstation.status === 2 ? '当前占用' : '工位分配' }}</span>
      </template>

      <!-- Occupied: show current user + release button -->
      <template v-if="workstation.status === 2">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="占用人">{{ workstation.employee_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="工号">{{ workstation.employee_no || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div style="margin-top: 12px">
          <el-button type="danger" @click="handleRelease">释放工位</el-button>
        </div>
      </template>

      <!-- Idle: show assign form -->
      <template v-else-if="workstation.status === 1">
        <el-form :model="assignForm" :rules="assignFormRules" label-width="100px">
          <el-form-item label="员工" prop="employee_id">
            <el-select
              v-model="assignForm.employee_id"
              placeholder="搜索并选择员工"
              filterable
              remote
              :remote-method="searchEmployees"
              :loading="searchingEmployee"
              style="width: 320px"
            >
              <el-option
                v-for="emp in employeeOptions"
                :key="emp.id"
                :label="emp.name + ' (' + emp.employee_no + ')'"
                :value="emp.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="分配日期">
            <el-date-picker
              v-model="assignForm.assign_date"
              type="date"
              placeholder="选择日期"
              value-format="YYYY-MM-DD"
              style="width: 320px"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="assignLoading" @click="confirmAssign">
              分配
            </el-button>
          </el-form-item>
        </el-form>
      </template>

      <!-- Reserved or Disabled -->
      <template v-else>
        <p style="color: #909399; margin: 0">
          {{ workstation.status === 3 ? '该工位已预留' : '该工位已禁用' }}
        </p>
      </template>
    </el-card>

    <!-- Status actions -->
    <el-card v-if="workstation" style="margin-bottom: 16px">
      <template #header><span>操作</span></template>
      <el-button
        v-if="workstation.status === 1 || workstation.status === 2"
        type="warning"
        @click="handleStatusChange(3)"
      >
        预留
      </el-button>
      <el-button
        v-if="workstation.status !== 4"
        type="danger"
        @click="handleStatusChange(4)"
      >
        禁用
      </el-button>
      <el-button
        v-if="workstation.status === 4"
        type="info"
        @click="handleStatusChange(1)"
      >
        启用
      </el-button>
      <span v-if="workstation.status !== 1 && workstation.status !== 2 && workstation.status !== 4" style="color: #909399">
        当前无可执行操作
      </span>
    </el-card>

    <!-- History -->
    <el-card v-if="workstation">
      <template #header><span>使用历史</span></template>
      <div v-loading="historyLoading" style="min-height: 60px">
        <el-table v-if="historyList.length > 0" :data="historyList" stripe>
          <el-table-column prop="employee_name" label="员工" width="150" />
          <el-table-column prop="employee_no" label="工号" width="120" />
          <el-table-column prop="start_date" label="开始日期" width="120" />
          <el-table-column prop="end_date" label="结束日期" width="120">
            <template #default="{ row }">
              {{ row.end_date || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="operator_name" label="操作人" width="120" />
        </el-table>
        <el-empty v-else description="暂无使用历史" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getWorkstation,
  assignWorkstation,
  releaseWorkstation,
  updateWorkstationStatus,
  getWorkstationHistory,
} from '@/api/workstations'
import { listEmployees } from '@/api/employees'
import StatusTag from '@/components/StatusTag.vue'
import type { WorkstationItem, WorkstationHistoryItem } from '@/api/workstations'
import type { EmployeeItem } from '@/api/employees'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const workstation = ref<WorkstationItem | null>(null)
const historyList = ref<WorkstationHistoryItem[]>([])
const historyLoading = ref(false)

// ========== Assign form ==========
const assignForm = reactive({
  employee_id: '',
  assign_date: new Date().toISOString().split('T')[0],
})
const assignFormRules = {
  employee_id: [{ required: true, message: '请选择员工', trigger: 'change' }],
}
const employeeOptions = ref<EmployeeItem[]>([])
const searchingEmployee = ref(false)
const assignLoading = ref(false)

async function searchEmployees(query: string) {
  if (!query) return
  searchingEmployee.value = true
  try {
    const result = await listEmployees({ keyword: query, page: 1, page_size: 50, status: 1 })
    employeeOptions.value = result.items
  } catch {
    // handled by interceptor
  } finally {
    searchingEmployee.value = false
  }
}

async function loadEmployeeOptions() {
  searchingEmployee.value = true
  try {
    const result = await listEmployees({ page: 1, page_size: 50, status: 1 })
    employeeOptions.value = result.items
  } catch {
    // handled by interceptor
  } finally {
    searchingEmployee.value = false
  }
}

async function confirmAssign() {
  if (!workstation.value || !assignForm.employee_id) return
  assignLoading.value = true
  try {
    await assignWorkstation(workstation.value.id, {
      employee_id: assignForm.employee_id,
      assign_date: assignForm.assign_date || undefined,
      version: workstation.value.version,
    })
    ElMessage.success('分配成功')
    await fetchWorkstation()
  } catch (err) {
    const errObj = err as any
    if (errObj.response?.data?.code === 3001) {
      ElMessage.error('该工位已被占用，请刷新后重试')
      await fetchWorkstation()
    }
  } finally {
    assignLoading.value = false
  }
}

async function handleRelease() {
  if (!workstation.value) return
  try {
    await ElMessageBox.confirm('确定释放该工位吗？', '确认释放', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await releaseWorkstation(workstation.value.id)
    ElMessage.success('释放成功')
    await fetchWorkstation()
  } catch {
    // cancelled or handled by interceptor
  }
}

async function handleStatusChange(status: number) {
  if (!workstation.value) return
  const statusLabels: Record<number, string> = { 1: '启用', 3: '预留', 4: '禁用' }
  const label = statusLabels[status] || '变更'
  try {
    await ElMessageBox.confirm('确定将工位设为' + label + '吗？', '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await updateWorkstationStatus(workstation.value.id, { status })
    ElMessage.success('已' + label)
    await fetchWorkstation()
  } catch {
    // cancelled or handled by interceptor
  }
}

// ========== Data fetching ==========
async function fetchWorkstation() {
  loading.value = true
  try {
    const id = route.params.id as string
    workstation.value = await getWorkstation(id)
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}

async function fetchHistory() {
  historyLoading.value = true
  try {
    const id = route.params.id as string
    historyList.value = await getWorkstationHistory(id)
  } catch {
    // handled by interceptor
  } finally {
    historyLoading.value = false
  }
}

function goBack() {
  router.push('/workstations')
}

onMounted(() => {
  fetchWorkstation()
  fetchHistory()
  loadEmployeeOptions()
})
</script>

<style scoped>
.workstation-detail-page {
  padding: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
