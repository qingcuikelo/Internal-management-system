# 企业内部管理系统

基于 FastAPI + Vue3 的企业内部管理系统，用于统一管理**部门、员工、工位、IT 设备**四类核心资产，并提供账号权限、操作审计、数据字典等系统能力。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11 / FastAPI / SQLAlchemy 2.0 / Celery |
| 前端 | Vue 3 / TypeScript / Pinia / Element Plus |
| 数据库 | MySQL 8 |
| 缓存 | Redis 7 |
| 部署 | Docker Compose |

## 功能概览

- **组织管理**：部门树、员工 CRUD、批量调动、离职级联（自动释放工位+退还设备+禁用账号）
- **资产管理**：工位分配/释放（乐观锁防并发）、设备领用/退还/送修/报废、分配历史追溯
- **权限体系**：RBAC 五角色（超级管理员/HR/IT/部门主管/员工）、数据范围行级过滤
- **系统管理**：账号管理、角色权限分配、数据字典（Redis 缓存）、操作日志审计
- **报表**：员工资产概览、闲置资产统计、部门设备汇总、保修到期提醒
- **导入导出**：Excel 批量导入员工、筛选导出（异步 Celery 任务）

## 快速开始

### 1. 环境要求

- Docker 及 Docker Compose
- 或手工部署：Python 3.11、Node.js 22、MySQL 8、Redis 7

### 2. Docker 一键部署

```bash
git clone git@github.com:qingcuikelo/Internal-management-system.git
cd Internal-management-system

# 创建生产环境配置
cp .env.prod.example .env.prod
# 编辑 .env.prod，填入 MySQL 密码、JWT 密钥等

# 启动全部服务
docker compose --env-file .env.prod up -d

# 初始化数据库
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed.py

# 访问 http://localhost
# 默认超管账号: admin / 密码见 .env.prod 中的 SEED_ADMIN_PASSWORD
```

### 3. 本地开发

**后端**：
```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env  # 编辑数据库连接信息
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```

**前端**：
```bash
cd frontend
npm install
npm run dev  # 访问 http://localhost:5173，API 自动代理到 :8000
```

**测试**：
```bash
cd backend
pytest  # 151 测试，需要 MySQL 测试库和 Redis DB15
```

## 项目结构

```
├── backend/             # FastAPI 后端
│   ├── app/
│   │   ├── api/         # 路由挂载
│   │   ├── core/        # 配置、安全、依赖注入
│   │   ├── models/      # SQLAlchemy ORM 模型
│   │   ├── repositories/# 数据访问层
│   │   ├── routers/     # 接口控制器
│   │   ├── schemas/     # Pydantic 出入参
│   │   ├── services/    # 业务逻辑层
│   │   └── tasks/       # Celery 异步任务
│   ├── alembic/         # 数据库迁移
│   └── tests/           # pytest
├── frontend/            # Vue3 前端
│   └── src/
│       ├── api/         # Axios 请求模块
│       ├── components/  # 通用组件
│       ├── layouts/     # 布局组件
│       ├── router/      # 路由 + 权限守卫
│       ├── stores/      # Pinia 状态
│       └── views/       # 页面组件
├── docker-compose.yml   # 容器编排
└── .env.prod.example    # 生产环境变量模板
```
