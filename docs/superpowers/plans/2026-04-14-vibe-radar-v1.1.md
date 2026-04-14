# Vibe-Radar V1.1 Implementation Plan — Roast + Cross-Media Pivot + Share Poster

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend V1.0 with three user-facing improvements: (1) a "毒舌鉴定官" roast generator that replaces the flat objective `summary` as the card's hero copy, (2) a lazy-triggered cross-domain recommendation endpoint backed by an LLM "代餐官" that returns 3 items from 3 non-source domains, and (3) a 1080×1080 Canvas 2D poster generator with copy-to-clipboard and download-as-PNG paths.

**Architecture:** Backend adds two new LLM services (`llm_roaster`, `llm_recommender`) sitting alongside the existing `llm_tagger`. `analyze` route composes `llm_tagger` (cached) + `llm_roaster` (uncached per-user) and returns both `summary` and a new `roast` field. A new `/vibe/recommend` route takes the frontend's already-known data (original text + matched_tag_ids + source_domain) and calls `llm_recommender`, applying server-side cross-domain filtering. Frontend extends `VibeCard` to promote `roast` as primary copy (fallback to `summary` on empty), adds a share icon that generates a Canvas 2D poster, and adds a "> 寻找同频代餐" link that lazy-loads a `RecommendCard` sub-view.

**Tech Stack:** Same as V1.0 — Python 3.10+ / FastAPI / SQLAlchemy / pytest / httpx / TypeScript / esbuild / Chrome MV3. No new deps. Canvas 2D is native browser API; no html2canvas needed.

**Spec:** `docs/superpowers/specs/2026-04-14-vibe-radar-v1.1-design.md`

**Prereqs:**
- V1.0 is complete and working (backend 27/27 tests green, extension builds clean)
- `backend/.venv` is set up with existing deps
- `extension/node_modules` is installed
- Current HEAD is commit `55aedaa` (the V1.1 spec commit)

**Conventions (inherited from V1.0, reiterated here):**
- Commit after every passing test group, Conventional Commits
- TDD strict for backend (failing test → implement → passing test → commit)
- Extension: no automated tests, rely on `npm run build` + SMOKE.md manual check
- **Attribute-access database convention**: all services/tests use `from app import database; database.SessionLocal()`, never `from app.database import SessionLocal`
- pytest runs from `backend/` directory with venv activated: `cd backend && source .venv/Scripts/activate && pytest tests/`

**File structure map (cumulative — bold = new in V1.1):**

```
backend/app/
├── services/
│   ├── llm_tagger.py            (V1.0)
│   ├── **llm_roaster.py**       (V1.1 Task 1)
│   ├── **llm_recommender.py**   (V1.1 Task 3)
│   ├── profile_calc.py          (V1.0 — extended in Task 2)
│   └── seed.py                  (V1.0)
├── schemas/
│   ├── analyze.py               (V1.0 — extended in Task 2)
│   ├── **recommend.py**         (V1.1 Task 4)
│   ├── action.py                (V1.0)
│   ├── cold_start.py            (V1.0)
│   └── profile.py               (V1.0)
├── routers/
│   └── vibe.py                  (V1.0 — extended in Task 2 AND Task 4)
└── ...

backend/tests/
├── test_llm_tagger.py           (V1.0)
├── **test_llm_roaster.py**      (V1.1 Task 1)
├── **test_llm_recommender.py**  (V1.1 Task 3)
├── test_profile_calc.py         (V1.0 — extended in Task 2)
├── test_vibe.py                 (V1.0 — extended in Task 2 AND Task 4)
└── ...

extension/src/
├── shared/
│   └── types.ts                 (V1.0 — extended in Task 5)
├── background/
│   └── index.ts                 (V1.0 — extended in Task 5)
└── content/
    └── ui/
        ├── VibeCard.ts          (V1.0 — extended in Tasks 6, 7, 8)
        ├── **SharePoster.ts**   (V1.1 Task 7)
        ├── **RecommendCard.ts** (V1.1 Task 8)
        └── styles.css           (V1.0 — extended in Tasks 6, 7, 8)

extension/SMOKE.md               (V1.0 — extended in Task 9)
```

---

## Task 1: `llm_roaster` service with FakeLLM tests

**Files:**
- Create: `backend/app/services/llm_roaster.py`
- Create: `backend/tests/test_llm_roaster.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_llm_roaster.py`:

```python
import json

import pytest

from app.services import llm_roaster


class FakeLLM:
    def __init__(self, response=None, raise_exc=None):
        self.response = response
        self.raise_exc = raise_exc
        self.calls = 0
        self.last_prompt = None

    async def __call__(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        self.last_prompt = user_prompt
        if self.raise_exc:
            raise self.raise_exc
        return self.response


async def test_generate_roast_happy_path():
    fake = FakeLLM(response=json.dumps({"roast": "快逃！你会在影院睡着。"}))
    result = await llm_roaster.generate_roast(
        text="一部极慢的心理惊悚片",
        domain="movie",
        item_tag_names=["黑暗压抑", "慢炖沉浸"],
        user_top_tag_names=["日常烟火", "治愈温暖", "轻度思考"],
        llm_call=fake,
    )
    assert result == "快逃！你会在影院睡着。"
    assert fake.calls == 1


async def test_user_prompt_contains_all_context():
    fake = FakeLLM(response=json.dumps({"roast": "x"}))
    await llm_roaster.generate_roast(
        text="《闪灵》",
        domain="movie",
        item_tag_names=["黑暗压抑"],
        user_top_tag_names=["日常烟火"],
        llm_call=fake,
    )
    p = fake.last_prompt
    assert "movie" in p
    assert "《闪灵》" in p
    assert "黑暗压抑" in p
    assert "日常烟火" in p


async def test_parse_failure_returns_empty_string():
    fake = FakeLLM(response="not json")
    result = await llm_roaster.generate_roast(
        text="x", domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert result == ""


async def test_llm_exception_returns_empty_string():
    fake = FakeLLM(raise_exc=RuntimeError("timeout"))
    result = await llm_roaster.generate_roast(
        text="x", domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert result == ""


async def test_missing_roast_field_returns_empty_string():
    fake = FakeLLM(response=json.dumps({"other": "x"}))
    result = await llm_roaster.generate_roast(
        text="x", domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert result == ""


async def test_empty_user_tags_still_works():
    """Cold-start users have no core_weight yet — roaster should still produce output."""
    fake = FakeLLM(response=json.dumps({"roast": "你是一张白纸"}))
    result = await llm_roaster.generate_roast(
        text="x", domain="book",
        item_tag_names=["治愈温暖"], user_top_tag_names=[],
        llm_call=fake,
    )
    assert result == "你是一张白纸"
    # verify "无" or similar placeholder used in prompt when user has no tags
    assert fake.last_prompt is not None
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd D:/qhyProject/vibe4.0/backend && source .venv/Scripts/activate && pytest tests/test_llm_roaster.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.llm_roaster'`

- [ ] **Step 3: Create `backend/app/services/llm_roaster.py`**

```python
import json
from typing import Awaitable, Callable

import httpx

from app.config import settings

LlmCallable = Callable[[str, str], Awaitable[str]]

SYSTEM_PROMPT = """你是 Vibe-Radar 的"赛博毒舌鉴定官"。你看到一个物品和用户的喜好画像，要给出极其精准、刻薄或强烈安利的短评。

【人设与语气】
1. 极具网感、毒舌、一针见血，像极其懂行且脾气古怪的资深评测家
2. 绝对不要用 AI 腔调（"总之"、"综上所述"、"值得一提"禁用）
3. 冲突就狠狠劝退 + 指出致命雷点；契合就给出致命推坑理由
4. 字数严格控制在 30~50 字之间
5. 根据物品类型调整比喻：电影用"影院睡着"、游戏用"摔手柄"、书用"翻不过 30 页"、音乐用"耳机里塞满棉花"

【输出格式】
严格 JSON，不要 markdown 代码块：
{"roast": "你的点评"}
"""


def _build_user_prompt(
    text: str,
    domain: str,
    item_tag_names: list[str],
    user_top_tag_names: list[str],
) -> str:
    item_tags_str = "、".join(item_tag_names) if item_tag_names else "暂无"
    user_tags_str = "、".join(user_top_tag_names) if user_top_tag_names else "暂无（新用户）"
    return (
        f"【物品 ({domain})】：{text}\n"
        f"【物品的 vibe 标签】：{item_tags_str}\n"
        f"【该用户当前的主导审美】：{user_tags_str}\n\n"
        f"请开始你的毒舌鉴定。"
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
        "temperature": 0.7,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def generate_roast(
    text: str,
    domain: str,
    item_tag_names: list[str],
    user_top_tag_names: list[str],
    llm_call: LlmCallable | None = None,
) -> str:
    """Generate a 30-50 char roast. Returns empty string on ANY failure.

    The caller (vibe/analyze router) must never fail because of a roaster failure —
    this function swallows all exceptions and parse errors and returns "" so the
    frontend can fall back to displaying `summary` as primary copy.
    """
    llm_call = llm_call or _default_llm_call
    user_prompt = _build_user_prompt(text, domain, item_tag_names, user_top_tag_names)

    try:
        raw = await llm_call(SYSTEM_PROMPT, user_prompt)
    except Exception:
        return ""

    try:
        parsed = json.loads(raw)
        roast = parsed.get("roast", "")
        if not isinstance(roast, str):
            return ""
        return roast
    except json.JSONDecodeError:
        return ""
```

- [ ] **Step 4: Run test to verify passing**

```bash
pytest tests/test_llm_roaster.py -v
```
Expected: 6 passing.

- [ ] **Step 5: Run full backend suite to check no regression**

```bash
pytest tests/ -v
```
Expected: 33 passing (27 existing + 6 new).

- [ ] **Step 6: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/services/llm_roaster.py backend/tests/test_llm_roaster.py
git commit -m "feat(backend): add llm_roaster service for cyber-snark commentary"
git log --oneline | head -3
```
Expected: new commit on top of `55aedaa`, now 24 commits total.

---

## Task 2: Wire roaster into `/vibe/analyze` (schema + profile helper + router + test)

**Files:**
- Modify: `backend/app/services/profile_calc.py` (add `get_top_core_tag_names` helper)
- Modify: `backend/tests/test_profile_calc.py` (add helper test)
- Modify: `backend/app/schemas/analyze.py` (add `roast` field)
- Modify: `backend/app/routers/vibe.py` (call roaster, populate `roast` in response)
- Modify: `backend/tests/test_vibe.py` (add roast fake installer + new assertions)

- [ ] **Step 1: Add `get_top_core_tag_names` helper to profile_calc**

Open `backend/app/services/profile_calc.py` and append to the end of the file (after the existing `compute_radar` function):

```python
def get_top_core_tag_names(user_id: int, n: int = 3) -> list[str]:
    """Return the names of the N tags with highest core_weight for this user.

    Used by the analyze router to pass 'user_top_tag_names' into the roaster
    and recommender prompts. Ties are broken by tag_id ascending. Returns an
    empty list if the user has no relations yet (cold-start state).
    """
    db = database.SessionLocal()
    try:
        rels = db.scalars(
            select(UserVibeRelation).where(UserVibeRelation.user_id == user_id)
        ).all()
        if not rels:
            return []
        sorted_rels = sorted(rels, key=lambda r: (-r.core_weight, r.vibe_tag_id))
        top_ids = [r.vibe_tag_id for r in sorted_rels[:n] if r.core_weight > 0]
        if not top_ids:
            return []
        tags = db.scalars(select(VibeTag).where(VibeTag.id.in_(top_ids))).all()
        tag_by_id = {t.id: t.name for t in tags}
        return [tag_by_id[tid] for tid in top_ids if tid in tag_by_id]
    finally:
        db.close()
```

The `select` and `database` imports already exist at the top of the file from V1.0 — no new imports needed.

- [ ] **Step 2: Write failing test for helper**

Open `backend/tests/test_profile_calc.py` and append:

```python
def test_get_top_core_tag_names_returns_top_3_by_core_weight(seeded_user):
    db = database.SessionLocal()
    db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=1).one().core_weight = 30.0
    db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=5).one().core_weight = 20.0
    db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=9).one().core_weight = 10.0
    db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=13).one().core_weight = 5.0
    db.commit()
    db.close()

    names = profile_calc.get_top_core_tag_names(user_id=1, n=3)
    assert len(names) == 3
    # tag 1 = 慢炖沉浸, tag 5 = 治愈温暖, tag 9 = 放空友好 (per seed_data.py ordering)
    assert names[0] == "慢炖沉浸"
    assert names[1] == "治愈温暖"
    assert names[2] == "放空友好"


def test_get_top_core_tag_names_excludes_zero_and_negative_weights(seeded_user):
    db = database.SessionLocal()
    db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=1).one().core_weight = 10.0
    db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=2).one().core_weight = -5.0
    db.commit()
    db.close()

    names = profile_calc.get_top_core_tag_names(user_id=1, n=3)
    assert names == ["慢炖沉浸"]  # only the positive one


def test_get_top_core_tag_names_cold_start_user_returns_empty(seeded_user):
    # seeded_user fixture has all zeros
    names = profile_calc.get_top_core_tag_names(user_id=1, n=3)
    assert names == []
```

- [ ] **Step 3: Run helper tests**

```bash
pytest tests/test_profile_calc.py -v
```
Expected: 9 passing (6 existing + 3 new).

- [ ] **Step 4: Extend `AnalyzeResponse` schema**

Open `backend/app/schemas/analyze.py`. The current `AnalyzeResponse` class is:

```python
class AnalyzeResponse(BaseModel):
    match_score: int
    summary: str
    matched_tags: list[MatchedTag]
    text_hash: str
    cache_hit: bool
```

Replace with:

```python
class AnalyzeResponse(BaseModel):
    match_score: int
    summary: str
    roast: str = ""
    matched_tags: list[MatchedTag]
    text_hash: str
    cache_hit: bool
```

Just the one new `roast: str = ""` line. Default empty string so existing callers (there are none yet outside the router) don't break.

- [ ] **Step 5: Extend analyze route to call roaster**

Open `backend/app/routers/vibe.py`. Current imports at top:

```python
from app.services import llm_tagger, profile_calc
```

Change to:

```python
from app.services import llm_roaster, llm_tagger, profile_calc
```

Find the existing `analyze()` function. Its current shape:

```python
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    try:
        result = await llm_tagger.analyze(payload.text, payload.domain)
    except llm_tagger.LlmParseError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_PARSE_FAIL", "message": str(e)}},
        )
    except llm_tagger.LlmTimeoutError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_TIMEOUT", "message": str(e)}},
        )

    matched_tag_ids = [t["tag_id"] for t in result["matched_tags"]]
    item_tags = [(t["tag_id"], t["weight"]) for t in result["matched_tags"]]

    score = profile_calc.compute_match_score(user_id=user_id, item_tags=item_tags)
    profile_calc.apply_curiosity_delta(
        user_id=user_id,
        tag_ids=matched_tag_ids,
        delta=CURIOSITY_DELTA,
        action="analyze",
    )

    return AnalyzeResponse(
        match_score=score,
        summary=result["summary"],
        matched_tags=[MatchedTag(**t) for t in result["matched_tags"]],
        text_hash=result["text_hash"],
        cache_hit=result["cache_hit"],
    )
```

Replace the body (keeping the decorator + signature) with this expanded version that calls roaster between `compute_match_score` and the return:

```python
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    try:
        result = await llm_tagger.analyze(payload.text, payload.domain)
    except llm_tagger.LlmParseError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_PARSE_FAIL", "message": str(e)}},
        )
    except llm_tagger.LlmTimeoutError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_TIMEOUT", "message": str(e)}},
        )

    matched_tag_ids = [t["tag_id"] for t in result["matched_tags"]]
    matched_tag_names = [t["name"] for t in result["matched_tags"]]
    item_tags = [(t["tag_id"], t["weight"]) for t in result["matched_tags"]]

    score = profile_calc.compute_match_score(user_id=user_id, item_tags=item_tags)

    user_top_tag_names = profile_calc.get_top_core_tag_names(user_id=user_id, n=3)
    roast = await llm_roaster.generate_roast(
        text=payload.text,
        domain=payload.domain,
        item_tag_names=matched_tag_names,
        user_top_tag_names=user_top_tag_names,
    )

    profile_calc.apply_curiosity_delta(
        user_id=user_id,
        tag_ids=matched_tag_ids,
        delta=CURIOSITY_DELTA,
        action="analyze",
    )

    return AnalyzeResponse(
        match_score=score,
        summary=result["summary"],
        roast=roast,
        matched_tags=[MatchedTag(**t) for t in result["matched_tags"]],
        text_hash=result["text_hash"],
        cache_hit=result["cache_hit"],
    )
```

- [ ] **Step 6: Extend `test_vibe.py` with roaster injection helper and new assertions**

Open `backend/tests/test_vibe.py`. Find the existing `_install_fake_llm` helper:

```python
def _install_fake_llm(monkeypatch, response):
    async def fake(text, domain, tag_pool):
        return response
    from app.services import llm_tagger
    monkeypatch.setattr(llm_tagger, "_default_llm_call", fake)
```

Add a second helper right below it:

```python
def _install_fake_roaster(monkeypatch, roast_text):
    async def fake(system_prompt, user_prompt):
        return json.dumps({"roast": roast_text})
    from app.services import llm_roaster
    monkeypatch.setattr(llm_roaster, "_default_llm_call", fake)
```

Now find all the existing analyze tests that use `_install_fake_llm` and also make them install the roaster. Specifically modify these test functions:

For `test_analyze_returns_match_score_and_updates_curiosity`, change the beginning from:

```python
def test_analyze_returns_match_score_and_updates_curiosity(monkeypatch):
    _init_profile()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "A gentle slow piece", "domain": "book"})
    assert r.status_code == 200
    body = r.json()
    assert body["match_score"] > 0
    assert body["matched_tags"][0]["tag_id"] == 1
    assert body["cache_hit"] is False
```

To:

```python
def test_analyze_returns_match_score_and_updates_curiosity(monkeypatch):
    _init_profile()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_roaster(monkeypatch, "慢炖神作，你会睡着但心满意足")
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "A gentle slow piece", "domain": "book"})
    assert r.status_code == 200
    body = r.json()
    assert body["match_score"] > 0
    assert body["matched_tags"][0]["tag_id"] == 1
    assert body["cache_hit"] is False
    assert body["roast"] == "慢炖神作，你会睡着但心满意足"
```

For `test_analyze_second_call_hits_cache`, similarly install the fake roaster after the tagger:

```python
def test_analyze_second_call_hits_cache(monkeypatch):
    _init_profile()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_roaster(monkeypatch, "roast text")
    client.post("/api/v1/vibe/analyze",
                json={"text": "same text", "domain": "book"})
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "same text", "domain": "book"})
    assert r.json()["cache_hit"] is True
```

For `test_analyze_llm_parse_failure_returns_503`, ALSO install the roaster (it won't be called because tagger fails first, but the test shouldn't hit the real API even if ordering changes):

```python
def test_analyze_llm_parse_failure_returns_503(monkeypatch):
    _init_profile()
    _install_fake_llm(monkeypatch, "garbage")
    _install_fake_roaster(monkeypatch, "unused")
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "x is too short anyway", "domain": "book"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "LLM_PARSE_FAIL"
```

Now add a new test at the end of the file (before the action tests or after):

```python
def test_analyze_roaster_failure_returns_empty_roast(monkeypatch):
    """If the roaster fails, analyze still returns 200 with roast=''."""
    _init_profile()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))

    async def broken_roaster(system_prompt, user_prompt):
        raise RuntimeError("boom")
    from app.services import llm_roaster
    monkeypatch.setattr(llm_roaster, "_default_llm_call", broken_roaster)

    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "A gentle slow piece", "domain": "book"})
    assert r.status_code == 200
    body = r.json()
    assert body["roast"] == ""
    assert body["match_score"] >= 0  # analyze still works
```

- [ ] **Step 7: Run the extended test file**

```bash
pytest tests/test_vibe.py -v
```
Expected: 6 passing (5 existing + 1 new regression test). All existing tests should still pass with the roaster installed.

- [ ] **Step 8: Run the full suite**

```bash
pytest tests/ -v
```
Expected: 37 passing total (33 after Task 1 + 3 profile_calc tests + 1 new vibe test).

- [ ] **Step 9: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/services/profile_calc.py backend/tests/test_profile_calc.py backend/app/schemas/analyze.py backend/app/routers/vibe.py backend/tests/test_vibe.py
git commit -m "feat(backend): integrate llm_roaster into /vibe/analyze response"
```
Expected: 25 commits total.

---

## Task 3: `llm_recommender` service with cross-domain enforcement

**Files:**
- Create: `backend/app/services/llm_recommender.py`
- Create: `backend/tests/test_llm_recommender.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_llm_recommender.py`:

```python
import json

import pytest

from app.services import llm_recommender


class FakeLLM:
    def __init__(self, response=None, raise_exc=None):
        self.response = response
        self.raise_exc = raise_exc
        self.calls = 0
        self.last_prompt = None

    async def __call__(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        self.last_prompt = user_prompt
        if self.raise_exc:
            raise self.raise_exc
        return self.response


def _make_response(items):
    return json.dumps({"items": items})


async def test_happy_path_three_cross_domain_items():
    fake = FakeLLM(response=_make_response([
        {"domain": "game",  "name": "《逃生》",    "reason": "幽闭窒息，你拿着摄像机"},
        {"domain": "book",  "name": "《幽灵之家》", "reason": "慢炖心理压抑"},
        {"domain": "music", "name": "Ben Frost",   "reason": "黑暗环境音"},
    ]))
    items = await llm_recommender.recommend(
        text="《闪灵》", source_domain="movie",
        item_tag_names=["黑暗压抑"], user_top_tag_names=["烧脑解谜"],
        llm_call=fake,
    )
    assert len(items) == 3
    assert {i["domain"] for i in items} == {"game", "book", "music"}
    assert all(i["domain"] != "movie" for i in items)


async def test_same_domain_items_are_filtered():
    fake = FakeLLM(response=_make_response([
        {"domain": "movie", "name": "《沉默的羔羊》", "reason": "嘿嘿同域"},
        {"domain": "game",  "name": "《逃生》",       "reason": "跨域"},
        {"domain": "book",  "name": "《幽灵之家》",   "reason": "跨域"},
    ]))
    items = await llm_recommender.recommend(
        text="x", source_domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert len(items) == 2
    assert all(i["domain"] != "movie" for i in items)


async def test_all_same_domain_raises():
    fake = FakeLLM(response=_make_response([
        {"domain": "movie", "name": "a", "reason": "x"},
        {"domain": "movie", "name": "b", "reason": "y"},
    ]))
    with pytest.raises(llm_recommender.RecommendEmptyError):
        await llm_recommender.recommend(
            text="x", source_domain="movie",
            item_tag_names=[], user_top_tag_names=[],
            llm_call=fake,
        )


async def test_duplicate_names_are_deduped():
    fake = FakeLLM(response=_make_response([
        {"domain": "game", "name": "《逃生》", "reason": "a"},
        {"domain": "game", "name": "《逃生》", "reason": "duplicate"},
        {"domain": "book", "name": "《幽灵之家》", "reason": "b"},
    ]))
    items = await llm_recommender.recommend(
        text="x", source_domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert len(items) == 2
    names = [i["name"] for i in items]
    assert names.count("《逃生》") == 1


async def test_invalid_domain_items_dropped():
    fake = FakeLLM(response=_make_response([
        {"domain": "podcast", "name": "???", "reason": "bogus domain"},
        {"domain": "game", "name": "《逃生》", "reason": "valid"},
        {"domain": "book", "name": "《幽灵》", "reason": "valid"},
    ]))
    items = await llm_recommender.recommend(
        text="x", source_domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert len(items) == 2


async def test_missing_fields_are_dropped():
    fake = FakeLLM(response=_make_response([
        {"domain": "game", "name": "《逃生》"},  # missing reason
        {"domain": "book", "name": "《幽灵》", "reason": "valid"},
        {"domain": "music", "name": "Ben Frost", "reason": "valid"},
    ]))
    items = await llm_recommender.recommend(
        text="x", source_domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert len(items) == 2
    assert all("reason" in i and i["reason"] for i in items)


async def test_json_parse_failure_raises():
    fake = FakeLLM(response="not json")
    with pytest.raises(llm_recommender.LlmParseError):
        await llm_recommender.recommend(
            text="x", source_domain="movie",
            item_tag_names=[], user_top_tag_names=[],
            llm_call=fake,
        )


async def test_timeout_wraps_to_timeout_error():
    import httpx
    fake = FakeLLM(raise_exc=httpx.TimeoutException("slow"))
    with pytest.raises(llm_recommender.LlmTimeoutError):
        await llm_recommender.recommend(
            text="x", source_domain="movie",
            item_tag_names=[], user_top_tag_names=[],
            llm_call=fake,
        )


async def test_prompt_contains_source_domain_exclusion():
    fake = FakeLLM(response=_make_response([
        {"domain": "book", "name": "x", "reason": "y"},
        {"domain": "game", "name": "a", "reason": "b"},
    ]))
    await llm_recommender.recommend(
        text="《闪灵》", source_domain="movie",
        item_tag_names=["黑暗压抑"], user_top_tag_names=["烧脑解谜"],
        llm_call=fake,
    )
    assert "movie" in fake.last_prompt
    assert "禁止" in fake.last_prompt or "排除" in fake.last_prompt or "不要" in fake.last_prompt
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest tests/test_llm_recommender.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.llm_recommender'`.

- [ ] **Step 3: Create `backend/app/services/llm_recommender.py`**

```python
import json
from typing import Awaitable, Callable

import httpx

from app.config import settings

LlmCallable = Callable[[str, str], Awaitable[str]]

VALID_DOMAINS = {"book", "movie", "game", "music"}


class LlmParseError(Exception):
    pass


class LlmTimeoutError(Exception):
    pass


class RecommendEmptyError(Exception):
    """Raised when cross-domain filtering leaves fewer than 2 items."""
    pass


SYSTEM_PROMPT = """你是 Vibe-Radar 的"跨界代餐官"。用户给你一个物品和他的审美画像，你要推荐 3 个【非当前类型】的东西（书/游戏/电影/音乐），每条有一个不按常理出牌但精准的理由。

【规则】
1. 严格跨域：当前物品是电影就禁止推荐电影，是游戏就禁止推荐游戏，以此类推
2. 3 条必须来自 3 个不同的域（book / movie / game / music 选 3 个，排除当前域）
3. 每条 reason 15-25 字，要毒舌幽默，不能套话
4. 推荐真实存在的作品/游戏/专辑，别瞎编
5. name 字段要包含书名号/专辑名，例如 "《逃生》" 或 "Ben Frost - Aurora"

【输出格式】
严格 JSON，不要 markdown 代码块：
{"items": [{"domain": "book|game|movie|music", "name": "xxx", "reason": "xxx"}, ...]}
"""


def _build_user_prompt(
    text: str,
    source_domain: str,
    item_tag_names: list[str],
    user_top_tag_names: list[str],
) -> str:
    item_tags_str = "、".join(item_tag_names) if item_tag_names else "暂无"
    user_tags_str = "、".join(user_top_tag_names) if user_top_tag_names else "暂无（新用户）"
    return (
        f"【用户看到的物品 ({source_domain})】：{text}\n"
        f"【物品的 vibe】：{item_tags_str}\n"
        f"【用户主导审美】：{user_tags_str}\n\n"
        f"禁止推荐 {source_domain} 类型。请给 3 条跨域代餐。"
    )


async def _default_llm_call(system_prompt: str, user_prompt: str) -> str:
    url = f"{settings.llm_base_url}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.8,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException as e:
        raise LlmTimeoutError(str(e)) from e


async def recommend(
    text: str,
    source_domain: str,
    item_tag_names: list[str],
    user_top_tag_names: list[str],
    llm_call: LlmCallable | None = None,
) -> list[dict]:
    """Return 1-3 cross-domain recommendation items.

    Raises:
        LlmTimeoutError: upstream timeout
        LlmParseError: invalid JSON or structure
        RecommendEmptyError: after filtering, fewer than 2 valid items remain
    """
    llm_call = llm_call or _default_llm_call
    user_prompt = _build_user_prompt(text, source_domain, item_tag_names, user_top_tag_names)

    try:
        raw = await llm_call(SYSTEM_PROMPT, user_prompt)
    except LlmTimeoutError:
        raise
    except httpx.TimeoutException as e:
        raise LlmTimeoutError(str(e)) from e

    try:
        parsed = json.loads(raw)
        raw_items = parsed["items"]
        if not isinstance(raw_items, list):
            raise ValueError("items not a list")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise LlmParseError(f"invalid LLM response: {e}") from e

    seen_names: set[str] = set()
    filtered: list[dict] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        domain = item.get("domain")
        name = item.get("name")
        reason = item.get("reason")
        if not isinstance(domain, str) or domain not in VALID_DOMAINS:
            continue
        if domain == source_domain:
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(reason, str) or not reason.strip():
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        filtered.append({"domain": domain, "name": name, "reason": reason})
        if len(filtered) == 3:
            break

    if len(filtered) < 2:
        raise RecommendEmptyError(f"only {len(filtered)} valid items after filtering")

    return filtered
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_llm_recommender.py -v
```
Expected: 9 passing.

- [ ] **Step 5: Run full suite**

```bash
pytest tests/ -v
```
Expected: 46 passing total.

- [ ] **Step 6: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/services/llm_recommender.py backend/tests/test_llm_recommender.py
git commit -m "feat(backend): add llm_recommender with cross-domain filtering"
```
Expected: 26 commits.

---

## Task 4: `/vibe/recommend` route + schemas

**Files:**
- Create: `backend/app/schemas/recommend.py`
- Modify: `backend/app/routers/vibe.py` (add recommend route)
- Modify: `backend/tests/test_vibe.py` (add recommend route tests)

- [ ] **Step 1: Create `backend/app/schemas/recommend.py`**

```python
from typing import Literal

from pydantic import BaseModel, Field

Domain = Literal["book", "movie", "game", "music"]


class RecommendRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    source_domain: Domain
    matched_tag_ids: list[int] = Field(min_length=1, max_length=10)


class RecommendItem(BaseModel):
    domain: Domain
    name: str
    reason: str


class RecommendResponse(BaseModel):
    items: list[RecommendItem]
```

- [ ] **Step 2: Write the failing test**

Open `backend/tests/test_vibe.py`. Add a new helper and then new tests at the end of the file:

```python
def _install_fake_recommender(monkeypatch, items):
    async def fake(system_prompt, user_prompt):
        return json.dumps({"items": items})
    from app.services import llm_recommender
    monkeypatch.setattr(llm_recommender, "_default_llm_call", fake)


def test_recommend_happy_path_returns_3_cross_domain_items(monkeypatch):
    _init_profile()
    _install_fake_recommender(monkeypatch, [
        {"domain": "game", "name": "《逃生》",     "reason": "幽闭窒息"},
        {"domain": "book", "name": "《幽灵之家》", "reason": "心理压抑"},
        {"domain": "music", "name": "Ben Frost",  "reason": "黑暗环境音"},
    ])
    r = client.post("/api/v1/vibe/recommend", json={
        "text": "《闪灵》",
        "source_domain": "movie",
        "matched_tag_ids": [8, 11],
    })
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 3
    assert {i["domain"] for i in body["items"]} == {"game", "book", "music"}
    assert all(i["domain"] != "movie" for i in body["items"])


def test_recommend_empty_tag_ids_rejected_by_pydantic(monkeypatch):
    _init_profile()
    r = client.post("/api/v1/vibe/recommend", json={
        "text": "x",
        "source_domain": "movie",
        "matched_tag_ids": [],
    })
    assert r.status_code == 422


def test_recommend_invalid_tag_ids_returns_400(monkeypatch):
    _init_profile()
    r = client.post("/api/v1/vibe/recommend", json={
        "text": "x",
        "source_domain": "movie",
        "matched_tag_ids": [999],
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_TAG_IDS"


def test_recommend_all_same_domain_returns_503(monkeypatch):
    _init_profile()
    _install_fake_recommender(monkeypatch, [
        {"domain": "movie", "name": "a", "reason": "x"},
        {"domain": "movie", "name": "b", "reason": "y"},
    ])
    r = client.post("/api/v1/vibe/recommend", json={
        "text": "x",
        "source_domain": "movie",
        "matched_tag_ids": [1],
    })
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "NO_CROSS_DOMAIN"


def test_recommend_llm_parse_failure_returns_503(monkeypatch):
    _init_profile()
    async def broken(system_prompt, user_prompt):
        return "garbage"
    from app.services import llm_recommender
    monkeypatch.setattr(llm_recommender, "_default_llm_call", broken)
    r = client.post("/api/v1/vibe/recommend", json={
        "text": "x",
        "source_domain": "movie",
        "matched_tag_ids": [1],
    })
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "LLM_PARSE_FAIL"
```

- [ ] **Step 3: Run test to verify failure**

```bash
pytest tests/test_vibe.py -v -k "recommend"
```
Expected: all 5 new tests fail with 404 (route doesn't exist).

- [ ] **Step 4: Add the recommend route to `vibe.py`**

Open `backend/app/routers/vibe.py`. At the top, update imports — the current:

```python
from app.services import llm_roaster, llm_tagger, profile_calc
```

becomes:

```python
from app.services import llm_recommender, llm_roaster, llm_tagger, profile_calc
```

Also add to the existing imports block:

```python
from app.schemas.recommend import RecommendRequest, RecommendResponse
from app.models.vibe_tag import VibeTag
from sqlalchemy import select
```

(`select` may already be imported — check; if so, leave it. `VibeTag` is likely new.)

Then append this route at the bottom of the file, after the existing `action` route:

```python
@router.post("/recommend", response_model=RecommendResponse)
async def recommend(
    payload: RecommendRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    # 1. Resolve tag_ids → tag names, fail if any id is out of range
    tags = db.scalars(
        select(VibeTag).where(VibeTag.id.in_(payload.matched_tag_ids))
    ).all()
    if len(tags) != len(set(payload.matched_tag_ids)):
        raise HTTPException(
            status_code=400,
            detail={"error": {
                "code": "INVALID_TAG_IDS",
                "message": "one or more tag_ids are not in the 1-24 pool",
            }},
        )
    item_tag_names = [t.name for t in tags]

    # 2. User's top-3 core_weight tags for prompt context
    user_top_tag_names = profile_calc.get_top_core_tag_names(user_id=user_id, n=3)

    # 3. LLM call with cross-domain filtering
    try:
        items = await llm_recommender.recommend(
            text=payload.text,
            source_domain=payload.source_domain,
            item_tag_names=item_tag_names,
            user_top_tag_names=user_top_tag_names,
        )
    except llm_recommender.LlmParseError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_PARSE_FAIL", "message": str(e)}},
        )
    except llm_recommender.LlmTimeoutError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "LLM_TIMEOUT", "message": str(e)}},
        )
    except llm_recommender.RecommendEmptyError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "NO_CROSS_DOMAIN", "message": str(e)}},
        )

    return RecommendResponse(items=items)
```

- [ ] **Step 5: Run tests to verify passing**

```bash
pytest tests/test_vibe.py -v
```
Expected: 11 passing (6 existing + 5 new).

- [ ] **Step 6: Run full suite**

```bash
pytest tests/ -v
```
Expected: 51 passing.

- [ ] **Step 7: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/schemas/recommend.py backend/app/routers/vibe.py backend/tests/test_vibe.py
git commit -m "feat(backend): add /vibe/recommend route for cross-domain pivots"
```
Expected: 27 commits.

---

## Task 5: Extension shared types + background RECOMMEND routing

**Files:**
- Modify: `extension/src/shared/types.ts`
- Modify: `extension/src/background/index.ts`

- [ ] **Step 1: Extend `shared/types.ts`**

Open `extension/src/shared/types.ts`. Find the `AnalyzeResult` interface:

```typescript
export interface AnalyzeResult {
  match_score: number;
  summary: string;
  matched_tags: MatchedTag[];
  text_hash: string;
  cache_hit: boolean;
}
```

Add the `roast` field:

```typescript
export interface AnalyzeResult {
  match_score: number;
  summary: string;
  roast: string;
  matched_tags: MatchedTag[];
  text_hash: string;
  cache_hit: boolean;
}
```

Also add two new types below `RadarResult`:

```typescript
export interface RecommendItem {
  domain: Domain;
  name: string;
  reason: string;
}

export interface RecommendResult {
  items: RecommendItem[];
}
```

And add the `RECOMMEND` message variant to the `Msg` union. The current union:

```typescript
export type Msg =
  | { type: "ANALYZE"; payload: { text: string; domain: Domain; pageTitle: string; pageUrl: string } }
  | { type: "ACTION"; payload: { action: "star" | "bomb"; matchedTagIds: number[]; textHash?: string } }
  | { type: "COLD_START_GET_CARDS" }
  | { type: "COLD_START_SUBMIT"; payload: { selectedTagIds: number[] } }
  | { type: "GET_RADAR" };
```

becomes:

```typescript
export type Msg =
  | { type: "ANALYZE"; payload: { text: string; domain: Domain; pageTitle: string; pageUrl: string } }
  | { type: "ACTION"; payload: { action: "star" | "bomb"; matchedTagIds: number[]; textHash?: string } }
  | { type: "COLD_START_GET_CARDS" }
  | { type: "COLD_START_SUBMIT"; payload: { selectedTagIds: number[] } }
  | { type: "GET_RADAR" }
  | { type: "RECOMMEND"; payload: { text: string; sourceDomain: Domain; matchedTagIds: number[] } };
```

- [ ] **Step 2: Extend `background/index.ts` routing**

Open `extension/src/background/index.ts`. Find the `routeApi` switch:

```typescript
async function routeApi(msg: Msg): Promise<unknown> {
  switch (msg.type) {
    case "COLD_START_GET_CARDS":
      return fetchJson("GET", "/cold-start/cards");
    case "COLD_START_SUBMIT":
      return fetchJson("POST", "/cold-start/submit", {
        selected_tag_ids: msg.payload.selectedTagIds,
      });
    case "ANALYZE":
      return fetchJson("POST", "/vibe/analyze", {
        text: msg.payload.text,
        domain: msg.payload.domain,
        context: {
          page_title: msg.payload.pageTitle,
          page_url: msg.payload.pageUrl,
        },
      });
    case "ACTION":
      return fetchJson("POST", "/vibe/action", {
        action: msg.payload.action,
        matched_tag_ids: msg.payload.matchedTagIds,
        text_hash: msg.payload.textHash,
      });
    case "GET_RADAR":
      return fetchJson("GET", "/profile/radar");
  }
}
```

Add a `RECOMMEND` case before the closing brace:

```typescript
async function routeApi(msg: Msg): Promise<unknown> {
  switch (msg.type) {
    case "COLD_START_GET_CARDS":
      return fetchJson("GET", "/cold-start/cards");
    case "COLD_START_SUBMIT":
      return fetchJson("POST", "/cold-start/submit", {
        selected_tag_ids: msg.payload.selectedTagIds,
      });
    case "ANALYZE":
      return fetchJson("POST", "/vibe/analyze", {
        text: msg.payload.text,
        domain: msg.payload.domain,
        context: {
          page_title: msg.payload.pageTitle,
          page_url: msg.payload.pageUrl,
        },
      });
    case "ACTION":
      return fetchJson("POST", "/vibe/action", {
        action: msg.payload.action,
        matched_tag_ids: msg.payload.matchedTagIds,
        text_hash: msg.payload.textHash,
      });
    case "GET_RADAR":
      return fetchJson("GET", "/profile/radar");
    case "RECOMMEND":
      return fetchJson("POST", "/vibe/recommend", {
        text: msg.payload.text,
        source_domain: msg.payload.sourceDomain,
        matched_tag_ids: msg.payload.matchedTagIds,
      });
  }
}
```

- [ ] **Step 3: Build and verify no TypeScript errors**

```bash
cd D:/qhyProject/vibe4.0/extension && npm run build
```
Expected: `Extension built to build` with no errors.

- [ ] **Step 4: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/src/shared/types.ts extension/src/background/index.ts
git commit -m "feat(ext): add RECOMMEND message type and recommend route in bg"
```
Expected: 28 commits.

---

## Task 6: VibeCard — promote roast to primary, demote summary

**Files:**
- Modify: `extension/src/content/ui/VibeCard.ts`
- Modify: `extension/src/content/ui/styles.css`

- [ ] **Step 1: Add new CSS classes to `styles.css`**

Open `extension/src/content/ui/styles.css`. Find the existing `.vr-summary` block:

```css
.vr-summary {
  margin: 8px 0 12px;
  color: #555;
}
```

Replace it (keep the selector, change the purpose to "secondary caption") and add a new `.vr-roast` class above it:

```css
.vr-roast {
  font-size: 15px;
  font-weight: 600;
  color: #4a3db0;
  margin: 10px 0 6px;
  line-height: 1.5;
  letter-spacing: 0.2px;
}

.vr-summary {
  margin: 0 0 12px;
  color: #888;
  font-size: 11px;
  font-style: italic;
}
```

- [ ] **Step 2: Update `VibeCard.ts` to render roast and conditional summary**

Open `extension/src/content/ui/VibeCard.ts`. Find the existing summary rendering:

```typescript
const summary = document.createElement("div");
summary.className = "vr-summary";
summary.textContent = result.summary;
card.appendChild(summary);
```

Replace with:

```typescript
// Roast is the primary copy; if empty, fall back to showing summary as primary
const hasRoast = typeof result.roast === "string" && result.roast.trim() !== "";

if (hasRoast) {
  const roast = document.createElement("div");
  roast.className = "vr-roast";
  roast.textContent = result.roast;
  card.appendChild(roast);

  if (result.summary && result.summary.trim() !== "") {
    const summary = document.createElement("div");
    summary.className = "vr-summary";
    summary.textContent = result.summary;
    card.appendChild(summary);
  }
} else {
  // Fall back: promote summary to primary styling
  const roastFallback = document.createElement("div");
  roastFallback.className = "vr-roast";
  roastFallback.textContent = result.summary || "";
  card.appendChild(roastFallback);
}
```

- [ ] **Step 3: Build and check**

```bash
cd D:/qhyProject/vibe4.0/extension && npm run build
```
Expected: clean build.

- [ ] **Step 4: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/src/content/ui/VibeCard.ts extension/src/content/ui/styles.css
git commit -m "feat(ext): promote roast to primary copy in VibeCard, demote summary"
```
Expected: 29 commits.

---

## Task 7: SharePoster (Canvas 2D) + VibeCard share button

**Files:**
- Create: `extension/src/content/ui/SharePoster.ts`
- Modify: `extension/src/content/ui/VibeCard.ts`
- Modify: `extension/src/content/ui/styles.css`

- [ ] **Step 1: Create `extension/src/content/ui/SharePoster.ts`**

```typescript
import type { AnalyzeResult, Domain } from "../../shared/types";

const W = 1080;
const H = 1080;

const DOMAIN_LABEL: Record<Domain, string> = {
  book: "豆瓣读书",
  movie: "豆瓣电影",
  game: "Steam",
  music: "网易云音乐",
};

export function generatePoster(result: AnalyzeResult, sourceDomain: Domain): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d")!;

  drawBackground(ctx);
  drawWatermark(ctx);
  drawWordmark(ctx);
  drawScore(ctx, result.match_score);
  drawTagPills(ctx, result.matched_tags.map((t) => t.name));
  drawRoast(ctx, result.roast || result.summary || "");
  drawSourceLine(ctx, sourceDomain);
  drawFooter(ctx);

  return canvas;
}

function drawBackground(ctx: CanvasRenderingContext2D) {
  const grad = ctx.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, "#6c5ce7");
  grad.addColorStop(1, "#a29bfe");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);
}

function drawWatermark(ctx: CanvasRenderingContext2D) {
  // concentric circles in bottom-left, echoing the extension icon
  ctx.save();
  ctx.globalAlpha = 0.15;
  ctx.strokeStyle = "#fff";
  ctx.fillStyle = "#fff";
  const cx = 140;
  const cy = H - 140;
  [90, 60, 30].forEach((r) => {
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
  });
  ctx.beginPath();
  ctx.arc(cx, cy, 10, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawWordmark(ctx: CanvasRenderingContext2D) {
  ctx.save();
  ctx.fillStyle = "#fff";
  ctx.font = `bold 60px system-ui, "PingFang SC", sans-serif`;
  ctx.textBaseline = "top";
  ctx.fillText("Vibe-Radar", 60, 60);
  ctx.restore();
}

function drawScore(ctx: CanvasRenderingContext2D, score: number) {
  ctx.save();
  ctx.fillStyle = "#fff";
  ctx.font = `bold 280px system-ui, "PingFang SC", sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(`${score}%`, W / 2, 340);
  ctx.restore();
}

function drawTagPills(ctx: CanvasRenderingContext2D, tagNames: string[]) {
  if (tagNames.length === 0) return;
  ctx.save();
  ctx.font = `bold 36px system-ui, "PingFang SC", sans-serif`;
  ctx.textBaseline = "middle";
  const padX = 24;
  const gap = 16;
  const pillHeight = 64;
  const y = 520;

  // measure total width
  const widths = tagNames.map((n) => ctx.measureText(n).width + padX * 2);
  const total = widths.reduce((a, b) => a + b, 0) + gap * (tagNames.length - 1);
  let x = (W - total) / 2;

  for (let i = 0; i < tagNames.length; i++) {
    const w = widths[i];
    ctx.fillStyle = "rgba(255,255,255,0.16)";
    drawRoundedRect(ctx, x, y - pillHeight / 2, w, pillHeight, 32);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.textAlign = "center";
    ctx.fillText(tagNames[i], x + w / 2, y + 2);
    x += w + gap;
  }
  ctx.restore();
}

function drawRoast(ctx: CanvasRenderingContext2D, text: string) {
  ctx.save();
  ctx.fillStyle = "#fff";
  ctx.font = `bold 54px system-ui, "PingFang SC", sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const maxWidth = W * 0.8;
  const lineHeight = 76;
  const startY = 620;
  const lines = wrapCJK(text, maxWidth, ctx);
  const visible = lines.slice(0, 3);
  for (let i = 0; i < visible.length; i++) {
    ctx.fillText(visible[i], W / 2, startY + i * lineHeight);
  }
  ctx.restore();
}

function drawSourceLine(ctx: CanvasRenderingContext2D, sourceDomain: Domain) {
  ctx.save();
  ctx.globalAlpha = 0.8;
  ctx.fillStyle = "#fff";
  ctx.font = `32px system-ui, "PingFang SC", sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";
  ctx.fillText(`—— 来自 ${DOMAIN_LABEL[sourceDomain]} · 被我划了`, W / 2, H - 120);
  ctx.restore();
}

function drawFooter(ctx: CanvasRenderingContext2D) {
  ctx.save();
  ctx.globalAlpha = 0.6;
  ctx.fillStyle = "#fff";
  ctx.font = `28px system-ui, "PingFang SC", sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";
  ctx.fillText("vibe-radar.local", W / 2, H - 60);
  ctx.restore();
}

function drawRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function wrapCJK(text: string, maxWidth: number, ctx: CanvasRenderingContext2D): string[] {
  // CJK-aware wrap: break by character, no word boundaries
  const lines: string[] = [];
  let current = "";
  for (const ch of text) {
    const test = current + ch;
    if (ctx.measureText(test).width > maxWidth && current.length > 0) {
      lines.push(current);
      current = ch;
    } else {
      current = test;
    }
  }
  if (current) lines.push(current);
  return lines;
}

export async function copyPosterToClipboard(canvas: HTMLCanvasElement): Promise<void> {
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob((b) => resolve(b), "image/png"),
  );
  if (!blob) throw new Error("canvas.toBlob returned null");
  await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
}

export function downloadPoster(canvas: HTMLCanvasElement): void {
  const link = document.createElement("a");
  link.download = `vibe-radar-${Date.now()}.png`;
  link.href = canvas.toDataURL("image/png");
  link.click();
}
```

- [ ] **Step 2: Add new styles to `styles.css`**

Append to `extension/src/content/ui/styles.css`:

```css
.vr-share-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 28px;
  height: 28px;
  border: none;
  background: rgba(108, 92, 231, 0.12);
  color: #6c5ce7;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.vr-share-btn:hover { background: rgba(108, 92, 231, 0.22); }

.vr-share-dialog {
  position: absolute;
  top: 12px;
  right: 48px;
  background: #fff;
  border: 1px solid rgba(108, 92, 231, 0.18);
  border-radius: 10px;
  padding: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 10;
}
.vr-share-dialog button {
  padding: 6px 12px;
  border: none;
  background: #f0edff;
  color: #6c5ce7;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
}
.vr-share-dialog button:hover { background: #e4ddff; }

.vr-toast {
  position: absolute;
  bottom: -36px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  animation: vr-toast-fade 2s ease;
}
@keyframes vr-toast-fade {
  0%   { opacity: 0; transform: translate(-50%, 4px); }
  15%  { opacity: 1; transform: translate(-50%, 0); }
  85%  { opacity: 1; transform: translate(-50%, 0); }
  100% { opacity: 0; transform: translate(-50%, -4px); }
}
```

Also ensure `.vr-card` has `position: relative` so the absolute-positioned share button anchors correctly. Find `.vr-card` and verify — if it's already relative, leave it. The V1.0 `.vr-card` is `position: absolute`, which is also fine as a positioning ancestor.

- [ ] **Step 3: Add share button to `VibeCard.ts`**

Open `extension/src/content/ui/VibeCard.ts`. The existing signature starts with:

```typescript
export interface VibeCardProps {
  parent: HTMLElement;
  result: AnalyzeResult;
  onClose: () => void;
}

export function renderVibeCard(props: VibeCardProps): HTMLElement {
  const { parent, result, onClose } = props;
  const card = document.createElement("div");
  card.className = "vr-card";
  ...
```

Change the props and first lines:

```typescript
import { copyPosterToClipboard, downloadPoster, generatePoster } from "./SharePoster";
import type { AnalyzeResult, Domain, Msg } from "../../shared/types";

export interface VibeCardProps {
  parent: HTMLElement;
  result: AnalyzeResult;
  sourceDomain: Domain;
  onClose: () => void;
}

export function renderVibeCard(props: VibeCardProps): HTMLElement {
  const { parent, result, sourceDomain, onClose } = props;
  const card = document.createElement("div");
  card.className = "vr-card";

  // Share button (top-right)
  const shareBtn = document.createElement("button");
  shareBtn.className = "vr-share-btn";
  shareBtn.textContent = "📤";
  shareBtn.title = "生成分享海报";
  let dialogOpen = false;
  shareBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    if (dialogOpen) return;
    dialogOpen = true;
    const dialog = buildShareDialog(card, result, sourceDomain, () => {
      dialog.remove();
      dialogOpen = false;
    });
    card.appendChild(dialog);
  });
  card.appendChild(shareBtn);
```

Keep the rest of the existing body (score, roast, summary, tags, actions) unchanged. After the existing function body (after the `return card;` line), add the helper function `buildShareDialog` at module scope:

```typescript
function buildShareDialog(
  card: HTMLElement,
  result: AnalyzeResult,
  sourceDomain: Domain,
  onClose: () => void,
): HTMLElement {
  const dialog = document.createElement("div");
  dialog.className = "vr-share-dialog";

  const copyBtn = document.createElement("button");
  copyBtn.textContent = "📋 复制到剪贴板";
  copyBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    const canvas = generatePoster(result, sourceDomain);
    try {
      await copyPosterToClipboard(canvas);
      showToast(card, "已复制到剪贴板");
    } catch (err) {
      showToast(card, "剪贴板失败，已自动下载");
      downloadPoster(canvas);
    }
    onClose();
  });

  const downloadBtn = document.createElement("button");
  downloadBtn.textContent = "💾 下载 PNG";
  downloadBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const canvas = generatePoster(result, sourceDomain);
    downloadPoster(canvas);
    showToast(card, "已下载");
    onClose();
  });

  const cancelBtn = document.createElement("button");
  cancelBtn.textContent = "取消";
  cancelBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    onClose();
  });

  dialog.appendChild(copyBtn);
  dialog.appendChild(downloadBtn);
  dialog.appendChild(cancelBtn);
  return dialog;
}

function showToast(parent: HTMLElement, text: string): void {
  const toast = document.createElement("div");
  toast.className = "vr-toast";
  toast.textContent = text;
  parent.appendChild(toast);
  setTimeout(() => toast.remove(), 2000);
}
```

- [ ] **Step 4: Update caller in `content/index.ts` to pass `sourceDomain`**

Open `extension/src/content/index.ts`. Find the `onIconClick` function where `renderVibeCard` is called:

```typescript
currentCard = renderVibeCard({
  parent: currentIcon,
  result,
  onClose: clearUi,
});
```

Change to:

```typescript
currentCard = renderVibeCard({
  parent: currentIcon,
  result,
  sourceDomain: domain,
  onClose: clearUi,
});
```

The `domain` variable is already in scope from the function parameter `async function onIconClick(text: string, domain: Domain)`.

- [ ] **Step 5: Build and verify**

```bash
cd D:/qhyProject/vibe4.0/extension && npm run build
ls -l build/content.js
```
Expected: clean build, `content.js` grown by a few kb (CSS + SharePoster code).

- [ ] **Step 6: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/src/content/ui/SharePoster.ts extension/src/content/ui/VibeCard.ts extension/src/content/ui/styles.css extension/src/content/index.ts
git commit -m "feat(ext): add Canvas 2D share poster with clipboard and download"
```
Expected: 30 commits.

---

## Task 8: RecommendCard + "> 寻找同频代餐" link in VibeCard

**Files:**
- Create: `extension/src/content/ui/RecommendCard.ts`
- Modify: `extension/src/content/ui/VibeCard.ts`
- Modify: `extension/src/content/ui/styles.css`

- [ ] **Step 1: Create `extension/src/content/ui/RecommendCard.ts`**

```typescript
import { send } from "../../shared/api";
import type { Domain, Msg, RecommendItem, RecommendResult } from "../../shared/types";

const DOMAIN_EMOJI: Record<Domain, string> = {
  book: "📚",
  movie: "🎬",
  game: "🎮",
  music: "🎵",
};

export interface RecommendCardProps {
  parent: HTMLElement;
  text: string;
  sourceDomain: Domain;
  matchedTagIds: number[];
}

export function renderRecommendCard(props: RecommendCardProps): HTMLElement {
  const card = document.createElement("div");
  card.className = "vr-card vr-recommend-card";
  const body = document.createElement("div");
  body.className = "vr-recommend-body";
  card.appendChild(body);

  const rerollBtn = document.createElement("button");
  rerollBtn.className = "vr-btn vr-reroll";
  rerollBtn.textContent = "换一批 ↻";
  rerollBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    await loadAndRender(body, rerollBtn, props);
  });
  card.appendChild(rerollBtn);

  props.parent.appendChild(card);
  void loadAndRender(body, rerollBtn, props);

  return card;
}

async function loadAndRender(
  body: HTMLElement,
  btn: HTMLButtonElement,
  props: RecommendCardProps,
): Promise<void> {
  btn.disabled = true;
  body.innerHTML = "";
  const loading = document.createElement("div");
  loading.className = "vr-recommend-loading";
  loading.textContent = "代餐官思考中…";
  body.appendChild(loading);

  const msg: Msg = {
    type: "RECOMMEND",
    payload: {
      text: props.text,
      sourceDomain: props.sourceDomain,
      matchedTagIds: props.matchedTagIds,
    },
  };

  try {
    const result = await send<RecommendResult>(msg);
    body.innerHTML = "";
    for (const item of result.items) {
      body.appendChild(renderItem(item));
    }
  } catch (e: any) {
    body.innerHTML = "";
    const err = document.createElement("div");
    err.className = "vr-recommend-error";
    err.textContent = e?.message?.includes("NO_CROSS_DOMAIN")
      ? "这次没灵感，换一个物品试试"
      : "代餐官去冲咖啡了，稍后再试";
    body.appendChild(err);
  } finally {
    btn.disabled = false;
  }
}

function renderItem(item: RecommendItem): HTMLElement {
  const row = document.createElement("div");
  row.className = "vr-recommend-item";
  const head = document.createElement("div");
  head.className = "vr-recommend-name";
  head.textContent = `${DOMAIN_EMOJI[item.domain]} ${item.name}`;
  const reason = document.createElement("div");
  reason.className = "vr-recommend-reason";
  reason.textContent = item.reason;
  row.appendChild(head);
  row.appendChild(reason);
  return row;
}
```

- [ ] **Step 2: Add CSS classes for RecommendCard**

Append to `extension/src/content/ui/styles.css`:

```css
.vr-recommend-link {
  display: block;
  margin-top: 10px;
  font-size: 11px;
  color: #999;
  cursor: pointer;
  text-align: right;
  transition: color 0.15s;
}
.vr-recommend-link:hover { color: #6c5ce7; }

.vr-recommend-card {
  margin-top: 8px;
  position: relative;
  top: auto;
  left: auto;
  background: #f8f7ff;
  border: 1px solid rgba(108, 92, 231, 0.16);
}

.vr-recommend-body { display: flex; flex-direction: column; gap: 10px; }

.vr-recommend-item {
  padding: 8px 0;
  border-bottom: 1px dashed rgba(108, 92, 231, 0.12);
}
.vr-recommend-item:last-child { border-bottom: none; }

.vr-recommend-name {
  font-size: 13px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 3px;
}
.vr-recommend-reason {
  font-size: 11px;
  color: #666;
  line-height: 1.4;
}

.vr-recommend-loading { color: #888; font-size: 12px; padding: 8px 0; text-align: center; }
.vr-recommend-error { color: #d63031; font-size: 12px; padding: 8px 0; text-align: center; }

.vr-reroll {
  margin-top: 10px;
  width: 100%;
  background: #f0edff;
  color: #6c5ce7;
}
.vr-reroll:disabled { opacity: 0.5; cursor: not-allowed; }
```

- [ ] **Step 3: Add the "> 寻找同频代餐" link to VibeCard**

Open `extension/src/content/ui/VibeCard.ts`. At the top, add an import:

```typescript
import { renderRecommendCard } from "./RecommendCard";
```

The existing function body ends with the actions div and `return card;`. Right before `return card;`, insert:

```typescript
  // Recommend link (lazy trigger)
  const recommendLink = document.createElement("a");
  recommendLink.className = "vr-recommend-link";
  recommendLink.textContent = "> 寻找同频代餐";
  recommendLink.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    recommendLink.style.display = "none";
    renderRecommendCard({
      parent: card,
      text: props.text,
      sourceDomain,
      matchedTagIds: result.matched_tags.map((t) => t.tag_id),
    });
  });
  card.appendChild(recommendLink);
```

Note: this references `props.text`, which means `VibeCardProps` needs a `text` field. Update the interface:

```typescript
export interface VibeCardProps {
  parent: HTMLElement;
  result: AnalyzeResult;
  sourceDomain: Domain;
  text: string;
  onClose: () => void;
}
```

And in the function destructuring:

```typescript
export function renderVibeCard(props: VibeCardProps): HTMLElement {
  const { parent, result, sourceDomain, onClose } = props;
```

Change to:

```typescript
export function renderVibeCard(props: VibeCardProps): HTMLElement {
  const { parent, result, sourceDomain, text, onClose } = props;
```

And inside the recommend link handler use `text` directly:

```typescript
    renderRecommendCard({
      parent: card,
      text,
      sourceDomain,
      matchedTagIds: result.matched_tags.map((t) => t.tag_id),
    });
```

- [ ] **Step 4: Update `content/index.ts` to pass `text`**

Open `extension/src/content/index.ts`. Find the existing `renderVibeCard` call:

```typescript
currentCard = renderVibeCard({
  parent: currentIcon,
  result,
  sourceDomain: domain,
  onClose: clearUi,
});
```

Change to:

```typescript
currentCard = renderVibeCard({
  parent: currentIcon,
  result,
  sourceDomain: domain,
  text,
  onClose: clearUi,
});
```

The `text` variable is already in scope from the enclosing `async function onIconClick(text: string, domain: Domain)`.

- [ ] **Step 5: Build**

```bash
cd D:/qhyProject/vibe4.0/extension && npm run build
```
Expected: clean build.

- [ ] **Step 6: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/src/content/ui/RecommendCard.ts extension/src/content/ui/VibeCard.ts extension/src/content/ui/styles.css extension/src/content/index.ts
git commit -m "feat(ext): add cross-domain RecommendCard with lazy trigger link"
```
Expected: 31 commits.

---

## Task 9: SMOKE.md updates + final full-suite verification

**Files:**
- Modify: `extension/SMOKE.md`

- [ ] **Step 1: Extend `extension/SMOKE.md`**

Open `extension/SMOKE.md`. After the existing "7. Out-of-whitelist sites" step, append three new steps:

```markdown
### 8. Roast display (V1.1)
- Highlight text on 豆瓣电影 → click icon → wait for rate card
- Expected: a **bold purple roast line** appears as the prominent copy (30-50 chars)
- Below the roast, an **italic grey summary** (smaller) is still visible
- The roast should reference the current domain's metaphor (影院睡着 / 摔手柄 / 翻不过30页 / 塞满棉花)
- If roast cannot generate (backend glitch), the grey summary should promote to primary styling instead — never show an empty card

### 9. Cross-domain recommendation (V1.1)
- Rate something → click the small grey "> 寻找同频代餐" link at the bottom of the card
- Expected: the link disappears, a sub-card appears below with a "代餐官思考中…" placeholder
- After ~2-5 seconds, 3 items appear, each with a distinct domain emoji (📚🎬🎮🎵)
- **None of the 3 items must be from the source domain** — on `movie.douban.com`, zero 🎬 items; on `store.steampowered.com`, zero 🎮 items
- Click "换一批 ↻" → button disables briefly → new 3 items (different from previous)
- If the LLM keeps returning same-domain items, the card should show "这次没灵感，换一个物品试试"

### 10. Share poster (V1.1)
- On a rated card, click the [📤] button in the top-right
- Expected: a mini dialog with three buttons: "📋 复制到剪贴板", "💾 下载 PNG", "取消"
- Click 复制 → a toast "已复制到剪贴板" appears briefly at the bottom of the card
- Open WeChat / mspaint / any image-accepting target and paste → a 1080×1080 PNG with purple gradient background, the match score, tags, roast text, and "Vibe-Radar" wordmark should appear
- Click 下载 → a file named `vibe-radar-<timestamp>.png` downloads; open it to verify the same layout
- If clipboard permission is denied, a toast "剪贴板失败，已自动下载" appears and the file downloads automatically

## Pass criteria
All 10 steps complete without any JavaScript console errors in either the background worker or the content script.
```

Also update the top "Prereqs" section so step 4 notes that **both** LLM calls (tagger AND roaster) need a working API key now — adjust its wording from:

```
4. `backend/.env` configured with a real LLM API key (only needed for step 4)
```

to:

```
4. `backend/.env` configured with a real LLM API key (needed for steps 3-10; V1.1 adds roast + recommendation calls that also hit the LLM)
```

- [ ] **Step 2: Run the final full backend test suite**

```bash
cd D:/qhyProject/vibe4.0/backend && source .venv/Scripts/activate && pytest tests/ -v
```
Expected: 51 passing.

- [ ] **Step 3: Run the final extension build**

```bash
cd D:/qhyProject/vibe4.0/extension && npm run build
ls -l build/
ls -l build/popup/
```
Expected: `background.js` / `content.js` / `popup/popup.js` all present. `content.js` grew to ~20-25 kb due to SharePoster + RecommendCard.

- [ ] **Step 4: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/SMOKE.md
git commit -m "docs: extend SMOKE.md with V1.1 manual checks (roast/recommend/poster)"
git log --oneline | head -10
```
Expected: 32 commits total, HEAD at the SMOKE.md commit.

---

## Post-implementation checklist

- [ ] `pytest tests/ -v` runs 51 tests, all green
- [ ] `npm run build` succeeds with zero TypeScript errors
- [ ] Extension reloaded in Chrome, 豆瓣/Steam/网易云 page refreshed
- [ ] SMOKE steps 1-7 still pass (no V1.0 regression)
- [ ] SMOKE steps 8-10 pass (new V1.1 features)
- [ ] `git log --oneline` shows 32 commits total, V1.1 commits 24-32 match the task numbers above

---

## Appendix — V1.1 known limitations (carry forward as Non-Goals)

1. **Recommendations are stateless** — the backend never persists what was recommended; "换一批" is free-form LLM re-generation with no de-duplication across calls
2. **Roast never caches** — every `/analyze` call pays for a fresh roaster LLM round-trip even on tagger cache hits; cost scales linearly with usage
3. **Poster fonts rely on system-ui / PingFang SC** — on minimal Windows installs without PingFang SC, Canvas falls back to Microsoft YaHei or even Arial, which may render CJK less elegantly
4. **Clipboard API permission** is not prompted ahead of time — users see the fallback "已自动下载" toast once, then know to use the download button
5. **Recommend endpoint has no rate limit** — users spamming "换一批" would run up LLM cost; acceptable for V1.1 single-user local build
6. **F4 profile drift alerts** still deferred to V1.2+
