from datetime import date

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import WorkstationAssignment, DeviceAssignment


# --- workstation history ---
def create_ws(db: Session, workstation_id: str, employee_id: str,
              start_date: date, operator_id: str) -> WorkstationAssignment:
    row = WorkstationAssignment(workstation_id=workstation_id, employee_id=employee_id,
                                start_date=start_date, operator_id=operator_id)
    db.add(row)
    return row


def close_ws_open(db: Session, workstation_id: str, end_date: date) -> int:
    stmt = (update(WorkstationAssignment)
            .where(WorkstationAssignment.workstation_id == workstation_id,
                   WorkstationAssignment.end_date.is_(None))
            .values(end_date=end_date))
    return db.execute(stmt).rowcount


def list_ws(db: Session, workstation_id: str) -> list[WorkstationAssignment]:
    stmt = (select(WorkstationAssignment)
            .where(WorkstationAssignment.workstation_id == workstation_id)
            .order_by(WorkstationAssignment.created_at.desc()))
    return list(db.execute(stmt).scalars().all())


# --- device history (used in Task 4/5) ---
def create_dev(db: Session, device_id: str, employee_id: str,
               checkout_date: date, operator_id: str) -> DeviceAssignment:
    row = DeviceAssignment(device_id=device_id, employee_id=employee_id,
                           checkout_date=checkout_date, operator_id=operator_id)
    db.add(row)
    return row


def close_dev_open(db: Session, device_id: str, return_date: date) -> int:
    stmt = (update(DeviceAssignment)
            .where(DeviceAssignment.device_id == device_id,
                   DeviceAssignment.return_date.is_(None))
            .values(return_date=return_date))
    return db.execute(stmt).rowcount


def list_dev(db: Session, device_id: str) -> list[DeviceAssignment]:
    stmt = (select(DeviceAssignment)
            .where(DeviceAssignment.device_id == device_id)
            .order_by(DeviceAssignment.created_at.desc()))
    return list(db.execute(stmt).scalars().all())
