# Internal Management System

English | [中文](README_CN.md)

An enterprise internal management system built with FastAPI + Vue3 for managing **departments, employees, workstations, and IT devices** — plus account permissions, audit trails, and data dictionaries.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 / FastAPI / SQLAlchemy 2.0 / Celery |
| Frontend | Vue 3 / TypeScript / Pinia / Element Plus |
| Database | MySQL 8 |
| Cache | Redis 7 |
| Deployment | Docker Compose |

## Features

- **Organization**: department tree, employee CRUD, batch reassignment, resignation cascade (auto-release workstation + return devices + disable account)
- **Assets**: workstation assignment/release (optimistic locking), device checkout/return/repair/scrap, assignment history
- **RBAC**: 5 built-in roles (super admin / HR / IT / department manager / employee), row-level data scope filtering
- **System**: account management, role-permission assignment, data dictionary (Redis cache), operation log audit
- **Reports**: employee asset overview, idle assets, devices by department, warranty expiry alerts
- **Import/Export**: Excel batch import employees, filtered export (async Celery tasks)

## Quick Start

### 1. Prerequisites

- Docker & Docker Compose
- Or manual: Python 3.11, Node.js 22, MySQL 8, Redis 7

### 2. Docker (One Command)

```bash
git clone git@github.com:qingcuikelo/Internal-management-system.git
cd Internal-management-system

# Create production config
cp .env.prod.example .env.prod
# Edit .env.prod — fill in MySQL password, JWT secret, etc.

# Start all services
docker compose --env-file .env.prod up -d

# Initialize database
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed.py

# Visit http://localhost
# Default admin: admin / password: see SEED_ADMIN_PASSWORD in .env.prod
```

### 3. Local Development

**Backend**:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env  # configure DB connection
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev  # http://localhost:5173, API proxied to :8000
```

**Tests**:
```bash
cd backend
pytest  # 151 tests, requires MySQL test database and Redis DB15
```

## Project Structure

```
├── backend/             # FastAPI backend
│   ├── app/
│   │   ├── api/         # Router mounting
│   │   ├── core/        # Config, security, dependency injection
│   │   ├── models/      # SQLAlchemy ORM models
│   │   ├── repositories/# Data access layer
│   │   ├── routers/     # Endpoint controllers
│   │   ├── schemas/     # Pydantic request/response models
│   │   ├── services/    # Business logic layer
│   │   └── tasks/       # Celery async tasks
│   ├── alembic/         # Database migrations
│   └── tests/           # pytest
├── frontend/            # Vue3 frontend
│   └── src/
│       ├── api/         # Axios request modules
│       ├── components/  # Shared components
│       ├── layouts/     # Layout components
│       ├── router/      # Router + permission guards
│       ├── stores/      # Pinia stores
│       └── views/       # Page components
├── docker-compose.yml   # Container orchestration
└── .env.prod.example    # Production env template
```
