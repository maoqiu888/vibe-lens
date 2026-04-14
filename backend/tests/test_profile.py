from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.main import app
from app.models.user import User
from app.services.seed import seed_all

client = TestClient(app)


def _init_profile():
    seed_all()
    db = database.SessionLocal()
    if db.scalar(select(User).where(User.id == 1)) is None:
        db.add(User(id=1, username="default"))
        db.commit()
    db.close()
    client.post(
        "/api/v1/cold-start/submit",
        json={"selected_tag_ids": [1, 5, 9, 13, 17, 21]},
    )


def test_radar_returns_6_dimensions():
    _init_profile()
    r = client.get("/api/v1/profile/radar")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == 1
    assert len(body["dimensions"]) == 6
    cats = {d["category"] for d in body["dimensions"]}
    assert cats == {"pace", "mood", "cognition", "narrative", "world", "intensity"}
    for d in body["dimensions"]:
        assert 0 <= d["score"] <= 100
        assert "dominant_tag" in d
