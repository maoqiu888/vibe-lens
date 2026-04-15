# Vibe-Radar V1.3 SP-E Design — MBTI Fast-Track Cold Start + Personality Agent

> Status: Approved in brainstorming
> Date: 2026-04-15
> Scope: Sub-project E — MBTI/Constellation personality fast-track, renamed affordances, 24-tag vocabulary hidden from UI
> Parent specs:
> - V1.0: `docs/superpowers/specs/2026-04-14-vibe-radar-v1-design.md`
> - V1.1: `docs/superpowers/specs/2026-04-14-vibe-radar-v1.1-design.md`
> - V1.2 (SP-A): `docs/superpowers/specs/2026-04-14-vibe-radar-v1.2-design.md`

---

## 1. Context and Scope

### 1.1 Problems V1.0 – V1.2 left unsolved

V1.2 SP-A replaced the 18-card cold-start wizard with "first-interaction-as-cold-start" + a sqrt-curve level system. The user tested it and identified three gaps:

1. **Cold start still feels slow.** A new user's first match score is effectively zero (empty profile vector → cosine similarity = 0). The user does not see meaningful personalization until ~16 interactions (L4). The first-impression trick gives a +10 signal on the first analyze's tags, but that's too narrow to matter.
2. **The 24-tag vocabulary leaks everywhere.** Even though V1.2 hid percentages in learning stages, the VibeCard still renders matched tags as purple pills ("赛博机械", "黑暗压抑") and the roaster (pre-V1.2-roaster-fix) regurgitated those tag names in output. The user complained: "太难理解了". They want to think in culturally familiar personality systems (MBTI, 星座) and never see the internal 24-tag vocabulary.
3. **"懂我/踩雷" affordance is unclear.** First-time users don't know why they should click the buttons or what changes. The labels feel like a verdict ("did it nail you?") not a behavior signal ("tell me your taste").

### 1.2 The fix: a personality fast-track that augments, not replaces

The user explicitly chose the "augment" architecture: keep the 24-tag math backbone (cosine similarity, radar chart, dual-weight profile, level system) AND layer a new personality system on top.

**Key mechanism — LLM-powered MBTI → tag weight translation.** A new `llm_personality_agent` service takes `{mbti, constellation}` from a cold-start form and produces two outputs in a single LLM call:

1. **Tag seeds** — up to 8 of the 24 internal tags with weights in [-15, +15]. These are applied as `core_weight` via `apply_core_delta(action="personality_seed")`, giving the user a non-zero starting profile that drives match scores from day 0.
2. **Natural-language personality summary** — ~100-200 characters describing the user's taste in everyday Chinese. Stored in `user_personality.summary` and used as the roaster's `user_taste_hint` from that point on.

This means:
- Matching math is instantly personalized (no 16-interaction grind to L4)
- Roaster voice is anchored in MBTI insight, not tag regurgitation
- 24-tag vocabulary stays internal (math backbone), user never sees it

### 1.3 Button rename + onboarding hint

- `💎 懂我` → `❤️ 我喜欢`
- `💣 踩雷` → `👎 我不喜欢`
- First-time VibeCard renders a grey subtitle under the action row: *"点这两个按钮，让 Vibe 越来越懂你 · 点得越多越准"*. Dismissed after first view via `chrome.storage.local.has_seen_onboarding`.

Internal DB action names (`"star"` / `"bomb"`) and router/schema field names remain unchanged — only UI text + icons + the one-time hint banner change. This keeps the backend and test suite zero-touch for the rename.

### 1.4 Tag pills removed from VibeCard

The `.vr-tags` element (the row of purple pills with matched tag names) is deleted entirely. The user is now 100% insulated from the 24-tag internal vocabulary — they see the roaster's natural-language voice, the match percentage (at L4+), and nothing else that mentions specific tag names.

### 1.5 Non-goals (explicit)

- **Not replacing the 24-tag backbone.** The user explicitly chose "augment" (Plan B) over "replace" (Plan A) during brainstorming. The 24-tag vector, cosine similarity, radar chart, level system, dynamic weight scaling — all stay.
- **No embedded MBTI quiz.** The form is two input fields with an external link to 16personalities.com. We don't build a quiz.
- **No birthday → constellation auto-calculation.** 星座 is a simple 12-option dropdown.
- **No editable personality.** Once submitted, `user_personality` is locked. Re-submission returns 400 `ALREADY_SUBMITTED`. V1.4+ may add a "reset me" button.
- **No third personality system (sbti / Big Five / 九型人格).** MBTI + constellation only.
- **No removal of the radar chart.** Popup still shows 6-axis radar for users who've interacted enough. The axes are the 6 **categories** (节奏/情绪色调/etc.), not the 24 individual tag names — so no vocabulary leak there.
- **SP-B, SP-C, SP-D deferred.** This spec covers only the personality fast-track piece. Behavior profile (SP-B), growth timeline (SP-C), and LLM personality summaries over time (SP-D) are still deferred.

---

## 2. Data Model Changes

### 2.1 New table `user_personality`

```python
# backend/app/models/user_personality.py
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

One row per user. `user_id` is both PK and FK. `mbti` is a 4-letter string like `"INTP"`. `constellation` is a Chinese name like `"双鱼座"` (the canonical 12). `summary` is the LLM-generated natural-language description (50-300 chars expected).

### 2.2 `app/models/__init__.py` update

Add the new model to the package-level import so `Base.metadata.create_all` picks it up:

```python
from app.models.user_personality import UserPersonality

__all__ = [
    "User", "VibeTag", "UserVibeRelation", "AnalysisCache", "ActionLog",
    "UserPersonality",  # NEW
]
```

### 2.3 Database reset (manual, one-time)

V1.3 adds a new table `user_personality`. Users upgrading from V1.2 must `rm backend/data/vibe_radar.db` and re-seed before running V1.3. SMOKE.md Step 0 documents this. No alembic; V1.0's blow-away-the-db policy continues.

---

## 3. Backend Components

### 3.1 New service `llm_personality_agent.py`

**File:** `backend/app/services/llm_personality_agent.py`

```python
import json
from typing import Awaitable, Callable

import httpx

from app.config import settings

LlmCallable = Callable[[str, str], Awaitable[str]]

MAX_TAG_SEEDS = 8
WEIGHT_MIN = -15
WEIGHT_MAX = 15
SUMMARY_MIN_LEN = 30
SUMMARY_MAX_LEN = 400


class PersonalityAgentEmptyError(Exception):
    """Raised when neither MBTI nor constellation is supplied (never reaches LLM)."""


SYSTEM_PROMPT = """你是 Vibe-Radar 的"性格翻译官"。用户给你他的 MBTI 和/或星座，你要做两件事：

1. 从固定的 24 个"品味标签池"里选出最多 8 个对他显著的标签，并给每个 -15 到 +15 的权重（正数 = 他会喜欢这种内容，负数 = 他会讨厌）。只给你确信的；不确信的不要出现。
2. 用 100-200 字的自然大白话描述这个人的审美倾向和性格，像在跟一个不认识他的朋友介绍他。描述里不要提 MBTI、星座的术语缩写，也**不要用品味标签池里的词汇**——你只是在用日常语言描述。

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


def _load_tag_pool_json() -> str:
    """Build the tag pool JSON to inject into the system prompt at call time."""
    from sqlalchemy import select

    from app import database
    from app.models.vibe_tag import VibeTag

    db = database.SessionLocal()
    try:
        tags = db.scalars(select(VibeTag).order_by(VibeTag.id)).all()
        return json.dumps(
            [{"id": t.id, "name": t.name, "description": t.description} for t in tags],
            ensure_ascii=False,
        )
    finally:
        db.close()


async def analyze_personality(
    mbti: str | None,
    constellation: str | None,
    llm_call: LlmCallable | None = None,
) -> dict:
    """Return {tag_seeds: [...], personality_summary: str}.

    If both mbti and constellation are None, raises PersonalityAgentEmptyError
    (callers should detect this case and short-circuit before calling).

    On any LLM or parse failure, returns {"tag_seeds": [], "personality_summary": ""}
    instead of propagating the exception — the caller (personality router)
    must still persist a row to user_personality to prevent retry loops.
    """
    if not mbti and not constellation:
        raise PersonalityAgentEmptyError("neither mbti nor constellation supplied")

    llm_call = llm_call or _default_llm_call
    tag_pool_json = _load_tag_pool_json()
    system_prompt = SYSTEM_PROMPT.format(tag_pool_json=tag_pool_json)
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

    valid_seeds = []
    seen_tag_ids = set()
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
        # Clamp weight to valid range
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
    if len(summary) < SUMMARY_MIN_LEN or len(summary) > SUMMARY_MAX_LEN:
        # Truncate or blank out if absurdly short/long
        if len(summary) > SUMMARY_MAX_LEN:
            summary = summary[:SUMMARY_MAX_LEN]
        else:
            summary = ""

    return {"tag_seeds": valid_seeds, "personality_summary": summary}
```

**Key design points:**
- **Fail-safe:** Any exception inside the agent returns empty result (`{tag_seeds: [], personality_summary: ""}`) instead of propagating. The caller (router) uses this to decide whether to report 503 or silently succeed.
- **Empty-input guard:** The `PersonalityAgentEmptyError` is raised only when both fields are None — callers catch this early and return `{status: "skipped"}` without calling the LLM.
- **Weight clamping:** If the LLM returns `weight: 30`, we clamp to 15. If it returns 1000 tag seeds, we truncate to 8.
- **Dedup:** If the LLM returns the same tag_id twice, the first occurrence wins, the second is dropped.

### 3.2 New schemas

**File:** `backend/app/schemas/personality.py`

```python
from pydantic import BaseModel, Field, field_validator

VALID_MBTI_LETTERS = {
    ("I", "E"),
    ("N", "S"),
    ("T", "F"),
    ("P", "J"),
}

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
            raise ValueError(f"constellation must be one of the 12 canonical names")
        return v


class PersonalityResponse(BaseModel):
    status: str        # "ok" | "skipped"
    seeded_tag_count: int
    summary: str       # empty string if skipped or LLM failed
```

### 3.3 New router `/api/v1/personality/submit`

**File:** `backend/app/routers/personality.py`

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
    # Lazy-create user row if missing (first-ever interaction path)
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        user = User(id=user_id, username="default", interaction_count=0)
        db.add(user)
        db.flush()

    # Check for duplicate submission
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

    # Short-circuit if both fields empty
    if payload.mbti is None and payload.constellation is None:
        # Still write a row to lock the user into "I've been asked once" state
        db.add(UserPersonality(
            user_id=user_id, mbti=None, constellation=None, summary=None,
        ))
        db.commit()
        return PersonalityResponse(status="skipped", seeded_tag_count=0, summary="")

    # Call the agent
    try:
        result = await llm_personality_agent.analyze_personality(
            mbti=payload.mbti,
            constellation=payload.constellation,
        )
    except llm_personality_agent.PersonalityAgentEmptyError:
        # Shouldn't reach here (we already short-circuited), but defensive
        return PersonalityResponse(status="skipped", seeded_tag_count=0, summary="")

    tag_seeds = result["tag_seeds"]
    summary = result["personality_summary"]

    # Apply tag seeds via profile_calc (uses existing _apply_delta which
    # lazy-creates UserVibeRelation rows)
    for seed in tag_seeds:
        profile_calc.apply_core_delta(
            user_id=user_id,
            tag_ids=[seed["tag_id"]],
            delta=seed["weight"],
            action=PERSONALITY_SEED_ACTION,
        )

    # Persist the personality row
    db.add(UserPersonality(
        user_id=user_id,
        mbti=payload.mbti,
        constellation=payload.constellation,
        summary=summary,
    ))
    db.commit()

    return PersonalityResponse(
        status="ok",
        seeded_tag_count=len(tag_seeds),
        summary=summary,
    )
```

**Register in `backend/app/main.py`:** add `from app.routers import personality` and `app.include_router(personality.router)`.

**Important ordering notes:**
- `apply_core_delta` is called BEFORE `db.add(UserPersonality(...))` because `_apply_delta` commits its own transaction internally. If we wrote `UserPersonality` first and then `apply_core_delta` failed, we'd have a partial commit. Writing seeds first is safer.
- The `ALREADY_SUBMITTED` check also covers the "user skipped last time" case — once a row exists with all fields None, they can't submit again. This is a deliberate choice: don't give users unlimited retries.
- `personality_seed` action does NOT increment `interaction_count`. The level system remains purely driven by analyze/action calls. This is important: a user who filled MBTI should still be at Level 0 (welcome stage) until they do their first analyze.

### 3.4 `vibe.py analyze` route: `user_taste_hint` fallback

Current code in `vibe.py` step 4 (after V1.2 + tag-leak fix):

```python
user_taste_descriptions = profile_calc.get_top_core_tag_descriptions(
    user_id=user_id, n=2
)
user_taste_hint = "；".join(user_taste_descriptions)
```

Replace with a priority-ordered lookup:

```python
# Prefer the MBTI-derived natural-language summary if present.
# Fall back to top-tag descriptions only for users who skipped the quiz.
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
```

Add `from app.models.user_personality import UserPersonality` to `vibe.py` imports.

### 3.5 No changes to action route, recommend route, cold-start-is-first-interaction logic

These are all unchanged. The personality fast-track is **additive**:
- Users who submit MBTI/star get a seeded profile + MBTI-driven roaster voice
- Users who skip fall back to V1.2 behavior exactly (first-impression cold-start on first analyze)
- Either way, once the user starts interacting, the level system + dynamic weights work identically

---

## 4. Frontend Changes

### 4.1 Popup three-stage routing

Current V1.2 popup has 2 states: welcome (count=0) and radar (count≥1). V1.3 adds a third state, **personality quiz**, inserted BEFORE welcome.

Routing logic in `popup.ts`:

```typescript
async function main() {
  const root = document.getElementById("root")!;
  try {
    const data = await send<RadarResult>({ type: "GET_RADAR" });
    if (data.interaction_count > 0) {
      // Established user — show radar
      const mod = await import("./radar");
      await mod.renderRadar(root, data);
    } else if (data.has_personality) {
      // Zero interaction but already answered personality quiz — show welcome
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
```

The `GET_RADAR` response needs a new field `has_personality: boolean` to distinguish "never answered" from "answered but skipped". Extend `RadarResponse` backend schema and `RadarResult` frontend type accordingly:

```python
# schemas/profile.py
class RadarResponse(BaseModel):
    ...
    has_personality: bool  # NEW — true iff user_personality row exists
```

```python
# routers/profile.py — in the radar() function
user_personality = db.scalar(
    select(UserPersonality).where(UserPersonality.user_id == user_id)
)
has_personality = user_personality is not None
# ... include in response ...
```

### 4.2 New file `extension/src/popup/personality.ts`

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

  async function submit(mbti: string | null, constellation: string | null) {
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

### 4.3 `shared/types.ts` additions

```typescript
// Extend RadarResult
export interface RadarResult {
  // ... existing fields ...
  has_personality: boolean;  // NEW
}

// New type
export interface PersonalityResult {
  status: "ok" | "skipped";
  seeded_tag_count: number;
  summary: string;
}

// Extend Msg union
export type Msg =
  // ... existing variants ...
  | { type: "PERSONALITY_SUBMIT"; payload: { mbti: string | null; constellation: string | null } };
```

### 4.4 `background/index.ts` new routing

Add case in `routeApi` switch:

```typescript
case "PERSONALITY_SUBMIT":
  return fetchJson("POST", "/personality/submit", {
    mbti: msg.payload.mbti,
    constellation: msg.payload.constellation,
  });
```

### 4.5 VibeCard changes — button rename + tag pill removal + onboarding hint

**File:** `extension/src/content/ui/VibeCard.ts`

Three surgical changes:

**Change 1: Remove the tag pill block entirely.** Find the section that renders matched_tags as pills:

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

**Delete this entire block.** The `result.matched_tags` data is still computed and returned by the backend (needed for the 💎/💣 payload), but it's no longer rendered.

**Change 2: Rename button text.** Find:

```typescript
star.textContent = "💎 懂我";
// ...
bomb.textContent = "💣 踩雷";
```

Change to:

```typescript
star.textContent = "❤️ 我喜欢";
// ...
bomb.textContent = "👎 我不喜欢";
```

The button CSS classes (`.vr-btn.star`, `.vr-btn.bomb`), click handlers, and `sendAction(action: "star" | "bomb", ...)` call signature stay unchanged. The action name sent to the backend is still `"star"` / `"bomb"`. Only the UI surface is rebranded.

**Change 3: Add first-time onboarding hint.** After the actions row is appended to the card, read `chrome.storage.local.has_seen_onboarding` and conditionally append a hint line:

```typescript
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

Since this is async, the hint may appear a frame or two after the card renders. That's acceptable — it's a first-time-only flash.

### 4.6 New CSS additions

Append to `extension/src/content/ui/styles.css`:

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

Append to `extension/src/popup/popup.css`:

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

---

## 5. Error Handling Matrix

| Scenario | Location | Behavior |
|---|---|---|
| User submits empty MBTI + empty constellation | personality router | Returns `{status: "skipped"}`, writes a row with all NULLs to prevent resubmission, no LLM call |
| User submits invalid MBTI (not 4 letters or wrong letters) | pydantic validator | 422 validation error |
| User submits constellation not in the 12 canonical list | pydantic validator | 422 validation error |
| User has already submitted personality | personality router | 400 `ALREADY_SUBMITTED` |
| LLM timeout (>15s) | personality agent | Returns `{tag_seeds: [], summary: ""}`, router writes empty row, returns `status: "ok"` with `seeded_tag_count=0` |
| LLM JSON parse failure | personality agent | Same as timeout |
| LLM returns weights outside [-15, 15] | personality agent | Clamped to range |
| LLM returns >8 tag seeds | personality agent | Truncated to first 8 |
| LLM returns duplicate tag_ids | personality agent | First occurrence kept, others dropped |
| LLM returns tag_id outside [1, 24] | personality agent | Dropped |
| LLM returns empty / absurdly long summary | personality agent | Blanked out |
| User clicks "skip" after typing MBTI | frontend personality.ts | Submit path sends `{mbti: null, constellation: null}`, skipping the typed value (deliberate — the skip button means "skip this round entirely") |
| Frontend can't reach backend | frontend personality.ts | Error message, buttons re-enabled for retry |

---

## 6. Testing Strategy

### 6.1 Backend (pytest)

**New file `test_llm_personality_agent.py`** (~9 tests):

```python
# Happy path
async def test_analyze_returns_tag_seeds_and_summary()
# Both inputs
async def test_both_mbti_and_constellation()
# Empty inputs raise
async def test_empty_inputs_raise_empty_error()
# LLM exception returns empty result
async def test_llm_exception_returns_empty()
# JSON parse failure returns empty
async def test_json_parse_failure_returns_empty()
# Weight clamping
async def test_weight_out_of_range_clamped()
# Tag seed truncation
async def test_more_than_8_seeds_truncated()
# Duplicate tag_ids deduped
async def test_duplicate_tag_ids_deduped()
# Summary length validation
async def test_empty_summary_returns_empty()
```

**New file `test_personality_router.py`** (~7 tests):

```python
def test_skip_both_fields_returns_skipped_and_writes_null_row(monkeypatch)
def test_submit_mbti_only_writes_row_and_seeds_tags(monkeypatch)
def test_submit_constellation_only_also_works(monkeypatch)
def test_already_submitted_returns_400(monkeypatch)
def test_invalid_mbti_format_returns_422(monkeypatch)
def test_invalid_constellation_returns_422(monkeypatch)
def test_llm_failure_still_persists_empty_row(monkeypatch)
```

**Extend `test_vibe.py`** (~3 new tests):

```python
def test_analyze_uses_personality_summary_when_present(monkeypatch)
def test_analyze_falls_back_to_tag_descriptions_without_personality(monkeypatch)
def test_personality_seeds_drive_initial_match_score(monkeypatch)
```

**Extend `test_profile.py`** (~1 new test):

```python
def test_radar_response_includes_has_personality_flag()
```

**Extend `test_models.py`**: Add assertion for the new `user_personality` table.

**Expected total:** 68 → ~87 tests.

### 6.2 Frontend (manual, SMOKE.md)

Add 3 new steps (14, 15, 16) after the existing V1.2 steps:

```
### 14. Personality quiz on first install (V1.3)
- After resetting the DB, open the popup
- Expected: Personality Quiz Page (not Welcome) with MBTI input + 星座 dropdown + 跳过 / 确认提交 buttons

### 15. MBTI submission drives seeded profile (V1.3)
- In the quiz, type "INTP" in MBTI, select "双鱼座" from dropdown, click 确认提交
- Expected: "Vibe 正在理解你…" loading, then a summary paragraph appears, then 2 seconds later transitions to Welcome page
- Check DB:
  sqlite3 data/vibe_radar.db "SELECT mbti, constellation, length(summary) FROM user_personality;"
  → ('INTP', '双鱼座', ~100-200)
- Check seeded tag weights:
  sqlite3 data/vibe_radar.db "SELECT action, COUNT(*) FROM action_log WHERE action='personality_seed' GROUP BY action;"
  → ('personality_seed', 1-8)

### 16. Skip path (V1.3)
- Reset DB again
- Open popup → quiz page → click "跳过，让 Vibe 自己学"
- Expected: "✓ 已完成" message, then transition to Welcome
- Check DB:
  sqlite3 data/vibe_radar.db "SELECT mbti, constellation, summary FROM user_personality;"
  → (NULL, NULL, NULL)
- Open popup again → should show Welcome (not Quiz) because a user_personality row exists
- Highlight text on douban → should trigger V1.2 first-interaction cold start (level-up animation)

### 17. Button rename + onboarding hint (V1.3)
- With MBTI already submitted, highlight text on douban → click icon → vibe card appears
- Expected:
  - Buttons read "❤️ 我喜欢" and "👎 我不喜欢" (not 懂我/踩雷)
  - Below the buttons, a grey small line: "点这两个按钮，让 Vibe 越来越懂你 · 点得越多越准"
  - No tag pills under the roast (V1.2 used to show 赛博机械/黑暗压抑 pills, V1.3 should NOT)
- Close the card and highlight another text → open the new vibe card
- Expected: the onboarding hint does NOT appear this time (chrome.storage.local.has_seen_onboarding was set)

### 18. Roaster voice uses personality summary (V1.3)
- With MBTI=INTP submitted, highlight several different texts
- Expected: the roaster output references "深度思考"/"逻辑"/"独处" or similar INTP language, not generic tag phrases
- The roaster should never leak the 24 internal tag names (慢炖沉浸, 治愈温暖, 赛博机械, etc.)
```

---

## 7. Delivery and Commit Plan

Approximate commit sequence for V1.3 (each = 1 task):

1. `feat(backend): add user_personality model and migration reset`
2. `feat(backend): add llm_personality_agent service with 24-tag seeder`
3. `feat(backend): add personality schemas and /personality/submit router`
4. `feat(backend): analyze route prefers personality summary for user_taste_hint`
5. `feat(backend): radar response adds has_personality flag`
6. `feat(ext): shared types for personality + background RECOMMEND route`
7. `feat(ext): popup personality quiz page with MBTI + constellation form`
8. `feat(ext): VibeCard button rename, tag pill removal, onboarding hint`
9. `docs: extend SMOKE.md with V1.3 personality + button rename checks`

Roughly ~700 lines added, ~100 modified, ~50 deleted.

---

## 8. Known Limitations (carry-forward Non-Goals)

1. **One-shot personality.** Once submitted (even with all nulls), the user is locked. There is no "reset me" button. A user who mistyped "INFP" → "ENFP" cannot fix it. V1.4 may add a reset mechanism.
2. **Sparse signal for skipped users.** A user who skips the quiz AND never interacts gets level 0 forever. Only 划词 actions drive level-up. This is intentional — lurkers shouldn't level up.
3. **Constellation signal is weak.** As noted during brainstorming, 星座 carries less taste signal than MBTI. The LLM may produce lower-quality seeds when only 星座 is provided. Accept as a mild trade for user familiarity.
4. **No 16-type test integration.** Users who don't know their MBTI click an external link to 16personalities.com. They have to come back and re-open the popup. Out of V1.3 scope.
5. **Personality can't be overridden by 💎/💣 alone.** A +15 core_weight seed takes ~2 💎 hits to flip to the opposite direction. This is by design: the seed is the user's self-reported identity, the actions are corrections.
6. **First-impression + personality seed stack.** A user who submits MBTI AND then does their first analyze will get BOTH the `personality_seed` weights AND the V1.2 `first_impression` +10 on matched tags. This is intentional: both signals are legitimate self-reports. The combined boost means MBTI-submitters get a particularly strong initial profile. Accept as design, not a bug.
7. **SP-B, SP-C, SP-D still deferred.** Behavior profile (time-of-day / session patterns), XP timeline, LLM personality summaries updating over time — all future work.
