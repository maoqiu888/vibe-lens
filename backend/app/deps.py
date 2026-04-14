from typing import Generator

from sqlalchemy.orm import Session

from app import database

DEFAULT_USER_ID = 1  # V1.0 single-user hardcoded


def get_db() -> Generator[Session, None, None]:
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_id() -> int:
    return DEFAULT_USER_ID
