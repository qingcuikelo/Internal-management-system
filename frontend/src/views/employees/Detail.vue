<template>
  <div class="employee-detail-page" v-loading="loading">
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div class="card-header">
          <span>员工信息</span>
          <el-button @click="goBack">返回列表</el-button>
        </div>
      </template>

      <el-descriptions v-if="employee" :column="2" border>
        <el-descriptions-item label="工号">{{ employee.employee_no }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ employee.name }}</el-descriptions-item>
        <el-descriptions-item label="性别">
          {{ genderLabel[employee.gender] ?? '' }}
        </el-descriptions-item>
        <el-descriptions-item label="部门">{{ employee.department_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="职位">{{ employee.position || '-' }}</el-descriptions-item>
        <el-descriptions-item label="手机">{{ employee.phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ employee.email || '-' }}</el-descriptions-item>
        <el-descriptions-item label="直属上级">{{ employee.supervisor_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="入职日期">{{ employee.hire_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <StatusTag :status="employee.status" type="employee" />
        </el-descriptions-item>
        <el-descriptions-item v-if="employee.status === 0" label="离职日期">
          {{ employee.resign_date || '-' }}
        </el-descriptions-item>
      </el-descriptions>

      <el-empty v-else-if="!loading" description="未找到员工信息" />
    </el-card>

    <!-- Current Workstation -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <span>当前工位</span>
      </template>
      <div v-if="assetsLoading" v-loading="assetsLoading" style="min-height: 60px" />
      <template v-else-if="assets && assets.workstation">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="工位编码">
            {{ assets.workstation.code }}
          </el-descriptions-item>
          <el-descriptions-item label="位置">
            {{ assets.workstation.location || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="类型">
            {{ assets.workstation.type || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small">
              {{ assets.workstation.status === 2 ? '占用' : '闲置' }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </template>
      <el-empty v-else description="无工位信息" />
    </el-card>

    <!-- Current Devices -->
    <el-card>
      <template #header>
        <span>当前设备</span>
      </template>
      <div v-if="assetsLoading" v-loading="assetsLoading" style="min-height: 60px" />
      <template v-else-if="assets && assets.devices && assets.devices.length > 0">
        <el-table :data="assets.devices" stripe>
          <el-table-column prop="asset_code" label="资产编号" width="150" />
          <el-table-column prop="type" label="类型" width="120" />
          <el-table-column prop="brand" label="品牌" width="120" />
          <el-table-column prop="model" label="型号" width="120" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small">
                {{ row.status === 2 ? '使用中' : row.status === 1 ? '在库' : row.status === 3 ? '维修' : '报废' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <el-empty v-else description="无设备信息" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getEmployee } from '@/api/employees'
import { getEmployeeAssets } from '@/api/reports'
import StatusTag from '@/components/StatusTag.vue'
import { genderLabel } from '@/utils/format'
import type { EmployeeItem } from '@/api/employees'
import type { EmployeeAssets } from '@/api/reports'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const assetsLoading = ref(false)
const employee = ref<EmployeeItem | null>(null)
const assets = ref<EmployeeAssets | null>(null)

async function fetchEmployee() {
  loading.value = true
  try {
    const id = route.params.id as string
    employee.value = await getEmployee(id)
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}

async function fetchAssets() {
  assetsLoading.value = true
  try {
    const id = route.params.id as string
    assets.value = await getEmployeeAssets(id)
  } catch {
    // handled by interceptor
  } finally {
    assetsLoading.value = false
  }
}

function goBack() {
  router.push('/employees')
}

onMounted(() => {
  fetchEmployee()
  fetchAssets()
})
</script>

<style scoped>
.employee-detail-page {
  padding: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
