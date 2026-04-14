import json
from datetime import datetime, timedelta

import pytest

from app import database
from app.models.analysis_cache import AnalysisCache
from app.services import llm_tagger
from app.services.seed import seed_all


class FakeLLM:
    def __init__(self, response=None, raise_exc=None):
        self.response = response
        self.raise_exc = raise_exc
        self.calls = 0

    async def __call__(self, text: str, domain: str, tag_pool: list) -> str:
        self.calls += 1
        if self.raise_exc:
            raise self.raise_exc
        return self.response


async def test_cache_miss_calls_llm_and_writes_cache():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 19, "weight": 0.9}, {"tag_id": 8, "weight": 0.6}],
        "summary": "冷酷机械美学配文艺灵魂"
    }))
    result = await llm_tagger.analyze("cyberpunk soul", "game", fake)
    assert result["matched_tags"][0]["tag_id"] == 19
    assert result["cache_hit"] is False
    assert fake.calls == 1

    db = database.SessionLocal()
    cached = db.query(AnalysisCache).one()
    assert cached.domain == "game"
    db.close()


async def test_cache_hit_skips_llm():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 1, "weight": 1.0}], "summary": "s"
    }))
    await llm_tagger.analyze("same text", "book", fake)
    fake.calls = 0

    result = await llm_tagger.analyze("same text", "book", fake)
    assert fake.calls == 0
    assert result["cache_hit"] is True


async def test_invalid_tag_ids_are_filtered():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 999, "weight": 0.5}, {"tag_id": 3, "weight": 0.9}],
        "summary": "s"
    }))
    result = await llm_tagger.analyze("text", "book", fake)
    tag_ids = [t["tag_id"] for t in result["matched_tags"]]
    assert 999 not in tag_ids
    assert 3 in tag_ids


async def test_all_tags_invalid_raises():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 999, "weight": 0.5}], "summary": "s"
    }))
    with pytest.raises(llm_tagger.LlmParseError):
        await llm_tagger.analyze("text", "book", fake)


async def test_json_parse_failure_does_not_write_cache():
    seed_all()
    fake = FakeLLM(response="not json at all")
    with pytest.raises(llm_tagger.LlmParseError):
        await llm_tagger.analyze("text", "book", fake)
    db = database.SessionLocal()
    assert db.query(AnalysisCache).count() == 0
    db.close()


async def test_expired_cache_is_ignored():
    seed_all()
    db = database.SessionLocal()
    db.add(AnalysisCache(
        text_hash=llm_tagger.hash_text("old", "book"),
        domain="book",
        tags_json='{"tags":[{"tag_id":1,"weight":1.0}],"summary":"old"}',
        summary="old",
        created_at=datetime.utcnow() - timedelta(days=8),
    ))
    db.commit()
    db.close()

    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 2, "weight": 1.0}], "summary": "fresh"
    }))
    result = await llm_tagger.analyze("old", "book", fake)
    assert fake.calls == 1
    assert result["summary"] == "fresh"
