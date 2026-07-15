<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar">
      <div class="logo">{{ collapsed ? 'IMS' : '企业内部管理系统' }}</div>
      <el-menu
        :default-active="route.path"
        :collapse="collapsed"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </el-menu-item>

        <template v-for="item in visibleMenus" :key="item.index">
          <el-sub-menu v-if="item.children" :index="item.index">
            <template #title>
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </template>
            <el-menu-item v-for="child in item.children" :key="child.index" :index="child.index">
              {{ child.title }}
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.index">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-button @click="collapsed = !collapsed" :icon="collapsed ? Expand : Fold" text />
        </div>
        <div class="header-right">
          <span class="user-info">{{ auth.user?.username }} ({{ auth.user?.role }})</span>
          <el-button @click="auth.doLogout()" text type="danger">退出</el-button>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { HomeFilled, Expand, Fold, OfficeBuilding, User, Monitor, Cpu, Setting, DataAnalysis } from '@element-plus/icons-vue'

const route = useRoute()
const auth = useAuthStore()
const collapsed = ref(false)

interface MenuItem {
  index: string
  title: string
  icon: any
  permission?: string
  children?: { index: string; title: string; permission?: string }[]
}

const allMenus: MenuItem[] = [
  { index: '/departments', title: '部门管理', icon: OfficeBuilding, permission: 'department:view' },
  {
    index: 'employees-group', title: '员工管理', icon: User,
    children: [
      { index: '/employees', title: '员工列表', permission: 'employee:view' },
    ],
  },
  { index: '/workstations', title: '工位管理', icon: Monitor, permission: 'workstation:view' },
  { index: '/devices', title: '设备管理', icon: Cpu, permission: 'device:view' },
  { index: '/reports', title: '报表', icon: DataAnalysis, permission: 'report:view' },
  {
    index: 'system-group', title: '系统管理', icon: Setting,
    children: [
      { index: '/system/users', title: '账号管理', permission: 'system:user' },
      { index: '/system/roles', title: '角色权限', permission: 'system:role' },
      { index: '/system/dicts', title: '数据字典', permission: 'system:dict' },
      { index: '/system/logs', title: '操作日志', permission: 'system:log' },
    ],
  },
]

const visibleMenus = computed(() => {
  return allMenus
    .map((item) => {
      if (item.children) {
        const visible = item.children.filter((c) => auth.hasPermission(c.permission!))
        if (visible.length === 0) return null
        return { ...item, children: visible }
      }
      if (item.permission && !auth.hasPermission(item.permission)) return null
      return item
    })
    .filter(Boolean) as MenuItem[]
})
</script>

<style scoped>
.layout { height: 100vh; }
.sidebar { background-color: #304156; overflow-y: auto; }
.logo { height: 60px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; font-weight: bold; white-space: nowrap; overflow: hidden; }
.header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e6e6e6; background: #fff; height: 60px; }
.header-left, .header-right { display: flex; align-items: center; gap: 12px; }
.user-info { color: #606266; }
.el-menu { border-right: none; }
.el-main { background: #f0f2f5; padding: 20px; }
</style>
