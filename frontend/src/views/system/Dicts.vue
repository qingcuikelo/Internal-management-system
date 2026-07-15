<template>
  <div class="page">
    <el-row :gutter="16">
      <!-- Left Panel: Dict Types -->
      <el-col :span="6">
        <el-card>
          <template #header>
            <span>字典类型</span>
          </template>
          <el-menu
            :default-active="selectedType"
            @select="onSelectType"
            style="border-right: none"
          >
            <el-menu-item v-for="t in dictTypes" :key="t" :index="t">
              {{ t }}
            </el-menu-item>
          </el-menu>
          <div v-if="dictTypes.length === 0" style="text-align: center; color: #909399; padding: 24px 0">
            暂无字典类型
          </div>
        </el-card>
      </el-col>

      <!-- Right Panel: Dict Items -->
      <el-col :span="18">
        <el-card>
          <template #header>
            <div class="panel-header">
              <span>{{ selectedType || '请选择字典类型' }}</span>
              <el-button
                v-if="selectedType"
                type="primary"
                size="small"
                @click="openCreateDialog"
              >
                新增字典项
              </el-button>
            </div>
          </template>

          <el-table :data="dictItems" v-loading="itemsLoading" stripe>
            <el-table-column prop="dict_key" label="字典键" width="180" />
            <el-table-column prop="dict_label" label="字典值" width="200" />
            <el-table-column prop="sort_order" label="排序" width="80" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <StatusTag :status="row.status" type="user" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button type="warning" link size="small" @click="openEditDialog(row)">编辑</el-button>
                <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- Create / Edit Dialog -->
    <el-dialog
      v-model="formDialogVisible"
      :title="isEdit ? '编辑字典项' : '新增字典项'"
      width="500px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px" @submit.prevent="handleFormSubmit">
        <el-form-item label="字典类型" prop="dict_type">
          <el-input v-model="form.dict_type" :disabled="true" />
        </el-form-item>
        <el-form-item label="字典键" prop="dict_key">
          <el-input v-model="form.dict_key" placeholder="请输入字典键" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="字典值" prop="dict_label">
          <el-input v-model="form.dict_label" placeholder="请输入字典值" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="状态" v-if="isEdit">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleFormSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listDicts, createDict, updateDict, deleteDict } from '@/api/dicts'
import StatusTag from '@/components/StatusTag.vue'
import type { DictAdminItem } from '@/api/dicts'

// ========== State ==========
const allItems = ref<DictAdminItem[]>([])
const itemsLoading = ref(false)
const selectedType = ref('')

const dictTypes = computed(() => {
  const types = new Set(allItems.value.map((i) => i.dict_type))
  return Array.from(types).sort()
})

const dictItems = computed(() =>
  allItems.value.filter((i) => i.dict_type === selectedType.value),
)

function onSelectType(type: string) {
  selectedType.value = type
}

// ========== Fetch ==========
async function fetchAllItems() {
  itemsLoading.value = true
  try {
    const result = await listDicts({ page: 1, page_size: 9999 })
    allItems.value = result.items
    if (dictTypes.value.length > 0 && !selectedType.value) {
      selectedType.value = dictTypes.value[0]
    }
  } catch {
    // handled by interceptor
  } finally {
    itemsLoading.value = false
  }
}

// ========== Create / Edit Form ==========
const formDialogVisible = ref(false)
const isEdit = ref(false)
const editingItemId = ref<string | null>(null)
const submitLoading = ref(false)
const formRef = ref<any>(null)

interface DictForm {
  dict_type: string
  dict_key: string
  dict_label: string
  sort_order: number
  status: number
}

const form = reactive<DictForm>({
  dict_type: '',
  dict_key: '',
  dict_label: '',
  sort_order: 0,
  status: 1,
})

const formRules: Record<string, any> = {
  dict_key: [{ required: true, message: '请输入字典键', trigger: 'blur' }],
  dict_label: [{ required: true, message: '请输入字典值', trigger: 'blur' }],
}

function resetForm() {
  form.dict_key = ''
  form.dict_label = ''
  form.sort_order = 0
  form.status = 1
  editingItemId.value = null
  isEdit.value = false
}

function openCreateDialog() {
  resetForm()
  form.dict_type = selectedType.value
  formDialogVisible.value = true
}

function openEditDialog(row: DictAdminItem) {
  resetForm()
  isEdit.value = true
  editingItemId.value = row.id
  form.dict_type = row.dict_type
  form.dict_key = row.dict_key
  form.dict_label = row.dict_label
  form.sort_order = row.sort_order
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
      dict_type: form.dict_type,
      dict_key: form.dict_key,
      dict_label: form.dict_label,
      sort_order: form.sort_order,
    }

    if (isEdit.value && editingItemId.value) {
      payload.status = form.status
      await updateDict(editingItemId.value, payload)
      ElMessage.success('编辑成功')
    } else {
      payload.status = form.status
      await createDict(payload)
      ElMessage.success('新增成功')
    }
    formDialogVisible.value = false
    await fetchAllItems()
  } catch {
    // handled by interceptor
  } finally {
    submitLoading.value = false
  }
}

// ========== Delete ==========
async function handleDelete(row: DictAdminItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除字典项「${row.dict_key}」吗？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
    await deleteDict(row.id)
    ElMessage.success('删除成功')
    await fetchAllItems()
  } catch (err) {
    const e = err as any
    if (e === 'cancel') return
    // handled by interceptor otherwise
  }
}

// ========== Init ==========
onMounted(() => {
  fetchAllItems()
})
</script>

<style scoped>
.page {
  padding: 16px;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
