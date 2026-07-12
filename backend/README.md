# IMS Backend — Slice 1 (Foundation + Auth/RBAC)

## Prerequisites

- Python 3.11
- LAN MySQL 8 and Redis 7 reachable
- Databases created:

```sql
CREATE DATABASE IF NOT EXISTS ims CHARACTER SET utf8mb4;
CREATE DATABASE IF NOT EXISTS ims_test CHARACTER SET utf8mb4;
```

## Setup

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash
pip install -e ".[dev]"
cp .env.example .env                # fill DB/Redis creds, JWT_SECRET, SEED_ADMIN_PASSWORD
```

## Database & seed

```bash
alembic upgrade head
python scripts/seed.py
```

## Run

```bash
uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs
```

## Test

```bash
pytest                             # runs against ims_test
ruff check .
```

## Auth quickstart

1. `POST /api/v1/auth/login` `{ "username": "admin", "password": "<SEED_ADMIN_PASSWORD>" }`
2. Use `Authorization: Bearer <access_token>` for protected endpoints.
3. `GET /api/v1/auth/me` returns role + permission codes.
