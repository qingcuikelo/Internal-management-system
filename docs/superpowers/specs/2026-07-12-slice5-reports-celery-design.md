# 切片5 设计文档：报表 + Celery 异步（导入/导出/保修到期）

> 版本：v1 · 日期：2026-07-12
> 上游依据：《企业内部管理系统详细设计方案.md》§6.5、§8.6（Reports、Tasks）
> 前置：切片1-4 已合并。本切片在其上实现报表域与 Celery 异步任务体系。

---

## 1. 目标与验收标准

**目标**：实现报表查询（4 个 `report:view` 端点 + 数据范围）、Celery 异步任务体系（员工 Excel 导入/导出）、`GET /tasks/{task_id}` 轮询接口，以及 Celery Beat 定期保修到期扫描。

**验收标准（DoD）**：
1. **报表 4 端点**：`/reports/employee-assets`、`/reports/idle-assets`、`/reports/device-by-department`、`/reports/warranty-expiring`。全部 `report:view` 权限 + dept_manager 数据范围过滤（只统计本部门子树内员工的资产）。employee 角色无 `report:view` → 1003。
2. **员工导入**（employee:import，仅 super/hr）：`POST /employees/import` 接收 Excel 文件 → 返回 `task_id` → Celery 异步逐行校验入库 → 任务完成后 Redis 存摘要（success/fail/errors）。校验：employee_no 必填+唯一、name 必填、department_id 存在、direct_supervisor_id 存在且不构成循环。
3. **员工导出**（employee:export，仅 super/hr）：`POST /employees/export` 提交筛选条件（`?department_id/status/keyword`）→ 返回 `task_id` → Celery 生成 Excel（含工号/姓名/部门/职位/性别/状态/手机/邮箱/入职日期/离职日期）→ 存本地 `uploads/` → 任务结果含下载 URL `/exports/{filename}`。
4. **`GET /tasks/{task_id}`**（登录）：返回 `{status, result, error}`。status ∈ pending/running/success/failed。Celery AsyncResult + Redis 冗余 key（TTL 3600s，防 backend 过期）。
5. **`GET /exports/{filename}`**（登录）：静态文件下载（本地 `uploads/` 目录），仅限 `.xlsx` 文件，防止路径遍历。
6. **Celery Beat 保修到期扫描**：定时任务（每天 9:00），查询 `devices.warranty_expire BETWEEN today AND today + N days`（N 默认 30，可配）、status ≠ 4（报废），产出设备清单存 Redis（key `warranty_expiring:{days}`，TTL 24h）。报告端点直接读该缓存（无实时查询压力）。
7. **Celery 基础设施**：Redis broker + result backend（`redis://.../1`），任务定义在 `app/tasks/`，Beat schedule 在 `celery_config.py`。celery worker 由用户手动启动（`celery -A app.core.celery_app worker`），不集成到 pytest（测试用 `CELERY_TASK_ALWAYS_EAGER=True` 同步执行）。
8. **pytest** 全绿、ruff 干净、0 warning。

**不在本切片范围**：邮件通知（可扩展预留）、对象存储（切片7 Docker 含 MinIO/Nginx 时处理）、前端 Vue3（切片6）、Docker 部署（切片7）。表结构不改。

---

## 2. 相关数据表（不改表，只读查询）

- `employees`：emp no、name、dept、position、status、phone、email、entry/resign date。
- `workstations`：status、current_employee_id。
- `devices`：status、current_employee_id、warranty_expire。
- `departments`：name。
- `roles`（种子已配 `report:view`）：super_admin/hr_admin/it_admin/dept_manager 有；dept_manager 需数据范围过滤。

**权限分布（§3.2 种子已落库）**：
| 权限 | super | hr | it | dept_mgr | employee |
|---|---|---|---|---|---|
| report:view | ✅ | ✅ | ✅ | 🔒(本部门) | — |
| employee:import | ✅ | ✅ | — | — | — |
| employee:export | ✅ | ✅ | — | — | — |

---

## 3. 报表数据范围（复用 scope_service + 新增 report_scope）

报表 dept_manager 数据范围：按 `accessible_department_ids` → 子树内员工 id 集 → 以这些员工 id 过滤设备/工位/报表统计。

新增 `scope_service.report_scope(db, user) -> dict`（内部调用已有 `employee_scope` 的逻辑，产出 `{"mode":"all"}` 或 `{"mode":"employees","employee_ids":set}`）。dept_manager 无绑定员工（department_id=NULL）→ `employee_ids=∅` → 报表全空。

---

## 4. Celery 基础设施（新增）

### 4.1 配置
- `app/core/celery_app.py`：Celery 实例（`Celery("ims", broker=redis_url/1, backend=redis_url/1)`），`task_serializer="json"`，`result_expires=3600`，`task_always_eager=settings.celery_task_always_eager`（dev/test 默认 True = 同步执行；生产 False）。
- `app/core/config.py` 新增：
  - `celery_broker_db: int = 1`（Redis DB 1）
  - `celery_task_always_eager: bool = True`（同步执行默认，避免开发时需手动启动 worker）
  - `warranty_expiry_days: int = 30`
  - `exports_dir: str = "uploads"`

### 4.2 Beat schedule
- 任务 `app.tasks.warranty_scan`：`{"task": "app.tasks.scan_warranty_expiry", "schedule": crontab(hour=9, minute=7)}`（9:07 执行，错开整点高峰）。
- Beat 由用户手动启动：`celery -A app.core.celery_app beat -l info`（与 worker 分进程），不集成测试。

### 4.3 测试策略
- 测试用 `celery_task_always_eager=True`（默认），Celery 任务同步执行，无需 broker/worker。
- 不启动真实 worker；`CELERY_TASK_ALWAYS_EAGER` 让 `task.delay()` 变同步调用，结果立即可得。
- 任务本身有独立单元测试（同步执行后断言结果）。

---

## 5. 任务状态轮询 `/tasks/{task_id}`

### 5.1 存储
- Celery AsyncResult（从 result backend 读）。result backend = Redis DB1，与 Celery 共享。
- 辅助 Redis key `task:{task_id}`（当前 `redis_client` 的 DB），TTL 3600s。内容：`{"status":"success","result":{...},"error":null}`。每次任务完成后写入（`task_postrun` 信号），作为 Celery backend 的冗余（backend 结果也可能因 `result_expires` 而过期）。
- 注意 `redis_client`（app DB）与 Celery backend（DB1）是不同的 Redis DB，写入 `task:{id}` 需走 `app.core.redis.redis_client`，不可通过 Celery backend 直接读。

### 5.2 查询逻辑
1. 先查 Redis `task:{task_id}` → 命中直接返回（最快路径，且不受 `result_expires` 影响）。
2. Redis 未命中 → 查 Celery AsyncResult（`app.core.celery_app.AsyncResult(task_id)`）。
3. 两者均无 → 404（任务不存在或已过期）。

### 5.3 响应格式
```json
{
  "status": "success",
  "result": {"success_count": 10, "error_count": 2, "errors": [...]},
  "error": null
}
```

---

## 6. 导入/导出（employee:import / employee:export）

### 6.1 导入 `POST /employees/import`
- Content-Type: `multipart/form-data`，字段 `file`（.xlsx）。
- 路由：立即返回 `{"task_id": "<uuid>"}`（HTTP 202）。
- Celery 任务 `import_employees(file_path, user_id, trace_id)`：
  1. 读取 Excel，标题行映射列名（`employee_no` / `name` / `gender` / `department_id` / `position` / `direct_supervisor_id` / `phone` / `email` / `entry_date` / `status`）。
  2. 逐行校验：必填字段、employee_no 不重复（含 DB 已有）、department_id 存在、direct_supervisor_id（若有）存在且不循环、gender ∈ {0,1,2}。
  3. 通过的行 INSERT 入 employees 表；失败的行收集错误 msg（行号 + 原因）。
  4. 写 operation_logs（module=employee, action=import, detail={success,fail,errors}）。
  5. 任务完成写 Redis `task:{id}`。
- 文件暂存：上传至 `uploads/imports/`（任务完成后可清理）。

### 6.2 导出 `POST /employees/export`
- Content-Type: `application/json`（筛选条件 body：`department_id?/status?/keyword?`，均可选）。
- 路由：返回 `{"task_id": "<uuid>"}`（HTTP 202）。
- Celery 任务 `export_employees(filters, user_id)`：
  1. 按筛选条件分页查 employees（复用 `employee_repo.paginate`，去上限 100 → 导出时全量，分页循环）。dept_manager 应用数据范围（通过传入 `scope` 参数）。
  2. 生成 Excel（openpyxl）：标题行 → 数据行。
  3. 保存至 `uploads/exports/{task_id}.xlsx`。
  4. 任务完成写 Redis，result 含 `download_url=/exports/{task_id}.xlsx`。
- `GET /exports/{filename}`（登录）：返回 FileResponse，Content-Type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`。校验 filename 仅含安全字符（`[\w\-\.]+`）且后缀 `.xlsx`，防路径遍历。

### 6.3 导入/导出权限
- employee:import = super/hr；employee:export = super/hr；「员工导入」/「员工导出」权限已在种子中就位。
- 非持有者 → 1003。无需数据范围过滤（import/export 均为全局操作）。

---

## 7. 报表 4 端点（`report:view`）

### 7.1 GET `/reports/employee-assets?employee_id=`
- 返回该员工的当前工位（1 条或空）+ 持有设备列表（0-N 条）。
- dept_manager：校验 `employee_id` 是否在本部门子树内，否则 3404。
- 响应：`{"workstation": {...}|null, "devices": [...]}`

### 7.2 GET `/reports/idle-assets`
- 返回 `{"idle_workstations": N, "idle_devices": N}`。
- dept_manager：仅统计在库设备（status=1）和闲置工位（status=1），不按员工过滤（dept_manager 对闲置资产不可见 —— §3.3 规定闲置/在库资产对 dept/self 不可见，报表同理，闲置工位/在库设备计数对该角色返回 0 或无部门维度拆分）。
- **决策**：dept_manager 的此报表返回 `{idle_workstations: null, idle_devices: null}` 并附 note `"闲置资产归属全局管理，本角色不可见"`。全局角色返回实际数字。

### 7.3 GET `/reports/device-by-department?department_id=`
- 按部门统计设备数：`[{"department_id":"...", "department_name":"...", "count":N}, ...]`
- dept_manager：仅统计本部门子树的部门，且设备仅计 `current_employee_id` 在本部门子树内的（JOIN employees）。无占用人设备不计入。
- 不传 `department_id` → 返回所有可见部门；传则只返回该部门。

### 7.4 GET `/reports/warranty-expiring?days=30`
- 返回保修到期设备列表（含部门、占用人），按 `warranty_expire` 升序。
- dept_manager：仅见占用人在本部门子树内的设备。
- 复杂度低，直接实时查：`Device.warranty_expire BETWEEN today AND today+N AND status != 4 AND deleted_at IS NULL`。
- **与 Celery Beat 不冲突**：Beat 做预缓存（定期产出预警清单存 Redis），报告端点做实时查询（精确、简单），两者互补 —— Beat 产出可扩展邮件通知，报告端点为前端页面提供实时数据。

---

## 8. 接口清单（前缀 `/api/v1`）

**报表 Reports**
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/reports/employee-assets` | report:view | 员工资产概览（`?employee_id=`） |
| GET | `/reports/idle-assets` | report:view | 闲置工位+在库设备数 |
| GET | `/reports/device-by-department` | report:view | 部门设备统计（`?department_id=`） |
| GET | `/reports/warranty-expiring` | report:view | 保修到期设备列表（`?days=30`） |

**异步任务 / 文件下载**
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/tasks/{task_id}` | 登录 | 任务状态查询 |
| GET | `/exports/{filename}` | 登录 | 导出文件下载 |

**员工导入/导出**（扩展现有 `/employees` 路由）
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/employees/import` | employee:import | 上传 Excel 导入（→task_id） |
| POST | `/employees/export` | employee:export | 提交导出任务（→task_id） |

---

## 9. 分层落点与新增文件

```
app/
├── core/
│   ├── config.py              # 新增：celery_broker_db, celery_task_always_eager, warranty_expiry_days, exports_dir
│   └── celery_app.py          # 新建：Celery 实例 + Beat schedule
├── tasks/
│   ├── __init__.py
│   ├── import_employees.py    # 导入任务
│   ├── export_employees.py    # 导出任务
│   └── warranty_scan.py       # Beat 任务：保修到期扫描
├── services/
│   ├── report_service.py      # 新建：4 报表 + 数据范围
│   ├── task_service.py        # 新建：/tasks/{id} 查询（Redis + AsyncResult）
│   └── import_export_service.py # 新建：上传暂存/校验/提交任务
├── schemas/
│   └── report.py              # 新建：report 出参
├── routers/
│   ├── reports.py             # 新建：/reports/*
│   ├── tasks.py               # 新建：/tasks/{id} + /exports/{filename}
│   └── employees.py           # 扩展：import / export 端点
├── api/v1.py                  # 修改：挂载 reports、tasks 路由
└── uploads/
    ├── imports/               # 上传 Excel 暂存
    └── exports/               # 生成的 Excel
```

测试：
- `tests/test_reports.py` — 4 报表 + 数据范围 + dept/self/global 可见性
- `tests/test_import_export.py` — 导入/导出任务同步执行、权限检查、/tasks/{id} 查询、/exports/{filename} 下载
- `tests/test_warranty_scan.py` — Beat 任务同步执行结果校验
- `tests/test_task_service.py` — task 状态查询路径（Redis hit/Celery fallback/404）

---

## 10. 错误码
- 复用：`1003` forbidden（无权 import/export/report）、`3404` not_found（task/文件不存在、越范围 employee_id）、`3002`（导入时部门/上级不存在）、`3005`（导入时 employee_no 冲突）。
- 新增：`3010` import validation error（汇总行级校验错误，HTTP 422）—— 用于同步校验场景；异步导入时错误在任务 result 中体现，不抛这个错误。

---

## 11. 配置要点（.env 新增，均可选，默认值即用）
```
CELERY_BROKER_DB=1
CELERY_TASK_ALWAYS_EAGER=true
WARRANTY_EXPIRY_DAYS=30
EXPORTS_DIR=uploads
```

---

## 12. 风险与决策
- **Celery Eager 测试**：默认 `always_eager=True`，测试时不需要启动 worker。任务逻辑同步验证；不测真实异步调度（KISS）。
- **文件路径安全**：`/exports/{filename}` 仅通过正则 `^[\w\-]+\.xlsx$` 的文件名，拒绝 `..` 和绝对路径。
- **导入不拆事务**：逐行 INSERT 各自独立提交（1 行失败不影响其他行），非严格原子（符合 Excel 批量导入常见语义）。
- **Redis 冗余**：`task:{id}` key 作为 Celery backend 结果的补充（TTL 3600s），避免 `result_expires` 过期后轮询失效。
- **不建 async_tasks DB 表**：用 Celery backend + Redis 冗余，表结构不变（§2 约定）。
- **Celery worker/beat 由用户在生产环境手动启动**：不嵌入 pytest、不嵌入 FastAPI 启动钩子。
