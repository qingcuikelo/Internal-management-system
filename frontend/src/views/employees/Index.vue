<template>
  <div class="employee-page">
    <!-- Filter Bar -->
    <el-card style="margin-bottom: 16px">
      <el-form :model="filters" inline>
        <el-form-item label="关键词">
          <el-input
            v-model="filters.keyword"
            placeholder="姓名 / 工号"
            clearable
            style="width: 180px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="部门">
          <el-tree-select
            v-model="filters.department_id"
            :data="deptTree"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            placeholder="选择部门"
            clearable
            check-strictly
            filterable
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="员工状态" clearable style="width: 120px">
            <el-option label="在职" :value="1" />
            <el-option label="离职" :value="0" />
          </el-select>
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
          <el-button type="primary" @click="openCreateDialog()">新增员工</el-button>
          <el-button @click="openBatchDeptDialog" :disabled="selectedIds.length === 0">
            批量调部门
          </el-button>
          <el-button @click="handleImport">导入</el-button>
          <el-button @click="handleExport">导出</el-button>
        </div>
      </div>
    </el-card>

    <!-- Table -->
    <el-card>
      <el-table
        :data="employeeList"
        v-loading="listLoading"
        stripe
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="employee_no" label="工号" width="120" />
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column label="性别" width="70">
          <template #default="{ row }">
            {{ genderLabel(row.gender) }}
          </template>
        </el-table-column>
        <el-table-column prop="department_name" label="部门" min-width="150" />
        <el-table-column prop="position" label="职位" min-width="120" />
        <el-table-column prop="phone" label="手机" width="130" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row)">
              查看
            </el-button>
            <el-button type="warning" link size="small" @click="openEditDialog(row)">
              编辑
            </el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">
              删除
            </el-button>
            <el-button
              v-if="row.status === 1"
              type="info"
              link
              size="small"
              @click="openResignDialog(row)"
            >
              离职
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
      :title="isEdit ? '编辑员工' : '新增员工'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="120px"
        @submit.prevent="handleFormSubmit"
      >
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="工号" prop="employee_no">
              <el-input v-model="form.employee_no" placeholder="请输入工号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名" prop="name">
              <el-input v-model="form.name" placeholder="请输入姓名" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="性别" prop="gender">
              <el-select v-model="form.gender" placeholder="请选择性别" style="width: 100%">
                <el-option label="未知" :value="0" />
                <el-option label="男" :value="1" />
                <el-option label="女" :value="2" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="部门" prop="department_id">
              <el-tree-select
                v-model="form.department_id"
                :data="deptTree"
                :props="{ label: 'name', value: 'id', children: 'children' }"
                placeholder="选择部门"
                clearable
                check-strictly
                filterable
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="职位">
              <el-input v-model="form.position" placeholder="请输入职位" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="直属上级">
              <el-select
                v-model="form.direct_supervisor_id"
                placeholder="选择上级"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="emp in supervisorOptions"
                  :key="emp.id"
                  :label="emp.name"
                  :value="emp.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="手机" prop="phone">
              <el-input v-model="form.phone" placeholder="请输入手机号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="form.email" placeholder="请输入邮箱" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="入职日期">
          <el-date-picker v-model="form.hire_date" type="date" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleFormSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- Delete Confirm -->
    <el-dialog v-model="deleteDialogVisible" title="确认删除" width="400px">
      <p>确定删除员工「{{ deletingEmployee ? deletingEmployee.name : '' }}」吗？此操作不可恢复。</p>
      <template #footer>
        <el-button @click="deleteDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="deleting" @click="confirmDelete">确定删除</el-button>
      </template>
    </el-dialog>

    <!-- Resign Dialog -->
    <el-dialog v-model="resignDialogVisible" title="员工离职处理" width="420px">
      <el-form :model="resignForm" label-width="100px">
        <el-form-item label="员工姓名">
          <span>{{ resigningEmployee ? resigningEmployee.name : '' }}</span>
        </el-form-item>
        <el-form-item label="离职日期" required>
          <el-date-picker
            v-model="resignForm.resign_date"
            type="date"
            placeholder="选择离职日期"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resignDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="resigning" @click="confirmResign">确认离职</el-button>
      </template>
    </el-dialog>

    <!-- Resign Result Dialog -->
    <el-dialog v-model="resignResultVisible" title="离职处理结果" width="420px">
      <el-result icon="success" title="离职处理完成">
        <template #extra>
          <p>释放工位：{{ resignResult.released_workstations }} 个</p>
          <p>退还设备：{{ resignResult.returned_devices }} 台</p>
          <p>账号禁用：{{ resignResult.account_disabled ? '是' : '否' }}</p>
        </template>
      </el-result>
      <template #footer>
        <el-button type="primary" @click="resignResultVisible = false">知道了</el-button>
      </template>
    </el-dialog>

    <!-- Batch Department Dialog -->
    <el-dialog v-model="batchDeptDialogVisible" title="批量调整部门" width="420px">
      <p>已选择 {{ selectedIds.length }} 名员工</p>
      <el-form :model="batchDeptForm" label-width="100px">
        <el-form-item label="目标部门" required>
          <el-tree-select
            v-model="batchDeptForm.department_id"
            :data="deptTree"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            placeholder="选择部门"
            clearable
            check-strictly
            filterable
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchDeptDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchDeptLoading" @click="confirmBatchDept">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- Import Dialog -->
    <el-dialog v-model="importDialogVisible" title="导入员工" width="500px">
      <template v-if="!importTaskId">
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          accept=".xlsx"
          :on-change="handleFileChange"
          :limit="1"
          drag
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽文件到此处，或<em>点击选择</em></div>
          <template #tip>
            <div class="el-upload__tip">请选择 .xlsx 格式的员工数据文件</div>
          </template>
        </el-upload>
      </template>
      <template v-else>
        <div style="text-align: center; padding: 24px 0">
          <p>导入处理中，请稍候...</p>
          <el-progress :percentage="importPollingCount * 10" :stroke-width="8" style="margin-top: 16px" />
          <p style="margin-top: 12px; color: #909399; font-size: 13px">
            已等待 {{ importPollingCount * 2 }} 秒
          </p>
        </div>
      </template>
      <template #footer>
        <template v-if="!importTaskId">
          <el-button @click="importDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="importing" :disabled="!importFile" @click="startImport">
            开始导入
          </el-button>
        </template>
        <template v-else>
          <el-button @click="importDialogVisible = false" :disabled="importing">关闭</el-button>
        </template>
      </template>
    </el-dialog>

    <!-- Import Result Dialog -->
    <el-dialog v-model="importResultVisible" title="导入结果" width="480px">
      <el-result
        :icon="importSuccess ? 'success' : 'error'"
        :title="importSuccess ? '导入成功' : '导入失败'"
      >
        <template #extra>
          <pre style="white-space: pre-wrap; text-align: left">{{ importResultMessage }}</pre>
        </template>
      </el-result>
      <template #footer>
        <el-button type="primary" @click="importResultVisible = false; reloadAfterImport()">
          知道了
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, shallowRef } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { getTree } from '@/api/departments'
import {
  listEmployees,
  createEmployee,
  updateEmployee,
  deleteEmployee,
  resignEmployee,
  batchDepartment,
  importEmployees,
  exportEmployees,
} from '@/api/employees'
import { getTaskStatus } from '@/api/tasks'
import Pagination from '@/components/Pagination.vue'
import type { DeptNode } from '@/api/departments'
import type { EmployeeItem, ResignResult } from '@/api/employees'

const router = useRouter()

function genderLabel(val: number): string {
  if (val === 1) return '男'
  if (val === 2) return '女'
  return '未知'
}

function statusLabel(val: number): string {
  return val === 1 ? '在职' : '离职'
}

// ========== Filters ==========
const filters = reactive({
  keyword: '',
  department_id: null as string | null,
  status: null as number | null,
})

function handleSearch() {
  currentPage.value = 1
  fetchList()
}

function handleReset() {
  filters.keyword = ''
  filters.department_id = null
  filters.status = null
  currentPage.value = 1
  fetchList()
}

// ========== Dept Tree (for filters and form selects) ==========
const deptTree = ref<DeptNode[]>([])

async function fetchDeptTree() {
  try {
    deptTree.value = await getTree()
  } catch {
    // handled by interceptor
  }
}

// ========== Employee List ==========
const employeeList = ref<EmployeeItem[]>([])
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
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.department_id) params.department_id = filters.department_id
    if (filters.status !== null) params.status = filters.status

    const result = await listEmployees(params)
    employeeList.value = result.items
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

function viewDetail(row: EmployeeItem) {
  router.push(`/employees/${row.id}`)
}

// ========== Create / Edit Form ==========
const formDialogVisible = ref(false)
const isEdit = ref(false)
const editingEmployeeId = ref<string | null>(null)
const submitLoading = ref(false)
const formRef = ref<any>(null)
const supervisorOptions = ref<EmployeeItem[]>([])

interface EmployeeForm {
  employee_no: string
  name: string
  gender: number
  department_id: string | null
  position: string
  direct_supervisor_id: string | null
  phone: string
  email: string
  hire_date: string | null
}

const form = reactive<EmployeeForm>({
  employee_no: '',
  name: '',
  gender: 0,
  department_id: null,
  position: '',
  direct_supervisor_id: null,
  phone: '',
  email: '',
  hire_date: null,
})

const formRules = {
  employee_no: [{ required: true, message: '请输入工号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  gender: [{ required: true, message: '请选择性别', trigger: 'change' }],
}

function resetForm() {
  form.employee_no = ''
  form.name = ''
  form.gender = 0
  form.department_id = null
  form.position = ''
  form.direct_supervisor_id = null
  form.phone = ''
  form.email = ''
  form.hire_date = null
  editingEmployeeId.value = null
  isEdit.value = false
}

async function loadSupervisorOptions() {
  try {
    const result = await listEmployees({ page: 1, page_size: 9999, status: 1 })
    supervisorOptions.value = result.items
  } catch {
    supervisorOptions.value = []
  }
}

function openCreateDialog() {
  resetForm()
  loadSupervisorOptions()
  formDialogVisible.value = true
}

function openEditDialog(row: EmployeeItem) {
  resetForm()
  isEdit.value = true
  editingEmployeeId.value = row.id
  form.employee_no = row.employee_no
  form.name = row.name
  form.gender = row.gender
  form.department_id = row.department_id
  form.position = row.position || ''
  form.direct_supervisor_id = row.direct_supervisor_id
  form.phone = row.phone || ''
  form.email = row.email || ''
  form.hire_date = row.hire_date || null
  loadSupervisorOptions()
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
      employee_no: form.employee_no,
      name: form.name,
      gender: form.gender,
    }
    if (form.department_id) payload.department_id = form.department_id
    if (form.position) payload.position = form.position
    if (form.direct_supervisor_id) payload.direct_supervisor_id = form.direct_supervisor_id
    if (form.phone) payload.phone = form.phone
    if (form.email) payload.email = form.email
    if (form.hire_date) payload.hire_date = form.hire_date

    if (isEdit.value && editingEmployeeId.value) {
      await updateEmployee(editingEmployeeId.value, payload)
      ElMessage.success('编辑成功')
    } else {
      await createEmployee(payload)
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

// ========== Delete ==========
const deleteDialogVisible = ref(false)
const deletingEmployee = shallowRef<EmployeeItem | null>(null)
const deleting = ref(false)

function handleDelete(row: EmployeeItem) {
  deletingEmployee.value = row
  deleteDialogVisible.value = true
}

async function confirmDelete() {
  if (!deletingEmployee.value) return
  deleting.value = true
  try {
    await deleteEmployee(deletingEmployee.value.id)
    ElMessage.success('删除成功')
    deleteDialogVisible.value = false
    await fetchList()
  } catch {
    // handled by interceptor
  } finally {
    deleting.value = false
  }
}

// ========== Resign ==========
const resignDialogVisible = ref(false)
const resigningEmployee = shallowRef<EmployeeItem | null>(null)
const resigning = ref(false)
const resignForm = reactive({ resign_date: '' })

const resignResultVisible = ref(false)
const resignResult = reactive<ResignResult>({
  released_workstations: 0,
  returned_devices: 0,
  account_disabled: false,
})

function openResignDialog(row: EmployeeItem) {
  resigningEmployee.value = row
  resignForm.resign_date = ''
  resignDialogVisible.value = true
}

async function confirmResign() {
  if (!resignForm.resign_date || !resigningEmployee.value) {
    ElMessage.warning('请选择离职日期')
    return
  }
  resigning.value = true
  try {
    const result = await resignEmployee(resigningEmployee.value.id, {
      resign_date: resignForm.resign_date,
    })
    resignDialogVisible.value = false
    resignResult.released_workstations = result.released_workstations
    resignResult.returned_devices = result.returned_devices
    resignResult.account_disabled = result.account_disabled
    resignResultVisible.value = true
    await fetchList()
  } catch {
    // handled by interceptor
  } finally {
    resigning.value = false
  }
}

// ========== Batch Department ==========
const batchDeptDialogVisible = ref(false)
const batchDeptLoading = ref(false)
const batchDeptForm = reactive({ department_id: '' })

function openBatchDeptDialog() {
  batchDeptForm.department_id = ''
  batchDeptDialogVisible.value = true
}

async function confirmBatchDept() {
  if (!batchDeptForm.department_id) {
    ElMessage.warning('请选择目标部门')
    return
  }
  batchDeptLoading.value = true
  try {
    await batchDepartment({
      employee_ids: selectedIds.value,
      department_id: batchDeptForm.department_id,
    })
    ElMessage.success('批量调整部门成功')
    batchDeptDialogVisible.value = false
    selectedIds.value = []
    await fetchList()
  } catch {
    // handled by interceptor
  } finally {
    batchDeptLoading.value = false
  }
}

// ========== Import ==========
const importDialogVisible = ref(false)
const importFile = ref<File | null>(null)
const importTaskId = ref('')
const importPollingCount = ref(0)
const importing = ref(false)
const importResultVisible = ref(false)
const importSuccess = ref(false)
const importResultMessage = ref('')
// eslint-disable-next-line @typescript-eslint/no-unused-vars

function handleImport() {
  importFile.value = null
  importTaskId.value = ''
  importPollingCount.value = 0
  importDialogVisible.value = true
}

function handleFileChange(uploadFile: any) {
  importFile.value = uploadFile.raw
}

async function startImport() {
  if (!importFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  importing.value = true
  importPollingCount.value = 0
  try {
    const result = await importEmployees(importFile.value)
    importTaskId.value = result.task_id
    pollImportTask()
  } catch {
    importing.value = false
    // handled by interceptor
  }
}

function pollImportTask() {
  if (!importTaskId.value) return
  setTimeout(async () => {
    try {
      const task = await getTaskStatus(importTaskId.value)
      importPollingCount.value++

      if (task.status === 'SUCCESS') {
        importing.value = false
        importSuccess.value = true
        importResultMessage.value = task.result || '导入完成'
        importResultVisible.value = true
      } else if (task.status === 'FAILURE') {
        importing.value = false
        importSuccess.value = false
        importResultMessage.value = task.error || '导入失败'
        importResultVisible.value = true
      } else {
        // Still pending/started, poll again
        pollImportTask()
      }
    } catch {
      importing.value = false
      importTaskId.value = ''
      ElMessage.error('查询导入任务状态失败')
    }
  }, 2000)
}

function reloadAfterImport() {
  importDialogVisible.value = false
  fetchList()
}

// ========== Export ==========
const exporting = ref(false)

async function handleExport() {
  exporting.value = true
  try {
    const params: Record<string, any> = {}
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.department_id) params.department_id = filters.department_id
    if (filters.status !== null) params.status = filters.status

    const result = await exportEmployees(params)
    const taskId = result.task_id

    // Poll for export task
    const pollExport = (): any => {
      setTimeout(async () => {
        try {
          const task = await getTaskStatus(taskId)
          if (task.status === 'SUCCESS') {
            const filename = task.result
            const token = localStorage.getItem('access_token')
            const link = document.createElement('a')
            link.href = `/api/v1/exports/${filename}?token=${token || ''}`
            link.click()
            ElMessage.success('导出成功')
            exporting.value = false
          } else if (task.status === 'FAILURE') {
            ElMessage.error(task.error || '导出失败')
            exporting.value = false
          } else {
            pollExport()
          }
        } catch {
          ElMessage.error('查询导出任务状态失败')
          exporting.value = false
        }
      }, 2000)
    }
    pollExport()
  } catch {
    exporting.value = false
    // handled by interceptor
  }
}

// ========== Init ==========
onMounted(() => {
  fetchDeptTree()
  fetchList()
})
</script>

<style scoped>
.employee-page {
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
