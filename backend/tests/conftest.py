import os

os.environ["ALEMBIC_TARGET"] = "test"

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from starlette.testclient import TestClient

from app.core.config import settings
from app.core import database, redis as app_redis
from app.models import Base

test_engine = create_engine(settings.sqlalchemy_test_url, pool_pre_ping=True, future=True)
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, future=True)


def _drop_everything() -> None:
    with test_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for tbl in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DROP TABLE IF EXISTS `{tbl.name}`"))
        conn.execute(text("DROP TABLE IF EXISTS `alembic_version`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))


@pytest.fixture(scope="session", autouse=True)
def _schema():
    _drop_everything()
    command.upgrade(Config("alembic.ini"), "head")
    yield
    _drop_everything()


@pytest.fixture()
def db():
    conn = test_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture()
def redis_conn():
    client = app_redis.get_redis()
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture()
def client(db, redis_conn):
    from app.main import app

    app.dependency_overrides[database.get_db] = lambda: db
    app.dependency_overrides[app_redis.get_redis] = lambda: redis_conn
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
