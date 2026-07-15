<template>
  <div class="page">
    <!-- Toolbar -->
    <el-card style="margin-bottom: 16px">
      <div class="toolbar">
        <el-button type="primary" @click="openCreateDialog">新增角色</el-button>
      </div>
    </el-card>

    <!-- Table -->
    <el-card>
      <el-table :data="list" v-loading="listLoading" stripe>
        <el-table-column prop="name" label="角色名称" width="160" />
        <el-table-column prop="code" label="角色编码" width="160" />
        <el-table-column prop="data_scope" label="数据范围" width="120" />
        <el-table-column label="内置角色" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_builtin === 1" type="warning" size="small">内置</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <StatusTag :status="row.status" type="user" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button type="warning" link size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button type="success" link size="small" @click="openPermDialog(row)">权限</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create / Edit Dialog -->
    <el-dialog
      v-model="formDialogVisible"
      :title="isEdit ? '编辑角色' : '新增角色'"
      width="520px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="110px" @submit.prevent="handleFormSubmit">
        <el-form-item label="角色编码" prop="code">
          <el-input v-model="form.code" placeholder="请输入编码" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="数据范围" prop="data_scope">
          <el-select v-model="form.data_scope" placeholder="请选择" style="width: 100%" :disabled="isEdit && isBuiltinEditing">
            <el-option label="全部" value="all" />
            <el-option label="本部门" value="dept" />
            <el-option label="仅本人" value="self" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" v-if="isEdit">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" :disabled="isBuiltinEditing" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleFormSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- Permission Dialog -->
    <el-dialog
      v-model="permDialogVisible"
      title="权限配置"
      width="650px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div v-if="isSuperAdminRole" style="padding: 24px 0; text-align: center; color: #909399">
        超级管理员权限不可修改
      </div>
      <div v-else style="max-height: 500px; overflow-y: auto">
        <div v-for="group in allPerms" :key="group.module" style="margin-bottom: 20px">
          <h4 style="margin: 0 0 8px 0; font-size: 14px; color: #303133">{{ group.module }}</h4>
          <el-checkbox-group v-model="rolePermCodes">
            <el-checkbox
              v-for="p in group.permissions"
              :key="p.code"
              :label="p.code"
              style="margin-right: 16px; margin-bottom: 8px"
            >
              {{ p.name }}
            </el-checkbox>
          </el-checkbox-group>
        </div>
      </div>
      <template #footer>
        <el-button @click="permDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="permSaving"
          :disabled="isSuperAdminRole"
          @click="savePermissions"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listRoles,
  createRole,
  updateRole,
  deleteRole,
  getRolePermissions,
  updateRolePermissions,
  getAllPermissions,
} from '@/api/roles'
import StatusTag from '@/components/StatusTag.vue'
import type { RoleItem, PermissionGroup } from '@/api/roles'

// ========== List ==========
const list = ref<RoleItem[]>([])
const listLoading = ref(false)

async function fetchList() {
  listLoading.value = true
  try {
    list.value = await listRoles()
  } catch {
    // handled by interceptor
  } finally {
    listLoading.value = false
  }
}

// ========== Create / Edit Form ==========
const formDialogVisible = ref(false)
const isEdit = ref(false)
const editingRoleId = ref<string | null>(null)
const isBuiltinEditing = ref(false)
const submitLoading = ref(false)
const formRef = ref<any>(null)

interface RoleForm {
  code: string
  name: string
  data_scope: string
  status: number
}

const form = reactive<RoleForm>({
  code: '',
  name: '',
  data_scope: 'all',
  status: 1,
})

const formRules: Record<string, any> = {
  code: [{ required: true, message: '请输入角色编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
  data_scope: [{ required: true, message: '请选择数据范围', trigger: 'change' }],
}

function resetForm() {
  form.code = ''
  form.name = ''
  form.data_scope = 'all'
  form.status = 1
  editingRoleId.value = null
  isEdit.value = false
  isBuiltinEditing.value = false
}

function openCreateDialog() {
  resetForm()
  formDialogVisible.value = true
}

function openEditDialog(row: RoleItem) {
  resetForm()
  isEdit.value = true
  editingRoleId.value = row.id
  isBuiltinEditing.value = row.is_builtin === 1
  form.code = row.code
  form.name = row.name
  form.data_scope = row.data_scope
  form.status = row.status
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
      name: form.name,
    }
    if (!isEdit.value) {
      payload.code = form.code
      payload.data_scope = form.data_scope
    } else {
      if (!isBuiltinEditing.value) {
        payload.data_scope = form.data_scope
        payload.status = form.status
      }
    }

    if (isEdit.value && editingRoleId.value) {
      await updateRole(editingRoleId.value, payload)
      ElMessage.success('编辑成功')
    } else {
      await createRole(payload)
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
async function handleDelete(row: RoleItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除角色「${row.name}」吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
    await deleteRole(row.id)
    ElMessage.success('删除成功')
    await fetchList()
  } catch (err) {
    const e = err as any
    if (e === 'cancel') return
    if (e?.response?.data?.code === 3007 || e?.message?.includes('3007')) {
      ElMessage.error('内置角色不可删除')
    } else if (e?.response?.data?.code === 3002 || e?.message?.includes('3002')) {
      ElMessage.error('角色下有账号，无法删除')
    }
  }
}

// ========== Permissions ==========
const permDialogVisible = ref(false)
const permTargetRole = ref<RoleItem | null>(null)
const allPerms = ref<PermissionGroup[]>([])
const rolePermCodes = ref<string[]>([])
const permSaving = ref(false)
const isSuperAdminRole = ref(false)

async function openPermDialog(row: RoleItem) {
  permTargetRole.value = row
  isSuperAdminRole.value = row.code === 'super_admin'
  permSaving.value = false
  rolePermCodes.value = []

  try {
    const [permsResult, rolePermsResult] = await Promise.all([
      getAllPermissions(),
      getRolePermissions(row.id),
    ])
    allPerms.value = permsResult.items
    rolePermCodes.value = rolePermsResult.codes
    permDialogVisible.value = true
  } catch {
    // handled by interceptor
  }
}

async function savePermissions() {
  if (!permTargetRole.value || isSuperAdminRole.value) return

  permSaving.value = true
  try {
    await updateRolePermissions(permTargetRole.value.id, { codes: rolePermCodes.value })
    ElMessage.success('权限保存成功')
    permDialogVisible.value = false
  } catch {
    // handled by interceptor
  } finally {
    permSaving.value = false
  }
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
.toolbar {
  display: flex;
  align-items: center;
}
</style>
