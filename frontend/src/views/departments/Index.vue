<template>
  <div class="department-page">
    <el-card>
      <div class="page-header">
        <h2>部门管理</h2>
        <el-button type="primary" @click="openCreateDialog(null)">新增根部门</el-button>
      </div>

      <el-tree
        :data="treeData"
        :props="treeProps"
        node-key="id"
        default-expand-all
        v-loading="loading"
        style="margin-top: 16px"
      >
        <template #default="{ data }">
          <span class="custom-tree-node">
            <span class="node-label">
              <span>{{ data.name }}</span>
              <el-tag
                :type="data.status === 1 ? 'success' : 'danger'"
                size="small"
                style="margin-left: 8px"
              >
                {{ data.status === 1 ? '启用' : '禁用' }}
              </el-tag>
            </span>
            <span class="node-actions">
              <el-button type="primary" link size="small" @click.stop="openCreateDialog(data.id)">
                新增子部门
              </el-button>
              <el-button type="warning" link size="small" @click.stop="openEditDialog(data)">
                编辑
              </el-button>
              <el-button type="danger" link size="small" @click.stop="handleDelete(data)">
                删除
              </el-button>
            </span>
          </span>
        </template>
      </el-tree>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑部门' : '新增部门'"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        @submit.prevent="handleSubmit"
      >
        <el-form-item label="部门名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入部门名称" />
        </el-form-item>

        <el-form-item label="上级部门">
          <el-tree-select
            v-model="form.parent_id"
            :data="treeData"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            :disabled="isEdit"
            placeholder="选择上级部门"
            clearable
            check-strictly
            filterable
          />
        </el-form-item>

        <el-form-item label="负责人">
          <el-input v-model="form.manager_name" placeholder="请输入负责人姓名" />
        </el-form-item>

        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>

        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTree, createDept, updateDept, deleteDept } from '@/api/departments'
import type { DeptNode } from '@/api/departments'

const treeData = ref<DeptNode[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitLoading = ref(false)
const editingId = ref<string | null>(null)
const formRef = ref<any>(null)

const treeProps = {
  label: 'name' as const,
  children: 'children' as const,
}

interface DeptForm {
  name: string
  parent_id: string | null
  manager_name: string
  sort_order: number
  status: number
}

const form = reactive<DeptForm>({
  name: '',
  parent_id: null,
  manager_name: '',
  sort_order: 0,
  status: 1,
})

const rules = {
  name: [{ required: true, message: '请输入部门名称', trigger: 'blur' }],
}

async function fetchTree() {
  loading.value = true
  try {
    treeData.value = await getTree()
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.name = ''
  form.parent_id = null
  form.manager_name = ''
  form.sort_order = 0
  form.status = 1
  editingId.value = null
  isEdit.value = false
}

function openCreateDialog(parentId: string | null) {
  resetForm()
  form.parent_id = parentId
  dialogVisible.value = true
}

function openEditDialog(node: DeptNode) {
  resetForm()
  isEdit.value = true
  editingId.value = node.id
  form.name = node.name
  form.parent_id = node.parent_id
  form.manager_name = node.manager_name || ''
  form.sort_order = node.sort_order
  form.status = node.status
  dialogVisible.value = true
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  submitLoading.value = true
  try {
    const payload: Record<string, any> = {
      name: form.name,
      sort_order: form.sort_order,
      status: form.status,
    }
    if (form.parent_id) {
      payload.parent_id = form.parent_id
    }
    if (form.manager_name) {
      payload.manager_name = form.manager_name
    }

    if (isEdit.value && editingId.value) {
      await updateDept(editingId.value, payload)
      ElMessage.success('编辑成功')
    } else {
      await createDept(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchTree()
  } catch {
    // Error handled by interceptor
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(node: DeptNode) {
  try {
    await ElMessageBox.confirm(
      `确定删除部门「${node.name}」吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
    await deleteDept(node.id)
    ElMessage.success('删除成功')
    await fetchTree()
  } catch (e) {
    const err = e as any
    if (err === 'cancel') return
    if (err?.response?.data?.code === 3002) {
      ElMessage.error('该部门下有子部门或在职员工，不能删除')
    }
  }
}

onMounted(fetchTree)
</script>

<style scoped>
.department-page {
  padding: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-header h2 {
  margin: 0;
  font-size: 18px;
}

.custom-tree-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 1;
  padding: 4px 0;
}

.node-label {
  display: flex;
  align-items: center;
}

.node-actions {
  display: none;
  margin-left: 16px;
}

.custom-tree-node:hover .node-actions {
  display: inline-flex;
  gap: 4px;
}
</style>
