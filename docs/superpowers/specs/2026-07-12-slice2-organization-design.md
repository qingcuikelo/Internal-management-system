# 切片2 设计文档：组织域（部门 + 员工）

> 版本：v1 · 日期：2026-07-12
> 上游依据：《企业内部管理系统详细设计方案.md》§5.4、§5.5、§6.1、§6.2、§8.6
> 前置：切片1（地基 + 认证/RBAC）已合并到 main。本切片在其之上实现组织域。

---

## 1. 目标与验收标准

**目标**：实现部门与员工两个组织域资源的完整管理接口，并**首次接入行级数据范围过滤**（把切片1 建好的 `data_scope_descriptor` 落到查询上）。

**验收标准（DoD）**：
1. 部门接口：树查询、列表、详情、新增、编辑、删除（软删，删除前置校验：无子部门 + 无在职员工）。
2. 员工接口：分页查询（工号/姓名/部门/状态筛选，姓名与工号模糊）、详情、新增、编辑（改直属上级时防环）、删除（软删）、批量修改部门。
3. **数据范围**已接入部门/员工的查询与详情：
   - super_admin / hr_admin / it_admin（`data_scope=all`）：看全部。
   - dept_manager（`data_scope=dept`）：只看本部门 + 子部门（部门树递归）范围内的部门与员工。
   - employee（`data_scope=self`）：员工只看本人；部门无 `department:view` 权限，不可访问部门接口。
   - 越权访问单个资源（详情/编辑/删除不在自己数据范围内的对象）返回 404（不泄露存在性）。
4. 所有写操作（部门/员工的 create/update/delete、批量改部门）记入 `operation_logs`（复用切片1 的写日志基建）。
5. 权限点校验：每个接口按 §8.6 所需 `权限code` 用 `require_permission` 拦截。
6. pytest 在 `ims_test` 全绿（含数据范围过滤、防环、删除前置校验、分页筛选的用例）；`ruff` 干净、0 warning。

**不在本切片范围**（明确排除）：
- 员工离职处理 `POST /employees/{id}/resign`（含工位/设备释放级联）→ **切片3**。
- 员工批量导入/导出 `POST /employees/import`、`GET /employees/export`（Celery 异步）→ **切片5**。
- 工位/设备、报表、系统管理（账号/角色/日志/字典的管理接口）。
- 部门子树的 Redis 缓存：本切片直接从库计算子树（正确、简单）；Redis 缓存作为后续性能优化，**不在本切片**（在服务层留清晰接入点）。

---

## 2. 相关数据表（均已在切片1 建好，本切片不改表）

- `departments`（§5.4）：`id, name, parent_id(FK自关联), manager_id(FK→employees), sort_order, status, 审计, deleted_at`。
- `employees`（§5.5）：`id, employee_no(唯一,active_flag), name, gender, email(唯一), phone(唯一), department_id(FK), direct_supervisor_id(FK自关联), position, hire_date, resign_date, status, 审计, deleted_at`。

> 本切片仅新增 repository/service/router/schema 与测试，不新增/修改 Alembic 迁移（表结构已就位）。若发现确需改表，走新迁移并在报告中说明。

---

## 3. 数据范围落地（本切片核心新增能力）

切片1 已提供 `app/core/deps.py::data_scope_descriptor(user) -> dict`，返回：
- `{"scope": "all"}`
- `{"scope": "dept", "department_id": <本人部门, 可能为 None>}`
- `{"scope": "self", "employee_id": <本人绑定员工, 可能为 None>}`

本切片新增 `app/services/scope_service.py`（或在 department_service 内）一个 helper：

- `accessible_department_ids(db, user) -> set[str] | None`：
  - `all` → 返回 `None`（表示不加过滤）。
  - `dept` → 读取全部未删部门的 `(id, parent_id)`，用切片1 的 `utils.tree.descendant_ids` 求 `department_id` 的子树集合；`department_id` 为 None 时返回**空集合**（无可见部门，见切片1 交接注释）。
  - `self` → 员工无部门权限；用于员工域时不走这里。
- 员工查询的数据范围：
  - `all` → 不过滤。
  - `dept` → `WHERE department_id IN accessible_department_ids`（空集合 → 无结果）。
  - `self` → `WHERE id = employee_id`（employee_id 为 None → 无结果）。
- 部门查询的数据范围：
  - `all` → 不过滤。
  - `dept` → `WHERE id IN accessible_department_ids`。
  - `self` → 不可达（employee 无 `department:view`，接口层已被 `require_permission` 拦截）。

**详情/写操作的范围校验**：GET/PUT/DELETE `/{id}` 先取对象，再校验其是否落在上述可见集合内；不在则返回 404。新增 `app/core/exceptions.py::not_found(message="资源不存在") -> BizError(3404, message, 404)`（保持在 3xxx 业务段，HTTP 用 404）。对象本就不存在时也用它。

> 说明：写操作（create/update/delete）在 §3.2 中仅 super/hr（部门/员工）或全局角色可执行，其 `data_scope=all`，因此写操作实际不受行级过滤影响；但详情读取（view）对 dept_manager 受限，需要范围校验。为稳健，PUT/DELETE 也做范围校验（虽然当前有写权限的角色都是 all）。

---

## 4. 接口清单（前缀 `/api/v1`）

**部门 Departments**
| 方法 | 路径 | 权限 | 数据范围 | 说明 |
|---|---|---|---|---|
| GET | `/departments/tree` | department:view | 叠加 | 部门树（含层级），dept_manager 只返回其子树 |
| GET | `/departments` | department:view | 叠加 | 部门列表（可按 name 模糊、status 筛选） |
| GET | `/departments/{id}` | department:view | 叠加 | 部门详情；越范围 404 |
| POST | `/departments` | department:create | — | 新增部门（parent 存在校验；防环：parent 不能是自己/后代——新建无 id 时仅校验 parent 存在） |
| PUT | `/departments/{id}` | department:update | 校验 | 编辑（改 parent 时防环：新 parent 不得为自身或自身子树内节点） |
| DELETE | `/departments/{id}` | department:delete | 校验 | 软删；前置校验：无子部门且无在职员工，否则 3002 |

**员工 Employees**
| 方法 | 路径 | 权限 | 数据范围 | 说明 |
|---|---|---|---|---|
| GET | `/employees` | employee:view | 叠加 | 分页查询（keyword 匹配 name/employee_no 模糊；department_id、status 筛选） |
| GET | `/employees/{id}` | employee:view | 叠加 | 详情（含部门名、直属上级名）；越范围 404 |
| POST | `/employees` | employee:create | — | 新增（employee_no 唯一；email/phone 唯一可空；department/supervisor 存在校验） |
| PUT | `/employees/{id}` | employee:update | 校验 | 编辑（改 direct_supervisor_id 时防环：不得指向自身或自身下属链） |
| DELETE | `/employees/{id}` | employee:delete | 校验 | 软删 |
| PATCH | `/employees/batch-department` | employee:update | — | 批量改部门（body: `{employee_ids:[], department_id}`；校验部门存在） |

> 离职/导入/导出接口不在本切片（见 §1 排除）。

---

## 5. 关键业务规则

### 5.1 部门删除前置校验（§6.1）
删除前：① 该部门无未删子部门；② 该部门无在职（status=1、未删）员工。任一不满足 → `BizError(3002, "部门下有子部门或在职员工，不能删除")`，HTTP 409。满足则软删（置 `deleted_at`）。

### 5.2 部门防环（parent_id）
编辑部门 parent 时：新 parent 不得等于自身，且不得是自身子树内的任一节点（否则成环）。用 `descendant_ids(该部门)` 判断新 parent 是否在其中；命中 → `BizError(3003, "上级部门不能是自己或其下级")`。

### 5.3 员工直属上级防环（direct_supervisor_id，§4 约束）
编辑员工上级时：沿新上级的 `direct_supervisor_id` 链向上遍历，若遇到该员工自身 → 成环，拒绝 `BizError(3004, "直属上级不能形成环")`。也禁止上级为自身。

### 5.4 唯一性
`employee_no` 唯一（活跃记录间，active_flag 复合唯一，切片1 已建）；`email`、`phone` 唯一可空。新增/编辑冲突时捕获并返回 `BizError(3005, "工号/邮箱/手机号已存在")`（或分别的消息），HTTP 409。优先在 service 层显式查重给出友好信息，DB 唯一索引兜底。

### 5.5 存在性校验
新增/编辑员工时若给了 `department_id`/`direct_supervisor_id`，校验其存在且未删；部门新增/编辑时若给了 `parent_id`/`manager_id`，校验存在。不存在 → 2xxx 参数错误或 3xxx 业务错误（用 3xxx 业务语义）。

### 5.6 审计与日志
create/update/delete/batch-department 均：设置 `created_by/updated_by`=当前用户 id；写 `operation_logs`（module=department/employee，action=create/update/delete/batch_update，target_type/target_id，detail 记录 before/after 关键字段），事务内提交。

---

## 6. 分层落点与新增文件

严格沿用切片1 四层（api → routers → services → repositories → models）。本切片新增：

```
app/
├── schemas/
│   ├── department.py        # DepartmentCreate/Update/Out/TreeNode
│   └── employee.py          # EmployeeCreate/Update/Out/ListItem/BatchDepartmentReq
├── repositories/
│   ├── department_repo.py   # 树/子节点/存在校验/软删过滤/分页/子树id
│   └── employee_repo.py     # 扩展：分页筛选(+数据范围)/create/update/软删/批量改部门/查重
├── services/
│   ├── department_service.py# 删除前置校验、防环、树构建、数据范围、写日志
│   ├── employee_service.py  # 上级防环、批量改部门、查重、数据范围、写日志
│   └── scope_service.py     # accessible_department_ids(db, user) 等数据范围 helper
├── routers/
│   ├── departments.py       # /departments/*
│   └── employees.py         # /employees/*
└── api/v1.py                # 挂载 departments、employees 两个 router
```
> 切片1 的认证查询在 `user_repo.py`；`employee_repo.py` 与 `department_repo.py` 均为**本切片新建**。数据范围测试通过 `seed_service.run_seed(db)` 获得 5 个内置角色与权限矩阵，再构造部门/员工/账号。

测试：
```
tests/
├── test_departments.py      # CRUD、树、删除前置校验、防环、数据范围
└── test_employees.py        # 分页筛选、详情、新增/编辑、上级防环、批量改部门、数据范围、查重
```

---

## 7. Schema 要点

- `DepartmentCreate`：`name(必填), parent_id?, manager_id?, sort_order=0, status=1`。
- `DepartmentUpdate`：同上可选字段。
- `DepartmentOut`：全字段 + `parent_id`；`DepartmentTreeNode`：`id,name,sort_order,status,children:[]`。
- `EmployeeCreate`：`employee_no(必填), name(必填), gender(必填,枚举校验), email?(EmailStr), phone?, department_id?, direct_supervisor_id?, position?, hire_date?`。
- `EmployeeUpdate`：上述可选。
- `EmployeeListItem`：`id, employee_no, name, department_name, position, status`（§8.7② 示例）。
- `EmployeeOut`：详情，含 `department_id, department_name, direct_supervisor_id, supervisor_name, gender, email, phone, hire_date, status`。
- `BatchDepartmentReq`：`employee_ids: list[str]（非空）, department_id: str | None`。
- gender/status 枚举取值用 Pydantic 校验（gender ∈ {0,1,2}）。

---

## 8. 测试要点（跑 ims_test）

- 部门：建树 → tree 返回层级；删除有子部门/在职员工被拒（3002）；改 parent 成环被拒（3003）；正常 CRUD；软删后同名可重建（若有唯一约束，此处部门 name 无唯一约束，跳过）。
- 员工：分页 + keyword 模糊（name/no）+ department/status 筛选；新增查重（重复 employee_no → 3005）；改上级成环被拒（3004）；批量改部门；软删。
- **数据范围**（核心）：构造 dept_manager 账号（绑定某部门的员工）与 employee 账号，验证：
  - dept_manager 列表只返回其子树部门/员工；越范围详情 404。
  - employee 员工详情只能取本人；他人 404；员工无部门接口权限（1003）。
  - hr_admin/super_admin 看全部。
- 写操作产生 operation_logs 记录。

---

## 9. 运行/验证
沿用切片1：`alembic upgrade head`（表已在）、`pytest`、`uvicorn` + `/docs` 手测 `/api/v1/departments/tree`、`/api/v1/employees`。数据范围可用不同角色 token 手测验证。

---

## 10. 风险与决策
- **子树计算**：本切片从库实时计算（`descendant_ids`），未加 Redis 缓存；在 `scope_service` 留缓存接入点，后续切片按 §3.3/§9 加缓存 + 部门写操作失效。
- **越范围返回 404 vs 403**：统一用 404（not-found 语义）避免泄露对象存在性；接口层无权限（缺 permission code）仍返回 1003/403。
- **写操作范围校验**：当前有写权限的角色均为 `all`，范围校验对它们是恒真；仍保留校验以防未来自定义角色。
- **error code 新增**：3002 部门有子/在职员工、3003 部门成环、3004 员工上级成环、3005 唯一冲突、3404 not-found（HTTP 404，`not_found()` helper）。
