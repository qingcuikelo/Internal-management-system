from app.core.database import SessionLocal
from app.services.seed_service import run_seed


def main() -> None:
    db = SessionLocal()
    try:
        run_seed(db)
        db.commit()
        print("Seed completed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
