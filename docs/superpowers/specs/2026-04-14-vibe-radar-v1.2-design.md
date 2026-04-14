# Vibe-Radar V1.2 (SP-A) Iteration Design — Behavioral Exhaust + Level System

> Status: Approved in brainstorming
> Date: 2026-04-14
> Scope: First of four sub-projects (SP-A) in the "让 Vibe 越用越懂你" vision
> Parent specs:
> - V1.0: `docs/superpowers/specs/2026-04-14-vibe-radar-v1-design.md`
> - V1.1: `docs/superpowers/specs/2026-04-14-vibe-radar-v1.1-design.md`

---

## 1. Context and Scope

### 1.1 The problem V1.0 + V1.1 left unsolved

V1.0's cold-start wizard (18 cards, `core_weight += 15` per pick) creates two problems the user flagged in their own use:

1. **Heavy up-front bias.** The 6 cold-start picks need ~90 subsequent analyses to overcome via curiosity alone. A mis-clicked card stays in the profile for weeks.
2. **The cards don't feel like "me."** Users experience the wizard as "declaring an identity" rather than "being recognized." The 18 hand-written taglines and examples can never match every user's taste.

Meanwhile, the profile IS already growing silently through `curiosity_weight += 0.5` on every analyze and `core_weight ± 10` on every star/bomb — but the user CAN'T SEE it happen. There's no retention hook.

### 1.2 The four-sub-project vision (from brainstorming)

The user articulated a broader "behavioral exhaust" philosophy: *the machine shouldn't listen to what users say, only watch what they do*. The full vision decomposes into four orthogonal sub-projects:

| Sub-project | Scope |
|---|---|
| **SP-A (this spec)** | Remove opinionated cold-start. Capture passive signals (hesitation, read duration, first-interaction-as-cold-start). Add a gamified level system with visible celebrations. |
| SP-B | Parallel "behavior profile" table (time-of-day, session intensity, selection length, star/bomb bias) independent of the 24 vibe tags |
| SP-C | XP / growth timeline / weekly report (deeper gamification) |
| SP-D | LLM-generated personality summary (periodic "Vibe's one-line verdict on you") |

**This spec covers SP-A only.** SP-B/C/D are explicit non-goals here; they get their own specs.

### 1.3 SP-A's load-bearing idea

Replace the static 18-card cold-start with three organic signals:

1. **First-interaction-as-cold-start (信号 2)** — The first `/analyze` call applies `core_weight += 10` to matched tags, mimicking a user's own voluntary "💎" on the very first thing they highlight.
2. **Hesitation time (信号 1)** — `hesitation_ms` (from icon shown to icon clicked) scales the `curiosity_weight` delta by 0.3–1.5×.
3. **Read duration (信号 3)** — `read_ms` (from card shown to star/bomb clicked) scales the `core_weight` delta by 0.5–1.5×.

Orthogonally, we add a 10+-level progression system driven by an `interaction_count` field on the user, with level-up animations in the rate card and a progress bar in the popup. This makes the invisible growth visible.

### 1.4 Non-goals (explicit)

- SP-B (behavior profile table / time-of-day / session clustering / selection-length stats)
- SP-C (timeline view / weekly report / XP history tab)
- SP-D (LLM personality summary)
- "Ignore signal" (icon shown but not clicked)
- Repeat-selection signal
- Global mousemove / mouse-dwell tracking
- Multi-user / auth
- Historical data migration or backfill — V1.2 adopts a **blow-away-the-db** policy (see §2.3)

---

## 2. Data Model Changes

### 2.1 `users` table gains `interaction_count`

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    interaction_count: Mapped[int] = mapped_column(Integer, default=0)  # NEW
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

This field is the **single source of truth for gamification**. It is incremented by exactly 1 on each successful `/vibe/analyze` AND each successful `/vibe/action` call. It is NOT incremented by `/vibe/recommend` (pure read) or `/profile/radar` (pure read).

### 2.2 Deleted tables, files, and code

Cold-start is removed root-and-branch:

| Path | Disposition |
|---|---|
| `backend/app/routers/cold_start.py` | DELETE entire file |
| `backend/app/schemas/cold_start.py` | DELETE entire file |
| `backend/tests/test_cold_start.py` | DELETE entire file |
| `backend/app/main.py` | REMOVE the `from app.routers import cold_start` import and `app.include_router(cold_start.router)` call |
| `backend/app/services/seed_data.py` | REMOVE the `CARD_META` dict. Keep `TAGS`, `CATEGORY_LABELS`, `compute_opposite` (still needed for the 24-tag vocabulary) |
| `extension/src/popup/coldStart.ts` | DELETE entire file |
| `extension/src/popup/popup.ts` | REWRITE to dispatch on `interaction_count` (from a new GET_RADAR call that also returns level info) rather than `chrome.storage.local.profile_initialized` |
| `extension/src/shared/types.ts` | REMOVE `COLD_START_GET_CARDS` and `COLD_START_SUBMIT` from the `Msg` union; REMOVE `CategoryCard` / `CardOption` / `ColdStartCardsResult` / `ColdStartSubmitResult` types |
| `extension/src/background/index.ts` | REMOVE the two cold-start cases from the `routeApi` switch |

### 2.3 Database reset (manual, one-time)

V1.2 schema requires the new `interaction_count` column on `users`. V1.0/V1.1 tests accumulated state in `backend/data/vibe_radar.db` that is no longer semantically correct (those users have cold-start-biased `core_weight`, old schema, etc.).

**Migration strategy: blow it away.** Before running V1.2, the user deletes `backend/data/vibe_radar.db` manually and re-runs `python -m app.services.seed`. The new schema is created fresh; user_id=1 starts with `interaction_count=0` and zero `user_vibe_relations`. This is consistent with V1.0's "V1.0 is a single-user local dev build" stance — no alembic, no migrations, no historical value to preserve.

The SMOKE.md document in V1.2 includes the reset command as step 0.

---

## 3. Backend Logic

### 3.1 New functions in `profile_calc.py`

#### 3.1.1 Level formula

```python
import math


def compute_level(interaction_count: int) -> int:
    """sqrt-based level curve.

    count=0 → L0 (陌生人, pre-interaction)
    count=1 → L1 (初遇)
    count=4 → L2 (浅尝)
    count=9 → L3 (识味)
    count=16 → L4 (入门) — FIRST LEVEL TO UNLOCK MATCH-SCORE DISPLAY
    count=25 → L5 (辨识)
    count=36 → L6 (洞察)
    count=49 → L7 (共鸣)
    count=64 → L8 (通透)
    count=81 → L9 (灵魂)
    count=100+ → L10 (知己, capped)
    """
    if interaction_count <= 0:
        return 0
    return int(math.sqrt(interaction_count))
```

#### 3.1.2 Level metadata

```python
LEVEL_DATA = {
    0:  {"title": "陌生人", "emoji": "👤"},
    1:  {"title": "初遇",   "emoji": "🌱"},
    2:  {"title": "浅尝",   "emoji": "🌿"},
    3:  {"title": "识味",   "emoji": "🌳"},
    4:  {"title": "入门",   "emoji": "🔍"},
    5:  {"title": "辨识",   "emoji": "🎯"},
    6:  {"title": "洞察",   "emoji": "🧠"},
    7:  {"title": "共鸣",   "emoji": "💞"},
    8:  {"title": "通透",   "emoji": "🔮"},
    9:  {"title": "灵魂",   "emoji": "👻"},
    10: {"title": "知己",   "emoji": "💎"},
}


def level_info(interaction_count: int) -> dict:
    """Return {level, title, emoji, next_level_at} for the given count.

    For L10+, level is capped at 10 (LEVEL_DATA only goes to 10) but
    next_level_at still computes as (level+1)**2 = 121 so the progress
    bar keeps advancing even for knowledge users.
    """
    level = compute_level(interaction_count)
    capped_level = min(level, 10)
    info = LEVEL_DATA[capped_level]
    next_at = (level + 1) ** 2
    return {
        "level": level,
        "title": info["title"],
        "emoji": info["emoji"],
        "next_level_at": next_at,
    }
```

#### 3.1.3 UI stage derivation

```python
def compute_ui_stage(level: int) -> str:
    """Map level to a frontend rendering stage.

    welcome  — popup pre-interaction state (level 0)
    learning — rate card with no % shown (L1-L3)
    early    — rate card with % shown + small level hint (L4-L5)
    stable   — rate card with %, no hint (L6+)
    """
    if level == 0:
        return "welcome"
    if level <= 3:
        return "learning"
    if level <= 5:
        return "early"
    return "stable"
```

#### 3.1.4 Atomic interaction counter

```python
from app.models.user import User


def increment_interaction(user_id: int) -> tuple[int, int, bool]:
    """Atomically increment user.interaction_count by 1.

    Creates the user row if it doesn't exist (lazy bootstrap — no cold-start
    router pre-creates the row any more).

    Returns (new_count, new_level, level_up) where level_up is True iff
    the increment crossed a sqrt boundary (e.g., 8→9 crosses L2→L3).
    """
    db = database.SessionLocal()
    try:
        user = db.scalar(select(User).where(User.id == user_id))
        if user is None:
            user = User(id=user_id, username="default", interaction_count=0)
            db.add(user)
            db.flush()
        old_level = compute_level(user.interaction_count)
        user.interaction_count += 1
        new_count = user.interaction_count
        new_level = compute_level(new_count)
        db.commit()
        return new_count, new_level, new_level > old_level
    finally:
        db.close()
```

#### 3.1.5 `_apply_delta` must lazy-create missing relations

**Critical change to existing V1.0 behavior.** In V1.0, the cold-start router pre-created all 24 `UserVibeRelation` rows for user_id=1 before any analyze call could happen. V1.0's `_apply_delta` had `if rel is None: continue` — silently skipping missing rows because it assumed cold-start had already run.

V1.2 deletes cold-start. On a brand-new user's first analyze, NO `UserVibeRelation` rows exist yet. The current `_apply_delta` would skip every tag and `FIRST_IMPRESSION_DELTA` would be a no-op — **silently breaking the entire cold-start replacement**.

Fix: `_apply_delta` must lazy-create the `UserVibeRelation` row if it doesn't exist, using `curiosity_weight=0.0, core_weight=0.0` as defaults, then apply the delta on top. Also lazy-create the `User` row if it doesn't exist (defensive, since `increment_interaction` already does this but `_apply_delta` runs first in the analyze router).

Modified function:

```python
def _apply_delta(user_id: int, tag_ids: list[int], delta: float,
                 target_column: str, action: str) -> None:
    db = database.SessionLocal()
    try:
        # Lazy-create user row if missing (defensive — increment_interaction
        # runs later in the same request but we need FK target to exist now)
        user = db.scalar(select(User).where(User.id == user_id))
        if user is None:
            db.add(User(id=user_id, username="default", interaction_count=0))
            db.flush()

        for tid in tag_ids:
            rel = db.scalar(
                select(UserVibeRelation).where(
                    UserVibeRelation.user_id == user_id,
                    UserVibeRelation.vibe_tag_id == tid,
                )
            )
            if rel is None:
                # Lazy-create with default weights, then apply delta on top
                rel = UserVibeRelation(
                    user_id=user_id,
                    vibe_tag_id=tid,
                    curiosity_weight=0.0,
                    core_weight=0.0,
                )
                db.add(rel)
                db.flush()

            if target_column == "curiosity":
                rel.curiosity_weight += delta
            elif target_column == "core":
                rel.core_weight += delta
            else:
                raise ValueError(f"unknown target_column: {target_column}")
            rel.updated_at = datetime.utcnow()
            db.add(ActionLog(
                user_id=user_id, vibe_tag_id=tid, action=action,
                delta=delta, target_column=target_column,
            ))
        db.commit()
    finally:
        db.close()
```

**Import note:** `_apply_delta` needs `from app.models.user import User` added to `profile_calc.py` (it was only importing `UserVibeRelation`, `VibeTag`, `ActionLog` before).

**Behavior on invalid `tid`:** If a caller passes a `tid` that isn't in the `vibe_tags` table, the `FOREIGN KEY` constraint on `UserVibeRelation.vibe_tag_id` will fail at `db.flush()`. This would crash the analyze route with a 500. `llm_tagger.analyze` already validates tag_ids are in 1-24 and filters invalid ones, so this shouldn't happen in practice. We accept the crash behavior as a fail-fast signal that seed wasn't run.

### 3.2 Dynamic weight functions

#### 3.2.1 Hesitation-scaled curiosity delta

```python
CURIOSITY_BASE = 0.5


def dynamic_curiosity_delta(hesitation_ms: int | None) -> float:
    """Scale CURIOSITY_BASE by hesitation duration.

    hesitation_ms is None (not captured) → baseline 0.5
    < 500   ms (impulsive click)         → 0.15  (0.3×)
    500-2000 ms (normal deliberation)    → 0.5   (baseline)
    2000-10000 ms (deep thought)         → 0.75  (1.5×)
    > 10000 ms (user walked away)         → 0.5   (fallback to baseline)
    Negative or absurd values → None treatment
    """
    if hesitation_ms is None or hesitation_ms < 0 or hesitation_ms > 60000:
        return CURIOSITY_BASE
    if hesitation_ms < 500:
        return CURIOSITY_BASE * 0.3
    if hesitation_ms < 2000:
        return CURIOSITY_BASE
    if hesitation_ms < 10000:
        return CURIOSITY_BASE * 1.5
    return CURIOSITY_BASE
```

#### 3.2.2 Read-time-scaled core delta

```python
STAR_BASE = 10.0
BOMB_BASE = -10.0


def dynamic_core_delta(action: str, read_ms: int | None) -> float:
    """Scale ±10 by read duration.

    read_ms is None → baseline
    < 1000   ms (reflex click)        → 0.5×
    1000-5000 ms (quick read)          → 1.0×
    5000-30000 ms (careful read)       → 1.5×
    > 30000 ms (user walked away)      → 1.0× fallback
    """
    base = STAR_BASE if action == "star" else BOMB_BASE
    if read_ms is None or read_ms < 0 or read_ms > 300000:
        return base
    if read_ms < 1000:
        return base * 0.5
    if read_ms < 5000:
        return base
    if read_ms < 30000:
        return base * 1.5
    return base
```

### 3.3 Router changes

#### 3.3.1 `/vibe/analyze`

Path: `backend/app/routers/vibe.py`. The existing handler is extended; the signature stays.

```python
CURIOSITY_DELTA = 0.5  # DELETED — replaced by dynamic function
STAR_DELTA = 10.0       # DELETED — replaced by dynamic function
BOMB_DELTA = -10.0      # DELETED — replaced by dynamic function

FIRST_IMPRESSION_DELTA = 10.0


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    # 1. Tagger (cache-aware, unchanged)
    try:
        result = await llm_tagger.analyze(payload.text, payload.domain)
    except llm_tagger.LlmParseError as e:
        raise HTTPException(503, detail={"error": {"code": "LLM_PARSE_FAIL", "message": str(e)}})
    except llm_tagger.LlmTimeoutError as e:
        raise HTTPException(503, detail={"error": {"code": "LLM_TIMEOUT", "message": str(e)}})

    matched_tag_ids = [t["tag_id"] for t in result["matched_tags"]]
    matched_tag_names = [t["name"] for t in result["matched_tags"]]
    item_tags = [(t["tag_id"], t["weight"]) for t in result["matched_tags"]]

    # 2. Detect first interaction (before counter increments)
    user = db.scalar(select(User).where(User.id == user_id))
    is_first = (user is None) or (user.interaction_count == 0)

    # 3. Match score (may return 0 for first-time — frontend hides the number)
    score = profile_calc.compute_match_score(user_id=user_id, item_tags=item_tags)

    # 4. Roast (unchanged)
    user_top_tag_names = profile_calc.get_top_core_tag_names(user_id=user_id, n=3)
    roast = await llm_roaster.generate_roast(
        text=payload.text, domain=payload.domain,
        item_tag_names=matched_tag_names,
        user_top_tag_names=user_top_tag_names,
    )

    # 5. Apply profile update (the KEY branch)
    if is_first:
        # First-interaction-as-cold-start: strong core signal instead of weak curiosity
        profile_calc.apply_core_delta(
            user_id=user_id,
            tag_ids=matched_tag_ids,
            delta=FIRST_IMPRESSION_DELTA,
            action="first_impression",
        )
    else:
        # Dynamic curiosity based on hesitation
        curiosity_delta = profile_calc.dynamic_curiosity_delta(payload.hesitation_ms)
        profile_calc.apply_curiosity_delta(
            user_id=user_id,
            tag_ids=matched_tag_ids,
            delta=curiosity_delta,
            action="analyze",
        )

    # 6. Increment interaction counter AFTER profile update
    new_count, new_level, level_up = profile_calc.increment_interaction(user_id)
    info = profile_calc.level_info(new_count)
    ui_stage = profile_calc.compute_ui_stage(new_level)

    return AnalyzeResponse(
        match_score=score,
        summary=result["summary"],
        roast=roast,
        matched_tags=[MatchedTag(**t) for t in result["matched_tags"]],
        text_hash=result["text_hash"],
        cache_hit=result["cache_hit"],
        interaction_count=new_count,
        level=new_level,
        level_title=info["title"],
        level_emoji=info["emoji"],
        next_level_at=info["next_level_at"],
        level_up=level_up,
        ui_stage=ui_stage,
    )
```

**Ordering matters:** `is_first` is determined from the **pre-increment** count. Then profile is updated (using `is_first` branch). Then counter is incremented. This guarantees the first interaction gets the cold-start bonus AND shows `level=1, level_up=true` in the response.

#### 3.3.2 `/vibe/action`

```python
@router.post("/action", response_model=ActionResponse)
def action(
    payload: ActionRequest,
    user_id: int = Depends(get_current_user_id),
):
    delta = profile_calc.dynamic_core_delta(payload.action, payload.read_ms)
    profile_calc.apply_core_delta(
        user_id=user_id,
        tag_ids=payload.matched_tag_ids,
        delta=delta,
        action=payload.action,
    )
    new_count, new_level, level_up = profile_calc.increment_interaction(user_id)
    info = profile_calc.level_info(new_count)
    return ActionResponse(
        status="ok",
        updated_tags=len(payload.matched_tag_ids),
        interaction_count=new_count,
        level=new_level,
        level_title=info["title"],
        level_emoji=info["emoji"],
        next_level_at=info["next_level_at"],
        level_up=level_up,
    )
```

#### 3.3.3 `/profile/radar`

```python
@router.get("/radar", response_model=RadarResponse)
def radar(db, user_id):
    user = db.scalar(select(User).where(User.id == user_id))
    count = user.interaction_count if user else 0
    info = profile_calc.level_info(count)
    ui_stage = profile_calc.compute_ui_stage(info["level"])

    data = profile_calc.compute_radar(user_id=user_id)
    total_analyze = db.scalar(...) or 0
    total_action = db.scalar(...) or 0

    return RadarResponse(
        user_id=user_id,
        interaction_count=count,
        level=info["level"],
        level_title=info["title"],
        level_emoji=info["emoji"],
        next_level_at=info["next_level_at"],
        ui_stage=ui_stage,
        dimensions=data["dimensions"],
        total_analyze_count=total_analyze,
        total_action_count=total_action,
    )
```

### 3.4 Schema changes

#### 3.4.1 `schemas/analyze.py`

```python
class AnalyzeContext(BaseModel):
    page_title: str | None = None
    page_url: str | None = None


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=2, max_length=500)
    domain: str
    context: AnalyzeContext | None = None
    hesitation_ms: int | None = None  # NEW


class MatchedTag(BaseModel):
    tag_id: int
    name: str
    weight: float


class AnalyzeResponse(BaseModel):
    match_score: int
    summary: str
    roast: str = ""
    matched_tags: list[MatchedTag]
    text_hash: str
    cache_hit: bool
    # NEW fields
    interaction_count: int
    level: int
    level_title: str
    level_emoji: str
    next_level_at: int
    level_up: bool
    ui_stage: str  # "welcome" | "learning" | "early" | "stable"
```

#### 3.4.2 `schemas/action.py`

```python
class ActionRequest(BaseModel):
    action: Literal["star", "bomb"]
    matched_tag_ids: list[int]
    text_hash: str | None = None
    read_ms: int | None = None  # NEW


class ActionResponse(BaseModel):
    status: str
    updated_tags: int
    # NEW fields
    interaction_count: int
    level: int
    level_title: str
    level_emoji: str
    next_level_at: int
    level_up: bool
```

#### 3.4.3 `schemas/profile.py`

```python
class RadarResponse(BaseModel):
    user_id: int
    # NEW fields
    interaction_count: int
    level: int
    level_title: str
    level_emoji: str
    next_level_at: int
    ui_stage: str
    # Existing
    dimensions: list[RadarDimension]
    total_analyze_count: int
    total_action_count: int
```

---

## 4. Frontend Changes

### 4.1 Timestamp capture

#### 4.1.1 `hesitation_ms` (content/index.ts)

```typescript
let iconShownAt: number | null = null;

// When the floating icon appears:
currentIcon = renderFloatingIcon(root, {
  x: rect.right + window.scrollX,
  y: rect.top + window.scrollY,
  onClick: () => onIconClick(text, domain),
});
iconShownAt = performance.now();  // NEW

// In onIconClick:
async function onIconClick(text: string, domain: Domain) {
  if (!currentIcon) return;
  const hesitationMs = iconShownAt !== null
    ? Math.max(0, Math.round(performance.now() - iconShownAt))
    : null;

  // ... existing loading animation setup ...

  const msg: Msg = {
    type: "ANALYZE",
    payload: {
      text,
      domain,
      pageTitle: document.title,
      pageUrl: location.href,
      hesitationMs,  // NEW
    },
  };
  // ... rest unchanged ...
}
```

Reset `iconShownAt = null` in `clearUi()` to avoid stale values.

#### 4.1.2 `read_ms` (VibeCard.ts)

```typescript
export function renderVibeCard(props: VibeCardProps): HTMLElement {
  const { parent, result, sourceDomain, text, onClose } = props;
  const card = document.createElement("div");
  card.className = "vr-card";
  const cardShownAt = performance.now();  // NEW

  // ... existing share button, roast, summary, tags setup ...

  const star = document.createElement("button");
  star.className = "vr-btn star";
  star.textContent = "💎 懂我";
  star.addEventListener("click", async () => {
    const readMs = Math.max(0, Math.round(performance.now() - cardShownAt));
    const actionResult = await sendAction("star", result, readMs);
    star.textContent = "✓ 已确权";
    handlePostActionLevelUp(card, actionResult, onClose);
  });

  const bomb = /* ... same pattern with readMs ... */;
}

async function sendAction(
  action: "star" | "bomb",
  result: AnalyzeResult,
  readMs: number,
): Promise<ActionResult> {
  const msg: Msg = {
    type: "ACTION",
    payload: {
      action,
      matchedTagIds: result.matched_tags.map((t) => t.tag_id),
      textHash: result.text_hash,
      readMs,  // NEW
    },
  };
  return await send<ActionResult>(msg);
}
```

### 4.2 Shared types (`shared/types.ts`)

```typescript
// Extended
export interface AnalyzeResult {
  match_score: number;
  summary: string;
  roast: string;
  matched_tags: MatchedTag[];
  text_hash: string;
  cache_hit: boolean;
  // NEW
  interaction_count: number;
  level: number;
  level_title: string;
  level_emoji: string;
  next_level_at: number;
  level_up: boolean;
  ui_stage: "welcome" | "learning" | "early" | "stable";
}

// NEW (replaces the loose `{status, updated_tags}` previously inferred)
export interface ActionResult {
  status: string;
  updated_tags: number;
  interaction_count: number;
  level: number;
  level_title: string;
  level_emoji: string;
  next_level_at: number;
  level_up: boolean;
}

// Extended
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

// Msg union — REMOVE cold_start variants, ADD hesitationMs/readMs to existing
export type Msg =
  | { type: "ANALYZE"; payload: { text: string; domain: Domain; pageTitle: string; pageUrl: string; hesitationMs: number | null } }
  | { type: "ACTION"; payload: { action: "star" | "bomb"; matchedTagIds: number[]; textHash?: string; readMs: number | null } }
  | { type: "GET_RADAR" }
  | { type: "RECOMMEND"; payload: { text: string; sourceDomain: Domain; matchedTagIds: number[] } };
// NOTE: COLD_START_GET_CARDS and COLD_START_SUBMIT DELETED

// Deleted types: CategoryCard, CardOption, ColdStartCardsResult, ColdStartSubmitResult
```

### 4.3 Background service worker changes

`background/index.ts` — remove cold-start cases, extend analyze and action bodies:

```typescript
case "ANALYZE":
  return fetchJson("POST", "/vibe/analyze", {
    text: msg.payload.text,
    domain: msg.payload.domain,
    context: {
      page_title: msg.payload.pageTitle,
      page_url: msg.payload.pageUrl,
    },
    hesitation_ms: msg.payload.hesitationMs,  // NEW
  });

case "ACTION":
  return fetchJson("POST", "/vibe/action", {
    action: msg.payload.action,
    matched_tag_ids: msg.payload.matchedTagIds,
    text_hash: msg.payload.textHash,
    read_ms: msg.payload.readMs,  // NEW
  });

// DELETED: COLD_START_GET_CARDS, COLD_START_SUBMIT cases
```

### 4.4 VibeCard stage-based rendering

```typescript
// After score element, before roast:
if (result.ui_stage === "learning") {
  // Hide the numeric percentage entirely
  // Replace with a level badge + learning hint
  score.style.display = "none";

  const learningBadge = document.createElement("div");
  learningBadge.className = "vr-learning-badge";
  learningBadge.innerHTML = `
    ${result.level_emoji} Lv.${result.level} ${result.level_title}
    <div class="vr-learning-sub">学习中 · 第 ${result.interaction_count} 次</div>
  `;
  card.appendChild(learningBadge);
} else if (result.ui_stage === "early") {
  // Show percentage + small level hint next to it
  const levelHint = document.createElement("div");
  levelHint.className = "vr-level-hint";
  levelHint.textContent = `${result.level_emoji} Lv.${result.level} ${result.level_title}`;
  score.appendChild(levelHint);
}
// "stable" → no level badge at all, card looks identical to V1.1
```

CSS adds `.vr-learning-badge`, `.vr-learning-sub`, `.vr-level-hint` classes (details in Task breakdown).

### 4.5 Level-up animation (`LevelUpOverlay.ts` NEW)

New file `extension/src/content/ui/LevelUpOverlay.ts`:

```typescript
import type { AnalyzeResult, ActionResult } from "../../shared/types";

type LevelUpSource = AnalyzeResult | ActionResult;

const PREV_LEVEL_DATA: Record<number, { title: string; emoji: string }> = {
  0:  { title: "陌生人", emoji: "👤" },
  1:  { title: "初遇",   emoji: "🌱" },
  2:  { title: "浅尝",   emoji: "🌿" },
  3:  { title: "识味",   emoji: "🌳" },
  4:  { title: "入门",   emoji: "🔍" },
  5:  { title: "辨识",   emoji: "🎯" },
  6:  { title: "洞察",   emoji: "🧠" },
  7:  { title: "共鸣",   emoji: "💞" },
  8:  { title: "通透",   emoji: "🔮" },
  9:  { title: "灵魂",   emoji: "👻" },
  10: { title: "知己",   emoji: "💎" },
};

function prevLevelEmoji(newLevel: number): string {
  const prev = Math.max(0, newLevel - 1);
  return PREV_LEVEL_DATA[Math.min(prev, 10)]?.emoji ?? "👤";
}

export function playLevelUpAnimation(
  container: HTMLElement,
  result: LevelUpSource,
  onDone: () => void,
): HTMLElement {
  const overlay = document.createElement("div");
  overlay.className = "vr-levelup-overlay";
  overlay.innerHTML = `
    <div class="vr-levelup-old">${prevLevelEmoji(result.level)}</div>
    <div class="vr-levelup-arrows">↓ ↓ ↓</div>
    <div class="vr-levelup-new">${result.level_emoji}</div>
    <div class="vr-levelup-title">Lv.${result.level} ${result.level_title}</div>
    <div class="vr-levelup-sub">🎉 你已经喂了 ${result.interaction_count} 个信号</div>
    <button class="vr-levelup-skip" title="跳过">×</button>
  `;
  container.appendChild(overlay);

  const skipBtn = overlay.querySelector(".vr-levelup-skip") as HTMLButtonElement;
  let finished = false;

  const finish = () => {
    if (finished) return;
    finished = true;
    overlay.style.opacity = "0";
    setTimeout(() => {
      overlay.remove();
      onDone();
    }, 300);
  };

  skipBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    finish();
  });

  setTimeout(finish, 1500);

  return overlay;
}
```

**CSS (append to `styles.css`):**

```css
.vr-levelup-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #6c5ce7, #a29bfe);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 100;
  transition: opacity 0.3s;
  overflow: hidden;
}

.vr-levelup-old {
  font-size: 36px;
  opacity: 0;
  animation: vr-old-fadeup 0.6s ease forwards;
}
@keyframes vr-old-fadeup {
  0%   { opacity: 0.9; transform: translateY(0) scale(1); }
  100% { opacity: 0; transform: translateY(-30px) scale(0.6); }
}

.vr-levelup-arrows {
  color: rgba(255, 255, 255, 0.7);
  font-size: 16px;
  margin: 8px 0;
  animation: vr-arrows-bounce 0.8s ease-in-out infinite;
}
@keyframes vr-arrows-bounce {
  0%, 100% { opacity: 0.4; transform: translateY(0); }
  50%      { opacity: 1;   transform: translateY(4px); }
}

.vr-levelup-new {
  font-size: 72px;
  opacity: 0;
  transform: scale(0.3);
  animation: vr-new-popin 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) 0.5s forwards;
}
@keyframes vr-new-popin {
  0%   { opacity: 0; transform: scale(0.3); }
  60%  { opacity: 1; transform: scale(1.15); }
  100% { opacity: 1; transform: scale(1.0); }
}

.vr-levelup-title {
  color: #fff;
  font-size: 24px;
  font-weight: 700;
  margin-top: 12px;
  opacity: 0;
  animation: vr-title-fadein 0.4s ease 1.1s forwards;
  letter-spacing: 2px;
}
@keyframes vr-title-fadein {
  to { opacity: 1; }
}

.vr-levelup-sub {
  color: rgba(255, 255, 255, 0.85);
  font-size: 12px;
  margin-top: 8px;
  opacity: 0;
  animation: vr-title-fadein 0.4s ease 1.3s forwards;
}

.vr-levelup-skip {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  border: none;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}
.vr-levelup-skip:hover { background: rgba(255, 255, 255, 0.3); }
```

### 4.6 Triggering level-up animation in content/index.ts

```typescript
const result = await send<AnalyzeResult>(msg);
loading.remove();

if (result.level_up) {
  const tempCard = document.createElement("div");
  tempCard.className = "vr-card";
  currentIcon.appendChild(tempCard);
  playLevelUpAnimation(tempCard, result, () => {
    tempCard.remove();
    currentCard = renderVibeCard({ parent: currentIcon, result, sourceDomain: domain, text, onClose: clearUi });
  });
} else {
  currentCard = renderVibeCard({ parent: currentIcon, result, sourceDomain: domain, text, onClose: clearUi });
}
```

### 4.7 Post-action level-up

When the user clicks 💎/💣, the action response may also carry `level_up: true`. Handle in VibeCard:

```typescript
function handlePostActionLevelUp(
  card: HTMLElement,
  actionResult: ActionResult,
  onClose: () => void,
): void {
  if (!actionResult.level_up) {
    setTimeout(onClose, 1500);
    return;
  }
  // Play level-up overlay ON TOP of the existing vibe card
  const overlay = playLevelUpAnimation(card, actionResult, () => {
    setTimeout(onClose, 400);
  });
  overlay.style.borderRadius = "12px";
}
```

### 4.8 Popup welcome page

`popup/welcome.ts` (NEW):

```typescript
export function renderWelcome(root: HTMLElement): void {
  root.innerHTML = `
    <div class="vr-welcome">
      <div class="vr-welcome-logo">◉ ◉ ◉</div>
      <h2>Vibe-Radar</h2>
      <p class="vr-welcome-tagline">我会通过你的真实行为认识你</p>
      <p class="vr-welcome-hint">
        去下列任意网站划一段文字，<br>
        让我从你的第一口开始了解你。
      </p>
      <ul class="vr-welcome-sites">
        <li>📚 豆瓣读书</li>
        <li>🎬 豆瓣电影</li>
        <li>🎮 Steam</li>
        <li>🎵 网易云音乐</li>
      </ul>
    </div>
  `;
}
```

`popup/popup.ts` rewritten:

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

Note: `profile_initialized` in `chrome.storage.local` is no longer read or written anywhere — deletion is fine (any residual value is simply ignored).

### 4.9 Popup radar view — add level progress bar

`popup/radar.ts`:

```typescript
export async function renderRadar(root: HTMLElement, data: RadarResult): Promise<void> {
  root.innerHTML = `
    <h2>你的审美雷达</h2>
    <div id="radar"></div>
    <div class="vr-level-panel">
      <div class="vr-level-current">${data.level_emoji} Lv.${data.level} ${data.level_title}</div>
      <div class="vr-level-bar">
        <div class="vr-level-fill" style="width: ${
          data.next_level_at > 0
            ? Math.min(100, Math.round((data.interaction_count / data.next_level_at) * 100))
            : 100
        }%"></div>
      </div>
      <div class="vr-level-counts">
        已喂入 <b>${data.interaction_count}</b> 个信号 · 下一级还差 <b>${Math.max(0, data.next_level_at - data.interaction_count)}</b> 次
      </div>
    </div>
    <div class="stats">
      已鉴定 <b>${data.total_analyze_count}</b> 次 · 已确权 <b>${data.total_action_count}</b> 次
    </div>
  `;

  // ... existing ECharts init using data.dimensions ...
}
```

The old `renderRadar` was parameterless and called `send<RadarResult>` itself. It now takes the pre-loaded `data` from `main()`. This avoids a double-call.

### 4.10 Deleted / renamed frontend files

| Path | Action |
|---|---|
| `extension/src/popup/coldStart.ts` | DELETE |
| `extension/src/popup/popup.ts` | REWRITE per §4.8 |
| `extension/src/popup/radar.ts` | MODIFY per §4.9 (signature change) |
| `extension/src/popup/welcome.ts` | CREATE per §4.8 |
| `extension/src/content/ui/LevelUpOverlay.ts` | CREATE per §4.5 |
| `extension/src/content/ui/VibeCard.ts` | MODIFY per §4.4 + §4.1.2 + §4.7 |
| `extension/src/content/index.ts` | MODIFY per §4.1.1 + §4.6 |
| `extension/src/shared/types.ts` | MODIFY per §4.2 |
| `extension/src/background/index.ts` | MODIFY per §4.3 |
| `extension/src/content/ui/styles.css` | APPEND level-up overlay + welcome + level badge classes |

---

## 5. Error Handling Matrix

| Scenario | Where | Behavior |
|---|---|---|
| `hesitation_ms` is negative, > 60000, or missing | backend `dynamic_curiosity_delta` | treat as None → baseline 0.5 |
| `read_ms` is negative, > 300000, or missing | backend `dynamic_core_delta` | treat as None → baseline ±10 |
| User row doesn't exist on first analyze | `increment_interaction` | lazy create with `interaction_count=0`, then increment to 1 |
| Two concurrent analyze calls (hypothetical — single-user V1.0 locally) | SQLAlchemy | commit transaction per call; worst case two increments in quick succession — acceptable |
| `/profile/radar` called before any interaction | radar router | returns `interaction_count=0, level=0, ui_stage="welcome"` with empty dimensions — popup uses these to show welcome page |
| Frontend loses `iconShownAt` (rapid reselect) | content/index.ts | reset to null on `clearUi`, send `hesitationMs: null` if null — backend uses baseline |
| `level > 10` in frontend rendering | VibeCard / Popup | `level_emoji` and `level_title` always fall back to L10 data ("💎 知己") via `min(level, 10)` on backend; progress bar still advances via `next_level_at=(level+1)**2` |
| User clicks "skip" on level-up animation | LevelUpOverlay | immediately transitions to final vibe card; no animation loss |

---

## 6. Testing Strategy

### 6.1 Backend unit tests

**`test_profile_calc.py` additions:**

```python
# Level formula
def test_compute_level_boundaries():
    assert profile_calc.compute_level(0) == 0
    assert profile_calc.compute_level(1) == 1
    assert profile_calc.compute_level(3) == 1
    assert profile_calc.compute_level(4) == 2  # L2 boundary
    assert profile_calc.compute_level(9) == 3
    assert profile_calc.compute_level(16) == 4
    assert profile_calc.compute_level(100) == 10
    assert profile_calc.compute_level(144) == 12  # L10+ returns raw level, caller caps

def test_level_info_next_level_at():
    assert profile_calc.level_info(0)["next_level_at"] == 1
    assert profile_calc.level_info(1)["next_level_at"] == 4
    assert profile_calc.level_info(15)["next_level_at"] == 16
    assert profile_calc.level_info(100)["level"] == 10
    assert profile_calc.level_info(100)["title"] == "知己"

def test_compute_ui_stage_boundaries():
    assert profile_calc.compute_ui_stage(0) == "welcome"
    assert profile_calc.compute_ui_stage(1) == "learning"
    assert profile_calc.compute_ui_stage(3) == "learning"
    assert profile_calc.compute_ui_stage(4) == "early"
    assert profile_calc.compute_ui_stage(5) == "early"
    assert profile_calc.compute_ui_stage(6) == "stable"
    assert profile_calc.compute_ui_stage(10) == "stable"

# Dynamic weights
def test_dynamic_curiosity_delta_all_brackets():
    assert profile_calc.dynamic_curiosity_delta(None) == 0.5
    assert profile_calc.dynamic_curiosity_delta(-100) == 0.5   # invalid
    assert profile_calc.dynamic_curiosity_delta(100) == 0.15   # <500
    assert profile_calc.dynamic_curiosity_delta(1000) == 0.5   # baseline
    assert profile_calc.dynamic_curiosity_delta(5000) == 0.75  # deep
    assert profile_calc.dynamic_curiosity_delta(15000) == 0.5  # walked away

def test_dynamic_core_delta_star_and_bomb():
    assert profile_calc.dynamic_core_delta("star", None) == 10.0
    assert profile_calc.dynamic_core_delta("star", 500) == 5.0   # reflex
    assert profile_calc.dynamic_core_delta("star", 3000) == 10.0 # normal
    assert profile_calc.dynamic_core_delta("star", 10000) == 15.0 # careful
    assert profile_calc.dynamic_core_delta("bomb", 3000) == -10.0
    assert profile_calc.dynamic_core_delta("bomb", 10000) == -15.0

# Counter + level-up detection
def test_increment_interaction_creates_user_if_missing():
    count, level, up = profile_calc.increment_interaction(user_id=1)
    assert count == 1
    assert level == 1
    assert up is True

def test_increment_interaction_crosses_boundary():
    # seed count=3, then increment to 4 → L1 → L2 = level_up
    db = database.SessionLocal()
    db.add(User(id=1, username="default", interaction_count=3))
    db.commit(); db.close()
    count, level, up = profile_calc.increment_interaction(user_id=1)
    assert count == 4
    assert level == 2
    assert up is True

def test_increment_interaction_no_boundary():
    db = database.SessionLocal()
    db.add(User(id=1, username="default", interaction_count=5))
    db.commit(); db.close()
    count, level, up = profile_calc.increment_interaction(user_id=1)
    assert count == 6
    assert level == 2
    assert up is False
```

**`test_vibe.py` additions (extends existing file, does not replace):**

```python
def test_analyze_first_interaction_applies_core_weight(monkeypatch):
    # Fresh user — no cold-start pre-seeding possible now
    seed_all()  # vibe_tags only
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_roaster(monkeypatch, "first impression roast")

    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "my first highlight", "domain": "book"})
    assert r.status_code == 200
    body = r.json()
    assert body["level"] == 1
    assert body["level_up"] is True
    assert body["ui_stage"] == "learning"
    assert body["interaction_count"] == 1

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    assert rel.core_weight == 10.0   # first-impression delta
    assert rel.curiosity_weight == 0.0  # NOT curiosity
    db.close()


def test_analyze_second_interaction_uses_curiosity(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_roaster(monkeypatch, "r")
    # Prime with one analyze
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    # Second — should use curiosity
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "second", "domain": "book", "hesitation_ms": 1000})
    body = r.json()
    assert body["interaction_count"] == 2

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    # core_weight still 10 from first, curiosity bumped by 0.5 (baseline)
    assert rel.core_weight == 10.0
    assert rel.curiosity_weight == 0.5
    db.close()


def test_analyze_hesitation_scales_curiosity(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 2, "weight": 0.9}], "summary": "x"
    }))
    _install_fake_roaster(monkeypatch, "r")
    # Prime
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    # Impulsive click — curiosity gets 0.15 not 0.5
    client.post("/api/v1/vibe/analyze",
                json={"text": "quick", "domain": "book", "hesitation_ms": 100})
    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 2,
        )
    )
    assert rel.curiosity_weight == 0.15
    db.close()


def test_analyze_reaches_level_up_at_count_4(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "x"
    }))
    _install_fake_roaster(monkeypatch, "r")
    for i in range(3):
        client.post("/api/v1/vibe/analyze", json={"text": f"text-{i}", "domain": "book"})
    r = client.post("/api/v1/vibe/analyze", json={"text": "fourth", "domain": "book"})
    body = r.json()
    assert body["interaction_count"] == 4
    assert body["level"] == 2
    assert body["level_up"] is True
    assert body["level_title"] == "浅尝"


def test_action_star_read_ms_scales_core_delta(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "x"
    }))
    _install_fake_roaster(monkeypatch, "r")
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    # First analyze already gave core_weight=10 via first_impression
    # Now star with 10 second read → +15 additional
    client.post("/api/v1/vibe/action", json={
        "action": "star",
        "matched_tag_ids": [1],
        "read_ms": 10000,
    })
    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    assert rel.core_weight == 25.0  # 10 (first) + 15 (careful star)
    db.close()


def test_action_response_carries_level_info(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({"tags": [{"tag_id": 1, "weight": 0.9}], "summary": "x"}))
    _install_fake_roaster(monkeypatch, "r")
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    r = client.post("/api/v1/vibe/action", json={
        "action": "star",
        "matched_tag_ids": [1],
    })
    body = r.json()
    assert "level" in body
    assert "level_title" in body
    assert body["interaction_count"] == 2
```

**`test_profile.py` additions:**

```python
def test_radar_returns_level_fields_and_welcome_stage_for_new_user():
    seed_all()
    r = client.get("/api/v1/profile/radar")
    body = r.json()
    assert body["interaction_count"] == 0
    assert body["level"] == 0
    assert body["ui_stage"] == "welcome"
    assert body["level_title"] == "陌生人"
    assert body["next_level_at"] == 1
```

**File deletion:** `test_cold_start.py` is removed in its entirety.

### 6.2 Frontend (no automated)

Manual smoke in `extension/SMOKE.md` — see §7.

### 6.3 Coverage targets

- `profile_calc.py` — ≥90% (pure functions, easy to cover)
- routers — ≥75%
- Total backend suite should grow from 51 tests to ~70 tests

---

## 7. Delivery and SMOKE.md Rewrite

### 7.1 Step 0: Reset database

The very first step of V1.2's smoke test is **destructive** and must be explicit:

```markdown
### 0. Reset database (one-time, required)
Run this once before any V1.2 smoke step:
```bash
cd D:/qhyProject/vibe4.0/backend
rm data/vibe_radar.db
source .venv/Scripts/activate
python -m app.services.seed
```
This rebuilds the schema with the new `interaction_count` column, re-inserts
the 24 vibe tags, and clears any V1.0/V1.1 test data. The user_id=1 row no
longer exists — it will be lazy-created on first analyze.
```

### 7.2 Updated smoke steps

The 10 existing steps are replaced/updated:

| Step | V1.1 behavior | V1.2 behavior |
|---|---|---|
| 1 (was "Cold start") | Open popup → 18 cards → pick 6 | **Delete.** Welcome page shows instead. |
| 2 (popup reopens) | Radar view after cold-start | Welcome page persists until `interaction_count > 0`, then radar |
| 3 (highlight-to-analyze) | Purple icon → card with 73% | **Modified:** First highlight shows `🌱 Lv.1 初遇` level-up animation → card has no % (shows `学习中 · 第 1 次`) |
| 4 (star/bomb flow) | Button → radar updates | Same but action response now carries level info; may trigger level-up animation on specific counts |
| 5 (cache hit) | — | Unchanged |
| 6 (backend down) | — | Unchanged |
| 7 (out-of-whitelist) | — | Unchanged |
| 8 (roast display) | — | Unchanged (V1.1) |
| 9 (cross-domain recommend) | — | Unchanged (V1.1) |
| 10 (share poster) | — | Unchanged (V1.1) |
| **NEW 11** | — | Hesitation scaling verification (impulsive click vs deliberate) |
| **NEW 12** | — | Read-time scaling verification (fast vs careful star) |
| **NEW 13** | — | Level progression: highlight 4× to trigger L1→L2 animation |

Full SMOKE.md rewrite will be produced in the implementation plan's Task for documentation.

---

## 8. Implementation size estimate

- **Approximately 10 tasks** split across backend and frontend:
  - T1: Delete cold-start backend (router + schema + tests + main.py import)
  - T2: Add `users.interaction_count` field + model test
  - T3: `profile_calc` new functions (`compute_level`, `level_info`, `compute_ui_stage`, `dynamic_curiosity_delta`, `dynamic_core_delta`, `increment_interaction`) + modify `_apply_delta` to lazy-create missing User and UserVibeRelation rows + unit tests
  - T4: Extend schemas (analyze / action / profile) with level fields and `hesitation_ms` / `read_ms`
  - T5: Rewrite `/vibe/analyze` and `/vibe/action` routers + extend `/profile/radar`; update `test_vibe.py` and `test_profile.py`
  - T6: Delete cold-start frontend (`coldStart.ts`, Msg types, bg cases, popup dispatch) + extend `shared/types.ts`
  - T7: Content script — capture `hesitationMs` and `readMs`; update `ActionResult` + `sendAction` signature; pass through background
  - T8: VibeCard stage-based rendering (`learning` / `early` / `stable` branches) + new CSS classes
  - T9: `LevelUpOverlay.ts` + CSS animations; wire into content/index.ts and VibeCard for both analyze and action paths
  - T10: Popup welcome page + radar level panel; SMOKE.md rewrite
- Roughly ~800 lines added, ~300 deleted net.
- Slightly larger than V1.1 (9 tasks / ~600 lines) but smaller than V1.0 (17 tasks).

---

## 9. Open questions / future work

These are NOT in V1.2 scope but worth logging:

- **Level celebration sound** — a brief audio cue on level-up would amplify the reward, but Chrome extensions in MV3 have restricted audio APIs. Park for SP-C.
- **Level-up notification persistence** — if the user dismisses the rate card mid-animation, the celebration is lost. V1.2 accepts this — the level change still commits to DB; only the animation is lost. SP-C could add a "missed celebrations" queue.
- **Recovery from mis-first-click** — if user's first highlight is an accidental wrong selection, their first-impression cold start is locked in permanently. Could add a "reset me" button in L4+ that clears `interaction_count` and `user_vibe_relations`. Out of scope for SP-A.
- **Empty-profile match score** — when level=1 but user browses a lot, `compute_match_score` still returns 0 on an all-zero vector (except for the first-impression tag). This is fine because the frontend hides the number in `learning` stage, but once they reach `early` stage (count=16), the match score may still feel biased toward the first-impression tags. Accept as known behavior; SP-B's behavior profile will provide additional signal to de-bias.
- **SP-B handoff** — SP-A explicitly records `hesitation_ms` and `read_ms` per interaction in `action_log` (via the existing `delta` field carrying the scaled value), which provides a data trail SP-B can mine later without needing new logging.
