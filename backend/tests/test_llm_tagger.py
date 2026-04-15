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
        self.last_page_title = None

    async def __call__(
        self,
        text: str,
        domain: str,
        page_title: str | None,
        tag_pool: list,
    ) -> str:
        self.calls += 1
        self.last_page_title = page_title
        if self.raise_exc:
            raise self.raise_exc
        return self.response


async def test_cache_miss_calls_llm_and_writes_cache():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 19, "weight": 0.9}, {"tag_id": 8, "weight": 0.6}],
        "summary": "冷酷机械美学配文艺灵魂",
        "item_context": "《赛博朋克 2077》是 CDPR 的开放世界 RPG，夜之城冷峻反乌托邦。",
    }))
    result = await llm_tagger.analyze("cyberpunk soul", "game", llm_call=fake)
    assert result["matched_tags"][0]["tag_id"] == 19
    assert result["cache_hit"] is False
    assert fake.calls == 1
    assert "赛博朋克" in result["item_context"]

    db = database.SessionLocal()
    cached = db.query(AnalysisCache).one()
    assert cached.domain == "game"
    db.close()


async def test_cache_hit_skips_llm():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 1, "weight": 1.0}],
        "summary": "s",
        "item_context": "一段测试用的书评片段",
    }))
    await llm_tagger.analyze("same text", "book", llm_call=fake)
    fake.calls = 0

    result = await llm_tagger.analyze("same text", "book", llm_call=fake)
    assert fake.calls == 0
    assert result["cache_hit"] is True
    assert result["item_context"] == "一段测试用的书评片段"


async def test_page_title_is_passed_to_llm():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 1, "weight": 1.0}],
        "summary": "s",
        "item_context": "a test",
    }))
    await llm_tagger.analyze(
        "挽救计划",
        "movie",
        page_title="挽救计划 (2015) - 豆瓣电影",
        llm_call=fake,
    )
    assert fake.last_page_title == "挽救计划 (2015) - 豆瓣电影"


async def test_item_context_synthesized_when_llm_omits_it():
    """V1.3.1: LLM must always return item_context, but if it doesn't we
    synthesize a fallback from summary. Never return empty item_context."""
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 1, "weight": 1.0}],
        "summary": "一段悲伤的评论",
        # item_context intentionally omitted
    }))
    result = await llm_tagger.analyze("some text", "book", llm_call=fake)
    assert result["item_context"] != ""
    assert "一段悲伤的评论" in result["item_context"]


async def test_invalid_tag_ids_are_filtered():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 999, "weight": 0.5}, {"tag_id": 3, "weight": 0.9}],
        "summary": "s",
        "item_context": "x",
    }))
    result = await llm_tagger.analyze("text", "book", llm_call=fake)
    tag_ids = [t["tag_id"] for t in result["matched_tags"]]
    assert 999 not in tag_ids
    assert 3 in tag_ids


async def test_all_tags_invalid_raises():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 999, "weight": 0.5}],
        "summary": "s",
        "item_context": "x",
    }))
    with pytest.raises(llm_tagger.LlmParseError):
        await llm_tagger.analyze("text", "book", llm_call=fake)


async def test_json_parse_failure_does_not_write_cache():
    seed_all()
    fake = FakeLLM(response="not json at all")
    with pytest.raises(llm_tagger.LlmParseError):
        await llm_tagger.analyze("text", "book", llm_call=fake)
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
        "tags": [{"tag_id": 2, "weight": 1.0}],
        "summary": "fresh",
        "item_context": "fresh context",
    }))
    result = await llm_tagger.analyze("old", "book", llm_call=fake)
    assert fake.calls == 1
    assert result["summary"] == "fresh"


async def test_parse_failure_preserves_existing_expired_row():
    seed_all()
    text_hash = llm_tagger.hash_text("probe", "book")
    db = database.SessionLocal()
    db.add(AnalysisCache(
        text_hash=text_hash, domain="book",
        tags_json='{"tags":[{"tag_id":1,"weight":1.0}],"summary":"old"}',
        summary="old",
        created_at=datetime.utcnow() - timedelta(days=8),
    ))
    db.commit(); db.close()

    fake = FakeLLM(response="garbage")
    with pytest.raises(llm_tagger.LlmParseError):
        await llm_tagger.analyze("probe", "book", llm_call=fake)

    db = database.SessionLocal()
    assert db.query(AnalysisCache).filter_by(text_hash=text_hash).count() == 1
    db.close()


async def test_old_cache_without_item_context_is_treated_as_miss():
    """V1.3.1: cached entries predating item_context should be regenerated
    rather than returning empty item_context."""
    seed_all()
    text_hash = llm_tagger.hash_text("old-cache", "book")
    db = database.SessionLocal()
    db.add(AnalysisCache(
        text_hash=text_hash, domain="book",
        # No item_context field in the JSON
        tags_json='{"tags":[{"tag_id":1,"weight":1.0}],"summary":"old"}',
        summary="old",
        created_at=datetime.utcnow() - timedelta(days=1),  # still fresh
    ))
    db.commit(); db.close()

    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 2, "weight": 1.0}],
        "summary": "regenerated",
        "item_context": "regenerated context",
    }))
    result = await llm_tagger.analyze("old-cache", "book", llm_call=fake)
    # Cache hit branch was skipped because item_context was missing
    assert result["cache_hit"] is False
    assert fake.calls == 1
    assert result["item_context"] == "regenerated context"
