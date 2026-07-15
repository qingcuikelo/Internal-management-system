from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    api_prefix: str = "/api/v1"

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "ims"
    db_name_test: str = "ims_test"

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_test_db: int = 15
    redis_password: str = ""

    jwt_secret: str
    jwt_alg: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    login_max_fail: int = 5
    login_lock_minutes: int = 15

    celery_broker_db: int = 1
    celery_task_always_eager: bool = True
    warranty_expiry_days: int = 30
    exports_dir: str = "uploads"

    dict_cache_ttl: int = 600

    seed_admin_username: str = "admin"
    seed_admin_password: str = ""

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    def _url(self, name: str) -> str:
        pwd = f":{self.db_password}" if self.db_password else ""
        return f"mysql+pymysql://{self.db_user}{pwd}@{self.db_host}:{self.db_port}/{name}?charset=utf8mb4"

    @property
    def sqlalchemy_url(self) -> str:
        return self._url(self.db_name)

    @property
    def sqlalchemy_test_url(self) -> str:
        return self._url(self.db_name_test)

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def redis_test_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_test_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
