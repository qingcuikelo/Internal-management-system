<template>
  <div class="device-detail-page" v-loading="loading">
    <!-- Info Card -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div class="card-header">
          <span>设备信息</span>
          <el-button @click="goBack">返回列表</el-button>
        </div>
      </template>

      <el-descriptions v-if="device" :column="2" border>
        <el-descriptions-item label="资产编号">{{ device.asset_code }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ device.type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="品牌">{{ device.brand || '-' }}</el-descriptions-item>
        <el-descriptions-item label="型号">{{ device.model || '-' }}</el-descriptions-item>
        <el-descriptions-item label="序列号">{{ device.serial_number || '-' }}</el-descriptions-item>
        <el-descriptions-item label="规格">{{ device.specs || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <StatusTag :status="device.status" type="device" />
        </el-descriptions-item>
        <el-descriptions-item label="使用人">
          {{ device.employee_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="购入日期">{{ device.purchase_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="保修到期">{{ device.warranty_expire || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ device.notes || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ device.created_at }}</el-descriptions-item>
      </el-descriptions>
      <el-empty v-else-if="!loading" description="未找到设备信息" />
    </el-card>

    <!-- Action buttons -->
    <el-card v-if="device" style="margin-bottom: 16px">
      <template #header><span>操作</span></template>
      <el-button
        v-if="device.status === 1"
        type="success"
        @click="openCheckoutDialog"
      >
        领用
      </el-button>
      <el-button
        v-if="device.status === 2"
        type="info"
        @click="handleReturn"
      >
        归还
      </el-button>
      <el-button
        v-if="device.status === 1"
        type="warning"
        @click="handleRepair"
      >
        维修
      </el-button>
      <el-button
        v-if="device.status !== 4"
        type="danger"
        @click="handleScrap"
      >
        报废
      </el-button>
      <span v-if="device.status === 4" style="color: #909399">该设备已报废</span>
    </el-card>

    <!-- Checkout Dialog (inline on detail page) -->
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
          <span>{{ device?.asset_code }}</span>
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

    <!-- History -->
    <el-card v-if="device">
      <template #header><span>使用历史</span></template>
      <div v-loading="historyLoading" style="min-height: 60px">
        <el-table v-if="historyList.length > 0" :data="historyList" stripe>
          <el-table-column prop="employee_name" label="员工" width="150" />
          <el-table-column prop="employee_no" label="工号" width="120" />
          <el-table-column prop="checkout_date" label="领用日期" width="120" />
          <el-table-column prop="return_date" label="归还日期" width="120">
            <template #default="{ row }">
              {{ row.return_date || '-' }}
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
  getDevice,
  checkoutDevice,
  returnDevice,
  repairDevice,
  scrapDevice,
  getDeviceHistory,
} from '@/api/devices'
import { listEmployees } from '@/api/employees'
import StatusTag from '@/components/StatusTag.vue'
import type { DeviceItem, DeviceHistoryItem } from '@/api/devices'
import type { EmployeeItem } from '@/api/employees'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const device = ref<DeviceItem | null>(null)
const historyList = ref<DeviceHistoryItem[]>([])
const historyLoading = ref(false)

// ========== Checkout ==========
const checkoutDialogVisible = ref(false)
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

function openCheckoutDialog() {
  if (!device.value) return
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

  if (!device.value) return

  checkoutLoading.value = true
  try {
    await checkoutDevice(device.value.id, {
      employee_id: checkoutForm.employee_id,
      assign_date: checkoutForm.assign_date || undefined,
      version: device.value.version,
    })
    ElMessage.success('领用成功')
    checkoutDialogVisible.value = false
    await fetchDevice()
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

async function handleReturn() {
  if (!device.value) return
  try {
    await ElMessageBox.confirm('确定归还设备「' + device.value.asset_code + '」吗？', '确认归还', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await returnDevice(device.value.id)
    ElMessage.success('归还成功')
    await fetchDevice()
  } catch {
    // cancelled or handled by interceptor
  }
}

async function handleRepair() {
  if (!device.value) return
  try {
    await ElMessageBox.confirm('确定送修设备「' + device.value.asset_code + '」吗？', '确认维修', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await repairDevice(device.value.id)
    ElMessage.success('已送修')
    await fetchDevice()
  } catch (err) {
    const errObj = err as any
    if (errObj.response?.data?.code === 3007) {
      ElMessage.error('当前状态不允许该操作')
    }
  }
}

async function handleScrap() {
  if (!device.value) return
  try {
    await ElMessageBox.confirm('确定报废设备「' + device.value.asset_code + '」吗？此操作不可逆。', '确认报废', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await scrapDevice(device.value.id)
    ElMessage.success('已报废')
    await fetchDevice()
  } catch {
    // cancelled or handled by interceptor
  }
}

// ========== Data fetching ==========
async function fetchDevice() {
  loading.value = true
  try {
    const id = route.params.id as string
    device.value = await getDevice(id)
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
    historyList.value = await getDeviceHistory(id)
  } catch {
    // handled by interceptor
  } finally {
    historyLoading.value = false
  }
}

function goBack() {
  router.push('/devices')
}

onMounted(() => {
  fetchDevice()
  fetchHistory()
})
</script>

<style scoped>
.device-detail-page {
  padding: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
