# 切片3 设计文档：资产域（工位 + 设备）+ 员工离职级联

> 版本：v1 · 日期：2026-07-12
> 上游依据：《企业内部管理系统详细设计方案.md》§5.6–5.9、§6.2、§6.3、§6.4、§8.6、§10
> 前置：切片1（地基+认证/RBAC）、切片2（组织域）已合并。本切片在其上实现资产域与离职级联。

---

## 1. 目标与验收标准

**目标**：实现工位与设备的全生命周期管理（含**事务 + 乐观锁**的分配/领用），资产的行级数据范围过滤，历史追溯，以及员工**离职级联**（释放工位/退还设备/禁用账号）。

**验收标准（DoD）**：
1. 工位：列表（筛选+数据范围）、详情、新增、编辑、**分配（事务+乐观锁）**、释放（单个/批量）、状态维护（预留/禁用）、分配历史。
2. 设备：列表、详情、入库登记、编辑、**领用（事务+乐观锁）**、退还、送修、报废、领用历史。
3. **并发安全**：分配/领用用 `version` 乐观锁条件更新，受影响行数=0 → 冲突返回 **3001**；主表与历史表同事务提交。并发重复分配的测试（模拟旧 version）验证只有一个成功。
4. **资产数据范围**（§3.3）：dept_manager 只见「当前占用人 ∈ 本部门子树」的工位/设备；employee 只见本人占用的；**闲置工位/在库设备（无占用人）对 dept_manager/employee 不可见**；全局角色见全部。
5. **离职级联（事务）**：`POST /employees/{id}/resign` → 员工 status=0 + resign_date → 释放其占用工位（置闲置+写历史 end_date）→ 退还其全部设备（置在库+写历史 return_date）→ 禁用其绑定登录账号（users.status=0）→ 记操作日志。返回释放/退还数量与账号禁用标志。
6. 权限：按 §3.2/§8.6，工位 view/manage、设备 view/manage、employee:resign 校验。（注意 **hr_admin 无 device:\* 权限**；device:manage 仅 super/it；workstation:manage 为 super/hr/it。）
7. 所有写操作记 `operation_logs`；pytest 全绿（含乐观锁并发、离职级联、数据范围、状态机校验）；ruff 干净、0 warning。

**不在本切片范围**：报表（§6.5，切片5）、Excel 导入导出（切片5）、系统管理接口（账号/角色/日志/字典的管理，切片4）、Celery 到期扫描（切片5）。表结构已在切片1 就位，本切片不改表。

---

## 2. 相关数据表（切片1 已建，不改表）
- `workstations`（§5.6）：status 1=闲置/2=占用/3=预留/4=禁用；`current_employee_id`、`assign_date`、`version`。
- `devices`（§5.7）：status 1=在库/2=使用中/3=维修/4=报废；`current_employee_id`、`assign_date`、`version`、`warranty_expire`。
- `workstation_assignments`（§5.8）：workstation_id、employee_id、start_date、end_date(NULL=占用中)、operator_id、created_at。
- `device_assignments`（§5.9）：device_id、employee_id、checkout_date、return_date(NULL=使用中)、operator_id、created_at。

**状态常量**（代码常量，不入字典，§7）：定义 `app/core/constants.py`：`WorkstationStatus`(IDLE=1, OCCUPIED=2, RESERVED=3, DISABLED=4)、`DeviceStatus`(IN_STOCK=1, IN_USE=2, REPAIR=3, SCRAPPED=4)。

---

## 3. 并发与一致性（本切片核心）

### 3.1 工位分配（事务 + 乐观锁）
```sql
UPDATE workstations
SET current_employee_id=:emp, status=2, assign_date=:d, version=version+1, updated_by=:u, updated_at=:now
WHERE id=:id AND status=1 AND version=:expected_version AND deleted_at IS NULL
```
- rowcount=0 → 工位不可分配（已被占用/预留/禁用 或 version 过期）→ `BizError(3001,"该工位已被占用，请刷新后重试",409)`。
- rowcount=1 → 同事务写 `workstation_assignments`（start_date=分配日, end_date=NULL, operator_id=当前账号）。
- 分配前校验目标员工存在且在职。

### 3.2 工位释放
- 条件更新：`SET status=1, current_employee_id=NULL, assign_date=NULL, version=version+1 WHERE id=? AND status=2 AND deleted_at IS NULL`。
- 同事务把该工位「当前未结束」的历史行 end_date 置为释放日。
- 批量释放：对多个 id 循环执行（各自事务或单事务批处理；本切片单请求事务内逐个处理，任一失败回滚整体或跳过——**约定：批量释放对每个 id 独立尝试，返回成功数；已闲置的跳过**）。

### 3.3 设备领用/退还（同构）
- 领用：`SET current_employee_id=:emp, status=2, assign_date=:d, version=version+1 WHERE id=? AND status=1 AND version=:v AND deleted_at IS NULL`；rowcount=0 → 3001（不可领用：非在库/version 过期）。写 `device_assignments`（checkout_date）。
- 退还：`SET status=1, current_employee_id=NULL, assign_date=NULL, version=version+1 WHERE id=? AND status=2 AND deleted_at IS NULL`；写历史 return_date。
- 送修：`SET status=3, version=version+1 WHERE id=? AND status IN (1) ...`（在库→维修；使用中需先退还，约定仅允许从在库转维修）。报废：`SET status=4 ...`（在库或维修→报废）。维修/报废后不可领用（领用条件 status=1 天然拦截）。非法状态转换 → `BizError(3007,"设备当前状态不允许该操作",409)`。

### 3.4 乐观锁 version 来源
- 分配/领用请求体带 `expected_version`（前端从详情读取）。若未传，服务先读当前 version 再用它做条件（降级为"读-改-写"，仍受 WHERE status 保护，但并发窗口略大）。**约定：请求体可选 `version`；不传则服务读当前值**。测试覆盖「传过期 version → 3001」。

---

## 4. 资产数据范围（§3.3）

新增 `scope_service.asset_scope(db, user) -> dict`：
- `all` → `{"mode":"all"}`（无过滤）。
- `dept` → 计算本部门子树内所有在职/未删员工 id 集合 `emp_ids`，返回 `{"mode":"employees","employee_ids": emp_ids}`。资产过滤：`current_employee_id IN emp_ids`（空集→无结果）。
- `self` → `{"mode":"self","employee_id": own}`。过滤：`current_employee_id == own`。
- **闲置/在库资产（current_employee_id 为 NULL）**：`IN`/`==` 对 NULL 天然不匹配 → dept/self 不可见，符合 §3.3。

需要 `employee_repo.ids_in_departments(db, dept_ids: set[str]) -> set[str]`（返回这些部门下未删员工 id）。子树 dept_ids 复用切片2 的 `scope_service.accessible_department_ids`。

单资源（详情/分配/释放/领用/退还/送修/报废/历史）：先取对象，`_visible(db,user,asset)` 校验（all→True；self→current_employee_id==own；employees→current_employee_id∈emp_ids）；不可见 → `not_found()`（3404）。

> 说明：写操作（manage）的角色都是全局（super/hr/it），数据范围对它们恒真；view 才受限。仍保留单资源可见性校验以防未来自定义角色。

---

## 5. 接口清单（前缀 `/api/v1`）

**工位 Workstations**（§8.6）
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/workstations` | workstation:view | 列表（code/location/type/status/占用人筛选 + 数据范围） |
| GET | `/workstations/{id}` | workstation:view | 详情 |
| POST | `/workstations` | workstation:manage | 新增（status=闲置） |
| PUT | `/workstations/{id}` | workstation:manage | 编辑基础信息 |
| POST | `/workstations/{id}/assign` | workstation:manage | 分配（事务+乐观锁，冲突 3001） |
| POST | `/workstations/{id}/release` | workstation:manage | 释放 |
| POST | `/workstations/batch-release` | workstation:manage | 批量释放（返回成功数） |
| PATCH | `/workstations/{id}/status` | workstation:manage | 设预留/禁用 |
| GET | `/workstations/{id}/history` | workstation:view | 分配历史 |

**设备 Devices**（§8.6）
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/devices` | device:view | 列表（资产编号/类型/状态/使用人筛选 + 数据范围） |
| GET | `/devices/{id}` | device:view | 详情 |
| POST | `/devices` | device:manage | 入库登记（status=在库） |
| PUT | `/devices/{id}` | device:manage | 编辑 |
| POST | `/devices/{id}/checkout` | device:manage | 领用（事务+乐观锁） |
| POST | `/devices/{id}/return` | device:manage | 退还 |
| POST | `/devices/{id}/repair` | device:manage | 送修 |
| POST | `/devices/{id}/scrap` | device:manage | 报废 |
| GET | `/devices/{id}/history` | device:view | 领用历史 |

**员工离职**（§8.6，扩展切片2 的 employees 路由）
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/employees/{id}/resign` | employee:resign | 离职级联（事务） |

---

## 6. 业务规则要点

- **状态机以代码常量为准**（§7），不经字典。工位/设备状态流转在 service 校验（非法转换 3007）。
- **分配/领用前置**：目标员工存在且在职（status=1）；工位须闲置(1)、设备须在库(1)。
- **释放/退还**：找到该资源当前未结束历史行（end_date/return_date 为 NULL）并置结束日；主表回到闲置/在库、清 current_employee_id、version+1。
- **离职级联**（§6.2，事务）：以员工 id 为条件，
  1. 员工：status=0、resign_date=入参日期、updated_by。
  2. 工位：所有 `current_employee_id=该员工` 且未删的工位 → 逐个释放（status=1、清占用、version+1、写历史 end_date=离职日）。
  3. 设备：所有 `current_employee_id=该员工` 且未删的设备 → 逐个退还（status=1、清占用、version+1、写历史 return_date=离职日）。
  4. 账号：`users.employee_id=该员工` → status=0（禁用）。
  5. 操作日志：module=employee, action=resign, detail={released_workstations, returned_devices, account_disabled}。
  - 全部在**一个数据库事务**内；任一步失败整体回滚。返回 `{released_workstations, returned_devices, account_disabled}`（§8.7④）。
  - 数据范围：resign 权限仅 super/hr（全局），无需行级校验；仍取员工存在校验。

- **审计与日志**：写操作设 created_by/updated_by、写 operation_logs（module=workstation/device/employee，action=create/update/assign/release/checkout/return/repair/scrap/resign）。

---

## 7. 分层落点与新增文件

```
app/
├── core/constants.py            # WorkstationStatus / DeviceStatus 常量
├── schemas/
│   ├── workstation.py           # Create/Update/Out/AssignReq/StatusReq/HistoryItem
│   └── device.py                # Create/Update/Out/CheckoutReq/HistoryItem
├── repositories/
│   ├── workstation_repo.py      # 分页(+scope)/get_active/create/update/assign_if_free/release_if_occupied/set_status
│   ├── device_repo.py           # 分页(+scope)/get_active/create/update/checkout_if_available/return_if_in_use/to_repair/to_scrap
│   └── assignment_repo.py       # 工位&设备历史：open_workstation/create_ws/close_ws/list_ws；open_device/create_dev/close_dev/list_dev
├── services/
│   ├── workstation_service.py   # CRUD/assign/release/batch-release/status/history/scope/事务/日志
│   ├── device_service.py        # CRUD/checkout/return/repair/scrap/history/scope/事务/日志
│   ├── employee_service.py      # 扩展：resign() 级联事务
│   └── scope_service.py         # 扩展：asset_scope()
├── repositories/employee_repo.py# 扩展：ids_in_departments()
├── routers/
│   ├── workstations.py          # /workstations/*
│   ├── devices.py               # /devices/*
│   └── employees.py             # 扩展：POST /{id}/resign
└── api/v1.py                    # 挂载 workstations、devices 路由
```

测试：`tests/test_workstation_repo.py`（乐观锁并发）、`tests/test_workstations.py`、`tests/test_device_repo.py`、`tests/test_devices.py`、`tests/test_resign.py`、`tests/test_asset_scope.py`。

---

## 8. Schema 要点
- `WorkstationCreate`：code(必填)、location?、type(必填,取字典 workstation_type 值,但仅字符串校验)、status? 默认1、notes?。
- `WorkstationAssignReq`：employee_id(必填)、assign_date?(默认今天)、version?(乐观锁,可选)。
- `WorkstationStatusReq`：status ∈ {3,4}（预留/禁用；置回闲置用 release）。
- `DeviceCreate`：asset_code(必填)、type(必填)、brand?/model?/serial_number?/specs?/purchase_date?/warranty_expire?/notes?。
- `DeviceCheckoutReq`：employee_id、assign_date?、version?。
- 历史项：工位 {employee_id, employee_name, start_date, end_date, operator_id}；设备 {employee_id, employee_name, checkout_date, return_date, operator_id}。

---

## 9. 错误码新增
- `3001` 资源冲突/已被占用（乐观锁失败）：`conflict()` → HTTP 409。
- `3007` 非法状态转换（如领用非在库设备、退还非使用中）：`invalid_state()` → HTTP 409。
- 复用 `3404`（not_found，越范围/不存在）、`3002`（引用实体不存在，如分配/领用的目标员工不存在）、`3005`（唯一冲突：code/asset_code/serial_number 重复）。

---

## 10. 测试要点（跑 ims_test）
- **乐观锁并发**（repo 层）：两次 assign_if_free 用同一 expected_version，仅一次 rowcount=1，另一次=0。
- 工位：分配→占用；重复分配已占用→3001；释放→闲置并写历史 end_date；批量释放计数；预留/禁用。
- 设备：入库→领用→使用中；领用非在库→3001/3007；退还→在库+历史 return；送修→维修，维修中领用→3001；报废→报废。
- **资产数据范围**：dept_manager 只见占用人在子树内的资产；闲置/在库资产对其不可见；employee 只见本人占用；越范围详情 404；全局见全部。
- **离职级联**：造一名占用工位+持有 2 台设备+绑定账号的员工 → resign → 断言工位释放、设备退还、账号禁用、员工 status=0/resign_date、历史行闭合、返回计数正确；操作日志写入。
- 权限：hr_admin 访问 device 接口→1003；dept_manager 访问 workstation:manage→1003。

---

## 11. 风险与决策
- **乐观锁 version 可选**：请求可不带 version（服务读当前值），带则严格校验。生产建议前端始终带 version。
- **批量释放语义**：逐个独立尝试，返回成功数；已闲置项跳过不算失败。
- **离职级联原子性**：全程单事务，任一步失败整体回滚（§10）。
- **资产 view 的数据范围经 current_employee JOIN**：闲置资产不归属部门，dept/self 不可见（§3.3 明确）。
- **状态机用常量非字典**（§7），避免运营误改状态逻辑。
