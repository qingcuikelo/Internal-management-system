import pytest
from datetime import date, timedelta

from app.models import Device
from app.services import seed_service


@pytest.fixture()
def seeded(db):
    seed_service.run_seed(db)
    db.flush()
    return db


def test_scan_warranty_expiry_finds_expiring(db, seeded):
    # add a device expiring in 10 days
    d = Device(asset_code="SCAN1", type="laptop", status=2, warranty_expire=date.today() + timedelta(days=10))
    db.add(d)
    # Commit so the Celery task (which creates its own SessionLocal) can see data
    db.commit()
    from app.tasks.warranty_scan import scan_warranty_expiry
    result = scan_warranty_expiry(days=30)
    assert result["count"] >= 1
    assert any(item["asset_code"] == "SCAN1" for item in result["items"])


def test_scan_warranty_skips_scrapped(db, seeded):
    d = Device(asset_code="SCRAP", type="laptop", status=4, warranty_expire=date.today() + timedelta(days=5))
    db.add(d)
    db.flush()
    from app.tasks.warranty_scan import scan_warranty_expiry
    result = scan_warranty_expiry(days=30)
    codes = {item["asset_code"] for item in result["items"]}
    assert "SCRAP" not in codes


def test_scan_warranty_skips_expired(db, seeded):
    d = Device(asset_code="OLD", type="laptop", status=2, warranty_expire=date.today() - timedelta(days=10))
    db.add(d)
    db.flush()
    from app.tasks.warranty_scan import scan_warranty_expiry
    result = scan_warranty_expiry(days=30)
    codes = {item["asset_code"] for item in result["items"]}
    assert "OLD" not in codes
