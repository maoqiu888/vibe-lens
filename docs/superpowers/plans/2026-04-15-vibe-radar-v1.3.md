# Vibe-Radar V1.3 SP-E Implementation Plan — MBTI Fast-Track + Personality Agent

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the cold-start friction of V1.2 with an optional MBTI + constellation quiz at first popup open, backed by a new `llm_personality_agent` that translates the user's personality into both (a) initial `core_weight` seeds on 24 internal tags and (b) a natural-language summary that becomes the roaster's `user_taste_hint`. Additionally rename VibeCard action buttons from "懂我/踩雷" to "我喜欢/我不喜欢", delete the tag pill display, and add a one-time onboarding hint under the action row.

**Architecture:** A new backend table `user_personality` stores MBTI/constellation/LLM summary per user. A new service `llm_personality_agent` wraps one LLM call that returns both a `tag_seeds` array (for DB seeding via the existing `apply_core_delta` path) and a `personality_summary` (for the roaster's taste hint). A new route `POST /api/v1/personality/submit` is called once at cold-start from a new popup quiz page. The analyze route prefers `user_personality.summary` over the V1.2 tag-description fallback. The VibeCard has three surgical changes (button text, tag pill deletion, onboarding hint); internal action names stay `"star"`/`"bomb"` so backend is unchanged there.

**Tech Stack:** Same as V1.2 — Python 3.10+ / FastAPI / SQLAlchemy / pytest / httpx / TypeScript / esbuild / Chrome MV3. Zero new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-15-vibe-radar-v1.3-design.md`

**Prereqs:**
- V1.2 is complete at commit `edcaa7a` or later (the full roaster surgical fix)
- Current HEAD is `1741bc4` (V1.3 spec commit)
- Git log shows 49 commits total
- `backend/.venv` set up with existing deps
- `extension/node_modules` installed
- Before any manual smoke testing: delete `backend/data/vibe_radar.db` and rerun `python -m app.services.seed`

**Conventions (inherited from V1.0-V1.2):**
- Strict TDD for backend: failing test → run → implement → run passing → commit
- Extension: no automated tests; verify via `npm run build` + manual SMOKE.md
- Attribute-access DB convention: `from app import database; database.SessionLocal()`, never `from app.database import SessionLocal`
- Conventional commits
- pytest from `backend/` with venv activated

**Test count arithmetic:**
- V1.2 end: 68 tests (66 + 2 new from roaster tag-leak regression)
- Task 1 extends test_models.py → 68 (same count, just new assertion)
- Task 2 adds test_llm_personality_agent.py (10 tests) → 78
- Task 4 adds test_personality_router.py (7 tests) → 85
- Task 5 adds test_vibe.py extensions (3 tests) → 88
- Task 6 adds test_profile.py extension (1 test) → 89
- Total: ~89 tests green at end

**File structure map (cumulative — bold = new in V1.3):**

```
backend/app/
├── models/
│   ├── **user_personality.py**       (V1.3 Task 1 NEW)
│   └── __init__.py                   (V1.3 Task 1 MODIFY — add UserPersonality)
├── services/
│   ├── **llm_personality_agent.py**  (V1.3 Task 2 NEW)
│   └── (others unchanged)
├── schemas/
│   └── **personality.py**            (V1.3 Task 3 NEW)
├── routers/
│   ├── **personality.py**            (V1.3 Task 4 NEW)
│   ├── vibe.py                       (V1.3 Task 5 MODIFY — taste_hint priority)
│   └── profile.py                    (V1.3 Task 6 MODIFY — has_personality flag)
└── main.py                           (V1.3 Task 4 MODIFY — include personality router)

backend/tests/
├── test_models.py                    (V1.3 Task 1 extend)
├── **test_llm_personality_agent.py** (V1.3 Task 2 NEW)
├── **test_personality_router.py**    (V1.3 Task 4 NEW)
├── test_vibe.py                      (V1.3 Task 5 extend)
└── test_profile.py                   (V1.3 Task 6 extend)

extension/src/
├── shared/
│   └── types.ts                      (V1.3 Task 7 MODIFY)
├── background/
│   └── index.ts                      (V1.3 Task 7 MODIFY)
├── popup/
│   ├── **personality.ts**            (V1.3 Task 8 NEW)
│   ├── popup.ts                      (V1.3 Task 8 MODIFY — three-stage routing)
│   └── popup.css                     (V1.3 Task 8 MODIFY — quiz styles)
└── content/
    └── ui/
        ├── VibeCard.ts               (V1.3 Task 9 MODIFY)
        └── styles.css                (V1.3 Task 9 MODIFY — onboarding hint)

extension/SMOKE.md                    (V1.3 Task 10 MODIFY — add steps 14-18)
```

---

## Task 1: `user_personality` model + registration

**Files:**
- Create: `backend/app/models/user_personality.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: Create `backend/app/models/user_personality.py`**

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserPersonality(Base):
    __tablename__ = "user_personality"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True
    )
    mbti: Mapped[str | None] = mapped_column(String(4), nullable=True)
    constellation: Mapped[str | None] = mapped_column(String(16), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
```

- [ ] **Step 2: Register in `backend/app/models/__init__.py`**

Read the current file. It should look like:

```python
from app.models.action_log import ActionLog
from app.models.analysis_cache import AnalysisCache
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.models.vibe_tag import VibeTag

__all__ = ["User", "VibeTag", "UserVibeRelation", "AnalysisCache", "ActionLog"]
```

Add the import and extend `__all__`:

```python
from app.models.action_log import ActionLog
from app.models.analysis_cache import AnalysisCache
from app.models.user import User
from app.models.user_personality import UserPersonality
from app.models.user_vibe_relation import UserVibeRelation
from app.models.vibe_tag import VibeTag

__all__ = [
    "User", "VibeTag", "UserVibeRelation", "AnalysisCache", "ActionLog",
    "UserPersonality",
]
```

- [ ] **Step 3: Extend `backend/tests/test_models.py` with a UserPersonality round-trip**

Open `backend/tests/test_models.py`. Find the existing `test_tables_are_created_and_basic_crud_works` function. At the top of the file, add this import alongside other model imports:

```python
from app.models.user_personality import UserPersonality
```

Then find the block of assertions after `db.commit()` (below the existing V1.2 `interaction_count == 0` assertion). Add these new lines RIGHT AFTER the existing assertions but BEFORE `db.close()`:

```python
    # V1.3: UserPersonality lazy-creates one row per user
    up = UserPersonality(
        user_id=1,
        mbti="INTP",
        constellation="双鱼座",
        summary="这个人是典型的深度思考者，同时保有柔软的内心。",
    )
    db.add(up)
    db.commit()
    stored = db.scalar(select(UserPersonality).where(UserPersonality.user_id == 1))
    assert stored is not None
    assert stored.mbti == "INTP"
    assert stored.constellation == "双鱼座"
    assert stored.summary.startswith("这个人")
```

- [ ] **Step 4: Run the model test**

```bash
cd D:/qhyProject/vibe4.0/backend && source .venv/Scripts/activate && pytest tests/test_models.py -v
```
Expected: 1 passing. The single `test_tables_are_created_and_basic_crud_works` test now exercises all 6 tables including `user_personality`.

- [ ] **Step 5: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/models/user_personality.py backend/app/models/__init__.py backend/tests/test_models.py
git commit -m "feat(backend): add user_personality model for V1.3 MBTI fast-track"
git log --oneline | head -3
```
Expected: 50 commits total, new commit on top of `1741bc4`.

---

## Task 2: `llm_personality_agent` service with 9 TDD tests

**Files:**
- Create: `backend/app/services/llm_personality_agent.py`
- Create: `backend/tests/test_llm_personality_agent.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_llm_personality_agent.py`:

```python
import json

import httpx
import pytest

from app.services import llm_personality_agent
from app.services.seed import seed_all


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


async def test_both_inputs_happy_path():
    seed_all()  # needs vibe_tags table populated for _load_tag_pool_json
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [
            {"tag_id": 11, "weight": 15},
            {"tag_id": 12, "weight": 10},
            {"tag_id": 9, "weight": -10},
        ],
        "personality_summary": (
            "这个朋友是典型的深度思考者，逻辑敏锐但情感上其实柔软。"
            "喜欢独处但不排斥有趣的人。看东西偏爱能引发思考的内容。"
        ),
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="INTP",
        constellation="双鱼座",
        llm_call=fake,
    )
    assert fake.calls == 1
    assert "INTP" in fake.last_prompt
    assert "双鱼座" in fake.last_prompt
    assert len(result["tag_seeds"]) == 3
    assert result["tag_seeds"][0] == {"tag_id": 11, "weight": 15.0}
    assert result["personality_summary"].startswith("这个朋友")


async def test_mbti_only_still_works():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [{"tag_id": 1, "weight": 5}],
        "personality_summary": "一个简约派。" * 10,  # >50 chars
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="ISTJ",
        constellation=None,
        llm_call=fake,
    )
    assert "ISTJ" in fake.last_prompt
    assert "双鱼座" not in fake.last_prompt
    assert len(result["tag_seeds"]) == 1


async def test_empty_inputs_raise_empty_error():
    with pytest.raises(llm_personality_agent.PersonalityAgentEmptyError):
        await llm_personality_agent.analyze_personality(
            mbti=None,
            constellation=None,
            llm_call=FakeLLM(response="unused"),
        )


async def test_llm_exception_returns_empty_result():
    seed_all()
    fake = FakeLLM(raise_exc=RuntimeError("boom"))
    result = await llm_personality_agent.analyze_personality(
        mbti="ENFP",
        constellation=None,
        llm_call=fake,
    )
    assert result == {"tag_seeds": [], "personality_summary": ""}


async def test_json_parse_failure_returns_empty_result():
    seed_all()
    fake = FakeLLM(response="not valid json")
    result = await llm_personality_agent.analyze_personality(
        mbti="ENFP",
        constellation=None,
        llm_call=fake,
    )
    assert result == {"tag_seeds": [], "personality_summary": ""}


async def test_weight_out_of_range_is_clamped():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [
            {"tag_id": 1, "weight": 30},     # too high → 15
            {"tag_id": 2, "weight": -100},   # too low → -15
            {"tag_id": 3, "weight": 5},      # OK
        ],
        "personality_summary": "这个人喜欢简单的东西。" * 3,
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="ISFJ", constellation=None, llm_call=fake,
    )
    weights = {s["tag_id"]: s["weight"] for s in result["tag_seeds"]}
    assert weights[1] == 15.0
    assert weights[2] == -15.0
    assert weights[3] == 5.0


async def test_more_than_8_seeds_truncated():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [{"tag_id": i, "weight": 5} for i in range(1, 15)],
        "personality_summary": "一个贪心的人。" * 5,
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="ENTP", constellation=None, llm_call=fake,
    )
    assert len(result["tag_seeds"]) == 8


async def test_duplicate_tag_ids_deduped():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [
            {"tag_id": 5, "weight": 10},
            {"tag_id": 5, "weight": -10},  # dup → dropped
            {"tag_id": 6, "weight": 8},
        ],
        "personality_summary": "这个人比较简单。" * 4,
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="ISFP", constellation=None, llm_call=fake,
    )
    ids = [s["tag_id"] for s in result["tag_seeds"]]
    assert ids.count(5) == 1
    assert 6 in ids
    # First occurrence wins
    first_five = next(s for s in result["tag_seeds"] if s["tag_id"] == 5)
    assert first_five["weight"] == 10.0


async def test_invalid_tag_id_dropped():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [
            {"tag_id": 100, "weight": 15},  # out of range → dropped
            {"tag_id": 0, "weight": 10},    # out of range → dropped
            {"tag_id": 15, "weight": 8},    # OK
        ],
        "personality_summary": "这个人偏好奇观。" * 4,
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="ESFP", constellation=None, llm_call=fake,
    )
    assert len(result["tag_seeds"]) == 1
    assert result["tag_seeds"][0]["tag_id"] == 15


async def test_empty_summary_returns_blank_summary():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [{"tag_id": 1, "weight": 5}],
        "personality_summary": "太短了",  # <50 chars
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="INTJ", constellation=None, llm_call=fake,
    )
    assert result["personality_summary"] == ""
    # tag_seeds should still be preserved
    assert len(result["tag_seeds"]) == 1
```

- [ ] **Step 2: Run to verify failure**

```bash
cd D:/qhyProject/vibe4.0/backend && source .venv/Scripts/activate && pytest tests/test_llm_personality_agent.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.llm_personality_agent'`.

- [ ] **Step 3: Create `backend/app/services/llm_personality_agent.py`**

```python
import json
from typing import Awaitable, Callable

import httpx

from app.config import settings

LlmCallable = Callable[[str, str], Awaitable[str]]

MAX_TAG_SEEDS = 8
WEIGHT_MIN = -15.0
WEIGHT_MAX = 15.0
SUMMARY_MIN_LEN = 30
SUMMARY_MAX_LEN = 400


class PersonalityAgentEmptyError(Exception):
    """Raised when neither MBTI nor constellation is supplied."""


_SYSTEM_PROMPT_TEMPLATE = """你是 Vibe-Radar 的"性格翻译官"。用户给你他的 MBTI 和/或星座，你要做两件事：

1. 从固定的 24 个"品味标签池"里选出最多 8 个对他显著的标签，并给每个 -15 到 +15 的权重（正数 = 他会喜欢这种内容，负数 = 他会讨厌）。只给你确信的；不确信的不要出现。
2. 用 100-200 字的自然大白话描述这个人的审美倾向和性格，像在跟一个不认识他的朋友介绍他。描述里不要提 MBTI、星座的术语缩写，也不要用品味标签池里的词汇——你只是在用日常语言描述。

【品味标签池】（你只能在 tag_seeds 的 tag_id 字段里引用这些 id）：
{tag_pool_json}

【输出格式】严格 JSON，不要 markdown 代码块：
{{"tag_seeds": [{{"tag_id": 11, "weight": 15}}, ...], "personality_summary": "这个人..."}}

【硬规则】
- tag_seeds 长度 ≤ 8
- 每个 weight ∈ [-15, 15]，且 tag_id ∈ [1, 24]
- personality_summary 长度 50-300 字
- 不要解释你的推理过程，只输出 JSON
"""


def _build_user_prompt(mbti: str | None, constellation: str | None) -> str:
    parts = []
    if mbti:
        parts.append(f"MBTI：{mbti}")
    if constellation:
        parts.append(f"星座：{constellation}")
    context = "、".join(parts) if parts else "（没有提供）"
    return (
        f"用户告诉你的信息：{context}\n\n"
        f"请按格式输出 tag_seeds 和 personality_summary。"
    )


def _load_tag_pool_json() -> str:
    """Build the tag pool JSON to inject into the system prompt."""
    from sqlalchemy import select

    from app import database
    from app.models.vibe_tag import VibeTag

    db = database.SessionLocal()
    try:
        tags = db.scalars(select(VibeTag).order_by(VibeTag.id)).all()
        return json.dumps(
            [
                {"id": t.id, "name": t.name, "description": t.description}
                for t in tags
            ],
            ensure_ascii=False,
        )
    finally:
        db.close()


async def _default_llm_call(system_prompt: str, user_prompt: str) -> str:
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
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def analyze_personality(
    mbti: str | None,
    constellation: str | None,
    llm_call: LlmCallable | None = None,
) -> dict:
    """Return {tag_seeds: [...], personality_summary: str}.

    Raises PersonalityAgentEmptyError iff both mbti and constellation are None.
    On any LLM or parse failure, returns {"tag_seeds": [], "personality_summary": ""}.
    """
    if not mbti and not constellation:
        raise PersonalityAgentEmptyError("neither mbti nor constellation supplied")

    llm_call = llm_call or _default_llm_call
    tag_pool_json = _load_tag_pool_json()
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(tag_pool_json=tag_pool_json)
    user_prompt = _build_user_prompt(mbti, constellation)

    try:
        raw = await llm_call(system_prompt, user_prompt)
    except Exception:
        return {"tag_seeds": [], "personality_summary": ""}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"tag_seeds": [], "personality_summary": ""}

    # Validate and filter tag_seeds
    raw_seeds = parsed.get("tag_seeds", [])
    if not isinstance(raw_seeds, list):
        raw_seeds = []

    valid_seeds: list[dict] = []
    seen_tag_ids: set[int] = set()
    for seed in raw_seeds:
        if not isinstance(seed, dict):
            continue
        tag_id = seed.get("tag_id")
        weight = seed.get("weight")
        if not isinstance(tag_id, int) or not (1 <= tag_id <= 24):
            continue
        if tag_id in seen_tag_ids:
            continue
        if not isinstance(weight, (int, float)):
            continue
        clamped = max(WEIGHT_MIN, min(WEIGHT_MAX, float(weight)))
        valid_seeds.append({"tag_id": tag_id, "weight": clamped})
        seen_tag_ids.add(tag_id)
        if len(valid_seeds) >= MAX_TAG_SEEDS:
            break

    # Validate summary
    summary = parsed.get("personality_summary", "")
    if not isinstance(summary, str):
        summary = ""
    summary = summary.strip()
    if len(summary) < SUMMARY_MIN_LEN:
        summary = ""
    elif len(summary) > SUMMARY_MAX_LEN:
        summary = summary[:SUMMARY_MAX_LEN]

    return {"tag_seeds": valid_seeds, "personality_summary": summary}
```

- [ ] **Step 4: Run the tests**

```bash
pytest tests/test_llm_personality_agent.py -v
```
Expected: 10 passing (the one "happy path" plus the 9 edge-case tests).

- [ ] **Step 5: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/services/llm_personality_agent.py backend/tests/test_llm_personality_agent.py
git commit -m "feat(backend): add llm_personality_agent service with validation + clamping"
git log --oneline | head -3
```
Expected: 51 commits.

---

## Task 3: Pydantic schemas for personality endpoint

**Files:**
- Create: `backend/app/schemas/personality.py`

- [ ] **Step 1: Create `backend/app/schemas/personality.py`**

```python
from pydantic import BaseModel, Field, field_validator

# Canonical 12 Chinese constellation names
VALID_CONSTELLATIONS = {
    "白羊座", "金牛座", "双子座", "巨蟹座",
    "狮子座", "处女座", "天秤座", "天蝎座",
    "射手座", "摩羯座", "水瓶座", "双鱼座",
}


class PersonalityRequest(BaseModel):
    mbti: str | None = Field(default=None, max_length=4)
    constellation: str | None = Field(default=None, max_length=16)

    @field_validator("mbti")
    @classmethod
    def _validate_mbti(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip().upper()
        if len(v) != 4:
            raise ValueError("MBTI must be exactly 4 letters")
        pairs = [(v[0], "IE"), (v[1], "NS"), (v[2], "TF"), (v[3], "PJ")]
        for letter, allowed in pairs:
            if letter not in allowed:
                raise ValueError(f"invalid MBTI letter at position: {letter}")
        return v

    @field_validator("constellation")
    @classmethod
    def _validate_constellation(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if v not in VALID_CONSTELLATIONS:
            raise ValueError("constellation must be one of the 12 canonical names")
        return v


class PersonalityResponse(BaseModel):
    status: str        # "ok" | "skipped"
    seeded_tag_count: int
    summary: str       # empty string if skipped or LLM failed
```

- [ ] **Step 2: Verify schemas import cleanly**

```bash
cd D:/qhyProject/vibe4.0/backend && source .venv/Scripts/activate
python -c "from app.schemas.personality import PersonalityRequest, PersonalityResponse, VALID_CONSTELLATIONS; print(f'{len(VALID_CONSTELLATIONS)} constellations')"
```
Expected: `12 constellations`.

Also verify validators work:

```bash
python -c "
from app.schemas.personality import PersonalityRequest
# valid
r = PersonalityRequest(mbti='INTP', constellation='双鱼座')
print(f'valid: mbti={r.mbti}, constellation={r.constellation}')
# empty strings become None
r = PersonalityRequest(mbti='', constellation='')
print(f'empty: mbti={r.mbti}, constellation={r.constellation}')
# lowercase is normalized to upper
r = PersonalityRequest(mbti='intp', constellation='双鱼座')
print(f'normalized: mbti={r.mbti}')
# invalid mbti raises
try:
    PersonalityRequest(mbti='XXXX', constellation=None)
except Exception as e:
    print(f'XXXX rejected: {type(e).__name__}')
# invalid constellation raises
try:
    PersonalityRequest(mbti=None, constellation='未知座')
except Exception as e:
    print(f'未知座 rejected: {type(e).__name__}')
"
```
Expected output:
```
valid: mbti=INTP, constellation=双鱼座
empty: mbti=None, constellation=None
normalized: mbti=INTP
XXXX rejected: ValidationError
未知座 rejected: ValidationError
```

- [ ] **Step 3: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/schemas/personality.py
git commit -m "feat(backend): add personality schemas with MBTI/constellation validators"
```
Expected: 52 commits.

---

## Task 4: `/api/v1/personality/submit` router + 7 tests + main.py wiring

**Files:**
- Create: `backend/app/routers/personality.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_personality_router.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_personality_router.py`:

```python
import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.main import app
from app.models.action_log import ActionLog
from app.models.user import User
from app.models.user_personality import UserPersonality
from app.models.user_vibe_relation import UserVibeRelation
from app.services.seed import seed_all

client = TestClient(app)


def _install_fake_agent(monkeypatch, tag_seeds, summary):
    async def fake(system_prompt, user_prompt):
        return json.dumps({
            "tag_seeds": tag_seeds,
            "personality_summary": summary,
        })
    from app.services import llm_personality_agent
    monkeypatch.setattr(llm_personality_agent, "_default_llm_call", fake)


def test_skip_both_fields_returns_skipped_and_writes_null_row():
    seed_all()
    r = client.post("/api/v1/personality/submit", json={
        "mbti": None,
        "constellation": None,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "skipped"
    assert body["seeded_tag_count"] == 0
    assert body["summary"] == ""

    db = database.SessionLocal()
    row = db.scalar(select(UserPersonality).where(UserPersonality.user_id == 1))
    assert row is not None
    assert row.mbti is None
    assert row.constellation is None
    assert row.summary is None
    db.close()


def test_submit_mbti_only_writes_row_and_seeds_tags(monkeypatch):
    seed_all()
    _install_fake_agent(
        monkeypatch,
        tag_seeds=[
            {"tag_id": 11, "weight": 15},
            {"tag_id": 12, "weight": 10},
        ],
        summary="这个朋友是典型的深度思考者。" * 3,  # ~54 chars, passes min 30
    )
    r = client.post("/api/v1/personality/submit", json={
        "mbti": "INTP",
        "constellation": None,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["seeded_tag_count"] == 2
    assert body["summary"].startswith("这个朋友")

    db = database.SessionLocal()
    # personality row stored
    row = db.scalar(select(UserPersonality).where(UserPersonality.user_id == 1))
    assert row.mbti == "INTP"
    assert row.constellation is None
    assert row.summary.startswith("这个朋友")

    # user_vibe_relations seeded with core_weight via apply_core_delta
    rel11 = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 11,
        )
    )
    assert rel11.core_weight == 15.0

    rel12 = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 12,
        )
    )
    assert rel12.core_weight == 10.0

    # action_log records personality_seed action per tag
    logs = db.scalars(
        select(ActionLog).where(ActionLog.action == "personality_seed")
    ).all()
    assert len(logs) == 2

    # interaction_count is NOT bumped by personality_seed
    user = db.scalar(select(User).where(User.id == 1))
    assert user.interaction_count == 0
    db.close()


def test_submit_constellation_only_also_works(monkeypatch):
    seed_all()
    _install_fake_agent(
        monkeypatch,
        tag_seeds=[{"tag_id": 5, "weight": 8}],
        summary="一个比较感性的人喜欢温暖柔和的东西。" * 2,
    )
    r = client.post("/api/v1/personality/submit", json={
        "mbti": None,
        "constellation": "双鱼座",
    })
    assert r.status_code == 200
    assert r.json()["seeded_tag_count"] == 1


def test_already_submitted_returns_400(monkeypatch):
    seed_all()
    # First submission — skip
    client.post("/api/v1/personality/submit", json={
        "mbti": None, "constellation": None,
    })
    # Second submission attempt
    r = client.post("/api/v1/personality/submit", json={
        "mbti": "INTP", "constellation": None,
    })
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "ALREADY_SUBMITTED"


def test_invalid_mbti_format_returns_422():
    seed_all()
    r = client.post("/api/v1/personality/submit", json={
        "mbti": "XXXX",
        "constellation": None,
    })
    assert r.status_code == 422


def test_invalid_constellation_returns_422():
    seed_all()
    r = client.post("/api/v1/personality/submit", json={
        "mbti": None,
        "constellation": "未知座",
    })
    assert r.status_code == 422


def test_llm_failure_still_persists_empty_row(monkeypatch):
    seed_all()
    async def broken(system_prompt, user_prompt):
        raise RuntimeError("timeout")
    from app.services import llm_personality_agent
    monkeypatch.setattr(llm_personality_agent, "_default_llm_call", broken)

    r = client.post("/api/v1/personality/submit", json={
        "mbti": "INTP",
        "constellation": None,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["seeded_tag_count"] == 0
    assert body["summary"] == ""

    # Row still persisted with empty summary — re-submission blocked
    db = database.SessionLocal()
    row = db.scalar(select(UserPersonality).where(UserPersonality.user_id == 1))
    assert row is not None
    assert row.mbti == "INTP"
    assert row.summary is None or row.summary == ""
    db.close()

    # Retry blocked
    r2 = client.post("/api/v1/personality/submit", json={
        "mbti": "ENFP", "constellation": None,
    })
    assert r2.status_code == 400
```

- [ ] **Step 2: Run to verify failures**

```bash
pytest tests/test_personality_router.py -v
```
Expected: All 7 tests fail with 404 (route doesn't exist) or ImportError.

- [ ] **Step 3: Create `backend/app/routers/personality.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db
from app.models.user import User
from app.models.user_personality import UserPersonality
from app.schemas.personality import PersonalityRequest, PersonalityResponse
from app.services import llm_personality_agent, profile_calc

router = APIRouter(prefix="/api/v1/personality", tags=["personality"])

PERSONALITY_SEED_ACTION = "personality_seed"


@router.post("/submit", response_model=PersonalityResponse)
async def submit(
    payload: PersonalityRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    # Lazy-create user row if missing
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        user = User(id=user_id, username="default", interaction_count=0)
        db.add(user)
        db.flush()

    # Reject resubmission
    existing = db.scalar(
        select(UserPersonality).where(UserPersonality.user_id == user_id)
    )
    if existing is not None:
        raise HTTPException(
            status_code=400,
            detail={"error": {
                "code": "ALREADY_SUBMITTED",
                "message": "personality profile already submitted; cannot resubmit in V1.3",
            }},
        )

    # Short-circuit if both fields empty — write null row and return "skipped"
    if payload.mbti is None and payload.constellation is None:
        db.add(UserPersonality(
            user_id=user_id, mbti=None, constellation=None, summary=None,
        ))
        db.commit()
        return PersonalityResponse(
            status="skipped",
            seeded_tag_count=0,
            summary="",
        )

    # Call the agent
    try:
        result = await llm_personality_agent.analyze_personality(
            mbti=payload.mbti,
            constellation=payload.constellation,
        )
    except llm_personality_agent.PersonalityAgentEmptyError:
        # Defensive — should have been caught by the short-circuit above
        return PersonalityResponse(
            status="skipped",
            seeded_tag_count=0,
            summary="",
        )

    tag_seeds = result["tag_seeds"]
    summary = result["personality_summary"]

    # Apply tag seeds via profile_calc — uses existing lazy-create _apply_delta
    for seed in tag_seeds:
        profile_calc.apply_core_delta(
            user_id=user_id,
            tag_ids=[seed["tag_id"]],
            delta=seed["weight"],
            action=PERSONALITY_SEED_ACTION,
        )

    # Persist personality row AFTER seeds are written
    db.add(UserPersonality(
        user_id=user_id,
        mbti=payload.mbti,
        constellation=payload.constellation,
        summary=summary if summary else None,
    ))
    db.commit()

    return PersonalityResponse(
        status="ok",
        seeded_tag_count=len(tag_seeds),
        summary=summary,
    )
```

- [ ] **Step 4: Register router in `backend/app/main.py`**

Read the current `main.py`. Find the imports block. Add:

```python
from app.routers import personality
```

Find the `app.include_router(...)` calls at the bottom. Add:

```python
app.include_router(personality.router)
```

The complete imports section should look like (your existing order may vary):

```python
from app.routers import personality
from app.routers import profile
from app.routers import vibe
```

And the include block:

```python
app.include_router(vibe.router)
app.include_router(profile.router)
app.include_router(personality.router)
```

- [ ] **Step 5: Run the router tests**

```bash
pytest tests/test_personality_router.py -v
```
Expected: 7 passing.

- [ ] **Step 6: Run the full backend suite to check no regression**

```bash
pytest tests/ -v
```
Expected: ~85 passing (68 existing + 10 agent + 7 router).

- [ ] **Step 7: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/routers/personality.py backend/app/main.py backend/tests/test_personality_router.py
git commit -m "feat(backend): add /personality/submit route with lazy-create and reject-resubmit"
git log --oneline | head -3
```
Expected: 53 commits.

---

## Task 5: `analyze` route prefers `personality.summary` for `user_taste_hint`

**Files:**
- Modify: `backend/app/routers/vibe.py`
- Modify: `backend/tests/test_vibe.py`

- [ ] **Step 1: Update `backend/app/routers/vibe.py` imports**

Read the file. Find the imports. Add this new import:

```python
from app.models.user_personality import UserPersonality
```

- [ ] **Step 2: Replace the `user_taste_hint` construction block**

Find this block inside the `analyze` function (currently around step 4 "Roast"):

```python
    # 4. Roast — pass ONLY match_score + natural-language taste hint.
    #    We deliberately do NOT pass tag names to the roaster so the LLM
    #    physically cannot leak internal vocabulary into its output.
    user_taste_descriptions = profile_calc.get_top_core_tag_descriptions(
        user_id=user_id, n=2
    )
    user_taste_hint = "；".join(user_taste_descriptions)
    roast = await llm_roaster.generate_roast(
        text=payload.text,
        domain=payload.domain,
        match_score=score,
        user_taste_hint=user_taste_hint,
    )
```

Replace with:

```python
    # 4. Roast — prefer MBTI-derived personality summary if present, else
    #    fall back to V1.2's top-tag descriptions. Either way, the roaster
    #    never sees tag names — only natural language.
    user_personality = db.scalar(
        select(UserPersonality).where(UserPersonality.user_id == user_id)
    )
    if user_personality and user_personality.summary:
        user_taste_hint = user_personality.summary
    else:
        user_taste_descriptions = profile_calc.get_top_core_tag_descriptions(
            user_id=user_id, n=2
        )
        user_taste_hint = "；".join(user_taste_descriptions)

    roast = await llm_roaster.generate_roast(
        text=payload.text,
        domain=payload.domain,
        match_score=score,
        user_taste_hint=user_taste_hint,
    )
```

- [ ] **Step 3: Add 3 new tests to `backend/tests/test_vibe.py`**

Open `backend/tests/test_vibe.py`. At the top of the file, add this import:

```python
from app.models.user_personality import UserPersonality
```

Append these 3 tests at the end of the file:

```python
def test_analyze_uses_personality_summary_as_taste_hint(monkeypatch):
    """When user has a personality summary, roaster gets it as taste_hint."""
    seed_all()

    # Pre-seed a personality row
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

    captured_hint = {}

    async def capture_roaster(system_prompt, user_prompt):
        captured_hint["prompt"] = user_prompt
        return json.dumps({"roast": "test roast"})

    from app.services import llm_roaster
    monkeypatch.setattr(llm_roaster, "_default_llm_call", capture_roaster)

    client.post("/api/v1/vibe/analyze",
                json={"text": "some text", "domain": "book"})

    # Verify the roaster's prompt includes the personality summary
    assert "深度思考者" in captured_hint["prompt"]


def test_analyze_falls_back_to_tag_descriptions_without_personality(monkeypatch):
    """When user has no personality row, roaster uses V1.2 tag description fallback."""
    seed_all()
    # Prime some tag weights (no personality row)
    db = database.SessionLocal()
    db.add(User(id=1, username="default", interaction_count=1))
    db.commit()
    db.add(UserVibeRelation(
        user_id=1, vibe_tag_id=1,  # 慢炖沉浸
        curiosity_weight=0.0, core_weight=20.0,
    ))
    db.commit()
    db.close()

    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 2, "weight": 0.9}], "summary": "slow"
    }))

    captured_hint = {}

    async def capture_roaster(system_prompt, user_prompt):
        captured_hint["prompt"] = user_prompt
        return json.dumps({"roast": "test roast"})

    from app.services import llm_roaster
    monkeypatch.setattr(llm_roaster, "_default_llm_call", capture_roaster)

    client.post("/api/v1/vibe/analyze",
                json={"text": "some text", "domain": "book"})

    # Verify the fallback description from VibeTag.description landed in prompt
    # The description for 慢炖沉浸 is "节奏极慢，像咖啡馆读一下午般从容铺陈"
    assert "节奏极慢" in captured_hint["prompt"]
    # And the personality summary path was NOT used (no "深度思考者" in prompt)
    assert "深度思考者" not in captured_hint["prompt"]


def test_personality_seeds_drive_initial_match_score(monkeypatch):
    """A user with personality seeds should get non-zero match score on first analyze."""
    seed_all()
    db = database.SessionLocal()
    db.add(User(id=1, username="default", interaction_count=0))
    db.commit()
    db.add(UserPersonality(
        user_id=1, mbti="INTP", constellation=None,
        summary="一段自然语言描述。" * 5,
    ))
    # Manually apply a tag_seed as if personality agent did it
    db.add(UserVibeRelation(
        user_id=1, vibe_tag_id=11,  # 烧脑解谜
        curiosity_weight=0.0, core_weight=15.0,
    ))
    db.commit()
    db.close()

    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 11, "weight": 1.0}], "summary": "brainy"
    }))
    _install_fake_roaster(monkeypatch, "test roast")

    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "烧脑的作品", "domain": "book"})
    body = r.json()
    # With a pre-seeded core_weight on tag 11 and the item matching that tag,
    # the cosine similarity should produce a non-zero match score.
    assert body["match_score"] > 0
```

- [ ] **Step 4: Run the vibe tests**

```bash
pytest tests/test_vibe.py -v
```
Expected: all existing tests still pass plus the 3 new ones. Total for test_vibe.py: ~22 tests.

- [ ] **Step 5: Run full suite**

```bash
pytest tests/ -v
```
Expected: ~88 passing.

- [ ] **Step 6: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/routers/vibe.py backend/tests/test_vibe.py
git commit -m "feat(backend): analyze route prefers personality summary for taste hint"
```
Expected: 54 commits.

---

## Task 6: `/profile/radar` adds `has_personality` flag

**Files:**
- Modify: `backend/app/schemas/profile.py`
- Modify: `backend/app/routers/profile.py`
- Modify: `backend/tests/test_profile.py`

- [ ] **Step 1: Update `backend/app/schemas/profile.py`**

Read the file. Current `RadarResponse`:

```python
class RadarResponse(BaseModel):
    user_id: int
    interaction_count: int
    level: int
    level_title: str
    level_emoji: str
    next_level_at: int
    ui_stage: str
    dimensions: list[RadarDimension]
    total_analyze_count: int
    total_action_count: int
```

Add `has_personality: bool` field (logical place: right after `ui_stage`):

```python
class RadarResponse(BaseModel):
    user_id: int
    interaction_count: int
    level: int
    level_title: str
    level_emoji: str
    next_level_at: int
    ui_stage: str
    has_personality: bool
    dimensions: list[RadarDimension]
    total_analyze_count: int
    total_action_count: int
```

- [ ] **Step 2: Update `backend/app/routers/profile.py`**

Read the file. Add this import at the top:

```python
from app.models.user_personality import UserPersonality
```

Find the `radar` function. Its body starts with:

```python
    user = db.scalar(select(User).where(User.id == user_id))
    interaction_count = user.interaction_count if user else 0

    info = profile_calc.level_info(interaction_count)
    ui_stage = profile_calc.compute_ui_stage(info["level"])
```

Right after `ui_stage = ...`, add the personality check:

```python
    personality_row = db.scalar(
        select(UserPersonality).where(UserPersonality.user_id == user_id)
    )
    has_personality = personality_row is not None
```

Then find the `return RadarResponse(...)` call at the end of the function. Add `has_personality=has_personality` to the kwargs:

```python
    return RadarResponse(
        user_id=user_id,
        interaction_count=interaction_count,
        level=info["level"],
        level_title=info["title"],
        level_emoji=info["emoji"],
        next_level_at=info["next_level_at"],
        ui_stage=ui_stage,
        has_personality=has_personality,
        dimensions=dimensions,
        total_analyze_count=total_analyze,
        total_action_count=total_action,
    )
```

- [ ] **Step 3: Add test to `backend/tests/test_profile.py`**

Open `backend/tests/test_profile.py`. At the top, add this import:

```python
from app.models.user_personality import UserPersonality
```

Append this new test at the end:

```python
def test_radar_response_includes_has_personality_flag():
    """The radar endpoint must expose has_personality so frontend can decide
    whether to show the quiz page, welcome page, or radar page."""
    seed_all()

    # Brand-new user — no personality row
    r = client.get("/api/v1/profile/radar")
    body = r.json()
    assert body["has_personality"] is False

    # Submit personality (any shape, skip path is fine)
    client.post("/api/v1/personality/submit", json={
        "mbti": None, "constellation": None,
    })

    # Now the flag flips
    r2 = client.get("/api/v1/profile/radar")
    body2 = r2.json()
    assert body2["has_personality"] is True
```

- [ ] **Step 4: Run the profile tests**

```bash
pytest tests/test_profile.py -v
```
Expected: all existing tests pass plus the new one. Total for test_profile.py: 3 tests.

- [ ] **Step 5: Run full suite**

```bash
pytest tests/ -v
```
Expected: ~89 passing (88 + 1 new).

- [ ] **Step 6: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/schemas/profile.py backend/app/routers/profile.py backend/tests/test_profile.py
git commit -m "feat(backend): radar response exposes has_personality flag for frontend routing"
```
Expected: 55 commits.

---

## Task 7: Extension shared types + background PERSONALITY_SUBMIT routing

**Files:**
- Modify: `extension/src/shared/types.ts`
- Modify: `extension/src/background/index.ts`

- [ ] **Step 1: Extend `extension/src/shared/types.ts`**

Read the file. Apply these three edits:

**Edit 1 — Extend `RadarResult`**. Current:

```typescript
export interface RadarResult {
  user_id: number;
  interaction_count: number;
  level: number;
  level_title: string;
  level_emoji: string;
  next_level_at: number;
  ui_stage: "welcome" | "learning" | "early" | "stable";
  dimensions: RadarDimension[];
  total_analyze_count: number;
  total_action_count: number;
}
```

Add `has_personality: boolean`:

```typescript
export interface RadarResult {
  user_id: number;
  interaction_count: number;
  level: number;
  level_title: string;
  level_emoji: string;
  next_level_at: number;
  ui_stage: "welcome" | "learning" | "early" | "stable";
  has_personality: boolean;
  dimensions: RadarDimension[];
  total_analyze_count: number;
  total_action_count: number;
}
```

**Edit 2 — Add new `PersonalityResult` type** below the existing interfaces:

```typescript
export interface PersonalityResult {
  status: "ok" | "skipped";
  seeded_tag_count: number;
  summary: string;
}
```

**Edit 3 — Extend `Msg` union**. Find the union (after the V1.2 edits it has ANALYZE, ACTION, GET_RADAR, RECOMMEND). Add the new `PERSONALITY_SUBMIT` variant:

```typescript
export type Msg =
  | { type: "ANALYZE"; payload: { text: string; domain: Domain; pageTitle: string; pageUrl: string; hesitationMs: number | null } }
  | { type: "ACTION"; payload: { action: "star" | "bomb"; matchedTagIds: number[]; textHash?: string; readMs: number | null } }
  | { type: "GET_RADAR" }
  | { type: "RECOMMEND"; payload: { text: string; sourceDomain: Domain; matchedTagIds: number[] } }
  | { type: "PERSONALITY_SUBMIT"; payload: { mbti: string | null; constellation: string | null } };
```

- [ ] **Step 2: Update `extension/src/background/index.ts`**

Read the file. Find the `routeApi` switch. Add a new case at the end (before the closing brace):

```typescript
    case "PERSONALITY_SUBMIT":
      return fetchJson("POST", "/personality/submit", {
        mbti: msg.payload.mbti,
        constellation: msg.payload.constellation,
      });
```

The complete switch now has 5 cases: ANALYZE, ACTION, GET_RADAR, RECOMMEND, PERSONALITY_SUBMIT.

- [ ] **Step 3: Build to verify types compile**

```bash
cd D:/qhyProject/vibe4.0/extension && npm run build
```
Expected: `Extension built to build`. If TypeScript errors occur, they're likely from downstream files using the old `RadarResult` without `has_personality` — but since `has_personality` is added as a required field, any file that constructs a `RadarResult` manually would break. We don't construct `RadarResult` manually anywhere; it's only returned from `send<RadarResult>(...)` which is typed-any at the boundary. The build should succeed.

- [ ] **Step 4: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/src/shared/types.ts extension/src/background/index.ts
git commit -m "feat(ext): add PERSONALITY_SUBMIT msg type and radar has_personality field"
```
Expected: 56 commits.

---

## Task 8: Popup personality quiz page + three-stage routing

**Files:**
- Create: `extension/src/popup/personality.ts`
- Modify: `extension/src/popup/popup.ts`
- Modify: `extension/src/popup/popup.css`

- [ ] **Step 1: Create `extension/src/popup/personality.ts`**

```typescript
import { send } from "../shared/api";
import type { PersonalityResult } from "../shared/types";

const CONSTELLATIONS = [
  "白羊座", "金牛座", "双子座", "巨蟹座",
  "狮子座", "处女座", "天秤座", "天蝎座",
  "射手座", "摩羯座", "水瓶座", "双鱼座",
];

export async function renderPersonalityQuiz(root: HTMLElement): Promise<void> {
  root.innerHTML = `
    <div class="vr-personality-quiz">
      <h2>Vibe-Radar 快速定位</h2>
      <p class="vr-quiz-sub">告诉我一点关于你的事，让 Vibe 马上懂你</p>

      <label class="vr-field-label">你的 MBTI <span class="vr-optional">（可选）</span></label>
      <input type="text" id="mbti-input" class="vr-input" placeholder="INTP" maxlength="4" />
      <a class="vr-ext-link" href="https://www.16personalities.com/ch/%E5%85%8D%E8%B4%B9%E4%BA%BA%E6%A0%BC%E6%B5%8B%E8%AF%95" target="_blank">不清楚？去 16personalities 测一下 →</a>

      <label class="vr-field-label">你的星座 <span class="vr-optional">（可选）</span></label>
      <select id="constellation-select" class="vr-input">
        <option value="">—— 不填 ——</option>
        ${CONSTELLATIONS.map((c) => `<option value="${c}">${c}</option>`).join("")}
      </select>

      <button class="vr-btn vr-btn-secondary" id="skip-btn">跳过，让 Vibe 自己学</button>
      <button class="vr-btn vr-btn-primary" id="submit-btn">确认提交</button>

      <div class="vr-quiz-msg" id="quiz-msg"></div>
    </div>
  `;

  const mbtiInput = root.querySelector("#mbti-input") as HTMLInputElement;
  const constellationSelect = root.querySelector("#constellation-select") as HTMLSelectElement;
  const skipBtn = root.querySelector("#skip-btn") as HTMLButtonElement;
  const submitBtn = root.querySelector("#submit-btn") as HTMLButtonElement;
  const msg = root.querySelector("#quiz-msg") as HTMLElement;

  async function submit(mbti: string | null, constellation: string | null): Promise<void> {
    submitBtn.disabled = true;
    skipBtn.disabled = true;
    msg.textContent = "Vibe 正在理解你…";
    try {
      const result = await send<PersonalityResult>({
        type: "PERSONALITY_SUBMIT",
        payload: { mbti, constellation },
      });
      if (result.status === "ok" && result.summary) {
        msg.innerHTML = `<strong>✓ 已完成</strong><br><br>${result.summary}<br><br>2 秒后进入主界面…`;
      } else {
        msg.textContent = "✓ 已完成，进入主界面…";
      }
      setTimeout(async () => {
        const mod = await import("./welcome");
        mod.renderWelcome(root);
      }, 2000);
    } catch (e: any) {
      msg.textContent = `提交失败: ${e?.message ?? "未知"}`;
      submitBtn.disabled = false;
      skipBtn.disabled = false;
    }
  }

  skipBtn.addEventListener("click", () => submit(null, null));
  submitBtn.addEventListener("click", () => {
    const mbti = mbtiInput.value.trim().toUpperCase();
    const constellation = constellationSelect.value;
    submit(mbti || null, constellation || null);
  });
}
```

- [ ] **Step 2: Rewrite `extension/src/popup/popup.ts` for three-stage routing**

Read the current file. It should be:

```typescript
import { send } from "../shared/api";
import type { RadarResult } from "../shared/types";
import { renderWelcome } from "./welcome";

async function main() {
  const root = document.getElementById("root")!;
  try {
    const data = await send<RadarResult>({ type: "GET_RADAR" });
    if (data.interaction_count === 0) {
      renderWelcome(root);
    } else {
      const mod = await import("./radar");
      await mod.renderRadar(root, data);
    }
  } catch (e: any) {
    root.innerHTML = `<div class="error">加载失败: ${e?.message ?? "未知"}</div>`;
  }
}

main();
```

Replace entire content with the three-stage version:

```typescript
import { send } from "../shared/api";
import type { RadarResult } from "../shared/types";

async function main() {
  const root = document.getElementById("root")!;
  try {
    const data = await send<RadarResult>({ type: "GET_RADAR" });
    if (data.interaction_count > 0) {
      // Established user — show radar
      const mod = await import("./radar");
      await mod.renderRadar(root, data);
    } else if (data.has_personality) {
      // Zero interaction but already answered (or skipped) the quiz — show welcome
      const mod = await import("./welcome");
      mod.renderWelcome(root);
    } else {
      // Brand-new user — show personality quiz
      const mod = await import("./personality");
      await mod.renderPersonalityQuiz(root);
    }
  } catch (e: any) {
    root.innerHTML = `<div class="error">加载失败: ${e?.message ?? "未知"}</div>`;
  }
}

main();
```

- [ ] **Step 3: Append styles to `extension/src/popup/popup.css`**

```css
/* V1.3 personality quiz page */
.vr-personality-quiz {
  padding: 16px 12px;
}
.vr-personality-quiz h2 {
  margin: 0 0 4px;
  font-size: 18px;
  color: #6c5ce7;
  text-align: center;
}
.vr-quiz-sub {
  color: #888;
  font-size: 12px;
  text-align: center;
  margin: 0 0 20px;
}
.vr-field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 12px 0 6px;
}
.vr-optional {
  font-weight: 400;
  color: #999;
  font-size: 11px;
}
.vr-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid rgba(108, 92, 231, 0.2);
  border-radius: 8px;
  font-size: 14px;
  background: #fff;
  font-family: inherit;
}
.vr-input:focus {
  outline: none;
  border-color: #6c5ce7;
  box-shadow: 0 0 0 2px rgba(108, 92, 231, 0.15);
}
.vr-ext-link {
  display: block;
  font-size: 11px;
  color: #888;
  text-decoration: none;
  margin-top: 4px;
}
.vr-ext-link:hover { color: #6c5ce7; }
.vr-btn-secondary {
  display: block;
  width: 100%;
  margin-top: 16px;
  padding: 10px;
  background: #f0edff;
  color: #6c5ce7;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
}
.vr-btn-primary {
  display: block;
  width: 100%;
  margin-top: 8px;
  padding: 12px;
  background: linear-gradient(135deg, #6c5ce7, #a29bfe);
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}
.vr-btn-secondary:disabled,
.vr-btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.vr-quiz-msg {
  margin-top: 16px;
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
  font-size: 12px;
  color: #555;
  line-height: 1.5;
  text-align: center;
  min-height: 40px;
}
```

- [ ] **Step 4: Build**

```bash
cd D:/qhyProject/vibe4.0/extension && npm run build
ls -l build/popup/popup.js
```
Expected: clean build. `popup.js` size stays around ~2.8MB (ECharts dominates).

- [ ] **Step 5: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/src/popup/personality.ts extension/src/popup/popup.ts extension/src/popup/popup.css
git commit -m "feat(ext): popup personality quiz page with three-stage routing"
```
Expected: 57 commits.

---

## Task 9: VibeCard button rename + tag pill removal + onboarding hint

**Files:**
- Modify: `extension/src/content/ui/VibeCard.ts`
- Modify: `extension/src/content/ui/styles.css`

- [ ] **Step 1: Update `extension/src/content/ui/VibeCard.ts`**

Read the file. Three surgical edits.

**Edit 1 — Delete the tag pill block.** Find:

```typescript
  const tagsWrap = document.createElement("div");
  tagsWrap.className = "vr-tags";
  for (const t of result.matched_tags) {
    const pill = document.createElement("span");
    pill.className = "vr-tag";
    pill.textContent = t.name;
    tagsWrap.appendChild(pill);
  }
  card.appendChild(tagsWrap);
```

Delete this entire block. (The `result.matched_tags` data is still used by sendAction's payload building, so don't touch the rest.)

**Edit 2 — Rename button text.** Find:

```typescript
  const star = document.createElement("button");
  star.className = "vr-btn star";
  star.textContent = "💎 懂我";
```

Change to:

```typescript
  const star = document.createElement("button");
  star.className = "vr-btn star";
  star.textContent = "❤️ 我喜欢";
```

Find:

```typescript
  const bomb = document.createElement("button");
  bomb.className = "vr-btn bomb";
  bomb.textContent = "💣 踩雷";
```

Change to:

```typescript
  const bomb = document.createElement("button");
  bomb.className = "vr-btn bomb";
  bomb.textContent = "👎 我不喜欢";
```

Also find the post-click text changes (inside the click handlers):

```typescript
    star.textContent = "✓ 已确权";
```
Leave as-is — this is the post-click confirmation, unchanged.

```typescript
    bomb.textContent = "✓ 已标记";
```
Leave as-is.

**Edit 3 — Add onboarding hint after the actions row.** Find the section where `card.appendChild(actions)` is called (actions is the div containing star/bomb buttons). Right after that line, BEFORE the recommend link block, insert:

```typescript
  // V1.3: first-time onboarding hint under the action row.
  chrome.storage.local.get("has_seen_onboarding").then((stored) => {
    if (!stored.has_seen_onboarding) {
      const hint = document.createElement("div");
      hint.className = "vr-onboarding-hint";
      hint.textContent = "点这两个按钮，让 Vibe 越来越懂你 · 点得越多越准";
      card.appendChild(hint);
      chrome.storage.local.set({ has_seen_onboarding: true });
    }
  });
```

Note: this runs async — the hint may appear a frame after the card renders. That's acceptable.

- [ ] **Step 2: Append CSS for the onboarding hint**

Open `extension/src/content/ui/styles.css`. Append at the end:

```css
/* V1.3 first-time onboarding hint under the action buttons */
.vr-onboarding-hint {
  margin-top: 8px;
  font-size: 10px;
  color: #999;
  text-align: center;
  line-height: 1.5;
  padding: 4px 8px;
  background: rgba(108, 92, 231, 0.04);
  border-radius: 6px;
}
```

- [ ] **Step 3: Build**

```bash
cd D:/qhyProject/vibe4.0/extension && npm run build
ls -l build/content.js
```
Expected: clean build. `content.js` size changes slightly (−~100 bytes from deleted tag pill block, +~300 bytes from onboarding hint). Should still be ~30kb.

- [ ] **Step 4: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/src/content/ui/VibeCard.ts extension/src/content/ui/styles.css
git commit -m "feat(ext): rename vibe card buttons, remove tag pills, add onboarding hint"
```
Expected: 58 commits.

---

## Task 10: SMOKE.md V1.3 updates + final full verification

**Files:**
- Modify: `extension/SMOKE.md`

- [ ] **Step 1: Update `extension/SMOKE.md`**

Read the current file. It starts with `# V1.2 Manual Smoke Test`. Change the header line to:

```markdown
# V1.3 Manual Smoke Test
```

Find Step 0 (database reset). Leave it unchanged — V1.3 also requires DB reset for the new `user_personality` table.

Find the "Start services" section. No changes.

Find the Steps section. After the existing Step 13, append these 5 new steps:

```markdown
### 14. Personality quiz on first install (V1.3)
- After resetting the DB and restarting uvicorn, open the popup
- Expected: a **Personality Quiz Page** (not Welcome or Radar) with:
  - Logo "Vibe-Radar 快速定位"
  - Subtitle "告诉我一点关于你的事，让 Vibe 马上懂你"
  - An MBTI text input (4 chars max)
  - A 16personalities.com link below the MBTI input
  - A 星座 dropdown with 12 options + "—— 不填 ——"
  - "跳过，让 Vibe 自己学" secondary button
  - "确认提交" primary button

### 15. MBTI submission seeds the profile (V1.3)
- In the quiz page, type "INTP" in MBTI, select "双鱼座" in 星座, click 确认提交
- Expected:
  - Buttons disable, "Vibe 正在理解你…" loading text appears
  - After 2-5 seconds, a summary paragraph appears (natural language description of INTP+双鱼座)
  - After 2 more seconds, transitions to the Welcome page
- Verify the backend state:
```bash
cd D:/qhyProject/vibe4.0/backend
python -c "
import sqlite3
con = sqlite3.connect('data/vibe_radar.db')
cur = con.cursor()
print('=== user_personality ===')
for row in cur.execute('SELECT user_id, mbti, constellation, substr(summary, 1, 40) FROM user_personality').fetchall():
    print(row)
print('=== personality_seed action_log count ===')
print(cur.execute(\"SELECT COUNT(*) FROM action_log WHERE action='personality_seed'\").fetchone())
print('=== seeded user_vibe_relations ===')
for row in cur.execute('SELECT uvr.vibe_tag_id, vt.name, uvr.core_weight FROM user_vibe_relations uvr JOIN vibe_tags vt ON vt.id = uvr.vibe_tag_id WHERE uvr.user_id=1 AND uvr.core_weight != 0 ORDER BY uvr.core_weight DESC').fetchall():
    print(row)
"
```
  - Expected: one row in user_personality with mbti='INTP', constellation='双鱼座', summary starting with Chinese text
  - Expected: personality_seed action_log count is 1-8
  - Expected: 1-8 user_vibe_relations rows with non-zero core_weight

### 16. Skip path (V1.3)
- Reset the DB and restart uvicorn
- Open popup → quiz page → click "跳过，让 Vibe 自己学"
- Expected: "✓ 已完成，进入主界面…" message, then transition to Welcome page
- Verify the DB:
```bash
python -c "
import sqlite3
con = sqlite3.connect('data/vibe_radar.db')
cur = con.cursor()
for row in cur.execute('SELECT user_id, mbti, constellation, summary FROM user_personality').fetchall():
    print(row)
"
```
  - Expected: one row with (1, None, None, None)
- Close popup and reopen → should show Welcome page (not the quiz again)
- This confirms the row-write-on-skip prevents re-prompting

### 17. Button rename + tag pill removal + onboarding hint (V1.3)
- With MBTI already submitted (from step 15), go to a supported site
- Highlight text → click purple icon → vibe card appears
- Expected (first time after install):
  - Buttons read "❤️ 我喜欢" and "👎 我不喜欢" — NOT "💎 懂我" / "💣 踩雷"
  - NO tag pills under the roast line (V1.2 used to show "赛博机械" / "黑暗压抑" pills — these should be GONE)
  - A small grey hint under the action row: "点这两个按钮，让 Vibe 越来越懂你 · 点得越多越准"
- Close the card, highlight different text, click icon again
- Expected: the onboarding hint does NOT appear this time (it was stored in chrome.storage.local and dismissed)

### 18. Roaster voice uses personality summary (V1.3)
- With MBTI=INTP submitted, highlight several different texts on different supported sites
- Expected: each roaster output reads like a friend talking about you, referencing the vibe of the text, not mechanical tag recitation
- The roast should NEVER contain the 24 internal tag names (慢炖沉浸 / 治愈温暖 / 赛博机械 / 黑暗压抑 / 烧脑解谜 / 认知挑战 / etc.)
- Some outputs should reference INTP-style insights like "深度思考", "独处", "逻辑", even though the word "INTP" itself never appears in the output
```

Find the "Pass criteria" line at the bottom:

```markdown
## Pass criteria
All 13 steps complete without any JavaScript console errors in either the background worker or the content script.
```

Change "13 steps" to "18 steps":

```markdown
## Pass criteria
All 18 steps complete without any JavaScript console errors in either the background worker or the content script.
```

- [ ] **Step 2: Final full backend pytest**

```bash
cd D:/qhyProject/vibe4.0/backend && source .venv/Scripts/activate && pytest tests/ -v 2>&1 | tail -5
```
Expected: `~89 passed` (68 V1.2 + 10 agent + 7 router + 3 vibe + 1 profile).

- [ ] **Step 3: Final extension build**

```bash
cd D:/qhyProject/vibe4.0/extension && npm run build
ls -l build/
ls -l build/popup/
```
Expected: all bundles present:
- `background.js` (~2kb)
- `content.js` (~30kb — slightly bigger than V1.2's 30.6kb or slightly smaller due to tag pill removal)
- `popup/popup.js` (~2.8mb — minimal change)
- `popup/popup.html`, `popup/popup.css`, `manifest.json`, `assets/icon.svg`

- [ ] **Step 4: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/SMOKE.md
git commit -m "docs: extend SMOKE.md with V1.3 personality quiz + button rename checks"
git log --oneline | head -15
```
Expected: **59 commits total**. V1.3 SP-E is complete.

---

## Post-implementation checklist

- [ ] `pytest tests/ -v` runs ~89 tests, all green
- [ ] `npm run build` succeeds with zero TypeScript errors
- [ ] Extension reloaded in Chrome, `backend/data/vibe_radar.db` deleted + re-seeded
- [ ] SMOKE step 0 completed (DB reset)
- [ ] SMOKE steps 1-13 still pass (no V1.2 regression)
- [ ] SMOKE steps 14-18 pass (new V1.3 features)
- [ ] `git log --oneline` shows 59 commits total

---

## Appendix — V1.3 known limitations (carry forward)

Copied from spec §8:

1. **One-shot personality.** Once submitted (even with all nulls), the user is locked into their personality state. There is no "reset me" button. V1.4 may add one.
2. **Sparse signal for skipped users.** A user who skips the quiz AND never interacts gets level 0 forever. Only 划词 actions drive level-up. Intentional.
3. **Constellation signal is weak.** The LLM produces lower-quality seeds when only 星座 is provided (vs MBTI). Accept as mild trade for user familiarity.
4. **No 16-type test integration.** Users who don't know their MBTI click an external link to 16personalities.com. They have to come back and re-open the popup.
5. **Personality can't be overridden by likes/dislikes alone.** A +15 core_weight seed takes ~2 💎 hits to flip to the opposite direction.
6. **First-impression + personality seed stack.** A user who submits MBTI AND then does their first analyze gets BOTH the `personality_seed` weights AND the V1.2 `first_impression` +10 on matched tags. Intentional double-boost.
7. **SP-B, SP-C, SP-D still deferred.** Behavior profile, XP timeline, personality updating over time — all future work.
