<template>
  <div class="page">
    <!-- Filter Bar -->
    <el-card style="margin-bottom: 16px">
      <el-form :model="filters" inline>
        <el-form-item label="关键词">
          <el-input
            v-model="filters.keyword"
            placeholder="用户名"
            clearable
            style="width: 160px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="filters.role_code" placeholder="全部" clearable style="width: 150px">
            <el-option v-for="r in roles" :key="r.code" :label="r.name" :value="r.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="启用" :value="1" />
            <el-option label="禁用" :value="0" />
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
        <el-button type="primary" @click="openCreateDialog">新增账号</el-button>
      </div>
    </el-card>

    <!-- Table -->
    <el-card>
      <el-table :data="list" v-loading="listLoading" stripe>
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column label="角色" width="130">
          <template #default="{ row }">
            {{ row.role_name || row.role_code || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="员工" width="120">
          <template #default="{ row }">
            {{ row.employee_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <StatusTag :status="row.status" type="user" />
          </template>
        </el-table-column>
        <el-table-column prop="last_login_at" label="最后登录" width="170" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <el-button type="warning" link size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
            <el-button
              :type="row.status === 1 ? 'warning' : 'success'"
              link
              size="small"
              @click="toggleStatus(row)"
            >
              {{ row.status === 1 ? '禁用' : '启用' }}
            </el-button>
            <el-button type="primary" link size="small" @click="openResetPwdDialog(row)">
              重置密码
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
      :title="isEdit ? '编辑账号' : '新增账号'"
      width="550px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="120px" @submit.prevent="handleFormSubmit">
        <template v-if="!isEdit">
          <el-form-item label="用户名" prop="username">
            <el-input v-model="form.username" placeholder="请输入用户名" />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input v-model="form.password" type="password" placeholder="至少8位" show-password />
          </el-form-item>
        </template>

        <el-form-item label="角色" prop="role_id">
          <el-select v-model="form.role_id" placeholder="请选择角色" style="width: 100%">
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="员工" prop="employee_id">
          <el-select
            v-model="form.employee_id"
            placeholder="搜索员工"
            filterable
            remote
            :remote-method="searchEmployees"
            :loading="searchingEmp"
            style="width: 100%"
          >
            <el-option
              v-for="e in empOptions"
              :key="e.id"
              :label="`${e.name} (${e.employee_no})`"
              :value="e.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleFormSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- Reset Password Dialog -->
    <el-dialog
      v-model="resetPwdDialogVisible"
      title="重置密码"
      width="400px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="resetPwdFormRef" :model="resetPwdForm" :rules="resetPwdRules" label-width="100px">
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="resetPwdForm.new_password" type="password" placeholder="至少8位" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwdDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetPwdLoading" @click="confirmResetPwd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listUsers,
  createUser,
  updateUser,
  deleteUser,
  updateUserStatus,
  resetPassword,
} from '@/api/users'
import { listRoles } from '@/api/roles'
import { listEmployees } from '@/api/employees'
import Pagination from '@/components/Pagination.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { UserItem } from '@/api/users'
import type { RoleItem } from '@/api/roles'
import type { EmployeeItem } from '@/api/employees'

// ========== Filters ==========
const filters = reactive({
  keyword: '',
  role_code: '',
  status: null as number | null,
})

function handleSearch() {
  currentPage.value = 1
  fetchList()
}

function handleReset() {
  filters.keyword = ''
  filters.role_code = ''
  filters.status = null
  currentPage.value = 1
  fetchList()
}

// ========== Roles for filter & form ==========
const roles = ref<RoleItem[]>([])

async function fetchRoles() {
  try {
    roles.value = await listRoles()
  } catch {
    // handled by interceptor
  }
}

// ========== List ==========
const list = ref<UserItem[]>([])
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
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.role_code) params.role_code = filters.role_code
    if (filters.status !== null) params.status = filters.status

    const result = await listUsers(params)
    list.value = result.items
    total.value = result.total
  } catch {
    // handled by interceptor
  } finally {
    listLoading.value = false
  }
}

// ========== Create / Edit Form ==========
const formDialogVisible = ref(false)
const isEdit = ref(false)
const editingUserId = ref<string | null>(null)
const submitLoading = ref(false)
const formRef = ref<any>(null)
const empOptions = ref<EmployeeItem[]>([])
const searchingEmp = ref(false)

interface UserForm {
  username: string
  password: string
  role_id: string
  employee_id: string
  status: number
}

const form = reactive<UserForm>({
  username: '',
  password: '',
  role_id: '',
  employee_id: '',
  status: 1,
})

const formRules: Record<string, any> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少8位', trigger: 'blur' },
  ],
  role_id: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

function resetForm() {
  form.username = ''
  form.password = ''
  form.role_id = ''
  form.employee_id = ''
  form.status = 1
  editingUserId.value = null
  isEdit.value = false
}

async function searchEmployees(query: string) {
  if (!query) return
  searchingEmp.value = true
  try {
    const result = await listEmployees({ keyword: query, page: 1, page_size: 50, status: 1 })
    empOptions.value = result.items
  } catch {
    // handled by interceptor
  } finally {
    searchingEmp.value = false
  }
}

async function loadEmpOptions() {
  searchingEmp.value = true
  try {
    const result = await listEmployees({ page: 1, page_size: 50, status: 1 })
    empOptions.value = result.items
  } catch {
    // handled by interceptor
  } finally {
    searchingEmp.value = false
  }
}

function openCreateDialog() {
  resetForm()
  loadEmpOptions()
  formDialogVisible.value = true
}

function openEditDialog(row: UserItem) {
  resetForm()
  isEdit.value = true
  editingUserId.value = row.id
  form.role_id = row.role_id
  form.employee_id = row.employee_id || ''
  form.status = row.status
  loadEmpOptions()
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
      role_id: form.role_id,
      status: form.status,
    }
    if (form.employee_id) payload.employee_id = form.employee_id

    if (isEdit.value && editingUserId.value) {
      await updateUser(editingUserId.value, payload)
      ElMessage.success('编辑成功')
    } else {
      payload.username = form.username
      payload.password = form.password
      await createUser(payload)
      ElMessage.success('新增成功')
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
async function handleDelete(row: UserItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.username}」吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    await fetchList()
  } catch (err) {
    const e = err as any
    if (e === 'cancel') return
    if (e?.response?.data?.code === 3007 || e?.message?.includes('3007')) {
      ElMessage.error('不能删除自己的账号')
    }
  }
}

// ========== Status Toggle ==========
async function toggleStatus(row: UserItem) {
  const newStatus = row.status === 1 ? 0 : 1
  const actionLabel = newStatus === 1 ? '启用' : '禁用'
  try {
    await ElMessageBox.confirm(
      `确定${actionLabel}用户「${row.username}」吗？`,
      '确认',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' },
    )
    await updateUserStatus(row.id, { status: newStatus })
    ElMessage.success(`${actionLabel}成功`)
    await fetchList()
  } catch (err) {
    const e = err as any
    if (e === 'cancel') return
    if (e?.response?.data?.code === 3007 || e?.message?.includes('3007')) {
      ElMessage.error('不能禁用自己的账号')
    }
  }
}

// ========== Reset Password ==========
const resetPwdDialogVisible = ref(false)
const resetPwdFormRef = ref<any>(null)
const resetPwdLoading = ref(false)
const resetTargetUser = ref<UserItem | null>(null)

const resetPwdForm = reactive({ new_password: '' })

const resetPwdRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码至少8位', trigger: 'blur' },
  ],
}

function openResetPwdDialog(row: UserItem) {
  resetTargetUser.value = row
  resetPwdForm.new_password = ''
  resetPwdDialogVisible.value = true
}

async function confirmResetPwd() {
  try {
    await resetPwdFormRef.value?.validate()
  } catch {
    return
  }

  if (!resetTargetUser.value) return

  resetPwdLoading.value = true
  try {
    await resetPassword(resetTargetUser.value.id, { new_password: resetPwdForm.new_password })
    ElMessage.success('密码重置成功')
    resetPwdDialogVisible.value = false
  } catch {
    // handled by interceptor
  } finally {
    resetPwdLoading.value = false
  }
}

// ========== Init ==========
onMounted(() => {
  fetchRoles()
  fetchList()
})
</script>

<style scoped>
.page {
  padding: 16px;
}
.toolbar {
  display: flex;
  align-items: center;
}
.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
