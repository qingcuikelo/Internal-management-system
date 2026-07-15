# ---- Build stage ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system deps needed for mysqlclient/bcrypt build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc-dev default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create minimal package so hatchling can build
RUN mkdir -p app && echo "" > app/__init__.py

# Copy dependency list and install
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# ---- Runtime stage ----
FROM python:3.11-slim

WORKDIR /app

# Runtime deps for mysqlclient
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
COPY scripts/ scripts/
COPY pyproject.toml .

# Create uploads directory and non-root user
RUN mkdir -p uploads/exports uploads/imports && \
    useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Default: run FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
