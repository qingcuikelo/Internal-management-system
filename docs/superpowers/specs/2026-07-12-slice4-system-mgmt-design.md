# 切片4 设计文档：系统管理域（账号 / 角色权限 / 操作日志 / 数据字典）

> 版本：v1 · 日期：2026-07-12
> 上游依据：《企业内部管理系统详细设计方案.md》§3、§5.1–5.3、§5.10–5.11、§7、§8.6、§8.7
> 前置：切片1（地基+认证/RBAC）、切片2（组织域）、切片3（资产域+离职级联）已合并。本切片在其上实现系统管理域。

---

## 1. 目标与验收标准

**目标**：实现系统管理域四个子模块——**账号管理**（CRUD/启停/重置密码/绑定员工）、**角色权限**（角色 CRUD + 权限分配）、**操作日志**（只读分页查询）、**数据字典**（可扩展枚举 CRUD + Redis 缓存），并落实 `system:*` 权限（仅 super_admin）与数据字典读取缓存。

**验收标准（DoD）**：
1. **账号**：列表（用户名/角色/状态筛选+分页）、详情、新增（设角色+可选绑定员工+初始密码）、编辑（角色/绑定员工）、软删除、启用/禁用、重置密码。
2. **角色权限**：角色列表/详情/新增/编辑/删除、查看角色已授权限、覆盖式分配权限、全部权限点（按模块分组）。
3. **操作日志**：分页查询（user_id/module/action/start/end 筛选），**只读、不可改**。
4. **数据字典**：按类型取全部启用项（登录可读、走 Redis 缓存）、分页查询、新增、编辑、删除；**任一写操作后失效该 `dict_type` 的缓存**。
5. **权限**：`system:user`/`system:role`/`system:log`/`system:dict` 均仅 super_admin（§3.2）；`GET /dicts/{dict_type}` 仅需登录。非 super 访问系统接口→**1003**。
6. **安全约束**：密码 bcrypt 哈希，严禁明文/回显；重置密码写 `pwd_updated_at`（自然吊销该账号旧 token）；不能禁用/删除自己；内置角色不可删除、不可改 `code`/`data_scope`；super_admin 角色的权限集合不可修改（始终全量）。
7. 所有写操作记 `operation_logs`（module=user/role/dict）；pytest 全绿（含权限守卫、缓存失效、内置角色约束、唯一冲突、自我禁用守卫）；ruff 干净、0 warning。

**不在本切片范围**：报表（§6.5，切片5）、Excel 导入导出与异步任务 `/tasks/{id}`（切片5）、前端（切片6）、Docker（切片7）。表结构已在切片1 就位，本切片不改表。

---

## 2. 相关数据表（切片1 已建，不改表）

- `users`（§5.1）：username(软删唯一 `uk_username_active`)、password_hash、role_id(FK)、employee_id(FK,NULL)、status(1启用/0禁用)、last_login_at、pwd_updated_at；软删除。
- `roles`（§5.2）：code(唯一)、name、is_builtin(1内置/0自定义)、data_scope(all/dept/self)、status；**无软删除、无审计列** → 硬删除。
- `permissions`（§5.3）：code(唯一)、name、module；系统内置只读（种子写入，本切片不增改权限点）。
- `role_permissions`（§5.3）：(role_id, permission_id) 联合主键。
- `operation_logs`（§5.10）：user_id、module、action、target_type、target_id、detail(JSON)、ip、user_agent、created_at；**只追加**。
- `data_dict`（§5.11）：dict_type、dict_key、dict_label、sort_order、status；`UNIQUE(dict_type,dict_key)`；**无软删除** → 硬删除。

---

## 3. 业务规则要点

### 3.1 账号管理（`system:user`）
- **新增**：username 全局唯一（活跃行），冲突→`3005`；role_id 必须存在→否则 `3002`；employee_id 若传须存在且未被其他活跃账号绑定（一员工至多一账号），冲突→`3002`/`3005`；`password` 必填、bcrypt 哈希入库并写 `pwd_updated_at`。
- **编辑**：可改 role_id、employee_id、status；改绑定同样校验存在性与唯一性；不在此改密码。
- **软删除**：`deleted_at`；不能删除自己（`id==当前用户`→`3007`）。
- **启用/禁用**：`PATCH /status`；不能禁用自己→`3007`。
- **重置密码**：生成/接收新密码，bcrypt 哈希，写 `pwd_updated_at`（旧 access/refresh 因 `password_changed_after_issue` 失效，强制重新登录）。响应不回显明文（约定：由请求方提供新密码；不做随机生成，保持无副信道）。
- 数据范围：super_admin 全局，无行级过滤。

### 3.2 角色权限（`system:role`）
- **新增角色**：code 唯一（`3005`）、data_scope∈{all,dept,self}、is_builtin=0、status=1。
- **编辑角色**：
  - 内置角色（is_builtin=1）：仅允许改 `name`；试图改 `code`/`data_scope`→`3007`「内置角色不可修改编码或数据范围」。
  - 自定义角色：name/data_scope/status 均可改；code 不可改（唯一稳定引用）。
- **删除角色**：内置→`3007`；被任一活跃账号引用（`users.role_id`）→`3002`「角色下有账号，不能删除」；否则硬删除，同事务清理其 `role_permissions`。
- **查看已授权限**：`GET /roles/{id}/permissions` → 该角色权限 code 列表。
- **分配权限（覆盖式）**：`PUT /roles/{id}/permissions`，body 为权限 code 集合；校验每个 code 存在（否则 `3002`）；**super_admin 角色不可改权限**（必须始终全量）→`3007`；实现为同事务删除旧 `role_permissions` 再插入新集合。
- **全部权限点**：`GET /permissions` → 按 module 分组返回（供前端勾选矩阵）。

### 3.3 操作日志（`system:log`）
- 仅 `GET /operation-logs`，分页 + 筛选：`user_id`、`module`、`action`、`start`/`end`（对 `created_at` 的闭区间，日期或日期时间）。
- 结果按 `created_at DESC`；每项附操作人 `username`（JOIN users）。只读，无任何写接口。

### 3.4 数据字典（`system:dict` 管理 / 登录读取）
- `GET /dicts/{dict_type}`：**任意登录用户**可读；返回该类型 **启用(status=1)** 项，按 `sort_order` 升序。走 Redis 缓存：键 `dict:{dict_type}`，命中直接返回；未命中查库后回填（TTL 见 §6）。
- `GET /dicts`（分页查询，`system:dict`）：可按 `dict_type`/`keyword`(key/label 模糊) 筛选，含禁用项。
- `POST /dicts` / `PUT /dicts/{id}` / `DELETE /dicts/{id}`（`system:dict`）：`UNIQUE(dict_type,dict_key)`，冲突→`3005`；删除为硬删除。**任一写操作后失效 `dict:{dict_type}` 缓存**（DEL 键，下次读重建）。

---

## 4. 接口清单（前缀 `/api/v1`）

**系统-账号 Users**（§8.6）
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/users` | system:user | 列表（username/role_code/status 筛选 + 分页） |
| GET | `/users/{id}` | system:user | 详情 |
| POST | `/users` | system:user | 新增（角色+可选绑定员工+初始密码） |
| PUT | `/users/{id}` | system:user | 编辑（角色/绑定员工/状态） |
| DELETE | `/users/{id}` | system:user | 软删除（不可删自己） |
| PATCH | `/users/{id}/status` | system:user | 启用/禁用（不可禁自己） |
| POST | `/users/{id}/reset-password` | system:user | 重置密码 |

**系统-角色权限 Roles / Permissions**（§8.6）
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/roles` | system:role | 角色列表 |
| GET | `/roles/{id}` | system:role | 角色详情 |
| POST | `/roles` | system:role | 新增角色 |
| PUT | `/roles/{id}` | system:role | 编辑角色（内置仅改名） |
| DELETE | `/roles/{id}` | system:role | 删除角色（内置/被引用不可删） |
| GET | `/roles/{id}/permissions` | system:role | 角色已授权限 code 列表 |
| PUT | `/roles/{id}/permissions` | system:role | 覆盖式分配权限 |
| GET | `/permissions` | system:role | 全部权限点（按 module 分组） |

**系统-日志 / 字典 Logs / Dict**（§8.6）
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/operation-logs` | system:log | 操作日志分页查询（user_id/module/action/start/end） |
| GET | `/dicts/{dict_type}` | 登录 | 取某类型全部启用项（读缓存） |
| GET | `/dicts` | system:dict | 字典项分页查询 |
| POST | `/dicts` | system:dict | 新增字典项 |
| PUT | `/dicts/{id}` | system:dict | 编辑字典项 |
| DELETE | `/dicts/{id}` | system:dict | 删除字典项 |

> 路由注意：`GET /dicts/{dict_type}`（登录）与 `GET /dicts`（system:dict）前缀相同、权限不同；`/dicts/{dict_type}` 用路径参数，`/dicts` 为查询列表，需保证 FastAPI 路由不冲突（`/dicts` 精确匹配空路径，`/dicts/{dict_type}` 匹配子路径）。

---

## 5. 分层落点与新增文件

```
app/
├── schemas/
│   ├── user.py            # UserCreate/UserUpdate/UserOut/UserStatusReq/ResetPasswordReq
│   ├── role.py            # RoleCreate/RoleUpdate/RoleOut/PermissionAssignReq/PermissionOut
│   └── dict.py            # DictCreate/DictUpdate/DictOut/DictItem
├── repositories/
│   ├── user_repo.py       # 扩展：paginate/create/update/soft_delete/set_status/employee_bound_by
│   ├── role_repo.py       # 扩展：list_all/get_by_code/create/update/delete/set_permissions/users_count
│   ├── permission_repo.py # 已有 list_all/get_by_code（复用）
│   ├── operation_log_repo.py # 扩展：paginate(filters)
│   └── data_dict_repo.py  # 新增：list_by_type/paginate/get/create/update/delete/get_by_type_key
├── services/
│   ├── user_service.py    # CRUD/status/reset-password/绑定校验/日志
│   ├── role_service.py    # CRUD/permissions 分配/内置约束/日志
│   ├── dict_service.py    # CRUD/按类型读(缓存)/缓存失效/日志
│   └── log_service.py     # 操作日志查询（附 username）
├── core/dict_cache.py     # Redis 字典缓存读写/失效（键 dict:{type}）
├── routers/
│   ├── users.py           # /users/*
│   ├── roles.py           # /roles/* + GET /permissions
│   ├── dicts.py           # /dicts/*
│   └── operation_logs.py  # /operation-logs
└── api/v1.py              # 挂载 users/roles/dicts/operation_logs 路由
```

> `GET /permissions` 挂在 `roles.py` 内以复用 `system:role` 依赖，用独立 `APIRouter(prefix="/permissions")` 或在同文件导出第二个 router；`v1.py` 分别 include。

测试：`tests/test_users.py`、`tests/test_roles.py`、`tests/test_dicts.py`、`tests/test_operation_logs.py`、`tests/test_user_repo.py`（可选）、`tests/test_data_dict_repo.py`（可选）。

---

## 6. Redis 缓存（数据字典）

- 键：`dict:{dict_type}`，值：该类型启用项 JSON 数组 `[{key,label,sort_order}, ...]`（`redis.from_url(decode_responses=True)`，存 `json.dumps`）。
- TTL：`settings.dict_cache_ttl`（默认 600s）；缓存穿透可接受（字典体量小）。
- 失效：`POST/PUT/DELETE /dicts` 命中的 `dict_type` → `redis.delete(f"dict:{dict_type}")`；PUT 若改了 `dict_type`（一般不允许改 type，约定 type 不可变），只失效原 type。**约定：编辑不允许修改 `dict_type`/`dict_key`**（改则删后重建），只改 label/sort_order/status。
- 测试用 `redis_conn` fixture（DB15，自动 flush），断言写操作后键被删除、读操作回填。

---

## 7. Schema 要点

- `UserCreate`：username(必填,1-64)、password(必填,≥8)、role_id(必填)、employee_id?、status?默认1。
- `UserUpdate`：role_id?/employee_id?(可置空解绑,用显式哨兵或 `Optional` 语义约定)/status?。（约定：`employee_id` 传空串或 null 语义见实现；本切片以 `None=不改`，解绑用独立字段或允许传 `""`→NULL，实现层决定并测试。）
- `UserOut`：id、username、role_id、role_code、role_name、employee_id、status、last_login_at、created_at。**绝不含 password_hash**。
- `ResetPasswordReq`：new_password(必填,≥8)。
- `UserStatusReq`：status∈{0,1}。
- `RoleCreate`：code(必填,1-32)、name(必填)、data_scope∈{all,dept,self}、status?默认1。
- `RoleUpdate`：name?、data_scope?、status?（内置角色仅 name 生效，余者拒绝）。
- `RoleOut`：id、code、name、is_builtin、data_scope、status。
- `PermissionAssignReq`：codes: list[str]（覆盖式）。
- `DictCreate`：dict_type(必填)、dict_key(必填)、dict_label(必填)、sort_order?默认0、status?默认1。
- `DictUpdate`：dict_label?、sort_order?、status?（不改 type/key）。
- `DictOut`：id、dict_type、dict_key、dict_label、sort_order、status。`DictItem`（按类型读）：dict_key、dict_label、sort_order。

---

## 8. 错误码（复用切片1-3，无新增）

- `3002` 引用实体不存在 / 被引用不可删（role_id/employee_id 不存在、角色下有账号、分配的权限 code 不存在）。
- `3005` 唯一冲突（username、role.code、data_dict(type,key) 重复；员工已被其他账号绑定）。
- `3007` 非法状态/操作（内置角色改 code/data_scope、删内置角色、改 super_admin 权限、禁用/删除自己）。
- `3404` not_found（对象不存在）。
- `1003` forbidden（非 super 访问 system:* 接口）。

---

## 9. 测试要点（跑 ims_test）

- **账号**：super 新增账号→列表可见；username 重复→3005；绑定不存在员工→3002；绑定已被占用员工→3002/3005；编辑改角色；禁用/启用；**禁用自己→3007**；**删除自己→3007**；重置密码后旧 token 失效（`password_changed_after_issue`）→用旧 token 请求得 1001；非 super（如 hr_admin）访问 `/users`→1003。
- **角色权限**：新增自定义角色；code 重复→3005；改内置角色 data_scope→3007；删内置→3007；删被账号引用的自定义角色→3002；删无引用自定义角色→成功且 role_permissions 清理；`PUT /roles/{id}/permissions` 覆盖后 `GET .../permissions` 一致；改 super_admin 权限→3007；`GET /permissions` 按 module 分组含全部权限点；非 super→1003。
- **数据字典**：`GET /dicts/gender` 登录可读且只含启用项、按 sort_order；首次读回填缓存、二次读命中；`POST/PUT/DELETE` 后 `dict:{type}` 缓存键被删除；(type,key) 重复→3005；`GET /dicts` 列表 super_admin 可见含禁用项；普通 employee 读 `/dicts/gender`→成功、访问 `/dicts`(列表)→1003、`POST /dicts`→1003。
- **操作日志**：造若干写操作后 `GET /operation-logs` 分页返回；按 module/action/user_id 筛选；start/end 日期过滤；每项含 username；非 super→1003；无任何写接口（仅 GET）。
- **审计**：账号/角色/字典的写操作在 `operation_logs` 留痕（module=user/role/dict，action=create/update/delete/reset_password/assign_permissions/status）。

---

## 10. 风险与决策

- **路由冲突**：`/dicts`（列表，system:dict）与 `/dicts/{dict_type}`（读，登录）权限不同——用两个精确/参数路由分别声明；`GET /dicts/{dict_type}` 不得吞掉 `GET /dicts`。测试同时覆盖两者与其权限差异。
- **super_admin 不可自锁**：禁止删除/禁用自己、禁止改 super_admin 角色权限，避免把系统锁死。
- **内置角色保护**：is_builtin=1 的角色 code/data_scope 冻结、不可删，保证程序内引用与数据范围逻辑稳定（§5.2）。
- **重置密码即吊销**：复用切片1 的 `pwd_updated_at` vs token `iat` 机制，重置后旧令牌自动失效，无需额外黑名单写入。
- **字典缓存一致性**：写后删键（而非改键），下次读重建，避免并发下的读改写竞态；字典体量小，穿透代价可忽略。
- **roles 硬删除**：Role 无软删除列，删除为物理删除并清理关联；仅对无账号引用的自定义角色开放。
- **employee↔account 绑定唯一**：一名员工至多绑定一个活跃账号，保证 `employee`/`dept_manager` 数据范围定位无歧义。
