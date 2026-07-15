<template>
  <div class="device-page">
    <!-- Filter Bar -->
    <el-card style="margin-bottom: 16px">
      <el-form :model="filters" inline>
        <el-form-item label="资产编号">
          <el-input
            v-model="filters.asset_code"
            placeholder="资产编号"
            clearable
            style="width: 150px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filters.type" placeholder="全部" clearable style="width: 120px">
            <el-option
              v-for="item in deviceTypes"
              :key="item.dict_key"
              :label="item.dict_label"
              :value="item.dict_key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="在库" :value="1" />
            <el-option label="使用中" :value="2" />
            <el-option label="维修" :value="3" />
            <el-option label="报废" :value="4" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="filters.keyword"
            placeholder="使用人"
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
          <el-button type="primary" @click="openCreateDialog">登记设备</el-button>
        </div>
      </div>
    </el-card>

    <!-- Table -->
    <el-card>
      <el-table
        :data="list"
        v-loading="listLoading"
        stripe
      >
        <el-table-column prop="asset_code" label="资产编号" width="150" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            {{ row.type || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="brand" label="品牌" width="120" show-overflow-tooltip />
        <el-table-column prop="model" label="型号" width="120" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <StatusTag :status="row.status" type="device" />
          </template>
        </el-table-column>
        <el-table-column label="使用人" width="120">
          <template #default="{ row }">
            {{ row.employee_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="保修到期" width="120">
          <template #default="{ row }">
            {{ row.warranty_expire || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row)">查看</el-button>
            <el-button type="warning" link size="small" @click="openEditDialog(row)">编辑</el-button>
            <el-button
              v-if="row.status === 1"
              type="success"
              link
              size="small"
              @click="openCheckoutDialog(row)"
            >
              领用
            </el-button>
            <el-button
              v-if="row.status === 2"
              type="info"
              link
              size="small"
              @click="handleReturn(row)"
            >
              归还
            </el-button>
            <el-button
              v-if="row.status === 1"
              type="warning"
              link
              size="small"
              @click="handleRepair(row)"
            >
              维修
            </el-button>
            <el-button
              v-if="row.status !== 4"
              type="danger"
              link
              size="small"
              @click="handleScrap(row)"
            >
              报废
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
      :title="isEdit ? '编辑设备' : '登记设备'"
      width="600px"
      :close-on-click-modal="false"
      destroy-on-close
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
            <el-form-item label="资产编号" prop="asset_code">
              <el-input v-model="form.asset_code" placeholder="请输入资产编号" :disabled="isEdit" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="类型" prop="type">
              <el-select v-model="form.type" placeholder="请选择类型" style="width: 100%">
                <el-option
                  v-for="item in deviceTypes"
                  :key="item.dict_key"
                  :label="item.dict_label"
                  :value="item.dict_key"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="品牌">
              <el-input v-model="form.brand" placeholder="请输入品牌" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="型号">
              <el-input v-model="form.model" placeholder="请输入型号" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="序列号">
              <el-input v-model="form.serial_number" placeholder="请输入序列号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="规格">
              <el-input v-model="form.specs" placeholder="请输入规格" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="购入日期">
              <el-date-picker
                v-model="form.purchase_date"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保修到期">
              <el-date-picker
                v-model="form.warranty_expire"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

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

    <!-- Checkout Dialog -->
    <el-dialog
      v-model="checkoutDialogVisible"
      title="领用设备"
      width="500px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="checkoutFormRef"
        :model="checkoutForm"
        :rules="checkoutFormRules"
        label-width="100px"
      >
        <el-form-item label="资产编号">
          <span>{{ checkingDevice?.asset_code }}</span>
        </el-form-item>
        <el-form-item label="员工" prop="employee_id">
          <el-select
            v-model="checkoutForm.employee_id"
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
              :label="emp.name + ' (' + emp.employee_no + ')'"
              :value="emp.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="领用日期">
          <el-date-picker
            v-model="checkoutForm.assign_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="checkoutDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="checkoutLoading" @click="confirmCheckout">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listDevices,
  createDevice,
  updateDevice,
  checkoutDevice,
  returnDevice,
  repairDevice,
  scrapDevice,
} from '@/api/devices'
import { listEmployees } from '@/api/employees'
import { getDict } from '@/api/dicts'
import Pagination from '@/components/Pagination.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { DeviceItem } from '@/api/devices'
import type { DictItem } from '@/api/dicts'
import type { EmployeeItem } from '@/api/employees'

const router = useRouter()

// ========== Filters ==========
const filters = reactive({
  asset_code: '',
  type: '',
  status: null as number | null,
  keyword: '',
})

function handleSearch() {
  currentPage.value = 1
  fetchList()
}

function handleReset() {
  filters.asset_code = ''
  filters.type = ''
  filters.status = null
  filters.keyword = ''
  currentPage.value = 1
  fetchList()
}

// ========== Dict Types ==========
const deviceTypes = ref<DictItem[]>([])

async function fetchDeviceTypes() {
  try {
    const result = await getDict('device_type')
    deviceTypes.value = result.items
  } catch {
    // handled by interceptor
  }
}

// ========== List ==========
const list = ref<DeviceItem[]>([])
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
    if (filters.asset_code) params.asset_code = filters.asset_code
    if (filters.type) params.type = filters.type
    if (filters.status !== null) params.status = filters.status
    if (filters.keyword) params.keyword = filters.keyword

    const result = await listDevices(params)
    list.value = result.items
    total.value = result.total
  } catch {
    // handled by interceptor
  } finally {
    listLoading.value = false
  }
}

function viewDetail(row: DeviceItem) {
  router.push(`/devices/${row.id}`)
}

// ========== Create / Edit Form ==========
const formDialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<string | null>(null)
const submitLoading = ref(false)
const formRef = ref<any>(null)

interface DeviceForm {
  asset_code: string
  type: string
  brand: string
  model: string
  serial_number: string
  specs: string
  purchase_date: string
  warranty_expire: string
  notes: string
}

const form = reactive<DeviceForm>({
  asset_code: '',
  type: '',
  brand: '',
  model: '',
  serial_number: '',
  specs: '',
  purchase_date: '',
  warranty_expire: '',
  notes: '',
})

const formRules = {
  asset_code: [{ required: true, message: '请输入资产编号', trigger: 'blur' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
}

function resetForm() {
  form.asset_code = ''
  form.type = ''
  form.brand = ''
  form.model = ''
  form.serial_number = ''
  form.specs = ''
  form.purchase_date = ''
  form.warranty_expire = ''
  form.notes = ''
  editingId.value = null
  isEdit.value = false
}

function openCreateDialog() {
  resetForm()
  formDialogVisible.value = true
}

function openEditDialog(row: DeviceItem) {
  resetForm()
  isEdit.value = true
  editingId.value = row.id
  form.asset_code = row.asset_code
  form.type = row.type
  form.brand = row.brand || ''
  form.model = row.model || ''
  form.serial_number = row.serial_number || ''
  form.specs = row.specs || ''
  form.purchase_date = row.purchase_date || ''
  form.warranty_expire = row.warranty_expire || ''
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
      asset_code: form.asset_code,
      type: form.type,
    }
    if (form.brand) payload.brand = form.brand
    if (form.model) payload.model = form.model
    if (form.serial_number) payload.serial_number = form.serial_number
    if (form.specs) payload.specs = form.specs
    if (form.purchase_date) payload.purchase_date = form.purchase_date
    if (form.warranty_expire) payload.warranty_expire = form.warranty_expire
    if (form.notes) payload.notes = form.notes

    if (isEdit.value && editingId.value) {
      await updateDevice(editingId.value, payload)
      ElMessage.success('编辑成功')
    } else {
      await createDevice(payload)
      ElMessage.success('登记成功')
    }
    formDialogVisible.value = false
    await fetchList()
  } catch {
    // handled by interceptor
  } finally {
    submitLoading.value = false
  }
}

// ========== Checkout ==========
const checkoutDialogVisible = ref(false)
const checkingDevice = ref<DeviceItem | null>(null)
const checkoutLoading = ref(false)
const checkoutFormRef = ref<any>(null)
const employeeOptions = ref<EmployeeItem[]>([])
const searchingEmployee = ref(false)

interface CheckoutForm {
  employee_id: string
  assign_date: string
}

const checkoutForm = reactive<CheckoutForm>({
  employee_id: '',
  assign_date: '',
})

const checkoutFormRules = {
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

function openCheckoutDialog(row: DeviceItem) {
  checkingDevice.value = row
  checkoutForm.employee_id = ''
  checkoutForm.assign_date = new Date().toISOString().split('T')[0]
  loadEmployeeOptions()
  checkoutDialogVisible.value = true
}

async function confirmCheckout() {
  try {
    await checkoutFormRef.value?.validate()
  } catch {
    return
  }

  if (!checkingDevice.value) return

  checkoutLoading.value = true
  try {
    await checkoutDevice(checkingDevice.value.id, {
      employee_id: checkoutForm.employee_id,
      assign_date: checkoutForm.assign_date || undefined,
      version: checkingDevice.value.version,
    })
    ElMessage.success('领用成功')
    checkoutDialogVisible.value = false
    await fetchList()
  } catch (err) {
    const errObj = err as any
    if (errObj.response?.data?.code === 3001) {
      ElMessage.error('该设备不可领用')
    } else if (errObj.response?.data?.code === 3007) {
      ElMessage.error('当前状态不允许该操作')
    }
  } finally {
    checkoutLoading.value = false
  }
}

// ========== Return ==========
async function handleReturn(row: DeviceItem) {
  try {
    await ElMessageBox.confirm('确定归还设备「' + row.asset_code + '」吗？', '确认归还', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await returnDevice(row.id)
    ElMessage.success('归还成功')
    await fetchList()
  } catch {
    // cancelled or handled by interceptor
  }
}

// ========== Repair ==========
async function handleRepair(row: DeviceItem) {
  try {
    await ElMessageBox.confirm('确定送修设备「' + row.asset_code + '」吗？', '确认维修', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await repairDevice(row.id)
    ElMessage.success('已送修')
    await fetchList()
  } catch (err) {
    const errObj = err as any
    if (errObj.response?.data?.code === 3007) {
      ElMessage.error('当前状态不允许该操作')
    }
  }
}

// ========== Scrap ==========
async function handleScrap(row: DeviceItem) {
  try {
    await ElMessageBox.confirm('确定报废设备「' + row.asset_code + '」吗？此操作不可逆。', '确认报废', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await scrapDevice(row.id)
    ElMessage.success('已报废')
    await fetchList()
  } catch {
    // cancelled or handled by interceptor
  }
}

// ========== Init ==========
onMounted(() => {
  fetchDeviceTypes()
  fetchList()
})
</script>

<style scoped>
.device-page {
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
