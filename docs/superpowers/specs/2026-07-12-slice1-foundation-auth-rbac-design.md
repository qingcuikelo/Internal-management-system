# 切片1 设计文档：地基 + 认证/RBAC

> 版本：v1 · 日期：2026-07-12
> 上游依据：《企业内部管理系统详细设计方案.md》（后端设计文档 v3）
> 本文是"企业内部管理系统"整体拆分后的**第 1 个切片**的落地设计。整体分 7 个切片，每个切片独立 spec → plan → implement。本切片是所有后续切片的 backbone。

---

## 0. 整体切片规划（背景）

| # | 切片 | 内容 | 依赖 |
|---|------|------|------|
| **1** | **地基 + 认证/RBAC**（本文） | 四层脚手架、core 基建、全部 11 表结构、Alembic、JWT 认证、RBAC 鉴权与数据范围地基、操作日志写入基建、seed、健康检查 | 无 |
| 2 | 组织域 | departments（树/CRUD/删除校验）+ employees（CRUD/筛选/批量改部门/上级防环） | 1 |
| 3 | 资产域 | workstations + devices（分配/释放/领用/退还/维修/报废、乐观锁、历史表）+ 员工离职级联 | 1,2 |
| 4 | 系统管理 | 账号/角色权限管理 CRUD、操作日志查询、数据字典 + Redis 缓存 | 1 |
| 5 | 报表 + 异步 | 报表接口、Celery、Excel 导入导出、保修到期扫描 | 1-3 |
| 6 | 前端 | Vue3 + TS + Pinia + Element Plus | 1-5 |
| 7 | 容器化部署 | Dockerfile、docker-compose、Nginx | 全部 |

---

## 1. 本切片目标与验收标准

**目标**：交付一个可启动、可交互、可测试的 FastAPI 后端骨架，认证与 RBAC 完整可用，全部数据库表结构就位。

**验收标准（Definition of Done）**：
1. 创建项目专属 venv，`pip install` 成功装齐依赖。
2. 配置 `.env`（连接局域网 MySQL/Redis）后，`alembic upgrade head` 一次性建出**全部 11 张表**（含循环外键）。
3. `python scripts/seed.py` 幂等写入：5 个内置角色、全部权限点、§3.2 权限矩阵、data_dict 枚举、首个超管（账号密码取自环境变量）。
4. `uvicorn app.main:app` 启动，`/docs` 可交互。
5. 认证闭环全部通过（真实 HTTP 验证）：
   - `POST /api/v1/auth/login` 超管登录成功，返回 access+refresh 双 token 与用户信息（含权限点列表）。
   - `GET /api/v1/auth/me` 返回当前用户、角色、权限点。
   - `POST /api/v1/auth/refresh` 用 refresh 换新 access。
   - `POST /api/v1/auth/logout` 后，旧 token 立即失效（Redis 黑名单）。
   - `PUT /api/v1/auth/password` 改密（校验旧密码），改密后旧 token 失效。
   - 连续登录失败 5 次 → 账号锁定 15 分钟。
6. `GET /health` 返回服务与 DB/Redis 探活结果。
7. `pytest` 在专用 `ims_test` 库全绿。

**不在本切片范围**（明确排除，避免范围蔓延）：
- 部门/员工/工位/设备/报表/账号管理/角色管理/日志查询/字典管理的**业务接口**（表结构建好，逻辑留后续切片）。
- 数据范围行级过滤的**实际接入**（本切片只建产出数据范围描述符 + 子部门ID集合的地基，因为尚无业务数据可过滤）。
- Celery、Excel、Docker、Nginx、前端。

---

## 2. 技术栈与工具

| 项 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.11 | |
| 环境 | 项目专属 `backend/.venv`（venv + pip） | 不使用全局 Python、不复用共享 venv |
| Web | FastAPI + uvicorn | 自带 OpenAPI/Swagger |
| ORM | SQLAlchemy 2.0（声明式，`Mapped`/`mapped_column`） | |
| 迁移 | Alembic | 禁止手工改表 |
| 数据库 | MySQL 8.x（局域网），驱动 PyMySQL | InnoDB，utf8mb4 |
| 缓存 | Redis 7（局域网），`redis-py` | Token 黑名单、登录失败计数、数据范围缓存 |
| 校验 | Pydantic v2 + pydantic-settings | |
| 认证 | PyJWT（JWT 签发/校验） | |
| 密码 | passlib[bcrypt] | bcrypt 加盐哈希 |
| 主键 | uuid-utils（UUIDv7，有序） | |
| Lint | ruff | |
| 测试 | pytest（跑专用 `ims_test` 库） | |

> 依赖清单（`pyproject.toml`）：`fastapi, uvicorn[standard], sqlalchemy>=2, alembic, pymysql, redis, pydantic>=2, pydantic-settings, pyjwt, passlib[bcrypt], uuid-utils, python-multipart`；dev：`ruff, pytest, httpx`。

---

## 3. 目录结构（backend/）

```text
backend/
├── app/
│   ├── main.py                     # FastAPI 入口：装配 app、中间件、异常处理、CORS、trace_id、挂 /api/v1 与 /health
│   ├── core/
│   │   ├── config.py               # Pydantic Settings 读取 .env（DB/Redis/JWT/超管等）
│   │   ├── database.py             # SQLAlchemy engine + SessionLocal + get_db 依赖
│   │   ├── redis.py                # Redis 连接池 + 客户端
│   │   ├── security.py             # 密码哈希、JWT 签发/校验、jti 生成
│   │   ├── deps.py                 # get_current_user、require_permission(code)、数据范围描述符
│   │   ├── permissions.py          # 全部权限点 code 常量（§3.4）
│   │   ├── exceptions.py           # 统一业务异常 + 错误码（§8.3）+ 注册异常处理器
│   │   ├── response.py             # 统一响应体、分页封装（§8.1/8.2）
│   │   └── logging.py              # 结构化日志 + trace_id 上下文 + 操作日志写入 helper
│   ├── api/
│   │   └── v1.py                   # 创建 /api/v1 主路由，include 各 router（本切片仅 auth）
│   ├── routers/
│   │   └── auth.py                 # /auth/*（login/refresh/logout/me/password）
│   ├── services/
│   │   └── auth_service.py         # 登录、失败锁定、刷新、登出黑名单、改密
│   ├── repositories/
│   │   ├── base.py                 # 通用 CRUD：按 id 取、分页、软删过滤、create/update
│   │   ├── user_repo.py
│   │   ├── role_repo.py
│   │   ├── permission_repo.py
│   │   └── operation_log_repo.py   # 操作日志写入
│   ├── models/                     # 全部 11 表 ORM（对应 §5）
│   │   ├── base.py                 # Base + Mixin（id/created_at/updated_at/软删/审计/version）
│   │   ├── user.py  role.py  permission.py  role_permission.py
│   │   ├── department.py  employee.py
│   │   ├── workstation.py  device.py  assignment.py   # workstation_assignments + device_assignments
│   │   ├── operation_log.py  data_dict.py
│   │   └── __init__.py             # 汇总导出，供 Alembic autogenerate 感知全部表
│   ├── schemas/
│   │   ├── common.py               # 分页请求/响应泛型、统一响应
│   │   └── auth.py                 # 登录/刷新/改密/用户信息出入参
│   └── utils/
│       ├── uuidv7.py               # UUIDv7 生成
│       └── tree.py                 # 子部门ID集合（数据范围用）
├── alembic/
│   ├── env.py                      # 指向 models.Base.metadata + Settings 的 DB URL
│   └── versions/                   # 基线迁移（含循环外键两步）
├── tests/
│   ├── conftest.py                 # ims_test 库、依赖覆盖、事务回滚 fixture
│   ├── test_auth.py                # 登录/失败锁定/刷新/登出/改密
│   ├── test_permissions.py         # require_permission 放行/拦截
│   ├── test_health.py
│   └── test_seed.py                # seed 幂等
├── scripts/
│   └── seed.py                     # 内置角色/权限点/权限矩阵/字典/首个超管
├── .env.example
├── pyproject.toml
├── alembic.ini
└── README.md                       # 本切片运行说明
```

依赖方向严格单向：`api → routers → services → repositories → models`；`core` 提供横切能力；`schemas` 定义出入参。

---

## 4. 数据模型（全部 11 表）

> 字段定义严格遵循上游文档 §5，本文不重复列全部列，仅说明本切片的落地约定与关键点。

### 4.1 通用 Mixin（models/base.py）
- `id: CHAR(36)` 主键，默认值由 `utils/uuidv7` 生成（UUIDv7，写入有序）。
- `created_at / updated_at: DATETIME(3)`，存 UTC；`updated_at` 更新时刷新。
- 软删表附加 `deleted_at: DATETIME(3) NULL`（NULL=有效）。
- 审计表附加 `created_by / updated_by: CHAR(36) NULL`。
- 并发表（workstations/devices）附加 `version: INT NOT NULL default 0`。

### 4.2 软删 + 唯一约束的复合方案
对 `users.username`、`employees.employee_no`、`workstations.code`、`devices.asset_code`、`devices.serial_number`：
- 增加生成列 `active_flag TINYINT AS (IF(deleted_at IS NULL, 1, NULL)) STORED`。
- 唯一索引建在 `(业务键, active_flag)`。已删行 `active_flag=NULL`，MySQL 允许多 NULL 并存，故唯一性仅在未删记录间生效。

### 4.3 全部 11 表清单（本切片全部建表，逻辑分批实现）
| 表 | 本切片是否有业务逻辑 | 备注 |
|---|---|---|
| users | ✅（认证核心） | password_hash、role_id FK、employee_id FK(可空)、status、last_login_at、pwd_updated_at |
| roles | ✅（seed + 读取） | code、data_scope(all/dept/self)、is_builtin |
| permissions | ✅（seed + 读取） | code=`模块:操作` |
| role_permissions | ✅（seed + 读取） | 联合主键(role_id, permission_id) |
| departments | 建表 | 含 `manager_id → employees.id`（循环外键） |
| employees | 建表 | 含 `department_id → departments.id`、`direct_supervisor_id` 自关联 |
| workstations | 建表 | 含 version、current_employee_id |
| devices | 建表 | 含 version、current_employee_id、warranty_expire |
| workstation_assignments | 建表 | 历史流水 |
| device_assignments | 建表 | 历史流水 |
| operation_logs | ✅（写入基建） | detail JSON、target(type,id)、ip、user_agent |
| data_dict | ✅（seed 枚举） | 唯一(dict_type, dict_key) |

### 4.4 Alembic 循环外键两步迁移
`departments.manager_id → employees.id` 与 `employees.department_id → departments.id` 互相引用。基线迁移策略：
1. 先建全部表，`departments` 与 `employees` 暂不含这对相互 FK。
2. 迁移末尾 `ALTER TABLE ... ADD CONSTRAINT` 分别补两个外键。
- downgrade 顺序相反：先 drop 这两个约束再 drop 表。

---

## 5. 认证与 RBAC（本切片核心逻辑）

### 5.1 JWT 双令牌
- `access_token`：有效期 15 分钟（可配），payload 含 `sub`(user_id)、`jti`、`type=access`、`exp`。
- `refresh_token`：有效期 7 天（可配），payload 含 `sub`、`jti`、`type=refresh`、`exp`。
- 算法 HS256，密钥取自 `.env`（`JWT_SECRET`）。
- 登录返回：`access_token, refresh_token, token_type=Bearer, expires_in, user{...}`（§8.7①）。

### 5.2 Token 失效 / 黑名单
- 登出（`/auth/logout`）：把当前 access token 的 `jti` 写入 Redis 黑名单，TTL=该 token 剩余有效期。
- 改密（`/auth/password`）成功：使当前用户既有 token 失效。实现方式：记录 `users.pwd_updated_at`，鉴权时校验 token 签发时间 `iat` 早于 `pwd_updated_at` 则拒绝（避免枚举全部 jti）。
- 鉴权依赖每次校验：token 未过期 && jti 不在黑名单 && `iat >= pwd_updated_at`。

### 5.3 登录失败锁定
- Redis key `login_fail:{username}` 计数，每次失败 +1；达 5 次（可配 `LOGIN_MAX_FAIL`）设锁定标记 `login_lock:{username}` TTL 15 分钟（可配 `LOGIN_LOCK_MINUTES`）。
- 锁定期内登录直接拒绝（错误码 1xxx，提示稍后再试）。
- 登录成功清零计数。

### 5.4 密码
- 存储：passlib `CryptContext(schemes=["bcrypt"])` 加盐哈希，严禁明文/MD5。
- 策略校验（Pydantic）：长度 ≥8 且同时包含大写字母、小写字母、数字，否则返回 2xxx。

### 5.5 鉴权与数据范围依赖（core/deps.py）
- `get_current_user`：解析 Bearer token → 校验（5.2）→ 载入 `users` + `role` + 该角色权限点集合（一次查询/可缓存）→ 返回当前用户上下文（含 permissions 集合、data_scope、employee_id、department_id）。
- `require_permission(code)`：依赖工厂，校验当前用户权限点集合是否含 `code`，否则抛 1003 无权限。
- **数据范围地基**：根据 `role.data_scope` 产出描述符：
  - `all` → 无过滤。
  - `dept` → 当前用户 employee 的 department_id + 其子部门ID集合（`utils/tree` 递归，结果缓存 Redis）。
  - `self` → 当前用户 employee_id。
  - 本切片仅**产出描述符与子部门集合工具**并单测；实际注入 repository 查询在有业务数据的切片进行。

### 5.6 权限点常量（core/permissions.py）
定义上游 §3.4 全部权限点 code 常量（department/employee/workstation/device/report/system 各模块），供本切片 seed 与后续切片 router 引用。

### 5.7 认证接口（routers/auth.py，前缀 `/api/v1`）
| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/auth/login` | 公开 | 账号密码登录，返回双 token + 用户信息 |
| POST | `/auth/refresh` | 公开(凭 refresh) | 刷新 access token |
| POST | `/auth/logout` | 登录 | jti 加黑名单 |
| GET | `/auth/me` | 登录 | 当前用户、角色、权限点列表 |
| PUT | `/auth/password` | 登录 | 改本人密码（校验旧密码） |

---

## 6. 横切基建

### 6.1 统一响应与分页（core/response.py, schemas/common.py）
- 响应体：`{ "code": 0, "message": "ok", "data": ..., "trace_id": "..." }`（§8.1）。`code=0` 成功。
- 分页入参：`page`(从1)、`page_size`(默认20，上限100)、`keyword`、`sort`、`order`(asc/desc，默认 desc) + 各筛选字段（§8.2）。
- 分页返回：`{ items:[], total, page, page_size }`。

### 6.2 错误码与异常（core/exceptions.py）
- 分段：`1xxx` 认证/授权（1001 未登录、1003 无权限、1002 账号锁定/禁用等）、`2xxx` 参数校验、`3xxx` 业务规则、`5xxx` 系统内部。
- 定义 `BizError(code, message, http_status)`；注册 FastAPI 异常处理器，把 `BizError`、`RequestValidationError`、未捕获异常统一转成响应体（携带 trace_id）。

### 6.3 trace_id 中间件（core/logging.py, main.py）
- 每请求生成 trace_id（UUID），放入 contextvar，注入日志与响应体。
- 结构化日志输出，预留 Prometheus 指标位（本切片仅埋点结构，不接监控）。

### 6.4 操作日志写入基建（operation_log_repo + logging helper）
- 提供 `write_operation_log(user_id, module, action, target_type, target_id, detail, ip, user_agent)`。
- 本切片接入点：登录成功、改密。日志**查询接口**留切片4。

### 6.5 健康检查（GET /health，公开，不带 /api/v1 前缀）
- 探活：DB（`SELECT 1`）、Redis（`PING`）。返回各依赖状态与总体健康标志，供容器编排/Nginx 上游探活。

---

## 7. 数据初始化（scripts/seed.py，幂等）

按顺序写入（存在则跳过/更新）：
1. **permissions**：§3.4 全部权限点。
2. **roles**：5 个内置角色，`is_builtin=1`，data_scope 对应：super_admin=all、hr_admin=all、it_admin=all、dept_manager=dept、employee=self。
3. **role_permissions**：按 §3.2 权限矩阵映射（如 hr_admin 无 device:*；it_admin 无 department 写、employee 只读；dept_manager/employee 只读子集等）。
4. **data_dict**：`gender`、`workstation_type`、`device_type` 等展示型枚举（状态机 status 用代码常量，不入字典）。
5. **首个超管账号**：`username/password` 取自环境变量（如 `SEED_ADMIN_USERNAME`/`SEED_ADMIN_PASSWORD`），role=super_admin，employee_id 为空。密码经 bcrypt 哈希。

幂等：以业务唯一键（permission.code、role.code、dict(type,key)、username）判断是否已存在。

---

## 8. 配置（.env / core/config.py）

`.env.example` 提供样例键（真实 `.env` 不入库）：
```
APP_ENV=dev
API_PREFIX=/api/v1
# MySQL（局域网）
DB_HOST=  DB_PORT=3306  DB_USER=  DB_PASSWORD=  DB_NAME=ims  DB_NAME_TEST=ims_test
# Redis（局域网）
REDIS_HOST=  REDIS_PORT=6379  REDIS_DB=0  REDIS_PASSWORD=
# JWT
JWT_SECRET=  JWT_ALG=HS256  ACCESS_TOKEN_MINUTES=15  REFRESH_TOKEN_DAYS=7
# 登录锁定
LOGIN_MAX_FAIL=5  LOGIN_LOCK_MINUTES=15
# 首个超管
SEED_ADMIN_USERNAME=admin  SEED_ADMIN_PASSWORD=
# CORS
CORS_ORIGINS=http://localhost:5173
```
`config.py` 用 pydantic-settings 读取，提供 `Settings` 单例；DB URL / Redis URL 由字段拼装；测试用 `DB_NAME_TEST`。

---

## 9. 测试（tests/，跑专用 ims_test 库）

- `conftest.py`：连接 `ims_test`，用例前建表（`Base.metadata.create_all` 或 alembic upgrade）、用例后回滚/清库；提供覆盖 `get_db`、`get_redis` 的 fixture 与测试客户端（httpx + FastAPI app）。
- 覆盖：
  - `test_auth`：登录成功返回双 token；错密失败；失败 5 次锁定；refresh 换新 token；logout 后旧 token 401；改密后旧 token 失效、新密码可登录；密码复杂度校验拒绝弱密码。
  - `test_permissions`：`require_permission` 有权限放行、无权限 1003。
  - `test_health`：DB/Redis 正常时 healthy。
  - `test_seed`：seed 幂等（重复执行不报错、不重复插入）；`active_flag` 唯一性（软删后同 username 可再建，活跃期不可重复）。

---

## 10. 运行手册（本切片验证步骤）

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash
pip install -e .                    # 或 pip install -r 依赖
cp .env.example .env                # 填入局域网 MySQL/Redis 连接与 JWT_SECRET、SEED_ADMIN_PASSWORD
alembic upgrade head               # 建全部 11 表
python scripts/seed.py             # 初始化角色/权限/超管/字典
uvicorn app.main:app --reload      # 启动，访问 /docs
pytest                             # 跑 ims_test 库全绿
```

---

## 11. 风险与决策记录

- **密码库**：选 passlib[bcrypt]（bcrypt 是文档首选）。注意 bcrypt 72 字节上限与 passlib/bcrypt 版本兼容，`pyproject` 锁定兼容版本。
- **JWT 库**：选 PyJWT（维护活跃），非 python-jose。
- **UUIDv7**：用 uuid-utils（Rust 实现，含 uuid7）。
- **改密使旧 token 失效**：用 `pwd_updated_at` vs token `iat` 比较，避免维护全量 jti。
- **数据范围**：本切片只建地基与单测，不接业务查询（无数据可过滤），切片2/3 接入。
- **建全部表**：一次基线迁移建 11 表，避免后续 FK 顺序与循环外键反复；后续切片只加业务逻辑不改表结构（如需调整走新迁移）。
