<template>
  <div class="page">
    <el-card>
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <!-- Tab 1: 员工资产概览 -->
        <el-tab-pane label="员工资产概览" name="assets">
          <div style="margin-bottom: 16px">
            <el-select
              v-model="assetEmployeeId"
              placeholder="选择员工"
              filterable
              remote
              :remote-method="searchEmployees"
              :loading="searchingEmp"
              style="width: 300px"
              @change="onEmployeeSelected"
            >
              <el-option
                v-for="e in empOptions"
                :key="e.id"
                :label="`${e.name} (${e.employee_no})`"
                :value="e.id"
              />
            </el-select>
          </div>

          <el-row :gutter="16">
            <el-col :span="12">
              <el-card>
                <template #header>当前工位</template>
                <div v-if="empAssetsLoading" v-loading="empAssetsLoading" style="height: 60px" />
                <div v-else-if="empAssetsWorkstation" style="line-height: 1.8">
                  <p>编号：{{ empAssetsWorkstation.code }}</p>
                  <p>位置：{{ empAssetsWorkstation.location }}</p>
                </div>
                <div v-else style="color: #909399">无</div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card>
                <template #header>持有设备</template>
                <div v-if="empAssetsLoading" v-loading="empAssetsLoading" style="height: 60px" />
                <el-table v-else-if="hasDevices" :data="empAssetsDevices" size="small" stripe>
                  <el-table-column prop="asset_code" label="资产编号" width="120" />
                  <el-table-column prop="type" label="类型" width="80" />
                  <el-table-column prop="brand" label="品牌" width="100" />
                  <el-table-column prop="model" label="型号" width="100" />
                </el-table>
                <div v-else style="color: #909399">无设备</div>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>

        <!-- Tab 2: 闲置资产 -->
        <el-tab-pane label="闲置资产" name="idle">
          <div v-loading="idleLoading" style="min-height: 100px">
            <el-row :gutter="32" style="margin-top: 24px">
              <el-col :span="12">
                <el-card style="text-align: center">
                  <h3 style="margin: 0 0 16px 0; color: #909399">闲置工位</h3>
                  <el-statistic :value="idleWorkstations" />
                </el-card>
              </el-col>
              <el-col :span="12">
                <el-card style="text-align: center">
                  <h3 style="margin: 0 0 16px 0; color: #909399">在库设备</h3>
                  <el-statistic :value="idleDevices" />
                </el-card>
              </el-col>
            </el-row>
          </div>
        </el-tab-pane>

        <!-- Tab 3: 部门设备统计 -->
        <el-tab-pane label="部门设备统计" name="dept">
          <div style="margin-bottom: 16px">
            <el-tree-select
              v-model="deptFilterId"
              :data="deptTree"
              :props="{ label: 'name', value: 'id', children: 'children' }"
              placeholder="选择部门（全部）"
              clearable
              check-strictly
              filterable
              style="width: 240px"
              @change="fetchDeptStats"
            />
          </div>
          <el-table :data="deptStats" v-loading="deptStatsLoading" stripe>
            <el-table-column prop="department_name" label="部门名称" min-width="200" />
            <el-table-column prop="count" label="设备数量" width="120" />
          </el-table>
        </el-tab-pane>

        <!-- Tab 4: 保修到期 -->
        <el-tab-pane label="保修到期" name="warranty">
          <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 12px">
            <span>到期天数：</span>
            <el-input-number v-model="warrantyDays" :min="1" :max="365" style="width: 120px" />
            <el-button type="primary" @click="fetchWarrantyData">查询</el-button>
          </div>
          <el-table :data="warrantyItems" v-loading="warrantyLoading" stripe>
            <el-table-column prop="asset_code" label="资产编号" width="150" />
            <el-table-column prop="type" label="类型" width="100" />
            <el-table-column prop="brand" label="品牌" width="120" />
            <el-table-column prop="model" label="型号" width="120" />
            <el-table-column prop="current_employee_id" label="使用人ID" width="120" />
            <el-table-column prop="warranty_expire" label="保修到期" width="120" sortable />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, shallowRef } from 'vue'
import { getEmployeeAssets, getIdleAssets, getDeviceByDepartment, getWarrantyExpiring } from '@/api/reports'
import { listEmployees } from '@/api/employees'
import { getTree } from '@/api/departments'
import type { EmployeeAssets, IdleAssets, DeviceByDeptItem, WarrantyExpiringItem } from '@/api/reports'
import type { EmployeeItem } from '@/api/employees'
import type { DeptNode } from '@/api/departments'

const activeTab = ref('assets')

// ========== Tab: Employee Assets ==========
const assetEmployeeId = ref('')
const empOptions = ref<EmployeeItem[]>([])
const searchingEmp = ref(false)
const empAssets = shallowRef<EmployeeAssets | null>(null)
const empAssetsLoading = ref(false)

const empAssetsWorkstation = computed(() => empAssets.value?.workstation ?? null)
const empAssetsDevices = computed(() => empAssets.value?.devices ?? [])
const hasDevices = computed(() => empAssetsDevices.value.length > 0)

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

function onEmployeeSelected() {
  if (!assetEmployeeId.value) return
  empAssetsLoading.value = true
  getEmployeeAssets(assetEmployeeId.value)
    .then((data) => {
      empAssets.value = data
    })
    .catch(() => {})
    .finally(() => {
      empAssetsLoading.value = false
    })
}

// ========== Tab: Idle Assets ==========
const idleLoading = ref(false)
const idleData = shallowRef<IdleAssets | null>(null)

const idleWorkstations = computed(() => {
  const v = idleData.value?.idle_workstations
  return v !== null && v !== undefined ? v : '—'
})

const idleDevices = computed(() => {
  const v = idleData.value?.idle_devices
  return v !== null && v !== undefined ? v : '—'
})

async function fetchIdleAssets() {
  idleLoading.value = true
  try {
    idleData.value = await getIdleAssets()
  } catch {
    // handled by interceptor
  } finally {
    idleLoading.value = false
  }
}

// ========== Tab: Department Stats ==========
const deptTree = ref<DeptNode[]>([])
const deptFilterId = ref('')
const deptStats = ref<DeviceByDeptItem[]>([])
const deptStatsLoading = ref(false)

async function fetchDeptTree() {
  try {
    deptTree.value = await getTree()
  } catch {
    // handled by interceptor
  }
}

async function fetchDeptStats() {
  deptStatsLoading.value = true
  try {
    const result = await getDeviceByDepartment(deptFilterId.value || undefined)
    deptStats.value = result.items
  } catch {
    // handled by interceptor
  } finally {
    deptStatsLoading.value = false
  }
}

// ========== Tab: Warranty Expiring ==========
const warrantyDays = ref(30)
const warrantyItems = ref<WarrantyExpiringItem[]>([])
const warrantyLoading = ref(false)

async function fetchWarrantyData() {
  warrantyLoading.value = true
  try {
    const result = await getWarrantyExpiring(warrantyDays.value)
    warrantyItems.value = result.items
  } catch {
    // handled by interceptor
  } finally {
    warrantyLoading.value = false
  }
}

// ========== Tab change handler ==========
async function onTabChange(tabName: string) {
  if (tabName === 'idle' && idleData.value === null) {
    fetchIdleAssets()
  } else if (tabName === 'dept') {
    if (deptTree.value.length === 0) await fetchDeptTree()
    if (deptStats.value.length === 0) fetchDeptStats()
  } else if (tabName === 'warranty' && warrantyItems.value.length === 0) {
    fetchWarrantyData()
  }
}
</script>

<style scoped>
.page {
  padding: 16px;
}
</style>
