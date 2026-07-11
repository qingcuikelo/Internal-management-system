import importlib


def test_settings_builds_urls(monkeypatch):
    monkeypatch.setenv("DB_HOST", "10.0.0.5")
    monkeypatch.setenv("DB_PORT", "3306")
    monkeypatch.setenv("DB_USER", "ims")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("DB_NAME", "ims")
    monkeypatch.setenv("DB_NAME_TEST", "ims_test")
    monkeypatch.setenv("REDIS_HOST", "10.0.0.6")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_DB", "1")
    monkeypatch.setenv("REDIS_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET", "x")

    from app.core import config
    importlib.reload(config)
    s = config.get_settings()

    assert s.sqlalchemy_url == "mysql+pymysql://ims:secret@10.0.0.5:3306/ims?charset=utf8mb4"
    assert s.sqlalchemy_test_url.endswith("/ims_test?charset=utf8mb4")
    assert s.redis_url == "redis://10.0.0.6:6379/1"
    assert s.access_token_minutes == 15
    assert s.cors_origins == ["http://localhost:5173"]


def test_cors_origins_parses_csv(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com,http://b.com")
    from app.core import config
    importlib.reload(config)
    s = config.get_settings()
    assert s.cors_origins == ["http://a.com", "http://b.com"]
