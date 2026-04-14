from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Each test runs against its own temp SQLite file.

    Why not `importlib.reload`? reload creates a fresh `Base` class whose
    metadata has no models registered. Models register against the original
    `Base` at import time, so we keep that `Base` alive and just swap
    `engine` / `SessionLocal` via attribute assignment.

    Corollary: all service code must access the session via
    `from app import database; database.SessionLocal()` (attribute lookup),
    not `from app.database import SessionLocal` (which would capture the
    production binding at import and skip this fixture).
    """
    from app import database
    from app.database import Base

    db_file = tmp_path / "test.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    TestSession = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, future=True
    )

    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "SessionLocal", TestSession)

    Base.metadata.create_all(test_engine)

    # Dependency override for FastAPI routes (only if app.deps exists —
    # it's created in Task 7, not present at Task 1).
    override_installed = False
    try:
        from app.deps import get_db
        from app.main import app

        def _override_get_db():
            db = TestSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_get_db
        override_installed = True
    except ImportError:
        pass

    try:
        yield
    finally:
        if override_installed:
            from app.deps import get_db
            from app.main import app
            app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(test_engine)
        test_engine.dispose()
