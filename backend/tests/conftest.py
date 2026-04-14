import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    """Each test runs against its own temp SQLite file."""
    tmp = tempfile.mkdtemp()
    db_file = Path(tmp) / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_file))

    # Force settings + engine reload for this test
    from importlib import reload
    from app import config, database
    reload(config)
    reload(database)

    from app.database import Base, engine
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
