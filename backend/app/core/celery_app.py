from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

_broker = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.celery_broker_db}"

celery_app = Celery("ims", broker=_broker, backend=_broker)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_always_eager=settings.celery_task_always_eager,
)

celery_app.conf.beat_schedule = {
    "scan-warranty-expiry": {
        "task": "app.tasks.warranty_scan.scan_warranty_expiry",
        "schedule": crontab(hour=9, minute=7),
    },
}
