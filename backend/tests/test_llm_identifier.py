import json
from datetime import datetime, timedelta

import pytest

from app import database
from app.models.analysis_cache import AnalysisCache
from app.services import llm_identifier
from app.services.seed import seed_all


class FakeLLM:
    """Matches llm_identifier._default_llm_call signature: (text, domain, page_title, tag_pool) -> str."""

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


def _make_response(
    item_profile: dict | None = None,
    tags: list | None = None,
    summary: str = "测试摘要",
) -> str:
    """Build a valid LLM JSON response string."""
    profile = item_profile or {
        "item_name": "《我，许可》",
        "item_name_alt": None,
        "year": 2024,
        "creator": "导演：刘抒鸣",
        "genre": "华语剧情片",
        "plot_gist": "一个普通人许可在城市中挣扎求存的故事。",
        "tone": "写实、克制、偏沉重但有微光",
        "name_vs_reality": "名字'我，许可'听着像个人名，其实是一部完整院线电影。",
        "confidence": "high",
    }
    return json.dumps({
        "item_profile": profile,
        "tags": tags or [{"tag_id": 1, "weight": 0.9}, {"tag_id": 8, "weight": 0.7}],
        "summary": summary,
    }, ensure_ascii=False)


async def test_happy_path_famous_movie():
    """Agent 1 identifies a famous movie and returns item_profile + tags + summary."""
    seed_all()
    fake = FakeLLM(response=_make_response())
    result = await llm_identifier.identify("我，许可", "movie", llm_call=fake)
    assert result["item_profile"]["item_name"] == "《我，许可》"
    assert result["item_profile"]["confidence"] == "high"
    assert result["cache_hit"] is False
    assert fake.calls == 1
    assert len(result["matched_tags"]) == 2
    assert result["matched_tags"][0]["tag_id"] == 1
    assert result["summary"] == "测试摘要"
    assert result["text_hash"]  # non-empty


async def test_domain_priority_movie_vs_book():
    """Domain hint is passed to LLM so it prioritizes the correct type."""
    seed_all()
    fake = FakeLLM(response=_make_response(
        item_profile={
            "item_name": "《挽救计划》",
            "item_name_alt": "Project Hail Mary",
            "year": 2021,
            "creator": "Andy Weir",
            "genre": "科幻小说",
            "plot_gist": "一个宇航员独自拯救地球的故事。",
            "tone": "乐观幽默",
            "name_vs_reality": "",
            "confidence": "high",
        },
        tags=[{"tag_id": 11, "weight": 0.9}],
        summary="科幻解谜向",
    ))
    result = await llm_identifier.identify(
        "挽救计划", "book", llm_call=fake,
    )
    assert result["item_profile"]["genre"] == "科幻小说"


async def test_page_title_passthrough():
    """page_title is forwarded to the LLM call."""
    seed_all()
    fake = FakeLLM(response=_make_response())
    await llm_identifier.identify(
        "挽救计划", "movie",
        page_title="挽救计划 (2015) - 豆瓣电影",
        llm_call=fake,
    )
    assert fake.last_page_title == "挽救计划 (2015) - 豆瓣电影"


async def test_confidence_levels_medium():
    """Medium confidence items still return a valid profile."""
    seed_all()
    fake = FakeLLM(response=_make_response(
        item_profile={
            "item_name": "某个不太确定的作品",
            "item_name_alt": None,
            "year": None,
            "creator": None,
            "genre": "可能是电影",
            "plot_gist": "看起来像一段关于旅行的故事。",
            "tone": "温暖",
            "name_vs_reality": "",
            "confidence": "medium",
        },
    ))
    result = await llm_identifier.identify("一段旅行", "movie", llm_call=fake)
    assert result["item_profile"]["confidence"] == "medium"


async def test_missing_fields_get_defaults():
    """LLM omits some item_profile fields — they get filled with defaults."""
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "item_profile": {
            "item_name": "《测试》",
            # All other fields omitted
        },
        "tags": [{"tag_id": 1, "weight": 0.8}],
        "summary": "test",
    }))
    result = await llm_identifier.identify("测试", "book", llm_call=fake)
    profile = result["item_profile"]
    assert profile["item_name"] == "《测试》"
    assert profile["confidence"] == "low"  # default when missing
    assert profile["year"] is None
    assert profile["creator"] is None
    assert profile["genre"] is not None  # should have a default
    assert profile["plot_gist"] is not None
    assert profile["tone"] is not None


async def test_cache_hit_returns_without_llm_call():
    """Second call with same text+domain hits cache and skips LLM."""
    seed_all()
    fake = FakeLLM(response=_make_response())
    await llm_identifier.identify("cached text", "book", llm_call=fake)
    fake.calls = 0

    result = await llm_identifier.identify("cached text", "book", llm_call=fake)
    assert fake.calls == 0
    assert result["cache_hit"] is True
    assert result["item_profile"]["item_name"] == "《我，许可》"


async def test_old_cache_without_item_profile_is_miss():
    """V1.3 cache entries without item_profile are treated as cache miss."""
    seed_all()
    text_hash = llm_identifier.hash_text("old-entry", "book")
    db = database.SessionLocal()
    db.add(AnalysisCache(
        text_hash=text_hash, domain="book",
        # Old V1.3 format: has item_context but NO item_profile
        tags_json=json.dumps({
            "tags": [{"tag_id": 1, "weight": 1.0}],
            "summary": "old",
            "item_context": "some old context",
        }),
        summary="old",
        created_at=datetime.utcnow() - timedelta(days=1),  # still fresh
    ))
    db.commit()
    db.close()

    fake = FakeLLM(response=_make_response(summary="regenerated"))
    result = await llm_identifier.identify("old-entry", "book", llm_call=fake)
    assert result["cache_hit"] is False
    assert fake.calls == 1
    assert result["summary"] == "regenerated"


async def test_tag_extraction_filters_invalid_ids():
    """Tags with out-of-range IDs are filtered out."""
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "item_profile": {"item_name": "test", "confidence": "high",
                         "genre": "x", "plot_gist": "x", "tone": "x",
                         "name_vs_reality": "", "year": None,
                         "creator": None, "item_name_alt": None},
        "tags": [
            {"tag_id": 999, "weight": 0.5},
            {"tag_id": 3, "weight": 0.9},
        ],
        "summary": "s",
    }))
    result = await llm_identifier.identify("text", "book", llm_call=fake)
    tag_ids = [t["tag_id"] for t in result["matched_tags"]]
    assert 999 not in tag_ids
    assert 3 in tag_ids


async def test_json_parse_failure_raises():
    """Invalid JSON from LLM raises LlmParseError."""
    seed_all()
    fake = FakeLLM(response="not json at all")
    with pytest.raises(llm_identifier.LlmParseError):
        await llm_identifier.identify("text", "book", llm_call=fake)


async def test_all_tags_invalid_raises():
    """If every returned tag has an invalid ID, raise LlmParseError."""
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "item_profile": {"item_name": "test", "confidence": "high",
                         "genre": "x", "plot_gist": "x", "tone": "x",
                         "name_vs_reality": "", "year": None,
                         "creator": None, "item_name_alt": None},
        "tags": [{"tag_id": 999, "weight": 0.5}],
        "summary": "s",
    }))
    with pytest.raises(llm_identifier.LlmParseError):
        await llm_identifier.identify("text", "book", llm_call=fake)
