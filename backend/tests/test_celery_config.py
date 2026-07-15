from app.core.config import Settings


def test_celery_config_defaults():
    s = Settings()
    assert s.celery_broker_db == 1
    assert s.celery_task_always_eager is True
    assert s.warranty_expiry_days == 30
    assert s.exports_dir == "uploads"


def test_celery_app_created():
    from app.core.celery_app import celery_app

    assert celery_app.conf.task_always_eager is True
    assert len(celery_app.conf.beat_schedule) == 1
