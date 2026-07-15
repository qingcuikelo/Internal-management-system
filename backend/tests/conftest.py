import os

os.environ["ALEMBIC_TARGET"] = "test"

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from app.core.config import settings
from app.core import database, redis as app_redis
test_engine = create_engine(settings.sqlalchemy_test_url, pool_pre_ping=True, future=True)
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, future=True)

# Celery tasks create their own session via SessionLocal(). Override to use the
# test database so those tasks see the same data as the test fixtures.
database.SessionLocal = TestSession


def _drop_everything() -> None:
    with test_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        names = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = :s"),
            {"s": settings.db_name_test},
        ).scalars().all()
        for name in names:
            conn.execute(text(f"DROP TABLE IF EXISTS `{name}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))


@pytest.fixture(scope="session", autouse=True)
def _schema():
    _drop_everything()
    command.upgrade(Config("alembic.ini"), "head")
    yield
    _drop_everything()


@pytest.fixture(autouse=True)
def _clear_tables():
    """Delete all rows before each test so state from a committed previous
    test does not leak into the next one."""
    with test_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        names = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = :s"),
            {"s": settings.db_name_test},
        ).scalars().all()
        for name in names:
            if name == "alembic_version":
                continue
            conn.execute(text(f"DELETE FROM `{name}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    yield


@pytest.fixture()
def db():
    """Session that commits on success (rolls back on failure).

    Data added via this fixture is persisted to the test database, making it
    visible to Celery tasks that create their own ``SessionLocal()``.
    """
    session = TestSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture()
def redis_conn():
    import redis

    client = redis.from_url(settings.redis_test_url, decode_responses=True)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


@pytest.fixture()
def client(db, redis_conn):
    from app.main import app

    app.dependency_overrides[database.get_db] = lambda: db
    app.dependency_overrides[app_redis.get_redis] = lambda: redis_conn
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
