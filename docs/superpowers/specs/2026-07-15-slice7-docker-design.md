# 切片7 设计文档：Docker 容器化部署

> 版本：v1 · 日期：2026-07-15
> 前置：切片1-6 已合并。本切片将完整系统打包为 Docker Compose 一键部署。

---

## 1. 目标

将企业内部管理系统打包为 `docker-compose up -d` 一键启动的容器化部署方案。

**容器编排**：
```
Browser → Nginx (:80)
  ├─ /           → 前端静态文件（Vue3 build）
  ├─ /api/*      → FastAPI (:8000)
  └─ /exports/*  → FastAPI (:8000)

FastAPI ← MySQL (:3306)
FastAPI ← Redis (:6379)

Celery Worker  │ 同 FastAPI 镜像，不同启动命令
Celery Beat    │
```

**6 个服务**：`nginx`、`backend`、`celery-worker`、`celery-beat`、`mysql`、`redis`

---

## 2. 文件清单

```
├── docker-compose.yml          # 6 服务编排（端口、卷、网络、健康检查、depends_on）
├── .gitignore                  # 追加排除项
├── backend/
│   ├── Dockerfile              # Python 3.11-slim, pip install, uvicorn
│   └── .dockerignore
├── frontend/
│   ├── Dockerfile              # 多阶段: node:22 build → nginx:alpine serve
│   └── .dockerignore
└── nginx.conf                  # 反向代理 + 静态文件 + gzip + 缓存策略
```

---

## 3. 关键决策

| 项目 | 选择 | 理由 |
|---|---|---|
| MySQL 8 | 官方镜像 `mysql:8.4` | 兼容已有数据库 |
| Redis 7 | 官方镜像 `redis:7-alpine` | 轻量 |
| 后端镜像 | `python:3.11-slim` | 体积小，生产够用 |
| 前端镜像 | 多阶段 `node:22-alpine` build → `nginx:alpine` | 最终镜像 ≈10MB |
| Celery | 复用 backend 镜像，不同 command | 避免重复构建 |
| 卷挂载 | `mysql_data`、`redis_data`、`exports_data` | 数据持久化，重启不丢失 |
| 健康检查 | 后端 `/api/v1/health`、MySQL/Redis 自带 check | 启动顺序保证 |
| Uvicorn workers | `--workers 4` | 多核利用（按 CPU 核数调整） |
| 前端缓存 | Vite 产物带 hash → `max-age=31536000`（强缓存）；`index.html` → `no-cache` | 正确缓存策略 |

---

## 4. 环境变量

通过 `.env.prod` 文件注入（docker-compose 读取）。关键变量：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码 | 必填 |
| `MYSQL_DATABASE` | 应用数据库名 | `ims` |
| `DB_USER` / `DB_PASSWORD` | 应用连接凭据 | — |
| `JWT_SECRET` | JWT 签名密钥 | 必填 |
| `SEED_ADMIN_PASSWORD` | 超管初始密码 | 必填 |
| `REDIS_PASSWORD` | Redis 密码（可选） | — |
| `CORS_ORIGINS` | 允许的前端源 | `http://localhost` |

---

## 5. 启动流程

```bash
# 1. 在服务器上克隆仓库
git clone <repo-url> && cd Internal-management-system

# 2. 创建 .env.prod（填写密码等）

# 3. 一键启动
docker-compose up -d

# 4. 查看状态
docker-compose ps

# 5. 初始化数据库（首次）
docker-compose exec backend python scripts/seed.py

# 6. 访问
# http://服务器IP
```
