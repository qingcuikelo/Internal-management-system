import json
from datetime import date, timedelta

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis import redis_client
from app.models import Device
from sqlalchemy import select


@celery_app.task(name="app.tasks.warranty_scan.scan_warranty_expiry")
def scan_warranty_expiry(days: int | None = None) -> dict:
    days = days or settings.warranty_expiry_days
    today = date.today()
    cutoff = today + timedelta(days=days)
    db = SessionLocal()
    try:
        devices = db.execute(
            select(Device).where(
                Device.warranty_expire.between(today, cutoff),
                Device.status != 4,
                Device.deleted_at.is_(None),
            ).order_by(Device.warranty_expire.asc())
        ).scalars().all()
        items = [{"id": d.id, "asset_code": d.asset_code, "type": d.type,
                  "brand": d.brand, "model": d.model,
                  "warranty_expire": str(d.warranty_expire),
                  "current_employee_id": d.current_employee_id}
                 for d in devices]
        result = {"count": len(items), "items": items, "scan_date": str(today)}
        redis_client.set(f"warranty_expiring:{days}", json.dumps(result, ensure_ascii=False), ex=86400)
        return result
    finally:
        db.close()
