# 切片6 设计文档：前端 SPA（Vue3 + TS + Pinia + Element Plus）

> 版本：v1 · 日期：2026-07-12
> 上游依据：《企业内部管理系统详细设计方案.md》§1（技术选型）、§3（RBAC 权限模型）、§8（API 接口清单）
> 前置：切片1-5 已合并（完整后端 API 就绪）。本切片构建消费这些 API 的前端 SPA。

---

## 1. 目标与验收标准

**目标**：构建完整的企业内部管理系统前端 SPA——登录认证、RBAC 权限驱动的菜单/路由守卫、5 个业务域（部门/员工/工位/设备/系统管理）的完整 CRUD 页面、报表页面、导入/导出交互，以及 Element Plus 统一 UI。

**验收标准（DoD）**：
1. **登录**：用户名+密码登录 → token 存储 → 跳转首页。Token 过期自动刷新（401 → refresh → 重试）；刷新也失败 → 跳登录。登出清除 token。
2. **布局**：侧边栏（根据权限展示菜单，`/auth/me` 返回的 `permissions` 决定可见性）+ 顶栏（当前用户信息 + 登出）+ 内容区。侧边栏可折叠。
3. **路由守卫**：未登录 → 重定向 `/login`。已登录但无目标路由所需权限 → 403 页。动态路由按角色权限过滤。
4. **部门**：树形展示 + 新增/编辑/删除（含校验阻断提示：子部门/在职员工）。
5. **员工**：分页列表（筛选：关键词/部门/状态）+ 新增/编辑/查看 + 批量改部门 + 离职处理 + 导入（上传 Excel → 轮询 task → 显示结果）+ 导出（提交→ 轮询 task → 下载）。
6. **工位**：列表（筛选：编号/位置/类型/状态/占用人）+ 详情 + 新增 + 编辑 + 分配（带乐观锁 version）+ 释放（单个/批量）+ 状态维护（预留/禁用）+ 分配历史。
7. **设备**：列表（筛选：资产编号/类型/状态/使用人）+ 详情 + 入库 + 编辑 + 领用 + 退还 + 送修 + 报废 + 领用历史。
8. **系统管理**（仅 super_admin 可见菜单组）：账号 CRUD/启停/重置密码 + 角色 CRUD/权限分配（勾选矩阵）+ 操作日志查询 + 数据字典 CRUD。
9. **报表**：员工资产概览 + 闲置资产 + 部门设备统计 + 保修到期。
10. **外观**：Element Plus 中文，统一 loading/错误/空状态，分页控件，表单校验。响应式适配 1366px+ 为主。
11. **构建**：`npm run build` 无错误。

**不在本切片范围**：Docker 部署（切片7）、E2E 测试（后续）、移动端适配、国际化。

---

## 2. 技术栈与项目结构

```
frontend/
├── index.html
├── package.json              # vue3, vue-router, pinia, axios, element-plus, @element-plus/icons-vue
├── vite.config.ts            # proxy /api → backend (dev)
├── tsconfig.json
├── public/
├── src/
│   ├── main.ts               # createApp, use router/pinia/ElementPlus
│   ├── App.vue               # <router-view>
│   ├── api/
│   │   ├── client.ts         # Axios 实例：baseURL=/api/v1, 拦截器（attach token, refresh on 401, unwrap envelope）
│   │   ├── auth.ts           # login, refresh, logout, me
│   │   ├── departments.ts    # CRUD + tree
│   │   ├── employees.ts      # CRUD + resign + batch-dept + import/export
│   │   ├── workstations.ts   # CRUD + assign/release/batch-release/status/history
│   │   ├── devices.ts        # CRUD + checkout/return/repair/scrap/history
│   │   ├── users.ts          # CRUD + status/reset-password
│   │   ├── roles.ts          # CRUD + permissions
│   │   ├── dicts.ts          # by-type (public) + CRUD (admin)
│   │   ├── reports.ts        # 4 report endpoints
│   │   └── tasks.ts          # task status + export download
│   ├── stores/
│   │   ├── auth.ts           # user info, token, login/logout/refresh actions
│   │   └── dict.ts           # dict cache (fetch by type, reuse across pages)
│   ├── router/
│   │   └── index.ts          # routes + beforeEach guard (auth, permission)
│   ├── layouts/
│   │   └── MainLayout.vue    # el-container: sidebar + header + main
│   ├── views/
│   │   ├── Login.vue
│   │   ├── Forbidden.vue
│   │   ├── dashboard/
│   │   │   └── Index.vue     # welcome/home
│   │   ├── departments/
│   │   │   └── Index.vue     # tree + CRUD dialogs
│   │   ├── employees/
│   │   │   ├── Index.vue     # table + filters + CRUD
│   │   │   ├── Detail.vue    # employee detail + assets
│   │   │   └── Import.vue    # upload + task polling
│   │   ├── workstations/
│   │   │   ├── Index.vue     # table + filters
│   │   │   └── Detail.vue    # detail + assign dialog + history
│   │   ├── devices/
│   │   │   ├── Index.vue     # table + filters
│   │   │   └── Detail.vue    # detail + checkout dialog + history
│   │   ├── system/
│   │   │   ├── Users.vue
│   │   │   ├── Roles.vue     # list + permission assignment dialog
│   │   │   ├── Dicts.vue
│   │   │   └── Logs.vue
│   │   └── reports/
│   │       └── Index.vue     # tab-based: 4 reports
│   ├── components/
│   │   ├── Pagination.vue    # 分页封装
│   │   ├── StatusTag.vue     # 状态标签（通用，按字典/常量映射颜色）
│   │   └── FileUpload.vue    # Excel 上传 + 进度
│   └── utils/
│       ├── permission.ts     # hasPermission(code) helper
│       └── format.ts         # date, gender, status formatters
```

---

## 3. 权限与路由设计

### 3.1 菜单可见性（由 `/auth/me` 返回的 `permissions` 决定）

| 菜单项 | 所需权限 | 可见角色 |
|---|---|---|
| 首页 | 登录 | 全部 |
| 部门管理 | department:view | super/hr/it/dept_mgr |
| 员工管理 | employee:view | super/hr/it/dept_mgr/employee(本人) |
| 工位管理 | workstation:view | super/hr/it/dept_mgr/employee |
| 设备管理 | device:view | super/it/dept_mgr/employee |
| 报表 | report:view | super/hr/it/dept_mgr |
| 系统管理 | system:user\|role\|log\|dict (任一) | super 仅 |

### 3.2 路由表（路径 + 权限 + 懒加载）

```
/login              → Login.vue (公开)
/                   → MainLayout > Dashboard (登录)
/departments        → MainLayout > departments/Index (department:view)
/employees          → MainLayout > employees/Index (employee:view)
/employees/:id      → MainLayout > employees/Detail (employee:view)
/employees/import   → MainLayout > employees/Import (employee:import)
/workstations       → MainLayout > workstations/Index (workstation:view)
/workstations/:id   → MainLayout > workstations/Detail (workstation:view)
/devices            → MainLayout > devices/Index (device:view)
/devices/:id        → MainLayout > devices/Detail (device:view)
/system/users       → MainLayout > system/Users (system:user)
/system/roles       → MainLayout > system/Roles (system:role)
/system/dicts       → MainLayout > system/Dicts (system:dict)
/system/logs        → MainLayout > system/Logs (system:log)
/reports            → MainLayout > reports/Index (report:view)
/403                → Forbidden.vue (登录)
```

### 3.3 路由守卫逻辑
```
beforeEach:
  1. 无 token → /login（白名单除外）
  2. 有 token 但无 user 信息 → fetch /auth/me → 存 store
  3. route.meta.permission 存在 → 检查 user.permissions 是否包含 → 不含则 /403
  4. 否则放行
```

---

## 4. API 层设计（Axios 封装）

### 4.1 拦截器
- **请求拦截**：自动附加 `Authorization: Bearer <access_token>`
- **响应拦截**：
  - `code == 0` → 解包返回 `data`（业务层无需处理 envelope）
  - `code == 1001` → 尝试 refresh → 成功则重试原请求（1 次）；refresh 也失败 → 清 token → 跳 /login
  - 其他非 0 → reject，调用方捕获处理（ElMessage.error 显示 message）

### 4.2 请求封装模式
每个 API 模块导出 async 函数，入参为业务参数，返回 Promise<业务数据类型>。示例：
```typescript
// api/workstations.ts
export function listWorkstations(params: WorkstationListParams): Promise<PageResult<Workstation>> {
  return client.get('/workstations', { params })
}
```

---

## 5. 页面设计要点

### 5.1 部门管理
- **树形展示**：`el-tree` 组件，每个节点显示名称+操作按钮（编辑/删除/添加子部门）
- **弹窗**：新增/编辑用 `el-dialog`，表单含名称、上级部门（下拉树）、主管、排序、状态
- **删除校验**：后端返回 3002 → 提示「部门下有子部门/在职员工，不能删除」

### 5.2 员工管理
- **列表**：`el-table` + 分页 + 筛选栏（关键词、部门下拉、状态下拉）
- **新增/编辑**：表单含工号、姓名、性别、部门、职位、上级、手机、邮箱、入职日期
- **批量操作**：批量改部门（勾选 + 下拉选择目标部门）
- **离职**：单行操作 → 弹窗确认 → 显示释放工位数/退还设备数/账号禁用结果
- **导入**：上传 Excel → 显示 task 进度 → 完成弹窗显示成功/失败统计
- **导出**：提交筛选条件 → 等待 task 完成 → 显示下载链接

### 5.3 工位管理
- **列表**：编号、位置、类型、状态（标签颜色）、占用人、操作
- **分配**：选择在职员工 → 提交（带 version） → 冲突→提示刷新
- **释放**：单个/多个勾选
- **状态维护**：预留/禁用按钮
- **历史**：在详情页展示分配历史时间线

### 5.4 设备管理
- **列表**：资产编号、类型、品牌、型号、状态、使用人
- **领用**：选择员工 + 可填领用日期 → 提交（带 version）
- **退还**：确认 → 退还成功
- **送修/报废**：状态流转按钮
- **历史**：领用历史列表

### 5.5 系统管理（super_admin 专属）
- **账号**：列表 + 新增（角色/绑定员工/初始密码）+ 编辑 + 启停 + 重置密码
- **角色权限**：角色列表 + 新增/编辑角色 + 权限分配（el-checkbox-group 按模块分组，覆盖式提交）
- **操作日志**：表格 + 筛选（用户/模块/操作/时间范围），只读
- **数据字典**：左侧类型列表 + 右侧该类型下的条目 CRUD

### 5.6 报表
- 4 个 Tab：员工资产概览（选择员工→展示工位+设备）、闲置资产（统计卡片）、部门设备统计（表格或柱状图预留）、保修到期（天数输入+表格）

### 5.7 通用交互
- **分页**：统一 `Pagination` 组件封装 `el-pagination`
- **空状态**：`el-empty` 占位
- **加载**：表格 `v-loading`，提交按钮 `loading` 属性
- **确认**：删除/离职等危险操作 → `el-message-box` 确认
- **提示**：成功 → `ElMessage.success`，失败 → `ElMessage.error(message)`
- **状态标签**：`StatusTag` 组件，根据状态值和对应枚举/常量映射 `el-tag` 的 type 颜色

---

## 6. 状态管理（Pinia）

### auth store
```typescript
{
  token: string | null,          // access_token (localStorage 持久化)
  refreshToken: string | null,   // refresh_token (localStorage 持久化)
  user: UserInfo | null,         // 来自 /auth/me
  permissions: Set<string>,      // 权限点集合
  isLoggedIn: computed,
  login(username, password),
  logout(),
  fetchUser(),
  refreshAccessToken()
}
```

### dict store
```typescript
{
  cache: Map<string, DictItem[]>,  // dict_type → items
  async fetchType(type: string),   // 查缓存，未命中则调 API
  getOptions(type: string)         // 转 el-option 格式
}
```

---

## 7. 权限指令/辅助
- `hasPermission(code)`: 从 auth store 读取 permissions 集合，返回 boolean
- `v-permission` 指令（可选，按钮级控制）
- 菜单项 `hidden` 由 permission check 动态计算

---

## 8. 构建与开发

### package.json 关键依赖
```json
{
  "vue": "^3.4",
  "vue-router": "^4.3",
  "pinia": "^2.1",
  "axios": "^1.7",
  "element-plus": "^2.8",
  "@element-plus/icons-vue": "^2.3"
}
```
开发时 `vite.config.ts` 配置 proxy：`/api` → `http://localhost:8000`（后端 uvicorn 端口）。

### 测试
- 本切片不做自动化测试（前端单元/E2E 延后）
- 验收手段：`npm run build` 成功 + 开发环境手动检查关键页面

---

## 9. 风险与决策
- **无 E2E/单元测试**：前端测试延后（切片6 交付手动验证构建 + 关键页面），后续可加 Playwright。
- **无 TypeScript 严格模式**：渐进式，先 `strict: false`，重点对 API 类型和 store 类型建模。
- **Element Plus 中文**：全局注册中文 locale。
- **Token 存储**：localStorage（简单可行；生产可改为 httpOnly cookie，切片7 考虑 Nginx 反向代理 + 安全加固时再议）。
- **403 页**：提供「返回首页」按钮，不做角色切换（一个账号一个角色）。
