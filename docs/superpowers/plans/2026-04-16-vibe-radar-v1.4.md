# Vibe-Radar V1.4 SP-F Implementation Plan — 3-Agent Chain Architecture

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 2-call tagger+roaster pipeline with a 3-Agent chain (识别官→匹配官→朋友) that separates item identification, personality-aware match scoring, and natural-language advice into dedicated LLM calls, dramatically improving recognition accuracy, match relevance, and voice quality.

**Architecture:** Three sequential LLM services: (1) `llm_identifier` identifies the item using pretrained knowledge + extracts 24 tags for cosine similarity, (2) `llm_matcher` takes the cosine base_score + item_profile + user personality and outputs a final adjusted score (±15) with 3 reasons + verdict, (3) `llm_advisor` translates the structured facts and reasoning into a 60-120 char friend-voice recommendation. The existing 24-tag math backbone (cosine similarity, radar chart, level system, MBTI seeding) is fully preserved.

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy / pytest / httpx / TypeScript / esbuild / Chrome MV3. Same as V1.3.

---

## Reference Files

| File | Role |
|---|---|
| `backend/app/services/llm_tagger.py` | Being REPLACED by `llm_identifier.py` — study for cache logic, hash_text, tag_pool loading, FakeLLM 4-arg signature |
| `backend/app/services/llm_roaster.py` | Being REPLACED by `llm_advisor.py` — study for FakeLLM 2-arg signature, generate_roast pattern, error handling |
| `backend/app/routers/vibe.py` | Rewrite target — current analyze route (lines 19-113) orchestrates tagger→cosine→roaster→profile_update |
| `backend/app/schemas/analyze.py` | Extend with `verdict` + `reasons` fields |
| `backend/app/services/profile_calc.py` | UNCHANGED — `compute_match_score`, `get_top_core_tag_descriptions`, `increment_interaction`, `apply_core_delta`, `apply_curiosity_delta`, `level_info`, `compute_ui_stage` |
| `backend/app/services/llm_personality_agent.py` | UNCHANGED — MBTI cold-start agent |
| `backend/app/models/analysis_cache.py` | Reused by identifier — same table, extended JSON content |
| `backend/app/models/user_personality.py` | UNCHANGED — UserPersonality model for MBTI/constellation/summary |
| `backend/tests/test_vibe.py` | Rewrite helpers and analyze tests in Task 5 |
| `backend/tests/test_llm_tagger.py` | DELETED in Task 5 (10 tests) |
| `backend/tests/test_llm_roaster.py` | DELETED in Task 5 (9 tests) |
| `extension/src/shared/types.ts` | Add `verdict` + `reasons` to `AnalyzeResult` |
| `extension/src/content/ui/VibeCard.ts` | Add verdict badge, remove summary grey text |
| `extension/src/content/ui/styles.css` | Verdict badge CSS |
| `extension/SMOKE.md` | Update with V1.4 steps |

---

## Task 1: Create `llm_identifier.py` (Agent 1) + tests

**Files:**
- NEW `backend/app/services/llm_identifier.py`
- NEW `backend/tests/test_llm_identifier.py`

**Approach:** TDD — write all tests first (expect failures), then implement, then verify all pass.

### Step 1.1: Write test file

- [ ] Create `backend/tests/test_llm_identifier.py` with the following 10 tests:

```python
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
```

### Step 1.2: Run tests — expect failures

- [ ] Run `cd D:/qhyProject/vibe4.0/backend && python -m pytest tests/test_llm_identifier.py -v` — all tests should fail (module not found)

### Step 1.3: Implement `llm_identifier.py`

- [ ] Create `backend/app/services/llm_identifier.py`:

```python
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable

import httpx
from sqlalchemy import select

from app import database
from app.config import settings
from app.models.analysis_cache import AnalysisCache
from app.models.vibe_tag import VibeTag

logger = logging.getLogger("vibe.identifier")

CACHE_TTL_DAYS = 7
NUM_TAGS = 24

# Signature: (text, domain, page_title, tag_pool) -> raw JSON string
LlmCallable = Callable[[str, str, str | None, list], Awaitable[str]]


class LlmParseError(Exception):
    pass


class LlmTimeoutError(Exception):
    pass


PROMPT_TEMPLATE = """你是一个专业的内容识别官。用户在一个【{domain}】类型的页面划了一段文字给你。

【页面标题】：{page_title}
【用户划到的文字】：{text}

你的任务是**精确识别**用户划的内容是什么，然后输出结构化信息。

【识别规则——域优先】
用户在 {domain} 页面上 → 你的搜索必须**优先匹配 {domain} 类型的作品**。如果同一个名字有书也有电影，**优先识别为 {domain} 版本**。

【默认假设】
划的文字绝大概率是一个具体作品的标题。不是碎片，不是评论片段。你必须把自己调到"我一定认得出这是什么"的模式。

【预训练知识激活】
你的训练数据覆盖了大量华语电影、英美电影、主流游戏、知名书籍和专辑。先搜记忆库再输出。把 {text} 和 {page_title} 当作查询，从训练知识里捞出匹配的作品。

【item_profile 输出要求】
- item_name: 必填。中文名加书名号（如果是具体作品）；描述短语（如果是评论片段）
- item_name_alt: 英文/原名，不知道就 null
- year: 整数年份，不知道就 null
- creator: 导演/作者/开发商，不知道就 null
- genre: 简短类型标签，2-8 字
- plot_gist: 1-3 句真实内容描述，用预训练知识，不靠标题猜
- tone: 形容词链描述真实情感调性。如果标题容易误导，必须明说反差
- name_vs_reality: 标题有误导性就写清楚，没有就空字符串
- confidence: "high"（≥60% 确认）, "medium"（30-60%）, "low"（<30%，最佳猜测）

【标签提取】
从下面的标签池里选 1-5 个最匹配的标签，给 0-1 的权重。

【摘要】
一句话（不超过 30 字）客观描述内容核心 Vibe。

【禁止】
- 禁止输出"无法确定"、"识别不出"、"碎片"、"没头没尾"
- 禁止瞎编不存在的事实
- confidence 高时直接陈述，不用"看起来像"退缩语气

【标签池】：
{tag_pool_json}

【输出格式】严格 JSON，不要 markdown 代码块：
{{"item_profile": {{...}}, "tags": [{{"tag_id": 11, "weight": 0.9}}, ...], "summary": "..."}}

不要输出任何解释。"""


_ITEM_PROFILE_DEFAULTS = {
    "item_name_alt": None,
    "year": None,
    "creator": None,
    "genre": "未知类型",
    "plot_gist": "暂无内容描述",
    "tone": "未知",
    "name_vs_reality": "",
    "confidence": "low",
}


def hash_text(text: str, domain: str) -> str:
    norm = text.strip()
    return hashlib.sha256(f"{norm}|{domain}".encode("utf-8")).hexdigest()


def _load_tag_pool() -> list[dict]:
    db = database.SessionLocal()
    try:
        tags = db.scalars(select(VibeTag).order_by(VibeTag.id)).all()
        return [
            {"id": t.id, "name": t.name, "category": t.category, "description": t.description}
            for t in tags
        ]
    finally:
        db.close()


def _fill_profile_defaults(raw_profile: dict, text: str) -> dict:
    """Fill missing item_profile fields with sensible defaults."""
    profile = dict(_ITEM_PROFILE_DEFAULTS)  # start with defaults
    profile.update({k: v for k, v in raw_profile.items() if v is not None or k in ("year", "creator", "item_name_alt")})
    # item_name is required and must never be empty
    if not profile.get("item_name"):
        profile["item_name"] = text
    return profile


async def _default_llm_call(
    text: str,
    domain: str,
    page_title: str | None,
    tag_pool: list,
) -> str:
    """DeepSeek-compatible chat completion. Replaceable in tests."""
    prompt = PROMPT_TEMPLATE.format(
        domain=domain,
        page_title=page_title or "（无页面标题）",
        tag_pool_json=json.dumps(tag_pool, ensure_ascii=False),
        text=text,
    )
    url = f"{settings.llm_base_url}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.5,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    logger.info(
        "IDENTIFIER CALL | text=%r | domain=%s | page_title=%r",
        text[:80], domain, (page_title or "")[:80],
    )
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            logger.info("IDENTIFIER RAW RESPONSE: %s", content[:500])
            return content
    except httpx.TimeoutException as e:
        raise LlmTimeoutError(str(e)) from e


async def identify(
    text: str,
    domain: str,
    page_title: str | None = None,
    llm_call: LlmCallable | None = None,
) -> dict:
    """Returns {item_profile: dict, matched_tags: list, summary: str,
               text_hash: str, cache_hit: bool}."""
    llm_call = llm_call or _default_llm_call
    db = database.SessionLocal()
    try:
        text_hash = hash_text(text, domain)
        cutoff = datetime.utcnow() - timedelta(days=CACHE_TTL_DAYS)
        cached = db.scalar(
            select(AnalysisCache).where(
                AnalysisCache.text_hash == text_hash,
                AnalysisCache.created_at > cutoff,
            )
        )
        if cached is not None:
            parsed = json.loads(cached.tags_json)
            cached_item_profile = parsed.get("item_profile")
            # V1.4: old cache entries without item_profile → cache miss
            if cached_item_profile and isinstance(cached_item_profile, dict):
                cached.hit_count += 1
                db.commit()
                return {
                    "item_profile": cached_item_profile,
                    "matched_tags": _enrich_tags(db, parsed["tags"]),
                    "summary": cached.summary,
                    "text_hash": text_hash,
                    "cache_hit": True,
                }

        tag_pool = _load_tag_pool()
        raw = await llm_call(text, domain, page_title, tag_pool)
        try:
            parsed = json.loads(raw)
            raw_profile = parsed.get("item_profile", {})
            if not isinstance(raw_profile, dict):
                raw_profile = {}
            raw_tags = parsed["tags"]
            summary = parsed["summary"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise LlmParseError(f"invalid LLM response: {e}") from e

        item_profile = _fill_profile_defaults(raw_profile, text)

        valid = [
            {"tag_id": t["tag_id"], "weight": float(t["weight"])}
            for t in raw_tags
            if isinstance(t.get("tag_id"), int) and 1 <= t["tag_id"] <= NUM_TAGS
        ]
        if not valid:
            raise LlmParseError("all tag_ids out of range")

        # Drop any expired/old entry sharing this hash
        stale = db.scalar(
            select(AnalysisCache).where(AnalysisCache.text_hash == text_hash)
        )
        if stale is not None:
            db.delete(stale)
            db.flush()

        db.add(AnalysisCache(
            text_hash=text_hash,
            domain=domain,
            tags_json=json.dumps(
                {"tags": valid, "summary": summary, "item_profile": item_profile},
                ensure_ascii=False,
            ),
            summary=summary,
            hit_count=0,
        ))
        db.commit()

        return {
            "item_profile": item_profile,
            "matched_tags": _enrich_tags(db, valid),
            "summary": summary,
            "text_hash": text_hash,
            "cache_hit": False,
        }
    finally:
        db.close()


def _enrich_tags(db, tags: list[dict]) -> list[dict]:
    name_by_id = {t.id: t.name for t in db.scalars(select(VibeTag)).all()}
    return [
        {"tag_id": t["tag_id"], "name": name_by_id.get(t["tag_id"], "?"), "weight": t["weight"]}
        for t in tags
    ]
```

### Step 1.4: Run tests — all 10 should pass

- [ ] Run `cd D:/qhyProject/vibe4.0/backend && python -m pytest tests/test_llm_identifier.py -v`
- [ ] Verify: 10 passed, 0 failed

### Step 1.5: Commit

- [ ] `git add backend/app/services/llm_identifier.py backend/tests/test_llm_identifier.py`
- [ ] `git commit -m "feat(agent1): add llm_identifier service + 10 tests (3-Agent chain)"`

---

## Task 2: Create `llm_matcher.py` (Agent 2) + tests

**Files:**
- NEW `backend/app/services/llm_matcher.py`
- NEW `backend/tests/test_llm_matcher.py`

**Approach:** TDD

### Step 2.1: Write test file

- [ ] Create `backend/tests/test_llm_matcher.py`:

```python
import json

import pytest

from app.services import llm_matcher


class FakeLLM:
    """Matches llm_matcher._default_llm_call signature: (system_prompt, user_prompt) -> str."""

    def __init__(self, response=None, raise_exc=None):
        self.response = response
        self.raise_exc = raise_exc
        self.calls = 0
        self.last_system = None
        self.last_user = None

    async def __call__(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        self.last_system = system_prompt
        self.last_user = user_prompt
        if self.raise_exc:
            raise self.raise_exc
        return self.response


_SAMPLE_PROFILE = {
    "item_name": "《赛博朋克 2077》",
    "item_name_alt": "Cyberpunk 2077",
    "year": 2020,
    "creator": "CD Projekt Red",
    "genre": "开放世界 RPG",
    "plot_gist": "夜之城里一个雇佣兵对抗跨国公司。",
    "tone": "冷峻、反乌托邦",
    "name_vs_reality": "",
    "confidence": "high",
}


async def test_happy_path():
    """Agent 2 returns final_score, 3 reasons, and verdict."""
    fake = FakeLLM(response=json.dumps({
        "adjustment": 8,
        "reasons": [
            "赛博朋克的冷峻调性和你的科幻偏好高度吻合",
            "开放世界 RPG 节奏偏慢，你可能中途失去耐心",
            "整体而言这部作品的氛围非常适合你的审美",
        ],
        "verdict": "追",
    }))
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=60,
        user_personality_summary="这个朋友偏好机械科幻和冷光调",
        user_top_tag_descriptions=["喜欢赛博机械美学", "偏好黑暗压抑氛围"],
        llm_call=fake,
    )
    assert result["final_score"] == 68  # 60 + 8
    assert len(result["reasons"]) == 3
    assert result["verdict"] == "追"
    assert fake.calls == 1


async def test_score_clamping_adjustment_too_large():
    """Adjustment > +15 is clamped to +15."""
    fake = FakeLLM(response=json.dumps({
        "adjustment": 30,
        "reasons": ["a", "b", "c"],
        "verdict": "追",
    }))
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=90,
        user_personality_summary="x",
        user_top_tag_descriptions=[],
        llm_call=fake,
    )
    # adjustment clamped to +15, then final 90+15=105 clamped to 100
    assert result["final_score"] == 100


async def test_score_clamping_adjustment_too_negative():
    """Adjustment < -15 is clamped to -15."""
    fake = FakeLLM(response=json.dumps({
        "adjustment": -25,
        "reasons": ["a", "b", "c"],
        "verdict": "跳过",
    }))
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=10,
        user_personality_summary="x",
        user_top_tag_descriptions=[],
        llm_call=fake,
    )
    # adjustment clamped to -15, then 10-15=-5 clamped to 0
    assert result["final_score"] == 0


async def test_exactly_3_reasons_padded_if_fewer():
    """If LLM returns fewer than 3 reasons, pad to 3."""
    fake = FakeLLM(response=json.dumps({
        "adjustment": 0,
        "reasons": ["only one"],
        "verdict": "看心情",
    }))
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=50,
        user_personality_summary="x",
        user_top_tag_descriptions=[],
        llm_call=fake,
    )
    assert len(result["reasons"]) == 3


async def test_verdict_validation_defaults_to_kan_xinqing():
    """Unknown verdict value maps to '看心情'."""
    fake = FakeLLM(response=json.dumps({
        "adjustment": 5,
        "reasons": ["a", "b", "c"],
        "verdict": "随便看看",
    }))
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=50,
        user_personality_summary="x",
        user_top_tag_descriptions=[],
        llm_call=fake,
    )
    assert result["verdict"] == "看心情"


async def test_graceful_degradation_on_exception():
    """LLM exception → degraded result with base_score passthrough."""
    fake = FakeLLM(raise_exc=RuntimeError("timeout"))
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=65,
        user_personality_summary="x",
        user_top_tag_descriptions=[],
        llm_call=fake,
    )
    assert result["final_score"] == 65
    assert result["verdict"] == "看心情"
    assert "匹配分析暂时不可用" in result["reasons"]


async def test_graceful_degradation_on_json_parse_failure():
    """Invalid JSON → degraded result."""
    fake = FakeLLM(response="not json at all")
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=42,
        user_personality_summary="x",
        user_top_tag_descriptions=[],
        llm_call=fake,
    )
    assert result["final_score"] == 42
    assert result["verdict"] == "看心情"


async def test_base_score_passthrough_on_degradation():
    """Degraded result always uses base_score as final_score, unmodified."""
    fake = FakeLLM(raise_exc=Exception("any error"))
    for score in [0, 50, 100]:
        result = await llm_matcher.compute_match(
            item_profile=_SAMPLE_PROFILE,
            base_score=score,
            user_personality_summary="x",
            user_top_tag_descriptions=[],
            llm_call=fake,
        )
        assert result["final_score"] == score
```

### Step 2.2: Run tests — expect failures

- [ ] Run `cd D:/qhyProject/vibe4.0/backend && python -m pytest tests/test_llm_matcher.py -v` — all fail (module not found)

### Step 2.3: Implement `llm_matcher.py`

- [ ] Create `backend/app/services/llm_matcher.py`:

```python
import json
import logging
from typing import Awaitable, Callable

import httpx

from app.config import settings

logger = logging.getLogger("vibe.matcher")

LlmCallable = Callable[[str, str], Awaitable[str]]

VALID_VERDICTS = {"追", "看心情", "跳过"}

SYSTEM_PROMPT = """你是一个匹配分析官。你的工作是判断一个内容作品和用户之间的契合度。

你会收到：
1. item_profile：作品的结构化信息（名称、类型、剧情、调性等）
2. base_score：数学模型算出的底分（0-100）
3. 用户的性格摘要和品味偏好描述

你需要输出：
1. adjustment：在 [-15, +15] 范围内的分数调整值。正数表示你认为底分偏低了（这人会比数学算的更喜欢），负数表示底分偏高了。
2. reasons：恰好 3 条理由，每条 15-40 字：
   - 第 1 条：一个**匹配点**（这个作品哪里契合用户）
   - 第 2 条：一个**风险点**（哪里可能不合）
   - 第 3 条：一个**综合判断**（把前两点合起来给结论）
3. verdict：三选一："追" / "看心情" / "跳过"

【重要】
- 底分偏低不代表一定差（可能用户标签信号不足）
- 底分偏高也不代表完美（可能有性格层面的隐含冲突）
- 你的工作是用理解补数学的缺陷

【输出格式】严格 JSON，不要 markdown 代码块：
{"adjustment": 8, "reasons": ["匹配点...", "风险点...", "综合判断..."], "verdict": "追"}
"""

GENERIC_REASON = "综合来看，可以根据心情决定"


def _build_user_prompt(
    item_profile: dict,
    base_score: int,
    user_personality_summary: str,
    user_top_tag_descriptions: list[str],
) -> str:
    desc_text = "；".join(user_top_tag_descriptions) if user_top_tag_descriptions else "暂无品味标签"
    return (
        f"【作品信息】\n{json.dumps(item_profile, ensure_ascii=False, indent=2)}\n\n"
        f"【数学底分】{base_score}/100\n\n"
        f"【用户性格摘要】{user_personality_summary or '新朋友，还不太了解'}\n\n"
        f"【用户品味标签描述】{desc_text}\n\n"
        f"请输出你的 adjustment、reasons 和 verdict。"
    )


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _degraded_result(base_score: int) -> dict:
    return {
        "final_score": base_score,
        "reasons": ["匹配分析暂时不可用"],
        "verdict": "看心情",
    }


async def _default_llm_call(system_prompt: str, user_prompt: str) -> str:
    """DeepSeek-compatible chat completion. Replaceable in tests."""
    url = f"{settings.llm_base_url}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def compute_match(
    item_profile: dict,
    base_score: int,
    user_personality_summary: str,
    user_top_tag_descriptions: list[str],
    llm_call: LlmCallable | None = None,
) -> dict:
    """Returns {final_score: int, reasons: list[str], verdict: str}.

    final_score is base_score adjusted by +/-15, clamped to [0, 100].
    reasons is exactly 3 strings.
    verdict is one of "追", "看心情", "跳过".

    On any LLM failure, returns a degraded result:
    {final_score: base_score, reasons: ["匹配分析暂时不可用"], verdict: "看心情"}
    """
    llm_call = llm_call or _default_llm_call
    user_prompt = _build_user_prompt(
        item_profile, base_score,
        user_personality_summary, user_top_tag_descriptions,
    )
    logger.info(
        "MATCHER CALL | item=%s | base_score=%d",
        item_profile.get("item_name", "?")[:40], base_score,
    )

    try:
        raw = await llm_call(SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.warning("MATCHER FAILED: %s", e)
        return _degraded_result(base_score)

    try:
        parsed = json.loads(raw)
        adjustment = int(parsed.get("adjustment", 0))
        reasons = parsed.get("reasons", [])
        verdict = parsed.get("verdict", "看心情")
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning("MATCHER JSON PARSE FAIL: %s", e)
        return _degraded_result(base_score)

    # Clamp adjustment to [-15, +15]
    adjustment = _clamp(adjustment, -15, 15)
    final_score = _clamp(base_score + adjustment, 0, 100)

    # Ensure exactly 3 reasons
    if not isinstance(reasons, list):
        reasons = []
    reasons = [str(r) for r in reasons]
    while len(reasons) < 3:
        reasons.append(GENERIC_REASON)
    reasons = reasons[:3]

    # Validate verdict
    if verdict not in VALID_VERDICTS:
        verdict = "看心情"

    return {
        "final_score": final_score,
        "reasons": reasons,
        "verdict": verdict,
    }
```

### Step 2.4: Run tests — all 8 should pass

- [ ] Run `cd D:/qhyProject/vibe4.0/backend && python -m pytest tests/test_llm_matcher.py -v`
- [ ] Verify: 8 passed, 0 failed

### Step 2.5: Commit

- [ ] `git add backend/app/services/llm_matcher.py backend/tests/test_llm_matcher.py`
- [ ] `git commit -m "feat(agent2): add llm_matcher service + 8 tests (3-Agent chain)"`

---

## Task 3: Create `llm_advisor.py` (Agent 3) + tests

**Files:**
- NEW `backend/app/services/llm_advisor.py`
- NEW `backend/tests/test_llm_advisor.py`

**Approach:** TDD

### Step 3.1: Write test file

- [ ] Create `backend/tests/test_llm_advisor.py`:

```python
import json

import pytest

from app.services import llm_advisor


class FakeLLM:
    """Matches llm_advisor._default_llm_call signature: (system_prompt, user_prompt) -> str."""

    def __init__(self, response=None, raise_exc=None):
        self.response = response
        self.raise_exc = raise_exc
        self.calls = 0
        self.last_system = None
        self.last_user = None

    async def __call__(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        self.last_system = system_prompt
        self.last_user = user_prompt
        if self.raise_exc:
            raise self.raise_exc
        return self.response


_SAMPLE_PROFILE = {
    "item_name": "《赛博朋克 2077》",
    "item_name_alt": "Cyberpunk 2077",
    "year": 2020,
    "creator": "CD Projekt Red",
    "genre": "开放世界 RPG",
    "plot_gist": "夜之城里一个雇佣兵对抗跨国公司。",
    "tone": "冷峻、反乌托邦",
    "name_vs_reality": "",
    "confidence": "high",
}


async def test_happy_path():
    """Agent 3 returns a non-empty friend-voice recommendation."""
    fake = FakeLLM(response=json.dumps({
        "roast": "夜之城那套冷峻反乌托邦简直为你量身打造，找个周末一口气沉进去，追。68%",
    }))
    result = await llm_advisor.advise(
        text="赛博朋克 2077",
        domain="game",
        item_profile=_SAMPLE_PROFILE,
        final_score=68,
        reasons=["科幻偏好吻合", "节奏偏慢有风险", "整体适合你的审美"],
        verdict="追",
        user_personality_summary="偏好机械科幻和冷光调",
        llm_call=fake,
    )
    assert isinstance(result, str)
    assert len(result) > 0
    assert fake.calls == 1


async def test_prompt_contains_item_profile_facts():
    """The user prompt must include item_profile details for grounded output."""
    fake = FakeLLM(response=json.dumps({"roast": "test"}))
    await llm_advisor.advise(
        text="赛博朋克 2077",
        domain="game",
        item_profile=_SAMPLE_PROFILE,
        final_score=68,
        reasons=["r1", "r2", "r3"],
        verdict="追",
        user_personality_summary="x",
        llm_call=fake,
    )
    p = fake.last_user
    assert "赛博朋克 2077" in p or "《赛博朋克 2077》" in p
    assert "CD Projekt Red" in p
    assert "夜之城" in p


async def test_prompt_contains_reasons_and_verdict():
    """Reasons and verdict from Agent 2 must be in the prompt."""
    fake = FakeLLM(response=json.dumps({"roast": "test"}))
    await llm_advisor.advise(
        text="x",
        domain="game",
        item_profile=_SAMPLE_PROFILE,
        final_score=68,
        reasons=["科幻偏好吻合", "节奏偏慢有风险", "整体适合你的审美"],
        verdict="追",
        user_personality_summary="x",
        llm_call=fake,
    )
    p = fake.last_user
    assert "科幻偏好吻合" in p
    assert "节奏偏慢有风险" in p
    assert "追" in p


async def test_prompt_contains_user_personality():
    """User personality summary must appear in the prompt."""
    fake = FakeLLM(response=json.dumps({"roast": "test"}))
    await llm_advisor.advise(
        text="x",
        domain="game",
        item_profile=_SAMPLE_PROFILE,
        final_score=68,
        reasons=["r1", "r2", "r3"],
        verdict="追",
        user_personality_summary="这个人偏好深度思考和独处",
        llm_call=fake,
    )
    assert "深度思考" in fake.last_user


async def test_failure_returns_empty_string():
    """Any LLM exception → return ''."""
    fake = FakeLLM(raise_exc=RuntimeError("timeout"))
    result = await llm_advisor.advise(
        text="x",
        domain="game",
        item_profile=_SAMPLE_PROFILE,
        final_score=68,
        reasons=["r1", "r2", "r3"],
        verdict="追",
        user_personality_summary="x",
        llm_call=fake,
    )
    assert result == ""


async def test_missing_roast_field_returns_empty_string():
    """JSON without 'roast' key → return ''."""
    fake = FakeLLM(response=json.dumps({"other": "x"}))
    result = await llm_advisor.advise(
        text="x",
        domain="game",
        item_profile=_SAMPLE_PROFILE,
        final_score=68,
        reasons=["r1", "r2", "r3"],
        verdict="追",
        user_personality_summary="x",
        llm_call=fake,
    )
    assert result == ""
```

### Step 3.2: Run tests — expect failures

- [ ] Run `cd D:/qhyProject/vibe4.0/backend && python -m pytest tests/test_llm_advisor.py -v` — all fail

### Step 3.3: Implement `llm_advisor.py`

- [ ] Create `backend/app/services/llm_advisor.py`:

```python
import json
import logging
from typing import Awaitable, Callable

import httpx

from app.config import settings

logger = logging.getLogger("vibe.advisor")

LlmCallable = Callable[[str, str], Awaitable[str]]

SYSTEM_PROMPT = """你是用户最挑剔的那个朋友。你知道他的审美、他最近在看什么、他的偏执在哪。现在他在网上划了一段话给你看，问你：这东西值不值他花时间。

你要像深夜在微信上随手回他一样说话——口语、直接、带情绪、偶尔跑题，但每一句都言之有物。把他当人，不要当"用户"。

【你收到的信息】
1. **item_profile**：识别官已经用预训练知识精确识别了这个作品——名称、类型、剧情、调性全在里面。这是真相，直接用。
2. **匹配分析**：匹配官已经给出了 final_score、3 条理由（匹配点/风险点/综合判断）和 verdict（追/看心情/跳过）。这是你判断的逻辑骨架。
3. **原文**：用户亲手划出的那段文字。
4. **对他品味的印象**：自然语言描述。

【你的唯一任务】
把上面的结构化事实和推理，翻译成一段自然的朋友语气建议。你不需要自己判断——识别官和匹配官已经判断完了，你只负责"怎么说"。

【核心规则】
1. **item_profile 是真相**——引用里面的具体细节（导演、剧情、调性）
2. **reasons 是逻辑骨架**——你的建议要体现这 3 条理由，但用朋友的口吻重新表达
3. **verdict + final_score 是结尾**——结尾给出 verdict 和 final_score%
4. **引用原文里的具体词句**加你的反应
5. **朋友视角**：用"你"、"你这人"、"以你的脾气"，禁止出现"用户"二字
6. **字数 60~120 字**

【绝对禁止】
- 不准瞎猜："听着像..."——item_profile 就是答案
- 抽象标签词汇泄露（"治愈系"、"烧脑向"、"轻度思考"这类标签名）
- AI 腔调：总之、综上所述、值得一提、不难看出
- 叙述结构：禁止"首先...其次...最后..."

【输出格式】
严格 JSON，不要 markdown 代码块：
{"roast": "你的点评"}
"""

_DOMAIN_LABEL = {
    "book": "书",
    "movie": "电影",
    "game": "游戏",
    "music": "音乐",
}


def _build_user_prompt(
    text: str,
    domain: str,
    item_profile: dict,
    final_score: int,
    reasons: list[str],
    verdict: str,
    user_personality_summary: str,
) -> str:
    domain_label = _DOMAIN_LABEL.get(domain, domain)
    taste_line = user_personality_summary.strip() if user_personality_summary.strip() else "新朋友，还不太了解他的品味"
    profile_json = json.dumps(item_profile, ensure_ascii=False, indent=2)
    reasons_text = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(reasons))
    return (
        f"【item_profile——作品真实信息】\n{profile_json}\n\n"
        f"【匹配分析结果】\n"
        f"  final_score: {final_score}/100\n"
        f"  verdict: {verdict}\n"
        f"  reasons:\n{reasons_text}\n\n"
        f"【他划到的原文】：{text}\n\n"
        f"【这是什么类型】：{domain_label}\n"
        f"【你对他品味的印象】：{taste_line}\n\n"
        f"基于以上所有信息，用朋友语气给他建议。结尾带上 verdict 和 final_score%。"
    )


async def _default_llm_call(system_prompt: str, user_prompt: str) -> str:
    """DeepSeek-compatible chat completion. Replaceable in tests."""
    url = f"{settings.llm_base_url}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.9,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def advise(
    text: str,
    domain: str,
    item_profile: dict,
    final_score: int,
    reasons: list[str],
    verdict: str,
    user_personality_summary: str,
    llm_call: LlmCallable | None = None,
) -> str:
    """Returns a 60-120 char friend-voice recommendation.

    On any failure, returns "".
    """
    llm_call = llm_call or _default_llm_call
    user_prompt = _build_user_prompt(
        text, domain, item_profile, final_score,
        reasons, verdict, user_personality_summary,
    )
    logger.info(
        "ADVISOR CALL | text=%r | final_score=%d | verdict=%s",
        text[:60], final_score, verdict,
    )

    try:
        raw = await llm_call(SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.warning("ADVISOR FAILED: %s", e)
        return ""

    try:
        parsed = json.loads(raw)
        roast = parsed.get("roast", "")
        if not isinstance(roast, str):
            return ""
        logger.info("ADVISOR OUTPUT: %s", roast[:200])
        return roast
    except json.JSONDecodeError:
        logger.warning("ADVISOR JSON PARSE FAIL: %s", raw[:200])
        return ""
```

### Step 3.4: Run tests — all 6 should pass

- [ ] Run `cd D:/qhyProject/vibe4.0/backend && python -m pytest tests/test_llm_advisor.py -v`
- [ ] Verify: 6 passed, 0 failed

### Step 3.5: Commit

- [ ] `git add backend/app/services/llm_advisor.py backend/tests/test_llm_advisor.py`
- [ ] `git commit -m "feat(agent3): add llm_advisor service + 6 tests (3-Agent chain)"`

---

## Task 4: Extend schemas + rewrite analyze route

**Files:**
- MODIFY `backend/app/schemas/analyze.py`
- MODIFY `backend/app/routers/vibe.py`

**Note:** After this task, tests that import `llm_tagger`/`llm_roaster` from `test_vibe.py` will break. This is expected and fixed in Task 5.

### Step 4.1: Add verdict + reasons to AnalyzeResponse

- [ ] Edit `backend/app/schemas/analyze.py` — add two fields to `AnalyzeResponse`:

```python
class AnalyzeResponse(BaseModel):
    match_score: int          # NOW: Agent 2's final_score (was: cosine raw)
    verdict: str = ""         # NEW: "追" | "看心情" | "跳过"
    reasons: list[str] = []   # NEW: 3 match/risk/summary reasons
    summary: str
    roast: str = ""
    matched_tags: list[MatchedTag]
    text_hash: str
    cache_hit: bool
    interaction_count: int
    level: int
    level_title: str
    level_emoji: str
    next_level_at: int
    level_up: bool
    ui_stage: str
```

### Step 4.2: Rewrite analyze route in vibe.py

- [ ] Edit `backend/app/routers/vibe.py`:
  - Change import line from `from app.services import llm_recommender, llm_roaster, llm_tagger, profile_calc` to `from app.services import llm_advisor, llm_identifier, llm_matcher, llm_recommender, profile_calc`
  - Rewrite the `analyze` function body:

```python
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    # Step 1: Agent 1 — Identify (cached)
    page_title = payload.context.page_title if payload.context else None
    try:
        identification = await llm_identifier.identify(
            payload.text, payload.domain, page_title=page_title
        )
    except llm_identifier.LlmParseError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_PARSE_FAIL", "message": str(e)}},
        )
    except llm_identifier.LlmTimeoutError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_TIMEOUT", "message": str(e)}},
        )

    item_profile = identification["item_profile"]
    matched_tags = identification["matched_tags"]

    matched_tag_ids = [t["tag_id"] for t in matched_tags]
    item_tags = [(t["tag_id"], t["weight"]) for t in matched_tags]

    # Step 2: Detect first-interaction BEFORE incrementing the counter
    user = db.scalar(select(User).where(User.id == user_id))
    is_first = (user is None) or (user.interaction_count == 0)

    # Step 3: Cosine base score
    base_score = profile_calc.compute_match_score(user_id=user_id, item_tags=item_tags)

    # Step 4: User context — prefer MBTI-derived personality summary if present
    user_personality = db.scalar(
        select(UserPersonality).where(UserPersonality.user_id == user_id)
    )
    if user_personality and user_personality.summary:
        user_hint = user_personality.summary
    else:
        user_taste_descriptions = profile_calc.get_top_core_tag_descriptions(
            user_id=user_id, n=2
        )
        user_hint = "；".join(user_taste_descriptions)

    # Step 5: Agent 2 — Match (uncached, graceful degradation)
    match_result = await llm_matcher.compute_match(
        item_profile=item_profile,
        base_score=base_score,
        user_personality_summary=user_hint,
        user_top_tag_descriptions=profile_calc.get_top_core_tag_descriptions(
            user_id=user_id, n=2
        ),
    )

    # Step 6: Agent 3 — Advise (uncached)
    roast = await llm_advisor.advise(
        text=payload.text,
        domain=payload.domain,
        item_profile=item_profile,
        final_score=match_result["final_score"],
        reasons=match_result["reasons"],
        verdict=match_result["verdict"],
        user_personality_summary=user_hint,
    )

    # Step 7: Apply profile update (unchanged from V1.2/V1.3)
    if is_first:
        profile_calc.apply_core_delta(
            user_id=user_id,
            tag_ids=matched_tag_ids,
            delta=FIRST_IMPRESSION_DELTA,
            action="first_impression",
        )
    else:
        curiosity_delta = profile_calc.dynamic_curiosity_delta(payload.hesitation_ms)
        profile_calc.apply_curiosity_delta(
            user_id=user_id,
            tag_ids=matched_tag_ids,
            delta=curiosity_delta,
            action="analyze",
        )

    # Step 8: Increment interaction counter AFTER profile update
    new_count, new_level, level_up = profile_calc.increment_interaction(user_id)
    info = profile_calc.level_info(new_count)
    ui_stage = profile_calc.compute_ui_stage(new_level)

    return AnalyzeResponse(
        match_score=match_result["final_score"],
        verdict=match_result["verdict"],
        reasons=match_result["reasons"],
        summary=identification["summary"],
        roast=roast,
        matched_tags=[MatchedTag(**t) for t in matched_tags],
        text_hash=identification["text_hash"],
        cache_hit=identification["cache_hit"],
        interaction_count=new_count,
        level=new_level,
        level_title=info["title"],
        level_emoji=info["emoji"],
        next_level_at=info["next_level_at"],
        level_up=level_up,
        ui_stage=ui_stage,
    )
```

### Step 4.3: Verify new agents' tests still pass

- [ ] Run `cd D:/qhyProject/vibe4.0/backend && python -m pytest tests/test_llm_identifier.py tests/test_llm_matcher.py tests/test_llm_advisor.py -v`
- [ ] Confirm all 24 new tests pass

### Step 4.4: Confirm test_vibe.py is broken (expected)

- [ ] Run `cd D:/qhyProject/vibe4.0/backend && python -m pytest tests/test_vibe.py -v` — expect import errors for `llm_tagger`/`llm_roaster`
- [ ] This is expected. Task 5 fixes it.

### Step 4.5: Commit

- [ ] `git add backend/app/schemas/analyze.py backend/app/routers/vibe.py`
- [ ] `git commit -m "feat(pipeline): rewrite analyze route to 3-Agent chain + add verdict/reasons to schema"`

---

## Task 5: Delete old services + fix test_vibe.py

**Files:**
- DELETE `backend/app/services/llm_tagger.py`
- DELETE `backend/app/services/llm_roaster.py`
- DELETE `backend/tests/test_llm_tagger.py`
- DELETE `backend/tests/test_llm_roaster.py`
- MODIFY `backend/tests/test_vibe.py`

### Step 5.1: Delete old files

- [ ] `rm backend/app/services/llm_tagger.py`
- [ ] `rm backend/app/services/llm_roaster.py`
- [ ] `rm backend/tests/test_llm_tagger.py`
- [ ] `rm backend/tests/test_llm_roaster.py`

### Step 5.2: Rewrite test_vibe.py helpers

- [ ] Replace `_install_fake_llm` with a new helper that patches `llm_identifier._default_llm_call`:

```python
def _install_fake_llm(monkeypatch, response):
    """Patch Agent 1 (identifier) with a fake LLM.

    Accepts either:
    - A raw string (treated as LLM JSON output)
    - A dict-like JSON string containing the V1.3 format {tags, summary}
      which gets auto-wrapped into V1.4 format {item_profile, tags, summary}
    """
    async def fake(text, domain, page_title, tag_pool):
        # Auto-wrap V1.3-style responses for backward compatibility
        try:
            parsed = json.loads(response)
            if "item_profile" not in parsed and "tags" in parsed:
                wrapped = {
                    "item_profile": {
                        "item_name": text,
                        "item_name_alt": None,
                        "year": None,
                        "creator": None,
                        "genre": domain,
                        "plot_gist": parsed.get("summary", ""),
                        "tone": "未知",
                        "name_vs_reality": "",
                        "confidence": "medium",
                    },
                    "tags": parsed["tags"],
                    "summary": parsed.get("summary", ""),
                }
                return json.dumps(wrapped, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass
        return response
    from app.services import llm_identifier
    monkeypatch.setattr(llm_identifier, "_default_llm_call", fake)
```

- [ ] Replace `_install_fake_roaster` with two new helpers:

```python
def _install_fake_matcher(monkeypatch, adjustment=0, reasons=None, verdict="看心情"):
    """Patch Agent 2 (matcher) with a fake LLM."""
    async def fake(system_prompt, user_prompt):
        return json.dumps({
            "adjustment": adjustment,
            "reasons": reasons or ["匹配点", "风险点", "综合判断"],
            "verdict": verdict,
        })
    from app.services import llm_matcher
    monkeypatch.setattr(llm_matcher, "_default_llm_call", fake)


def _install_fake_advisor(monkeypatch, roast_text="test roast"):
    """Patch Agent 3 (advisor) with a fake LLM."""
    async def fake(system_prompt, user_prompt):
        return json.dumps({"roast": roast_text})
    from app.services import llm_advisor
    monkeypatch.setattr(llm_advisor, "_default_llm_call", fake)
```

### Step 5.3: Update ALL existing analyze tests

Every test that previously called `_install_fake_roaster` must now call `_install_fake_matcher` AND `_install_fake_advisor`. Here is the complete list of tests to update:

- [ ] `test_analyze_returns_match_score_and_updates_curiosity` — replace `_install_fake_roaster(monkeypatch, "慢炖神作...")` with `_install_fake_matcher(monkeypatch)` + `_install_fake_advisor(monkeypatch, "慢炖神作，你会睡着但心满意足")`. Update assertion: `body["roast"]` check stays the same.

- [ ] `test_analyze_second_call_hits_cache` — replace roaster install with matcher+advisor install.

- [ ] `test_analyze_llm_parse_failure_returns_503` — replace roaster install with matcher+advisor install (these won't be called anyway since identifier fails first).

- [ ] `test_analyze_roaster_failure_returns_empty_roast` — rename conceptually to test advisor failure. Patch the advisor's `_default_llm_call` to raise, install fake matcher normally:

```python
def test_analyze_advisor_failure_returns_empty_roast(monkeypatch):
    """If the advisor (Agent 3) fails, analyze still returns 200 with roast=''."""
    _prime_profile()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_matcher(monkeypatch)

    async def broken_advisor(system_prompt, user_prompt):
        raise RuntimeError("boom")
    from app.services import llm_advisor
    monkeypatch.setattr(llm_advisor, "_default_llm_call", broken_advisor)

    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "A gentle slow piece", "domain": "book"})
    assert r.status_code == 200
    body = r.json()
    assert body["roast"] == ""
    assert body["match_score"] >= 0
```

- [ ] `test_analyze_first_interaction_applies_first_impression_delta` — replace `_install_fake_roaster` with `_install_fake_matcher` + `_install_fake_advisor`.

- [ ] `test_analyze_second_interaction_uses_curiosity` — same replacement.

- [ ] `test_analyze_impulsive_hesitation_gives_small_curiosity` — same replacement.

- [ ] `test_analyze_deliberate_hesitation_gives_bigger_curiosity` — same replacement.

- [ ] `test_analyze_crosses_level_up_at_count_4` — same replacement.

- [ ] `test_action_star_read_ms_scales_core_delta` — same replacement (for the initial analyze call).

- [ ] `test_action_response_carries_level_fields` — same replacement.

- [ ] `test_analyze_uses_personality_summary_as_taste_hint` — this test captures the roaster prompt to check for "深度思考者". Rewrite to capture the **advisor** prompt:

```python
def test_analyze_uses_personality_summary_as_taste_hint(monkeypatch):
    """When user has a personality summary, advisor gets it as taste_hint."""
    seed_all()

    db = database.SessionLocal()
    db.add(User(id=1, username="default", interaction_count=0))
    db.commit()
    db.add(UserPersonality(
        user_id=1,
        mbti="INTP",
        constellation="双鱼座",
        summary="这个朋友是典型的深度思考者，逻辑敏锐但情感其实柔软。",
    ))
    db.commit()
    db.close()

    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_matcher(monkeypatch)

    captured_hint = {}

    async def capture_advisor(system_prompt, user_prompt):
        captured_hint["prompt"] = user_prompt
        return json.dumps({"roast": "test roast"})

    from app.services import llm_advisor
    monkeypatch.setattr(llm_advisor, "_default_llm_call", capture_advisor)

    client.post("/api/v1/vibe/analyze",
                json={"text": "some text", "domain": "book"})

    assert "深度思考者" in captured_hint["prompt"]
```

- [ ] `test_analyze_falls_back_to_tag_descriptions_without_personality` — same pattern, capture advisor prompt, check for "节奏极慢":

```python
def test_analyze_falls_back_to_tag_descriptions_without_personality(monkeypatch):
    """When user has no personality row, advisor uses V1.2 tag description fallback."""
    seed_all()
    db = database.SessionLocal()
    db.add(User(id=1, username="default", interaction_count=1))
    db.commit()
    db.add(UserVibeRelation(
        user_id=1, vibe_tag_id=1,
        curiosity_weight=0.0, core_weight=20.0,
    ))
    db.commit()
    db.close()

    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 2, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_matcher(monkeypatch)

    captured_hint = {}

    async def capture_advisor(system_prompt, user_prompt):
        captured_hint["prompt"] = user_prompt
        return json.dumps({"roast": "test roast"})

    from app.services import llm_advisor
    monkeypatch.setattr(llm_advisor, "_default_llm_call", capture_advisor)

    client.post("/api/v1/vibe/analyze",
                json={"text": "some text", "domain": "book"})

    assert "节奏极慢" in captured_hint["prompt"]
    assert "深度思考者" not in captured_hint["prompt"]
```

- [ ] `test_personality_seeds_drive_initial_match_score` — replace `_install_fake_roaster` with `_install_fake_matcher` + `_install_fake_advisor`.

### Step 5.4: Add 3 new integration tests

- [ ] Add these tests to `test_vibe.py`:

```python
def test_analyze_response_includes_verdict_and_reasons(monkeypatch):
    """V1.4: analyze response carries verdict and reasons from Agent 2."""
    _prime_profile()
    db = database.SessionLocal()
    user = db.scalar(select(User).where(User.id == 1))
    user.interaction_count = 1
    db.commit()
    db.close()

    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_matcher(monkeypatch, adjustment=5, reasons=["a", "b", "c"], verdict="追")
    _install_fake_advisor(monkeypatch, "friend voice")

    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "test verdict", "domain": "book"})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "追"
    assert len(body["reasons"]) == 3
    assert body["roast"] == "friend voice"


def test_analyze_matcher_failure_degrades_gracefully(monkeypatch):
    """V1.4: if Agent 2 fails, analyze still returns 200 with cosine base_score."""
    _prime_profile()
    db = database.SessionLocal()
    user = db.scalar(select(User).where(User.id == 1))
    user.interaction_count = 1
    db.commit()
    db.close()

    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))

    async def broken_matcher(system_prompt, user_prompt):
        raise RuntimeError("timeout")
    from app.services import llm_matcher
    monkeypatch.setattr(llm_matcher, "_default_llm_call", broken_matcher)

    _install_fake_advisor(monkeypatch, "still works")

    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "matcher fails", "domain": "book"})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "看心情"
    assert "匹配分析暂时不可用" in body["reasons"]


def test_analyze_3agent_chain_end_to_end(monkeypatch):
    """V1.4: full 3-Agent pipeline from identifier through matcher to advisor."""
    _prime_profile()
    db = database.SessionLocal()
    user = db.scalar(select(User).where(User.id == 1))
    user.interaction_count = 1
    db.commit()
    db.close()

    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}, {"tag_id": 5, "weight": 0.7}],
        "summary": "慢节奏但治愈"
    }))
    _install_fake_matcher(monkeypatch, adjustment=10, reasons=["匹配", "风险", "综合"], verdict="追")
    _install_fake_advisor(monkeypatch, "完整的三步链输出")

    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "三步链测试", "domain": "book"})
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == "慢节奏但治愈"
    assert body["roast"] == "完整的三步链输出"
    assert body["verdict"] == "追"
    assert len(body["reasons"]) == 3
    assert len(body["matched_tags"]) == 2
    assert body["cache_hit"] is False
```

### Step 5.5: Run full test suite

- [ ] Run `cd D:/qhyProject/vibe4.0/backend && python -m pytest -v`
- [ ] Expected: ~95 tests pass (old ~20 tagger/roaster tests deleted, ~24 new agent tests + 3 integration tests added)

### Step 5.6: Commit

- [ ] `git add -A`  (covers deletions + modified test_vibe.py)
- [ ] `git commit -m "refactor(pipeline): delete llm_tagger/llm_roaster, update test_vibe for 3-Agent chain"`

---

## Task 6: Frontend shared types + background

**Files:**
- MODIFY `extension/src/shared/types.ts`

### Step 6.1: Add verdict + reasons to AnalyzeResult

- [ ] Edit `extension/src/shared/types.ts` — add two fields to the `AnalyzeResult` interface:

```typescript
export interface AnalyzeResult {
  match_score: number;
  verdict: string;           // NEW: "追" | "看心情" | "跳过"
  reasons: string[];         // NEW: 3 match/risk/summary reasons
  summary: string;
  roast: string;
  matched_tags: MatchedTag[];
  text_hash: string;
  cache_hit: boolean;
  interaction_count: number;
  level: number;
  level_title: string;
  level_emoji: string;
  next_level_at: number;
  level_up: boolean;
  ui_stage: "welcome" | "learning" | "early" | "stable";
}
```

### Step 6.2: Build to verify

- [ ] Run `cd D:/qhyProject/vibe4.0/extension && npm run build`
- [ ] Verify no TypeScript errors

### Step 6.3: Commit

- [ ] `git add extension/src/shared/types.ts`
- [ ] `git commit -m "feat(types): add verdict and reasons to AnalyzeResult"`

---

## Task 7: VibeCard verdict badge + remove summary

**Files:**
- MODIFY `extension/src/content/ui/VibeCard.ts`
- MODIFY `extension/src/content/ui/styles.css`

### Step 7.1: Add verdict badge to VibeCard

- [ ] Edit `extension/src/content/ui/VibeCard.ts` — after the roast section and before the actions section, add a verdict badge:

Replace the summary grey text section (lines 69-87) with:

```typescript
  // Roast is the primary copy; if empty, fall back to showing summary as primary
  const hasRoast = typeof result.roast === "string" && result.roast.trim() !== "";

  if (hasRoast) {
    const roast = document.createElement("div");
    roast.className = "vr-roast";
    roast.textContent = result.roast;
    card.appendChild(roast);
  } else {
    // Fall back: promote summary to primary styling
    const roastFallback = document.createElement("div");
    roastFallback.className = "vr-roast";
    roastFallback.textContent = result.summary || "";
    card.appendChild(roastFallback);
  }

  // V1.4: Verdict badge
  if (result.verdict && result.verdict.trim() !== "") {
    const verdictBadge = document.createElement("div");
    const v = result.verdict.trim();
    const colorClass =
      v === "追" ? "vr-verdict-green" :
      v === "跳过" ? "vr-verdict-red" :
      "vr-verdict-yellow";
    verdictBadge.className = `vr-verdict-badge ${colorClass}`;
    verdictBadge.textContent = v;
    card.appendChild(verdictBadge);
  }
```

Note: The old code that rendered `result.summary` as grey italic text below roast (the `vr-summary` div) is **removed**. The summary is only used as a fallback when roast is empty.

### Step 7.2: Add verdict badge CSS

- [ ] Edit `extension/src/content/ui/styles.css` — add after the `.vr-summary` block (which can stay as dead CSS or be removed):

```css
/* V1.4 verdict badge */
.vr-verdict-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  margin: 4px 0 8px;
  letter-spacing: 1px;
}
.vr-verdict-green {
  background: #e6f9e6;
  color: #2d8c2d;
}
.vr-verdict-yellow {
  background: #fff8e1;
  color: #b8860b;
}
.vr-verdict-red {
  background: #ffe0e0;
  color: #d63031;
}
```

### Step 7.3: Build to verify

- [ ] Run `cd D:/qhyProject/vibe4.0/extension && npm run build`
- [ ] Verify no errors

### Step 7.4: Commit

- [ ] `git add extension/src/content/ui/VibeCard.ts extension/src/content/ui/styles.css`
- [ ] `git commit -m "feat(vibecard): add verdict color badge, remove summary grey text"`

---

## Task 8: SMOKE.md + final verify

**Files:**
- MODIFY `extension/SMOKE.md`

### Step 8.1: Update SMOKE.md

- [ ] Edit `extension/SMOKE.md`:
  - Update the header to "# V1.4 Manual Smoke Test"
  - Add new steps after step 18 (or renumber):

```markdown
### 19. Verdict badge on VibeCard (V1.4)
- Highlight text on a supported site → click purple icon
- Expected: the vibe card shows a colored verdict badge:
  - "追" in green if the match is good
  - "看心情" in yellow/amber if uncertain
  - "跳过" in red if poor match
- The old grey italic summary line below the roast is gone

### 20. Three-reason display in API response (V1.4)
- In the browser DevTools Network tab, inspect the POST /api/v1/vibe/analyze response
- Expected: JSON includes `verdict` (string) and `reasons` (array of 3 strings)
- The `match_score` may differ from the pure cosine score (Agent 2 adjusted it by up to ±15)

### 21. Agent 2 graceful degradation (V1.4)
- Temporarily break the LLM API (e.g., set an invalid API key)
- Highlight text → click icon
- Expected: Agent 1 will fail → 503 error card
- Restore the API key. Now highlight text again → should work normally
- Note: Agent 2 failure is invisible — it degrades to cosine base_score silently. To test Agent 2 specifically, check backend logs for "MATCHER FAILED" lines.

### 22. Roast references item details (V1.4)
- Highlight a well-known movie/book title (e.g., "三体", "赛博朋克 2077")
- Expected: the roast text references specific details (director/author, plot elements, tone) — not just the title
- This is because Agent 3 (advisor) now receives structured item_profile from Agent 1

## Pass criteria
All 22 steps complete without any JavaScript console errors in either the background worker or the content script.
```

### Step 8.2: Final full pytest

- [ ] Run `cd D:/qhyProject/vibe4.0/backend && python -m pytest -v`
- [ ] Expected: ~95 tests pass, 0 failures

### Step 8.3: Final extension build

- [ ] Run `cd D:/qhyProject/vibe4.0/extension && npm run build`
- [ ] Expected: clean build, no errors

### Step 8.4: Commit

- [ ] `git add extension/SMOKE.md`
- [ ] `git commit -m "docs: update SMOKE.md with V1.4 3-Agent chain smoke steps"`

---

## Summary

| Task | Files | New Tests | Commit Message |
|---|---|---|---|
| T1 | `llm_identifier.py` + tests | 10 | `feat(agent1): add llm_identifier service + 10 tests` |
| T2 | `llm_matcher.py` + tests | 8 | `feat(agent2): add llm_matcher service + 8 tests` |
| T3 | `llm_advisor.py` + tests | 6 | `feat(agent3): add llm_advisor service + 6 tests` |
| T4 | `schemas/analyze.py` + `routers/vibe.py` | 0 | `feat(pipeline): rewrite analyze route to 3-Agent chain` |
| T5 | Delete old + fix `test_vibe.py` | 3 | `refactor(pipeline): delete llm_tagger/llm_roaster, update tests` |
| T6 | `types.ts` | 0 | `feat(types): add verdict and reasons to AnalyzeResult` |
| T7 | `VibeCard.ts` + `styles.css` | 0 | `feat(vibecard): add verdict color badge` |
| T8 | `SMOKE.md` | 0 | `docs: update SMOKE.md with V1.4 smoke steps` |

**Total new tests:** ~27 (10 + 8 + 6 + 3 integration)
**Total deleted tests:** ~19 (10 tagger + 9 roaster)
**Expected final test count:** ~95 (93 - 19 + 24 unit + 3 integration = ~101, but some existing tests are restructured)

**Lines estimate:** ~800 new, ~400 deleted, ~200 modified
