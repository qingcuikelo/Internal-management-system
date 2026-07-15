<template>
  <div class="workstation-page">
    <!-- Filter Bar -->
    <el-card style="margin-bottom: 16px">
      <el-form :model="filters" inline>
        <el-form-item label="编号">
          <el-input
            v-model="filters.code"
            placeholder="工位编号"
            clearable
            style="width: 150px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="位置">
          <el-input
            v-model="filters.location"
            placeholder="位置"
            clearable
            style="width: 150px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filters.type" placeholder="全部" clearable style="width: 120px">
            <el-option
              v-for="item in workstationTypes"
              :key="item.dict_key"
              :label="item.dict_label"
              :value="item.dict_key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="闲置" :value="1" />
            <el-option label="占用" :value="2" />
            <el-option label="预留" :value="3" />
            <el-option label="禁用" :value="4" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="filters.keyword"
            placeholder="占用人"
            clearable
            style="width: 150px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Toolbar -->
    <el-card style="margin-bottom: 16px">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-button type="primary" @click="openCreateDialog">新增工位</el-button>
          <el-button :disabled="selectedIds.length === 0" @click="handleBatchRelease">
            批量释放
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- Table -->
    <el-card>
      <el-table
        :data="list"
        v-loading="listLoading"
        stripe
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="code" label="编号" width="150" />
        <el-table-column prop="location" label="位置" min-width="150" show-overflow-tooltip />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            {{ row.type || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <StatusTag :status="row.status" type="workstation" />
          </template>
        </el-table-column>
        <el-table-column label="占用人" width="120">
          <template #default="{ row }">
            {{ row.employee_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row)">查看</el-button>
            <el-button type="warning" link size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button
              v-if="row.status === 1"
              type="success"
              link
              size="small"
              @click="openAssignDialog(row)"
            >
              分配
            </el-button>
            <el-button
              v-if="row.status === 2"
              type="info"
              link
              size="small"
              @click="handleRelease(row)"
            >
              释放
            </el-button>
            <el-button
              v-if="row.status === 1 || row.status === 2"
              type="warning"
              link
              size="small"
              @click="handleStatusChange(row, 3)"
            >
              预留
            </el-button>
            <el-button
              v-if="row.status !== 4"
              type="danger"
              link
              size="small"
              @click="handleStatusChange(row, 4)"
            >
              禁用
            </el-button>
            <el-button
              v-if="row.status === 4"
              type="info"
              link
              size="small"
              @click="handleStatusChange(row, 1)"
            >
              启用
            </el-button>
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

    <!-- Create / Edit Dialog -->
    <el-dialog
      v-model="formDialogVisible"
      :title="isEdit ? '编辑工位' : '新增工位'"
      width="500px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="100px"
        @submit.prevent="handleFormSubmit"
      >
        <el-form-item label="编号" prop="code">
          <el-input v-model="form.code" placeholder="请输入工位编号" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="form.location" placeholder="请输入位置" />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-select v-model="form.type" placeholder="请选择类型" style="width: 100%">
            <el-option
              v-for="item in workstationTypes"
              :key="item.dict_key"
              :label="item.dict_label"
              :value="item.dict_key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" placeholder="备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleFormSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- Assign Dialog -->
    <el-dialog
      v-model="assignDialogVisible"
      title="分配工位"
      width="500px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="assignFormRef"
        :model="assignForm"
        :rules="assignFormRules"
        label-width="100px"
      >
        <el-form-item label="工位编号">
          <span>{{ assigningWorkstation?.code }}</span>
        </el-form-item>
        <el-form-item label="员工" prop="employee_id">
          <el-select
            v-model="assignForm.employee_id"
            placeholder="搜索并选择员工"
            filterable
            remote
            :remote-method="searchEmployees"
            :loading="searchingEmployee"
            style="width: 100%"
          >
            <el-option
              v-for="emp in employeeOptions"
              :key="emp.id"
              :label="`${emp.name} (${emp.employee_no})`"
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
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="assignLoading" @click="confirmAssign">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- Batch Release Result -->
    <el-dialog v-model="batchReleaseVisible" title="批量释放结果" width="400px">
      <p>成功释放 {{ batchReleaseCount }} 个工位</p>
      <template #footer>
        <el-button type="primary" @click="batchReleaseVisible = false">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listWorkstations,
  createWorkstation,
  updateWorkstation,
  assignWorkstation,
  releaseWorkstation,
  batchReleaseWorkstations,
  updateWorkstationStatus,
} from '@/api/workstations'
import { listEmployees } from '@/api/employees'
import { getDict } from '@/api/dicts'
import Pagination from '@/components/Pagination.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { WorkstationItem } from '@/api/workstations'
import type { DictItem } from '@/api/dicts'
import type { EmployeeItem } from '@/api/employees'

const router = useRouter()

// ========== Filters ==========
const filters = reactive({
  code: '',
  location: '',
  type: '',
  status: null as number | null,
  keyword: '',
})

function handleSearch() {
  currentPage.value = 1
  fetchList()
}

function handleReset() {
  filters.code = ''
  filters.location = ''
  filters.type = ''
  filters.status = null
  filters.keyword = ''
  currentPage.value = 1
  fetchList()
}

// ========== Dict Types ==========
const workstationTypes = ref<DictItem[]>([])

async function fetchWorkstationTypes() {
  try {
    const result = await getDict('workstation_type')
    workstationTypes.value = result.items
  } catch {
    // handled by interceptor
  }
}

// ========== List ==========
const list = ref<WorkstationItem[]>([])
const listLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const selectedIds = ref<string[]>([])

async function fetchList() {
  listLoading.value = true
  try {
    const params: Record<string, any> = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (filters.code) params.code = filters.code
    if (filters.location) params.location = filters.location
    if (filters.type) params.type = filters.type
    if (filters.status !== null) params.status = filters.status
    if (filters.keyword) params.keyword = filters.keyword

    const result = await listWorkstations(params)
    list.value = result.items
    total.value = result.total
  } catch {
    // handled by interceptor
  } finally {
    listLoading.value = false
  }
}

function onSelectionChange(rows: any[]) {
  selectedIds.value = rows.map((r) => r.id)
}

function viewDetail(row: WorkstationItem) {
  router.push(`/workstations/${row.id}`)
}

// ========== Create / Edit Form ==========
const formDialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<string | null>(null)
const submitLoading = ref(false)
const formRef = ref<any>(null)

interface WorkstationForm {
  code: string
  location: string
  type: string
  notes: string
}

const form = reactive<WorkstationForm>({
  code: '',
  location: '',
  type: '',
  notes: '',
})

const formRules = {
  code: [{ required: true, message: '请输入工位编号', trigger: 'blur' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
}

function resetForm() {
  form.code = ''
  form.location = ''
  form.type = ''
  form.notes = ''
  editingId.value = null
  isEdit.value = false
}

function openCreateDialog() {
  resetForm()
  formDialogVisible.value = true
}

function openEditDialog(row: WorkstationItem) {
  resetForm()
  isEdit.value = true
  editingId.value = row.id
  form.code = row.code
  form.location = row.location || ''
  form.type = row.type
  form.notes = row.notes || ''
  formDialogVisible.value = true
}

async function handleFormSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  submitLoading.value = true
  try {
    const payload: Record<string, any> = {
      code: form.code,
      type: form.type,
    }
    if (form.location) payload.location = form.location
    if (form.notes) payload.notes = form.notes

    if (isEdit.value && editingId.value) {
      await updateWorkstation(editingId.value, payload)
      ElMessage.success('编辑成功')
    } else {
      await createWorkstation(payload)
      ElMessage.success('创建成功')
    }
    formDialogVisible.value = false
    await fetchList()
  } catch {
    // handled by interceptor
  } finally {
    submitLoading.value = false
  }
}

// ========== Assign ==========
const assignDialogVisible = ref(false)
const assigningWorkstation = ref<WorkstationItem | null>(null)
const assignLoading = ref(false)
const assignFormRef = ref<any>(null)
const employeeOptions = ref<EmployeeItem[]>([])
const searchingEmployee = ref(false)

interface AssignForm {
  employee_id: string
  assign_date: string
}

const assignForm = reactive<AssignForm>({
  employee_id: '',
  assign_date: '',
})

const assignFormRules = {
  employee_id: [{ required: true, message: '请选择员工', trigger: 'change' }],
}

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

function openAssignDialog(row: WorkstationItem) {
  assigningWorkstation.value = row
  assignForm.employee_id = ''
  assignForm.assign_date = new Date().toISOString().split('T')[0]
  loadEmployeeOptions()
  assignDialogVisible.value = true
}

async function confirmAssign() {
  try {
    await assignFormRef.value?.validate()
  } catch {
    return
  }

  if (!assigningWorkstation.value) return

  assignLoading.value = true
  try {
    await assignWorkstation(assigningWorkstation.value.id, {
      employee_id: assignForm.employee_id,
      assign_date: assignForm.assign_date || undefined,
      version: assigningWorkstation.value.version,
    })
    ElMessage.success('分配成功')
    assignDialogVisible.value = false
    await fetchList()
  } catch (err) {
    const errObj = err as any
    if (errObj.response?.data?.code === 3001) {
      ElMessage.error('该工位已被占用，请刷新后重试')
      // Re-fetch workstation to get new version
      try {
        const updated = await listWorkstations({ page: 1, page_size: 1, code: assigningWorkstation.value.code })
        if (updated.items.length > 0) {
          assigningWorkstation.value = updated.items[0]
        }
      } catch {
        // handled by interceptor
      }
    }
  } finally {
    assignLoading.value = false
  }
}

// ========== Release ==========
async function handleRelease(row: WorkstationItem) {
  try {
    await ElMessageBox.confirm(`确定释放工位「${row.code}」吗？`, '确认释放', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await releaseWorkstation(row.id)
    ElMessage.success('释放成功')
    await fetchList()
  } catch {
    // cancelled or handled by interceptor
  }
}

// ========== Batch Release ==========
const batchReleaseVisible = ref(false)
const batchReleaseCount = ref(0)

async function handleBatchRelease() {
  try {
    await ElMessageBox.confirm(
      `确定释放选中的 ${selectedIds.value.length} 个工位吗？`,
      '确认批量释放',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    const result = await batchReleaseWorkstations({ ids: selectedIds.value })
    batchReleaseCount.value = result.success_count || selectedIds.value.length
    batchReleaseVisible.value = true
    selectedIds.value = []
    await fetchList()
  } catch {
    // cancelled or handled by interceptor
  }
}

// ========== Status Change ==========
async function handleStatusChange(row: WorkstationItem, status: number) {
  const statusLabels: Record<number, string> = { 1: '启用', 3: '预留', 4: '禁用' }
  const label = statusLabels[status] || '变更'
  try {
    await ElMessageBox.confirm(
      `确定将工位「${row.code}」设为${label}吗？`,
      '确认操作',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
    await updateWorkstationStatus(row.id, { status })
    ElMessage.success(`已${label}`)
    await fetchList()
  } catch {
    // cancelled or handled by interceptor
  }
}

// ========== Init ==========
onMounted(() => {
  fetchWorkstationTypes()
  fetchList()
})
</script>

<style scoped>
.workstation-page {
  padding: 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
