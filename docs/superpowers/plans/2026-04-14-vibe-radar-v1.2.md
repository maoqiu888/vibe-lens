# Vibe-Radar V1.2 (SP-A) Implementation Plan — Behavioral Exhaust + Level System

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace V1.0's static 18-card cold-start wizard with organic, behavior-driven signal harvesting (first-interaction-as-cold-start, hesitation-scaled curiosity, read-time-scaled core weight) and add a sqrt-curve 10+-level gamification system with visible level-up animations to make profile growth feel like a game.

**Architecture:** Backend deletes the cold-start router + schemas + cards data entirely and adds a new `interaction_count` field on the `users` table that drives level computation. A new set of pure functions in `profile_calc.py` handles level math, dynamic weight scaling, and atomic counter increment. The `_apply_delta` function is modified to lazy-create missing `User` and `UserVibeRelation` rows so the first interaction can populate weights with no pre-seeding. Frontend deletes the 18-card popup flow, captures `hesitation_ms` and `read_ms` via `performance.now()` at key UI events, renders the rate card differently based on a new `ui_stage` field (learning / early / stable), and plays a 1.5-second Canvas-free CSS animation overlay inside the rate card whenever the backend response sets `level_up: true`. The popup gains a welcome page for zero-interaction users and a level progress bar below the radar chart.

**Tech Stack:** Same as V1.1 — Python 3.10+ / FastAPI / SQLAlchemy / pytest / httpx / TypeScript / esbuild / Chrome MV3. Zero new dependencies. All animations are pure CSS keyframes.

**Spec:** `docs/superpowers/specs/2026-04-14-vibe-radar-v1.2-design.md`

**Prereqs:**
- V1.1 is complete and working (backend 51 tests green at commit `5b16f08`)
- Current HEAD is commit `99390b8` (the V1.2 spec commit), 33 total commits
- `backend/.venv` active deps installed
- `extension/node_modules` installed
- **Before any manual smoke testing:** delete `backend/data/vibe_radar.db` and re-run `python -m app.services.seed` (automated pytest uses its own temp DB per test via the `_isolated_db` fixture, so no reset needed for test runs — only for interactive use of the extension after V1.2 lands)

**Conventions (inherited):**
- Strict TDD for backend: failing test → run → implement → run passing → commit
- Extension: no automated tests; verify via `npm run build` and manual SMOKE.md steps
- Attribute-access DB convention: `from app import database; database.SessionLocal()`, never `from app.database import SessionLocal`
- Conventional commits
- pytest from `backend/` with venv activated: `source .venv/Scripts/activate && pytest tests/`

**Test count arithmetic:**
- V1.1 end: 51 tests
- Task 1 deletes `test_cold_start.py` (−5 tests) → 46
- Task 3 adds ~12 profile_calc tests → 58
- Task 5 adds ~7 router tests and cleans up `test_vibe._init_profile` → ~65
- Final: **~65 tests green**

**File structure map (cumulative — bold = new in V1.2; strikethrough = deleted):**

```
backend/app/
├── services/
│   ├── llm_tagger.py            (unchanged)
│   ├── llm_roaster.py           (unchanged)
│   ├── llm_recommender.py       (unchanged)
│   ├── profile_calc.py          (MAJOR: new funcs + _apply_delta lazy-create)
│   ├── seed.py                  (unchanged)
│   └── seed_data.py             (remove CARD_META dict)
├── schemas/
│   ├── analyze.py               (extend: hesitation_ms + level fields)
│   ├── action.py                (extend: read_ms + level fields)
│   ├── profile.py               (extend: level fields)
│   ├── recommend.py             (unchanged)
│   └── ~~cold_start.py~~        (DELETE)
├── routers/
│   ├── vibe.py                  (MAJOR: first-interaction branch, dynamic weights, level fields)
│   ├── profile.py               (extend: level fields)
│   └── ~~cold_start.py~~        (DELETE)
├── models/
│   └── user.py                  (add interaction_count field)
└── main.py                      (remove cold_start import + include_router)

backend/tests/
├── test_profile_calc.py         (MAJOR: +12 tests for level/dynamic/increment/lazy-create)
├── test_vibe.py                 (rewrite _init_profile helper; add 7 new tests)
├── test_profile.py              (extend: new level fields assertion)
├── test_llm_tagger.py           (unchanged)
├── test_llm_roaster.py          (unchanged)
├── test_llm_recommender.py      (unchanged)
├── test_models.py               (add interaction_count assertion)
├── test_seed.py                 (unchanged)
└── ~~test_cold_start.py~~       (DELETE)

extension/src/
├── shared/
│   └── types.ts                 (remove cold_start types, add level fields, ActionResult)
├── background/
│   └── index.ts                 (remove cold_start cases, add hesitation_ms/read_ms mapping)
├── content/
│   ├── index.ts                 (capture iconShownAt → hesitationMs on click)
│   └── ui/
│       ├── VibeCard.ts          (stage-based rendering, capture cardShownAt → readMs)
│       ├── **LevelUpOverlay.ts**    (NEW: 1.5s celebration overlay)
│       ├── styles.css           (append level-up + welcome + level-hint classes)
│       ├── FloatingIcon.ts      (unchanged)
│       ├── SharePoster.ts       (unchanged)
│       └── RecommendCard.ts     (unchanged)
└── popup/
    ├── popup.ts                 (rewrite: welcome or radar branch)
    ├── popup.html               (unchanged)
    ├── popup.css                (append welcome + level panel classes)
    ├── **welcome.ts**           (NEW: welcome page renderer)
    ├── radar.ts                 (signature change: take pre-loaded RadarResult)
    └── ~~coldStart.ts~~         (DELETE)

extension/SMOKE.md               (rewrite: step 0 + steps 1/2/3 + new steps 11/12/13)
```

---

## Task 1: Delete cold-start backend (router + schema + test + wiring)

**Files:**
- Delete: `backend/app/routers/cold_start.py`
- Delete: `backend/app/schemas/cold_start.py`
- Delete: `backend/tests/test_cold_start.py`
- Modify: `backend/app/main.py` (remove import + include_router)
- Modify: `backend/app/services/seed_data.py` (remove CARD_META dict)

- [ ] **Step 1: Delete the three cold-start files**

```bash
cd D:/qhyProject/vibe4.0
rm backend/app/routers/cold_start.py
rm backend/app/schemas/cold_start.py
rm backend/tests/test_cold_start.py
```

- [ ] **Step 2: Edit `backend/app/main.py` to remove cold-start wiring**

Find the imports section. Current imports include:

```python
from app.routers import cold_start
from app.routers import vibe
from app.routers import profile
```

Change to:

```python
from app.routers import vibe
from app.routers import profile
```

Find the `app.include_router` calls at the bottom. Current:

```python
app.include_router(cold_start.router)
app.include_router(vibe.router)
app.include_router(profile.router)
```

Change to:

```python
app.include_router(vibe.router)
app.include_router(profile.router)
```

- [ ] **Step 3: Edit `backend/app/services/seed_data.py` to remove CARD_META**

Open the file. Find the `CARD_META = {...}` dict (a large dict with keys 1-24 mapping to `{"tagline": ..., "examples": [...]}`). **Delete the entire dict**, including its preceding comment line `# Taglines and example works for cold-start cards (keyed by tag_id)`. Also delete any trailing blank lines that become excessive.

The file should retain exactly three top-level names: `TAGS`, `CATEGORY_LABELS`, `compute_opposite`. Verify after editing:

```bash
cd D:/qhyProject/vibe4.0/backend && source .venv/Scripts/activate
python -c "from app.services.seed_data import TAGS, CATEGORY_LABELS, compute_opposite; print(len(TAGS), len(CATEGORY_LABELS))"
```
Expected: `24 6`

And verify CARD_META is gone:

```bash
python -c "from app.services.seed_data import CARD_META" 2>&1 | grep -o "ImportError.*CARD_META"
```
Expected: `ImportError: cannot import name 'CARD_META' from 'app.services.seed_data'`

- [ ] **Step 4: Sanity-import main.py**

```bash
python -c "from app.main import app; print('ok')"
```
Expected: `ok`. No ImportError.

Note: pytest is intentionally NOT run in this task. The existing `test_vibe.py::_init_profile` helper still calls `client.post("/api/v1/cold-start/submit", ...)` which would now 404. We'll fix that helper in Task 5 when we rewrite `test_vibe.py`. Running pytest between Task 1 and Task 5 will show failures — this is expected and tracked.

- [ ] **Step 5: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/routers/ backend/app/schemas/ backend/tests/ backend/app/main.py backend/app/services/seed_data.py
git commit -m "chore(backend): delete cold-start router, schema, tests, and CARD_META"
git log --oneline | head -3
```
Expected: 34 commits total, new commit on top of `99390b8`.

---

## Task 2: Add `users.interaction_count` field

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/tests/test_models.py` (add interaction_count assertion)

- [ ] **Step 1: Update `backend/app/models/user.py`**

Current file:

```python
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

Replace with:

```python
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    interaction_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: Extend `backend/tests/test_models.py`**

Find the existing `test_tables_are_created_and_basic_crud_works` function. The existing test inserts a `User(id=1, username="default")` and reads it back. Add assertions around the `interaction_count` default. The existing user insert line:

```python
    u = User(id=1, username="default")
    db.add(u)
```

Right after the `db.commit()` call (where other assertions already live), add before the final `db.close()`:

```python
    # interaction_count defaults to 0 and is readable
    u2 = db.scalar(select(User).where(User.id == 1))
    assert u2.interaction_count == 0
```

The `select` import should already be at the top of the file from V1.0. If not, add `from sqlalchemy import select`.

- [ ] **Step 3: Run the model test**

```bash
cd D:/qhyProject/vibe4.0/backend && source .venv/Scripts/activate && pytest tests/test_models.py -v
```
Expected: 1 passing. The test exercises the new column's default.

- [ ] **Step 4: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/models/user.py backend/tests/test_models.py
git commit -m "feat(backend): add users.interaction_count column for gamification counter"
```
Expected: 35 commits.

---

## Task 3: `profile_calc` new functions + `_apply_delta` lazy-create + tests

**Files:**
- Modify: `backend/app/services/profile_calc.py`
- Modify: `backend/tests/test_profile_calc.py`

- [ ] **Step 1: Write failing tests for level functions**

Open `backend/tests/test_profile_calc.py`. At the top, verify these imports exist; add what's missing:

```python
import pytest

from app import database
from app.models.action_log import ActionLog
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.services import profile_calc
from app.services.seed import seed_all
```

Append these tests at the end of the file:

```python
# ------------------- V1.2 level system -------------------

def test_compute_level_zero_interactions():
    assert profile_calc.compute_level(0) == 0


def test_compute_level_sqrt_boundaries():
    assert profile_calc.compute_level(1) == 1
    assert profile_calc.compute_level(3) == 1
    assert profile_calc.compute_level(4) == 2
    assert profile_calc.compute_level(8) == 2
    assert profile_calc.compute_level(9) == 3
    assert profile_calc.compute_level(15) == 3
    assert profile_calc.compute_level(16) == 4
    assert profile_calc.compute_level(24) == 4
    assert profile_calc.compute_level(25) == 5
    assert profile_calc.compute_level(100) == 10
    # L10+ returns raw sqrt — caller caps for metadata lookup
    assert profile_calc.compute_level(144) == 12


def test_level_info_returns_title_emoji_next_at():
    info = profile_calc.level_info(0)
    assert info == {"level": 0, "title": "陌生人", "emoji": "👤", "next_level_at": 1}

    info = profile_calc.level_info(1)
    assert info["level"] == 1
    assert info["title"] == "初遇"
    assert info["emoji"] == "🌱"
    assert info["next_level_at"] == 4

    info = profile_calc.level_info(15)
    assert info["level"] == 3
    assert info["title"] == "识味"
    assert info["next_level_at"] == 16

    info = profile_calc.level_info(100)
    assert info["level"] == 10
    assert info["title"] == "知己"
    assert info["next_level_at"] == 121

    # L10+ caps metadata but keeps next_level_at advancing
    info = profile_calc.level_info(144)
    assert info["level"] == 12
    assert info["title"] == "知己"  # capped metadata
    assert info["emoji"] == "💎"
    assert info["next_level_at"] == 169


def test_compute_ui_stage_boundaries():
    assert profile_calc.compute_ui_stage(0) == "welcome"
    assert profile_calc.compute_ui_stage(1) == "learning"
    assert profile_calc.compute_ui_stage(3) == "learning"
    assert profile_calc.compute_ui_stage(4) == "early"
    assert profile_calc.compute_ui_stage(5) == "early"
    assert profile_calc.compute_ui_stage(6) == "stable"
    assert profile_calc.compute_ui_stage(10) == "stable"


def test_dynamic_curiosity_delta_all_brackets():
    assert profile_calc.dynamic_curiosity_delta(None) == 0.5
    assert profile_calc.dynamic_curiosity_delta(-1) == 0.5
    assert profile_calc.dynamic_curiosity_delta(70000) == 0.5
    assert profile_calc.dynamic_curiosity_delta(100) == pytest.approx(0.15)
    assert profile_calc.dynamic_curiosity_delta(499) == pytest.approx(0.15)
    assert profile_calc.dynamic_curiosity_delta(500) == 0.5
    assert profile_calc.dynamic_curiosity_delta(1999) == 0.5
    assert profile_calc.dynamic_curiosity_delta(2000) == 0.75
    assert profile_calc.dynamic_curiosity_delta(9999) == 0.75
    assert profile_calc.dynamic_curiosity_delta(10000) == 0.5


def test_dynamic_core_delta_star_brackets():
    assert profile_calc.dynamic_core_delta("star", None) == 10.0
    assert profile_calc.dynamic_core_delta("star", 500) == 5.0
    assert profile_calc.dynamic_core_delta("star", 999) == 5.0
    assert profile_calc.dynamic_core_delta("star", 1000) == 10.0
    assert profile_calc.dynamic_core_delta("star", 4999) == 10.0
    assert profile_calc.dynamic_core_delta("star", 5000) == 15.0
    assert profile_calc.dynamic_core_delta("star", 29999) == 15.0
    assert profile_calc.dynamic_core_delta("star", 30000) == 10.0
    assert profile_calc.dynamic_core_delta("star", 500000) == 10.0


def test_dynamic_core_delta_bomb_brackets():
    assert profile_calc.dynamic_core_delta("bomb", None) == -10.0
    assert profile_calc.dynamic_core_delta("bomb", 500) == -5.0
    assert profile_calc.dynamic_core_delta("bomb", 3000) == -10.0
    assert profile_calc.dynamic_core_delta("bomb", 10000) == -15.0


def test_increment_interaction_creates_user_lazily():
    seed_all()
    # No pre-existing user row
    count, level, level_up = profile_calc.increment_interaction(user_id=1)
    assert count == 1
    assert level == 1
    assert level_up is True

    db = database.SessionLocal()
    user = db.scalar(select(User).where(User.id == 1))
    assert user is not None
    assert user.interaction_count == 1
    db.close()


def test_increment_interaction_crosses_sqrt_boundary():
    seed_all()
    db = database.SessionLocal()
    db.add(User(id=1, username="default", interaction_count=3))
    db.commit()
    db.close()

    count, level, level_up = profile_calc.increment_interaction(user_id=1)
    assert count == 4
    assert level == 2
    assert level_up is True


def test_increment_interaction_no_level_up_within_bracket():
    seed_all()
    db = database.SessionLocal()
    db.add(User(id=1, username="default", interaction_count=5))
    db.commit()
    db.close()

    count, level, level_up = profile_calc.increment_interaction(user_id=1)
    assert count == 6
    assert level == 2
    assert level_up is False


def test_apply_delta_lazy_creates_user_and_relation():
    """V1.2 core fix — _apply_delta must lazy-create missing rows.

    Before V1.2, cold-start pre-created 24 UserVibeRelation rows. V1.2
    deletes cold-start, so on a brand-new user the first _apply_delta
    call encounters zero rows. It must create them on the fly.
    """
    seed_all()
    # No user row, no relations — pristine state
    profile_calc.apply_core_delta(
        user_id=1,
        tag_ids=[1, 5],
        delta=10.0,
        action="first_impression",
    )

    db = database.SessionLocal()
    # User row was lazy-created
    user = db.scalar(select(User).where(User.id == 1))
    assert user is not None
    assert user.interaction_count == 0  # apply_delta does NOT touch counter

    # Both relations were lazy-created with the delta applied
    rels = db.scalars(
        select(UserVibeRelation).where(UserVibeRelation.user_id == 1)
    ).all()
    by_tag = {r.vibe_tag_id: r for r in rels}
    assert len(rels) == 2
    assert by_tag[1].core_weight == 10.0
    assert by_tag[1].curiosity_weight == 0.0
    assert by_tag[5].core_weight == 10.0

    # ActionLog was written for each tag
    logs = db.scalars(select(ActionLog).where(ActionLog.action == "first_impression")).all()
    assert len(logs) == 2
    db.close()


def test_apply_delta_does_not_duplicate_on_second_call():
    """Second _apply_delta for the same tag must UPDATE, not INSERT."""
    seed_all()
    profile_calc.apply_core_delta(user_id=1, tag_ids=[1], delta=10.0, action="first_impression")
    profile_calc.apply_core_delta(user_id=1, tag_ids=[1], delta=10.0, action="star")

    db = database.SessionLocal()
    rels = db.scalars(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    ).all()
    assert len(rels) == 1
    assert rels[0].core_weight == 20.0
    db.close()
```

Note: `select` import is used throughout — ensure `from sqlalchemy import select` is at the top of the test file (V1.0 tests already have it).

- [ ] **Step 2: Run to verify failures**

```bash
cd D:/qhyProject/vibe4.0/backend && source .venv/Scripts/activate && pytest tests/test_profile_calc.py -v
```
Expected: ALL new tests fail with `AttributeError: module 'app.services.profile_calc' has no attribute 'compute_level'` or similar. Existing tests (6 from V1.0) continue to pass.

- [ ] **Step 3: Add the new functions to `profile_calc.py`**

Open `backend/app/services/profile_calc.py`. At the top, verify imports — you should currently have:

```python
from datetime import datetime

import numpy as np
from sqlalchemy import select

from app import database
from app.models.action_log import ActionLog
from app.models.user_vibe_relation import UserVibeRelation
from app.models.vibe_tag import VibeTag
from app.services.seed_data import CATEGORY_LABELS
```

Add one more import:

```python
from app.models.user import User
```

And at the top, add `import math`:

```python
import math
from datetime import datetime

import numpy as np
from sqlalchemy import select

from app import database
from app.models.action_log import ActionLog
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.models.vibe_tag import VibeTag
from app.services.seed_data import CATEGORY_LABELS
```

Append these new constants and functions to the END of the file (after the existing `compute_radar` and `get_top_core_tag_names`):

```python
# ----------------------------------------------------------------------
# V1.2 — Level system and dynamic weights
# ----------------------------------------------------------------------

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


def compute_level(interaction_count: int) -> int:
    """sqrt-based level curve. L0 is pre-interaction, L10+ keeps climbing."""
    if interaction_count <= 0:
        return 0
    return int(math.sqrt(interaction_count))


def level_info(interaction_count: int) -> dict:
    """Return a dict with level, title, emoji, next_level_at.

    For levels above 10, metadata (title/emoji) is capped at L10's data
    ("知己" / "💎") but the raw level and next_level_at keep advancing.
    """
    level = compute_level(interaction_count)
    capped = min(level, 10)
    info = LEVEL_DATA[capped]
    next_at = (level + 1) ** 2
    return {
        "level": level,
        "title": info["title"],
        "emoji": info["emoji"],
        "next_level_at": next_at,
    }


def compute_ui_stage(level: int) -> str:
    """Map a level to the frontend rendering stage.

    welcome  — L0 (popup pre-interaction)
    learning — L1-L3 (rate card hides percentage)
    early    — L4-L5 (percentage visible with level hint)
    stable   — L6+ (percentage visible, no level hint)
    """
    if level <= 0:
        return "welcome"
    if level <= 3:
        return "learning"
    if level <= 5:
        return "early"
    return "stable"


CURIOSITY_BASE = 0.5


def dynamic_curiosity_delta(hesitation_ms: int | None) -> float:
    """Scale curiosity delta by hesitation duration.

    <500ms:       0.3× baseline (impulsive)
    500-2000ms:   1.0× baseline (normal)
    2000-10000ms: 1.5× baseline (deliberate)
    >10000ms or invalid: 1.0× baseline (fallback)
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


STAR_BASE = 10.0
BOMB_BASE = -10.0


def dynamic_core_delta(action: str, read_ms: int | None) -> float:
    """Scale ±10 by read duration on the vibe card.

    <1000ms: 0.5× (reflex)
    1000-5000ms: 1.0× (normal)
    5000-30000ms: 1.5× (careful)
    >30000ms or invalid: 1.0× fallback
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


def increment_interaction(user_id: int) -> tuple[int, int, bool]:
    """Atomically increment user.interaction_count by 1.

    Lazy-creates the user row if missing. Returns (new_count, new_level,
    level_up) where level_up is True iff the increment crossed a sqrt boundary.
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

- [ ] **Step 4: Rewrite `_apply_delta` to lazy-create missing rows**

In the same `profile_calc.py`, find the existing `_apply_delta` function. Its current body:

```python
def _apply_delta(user_id: int, tag_ids: list[int], delta: float,
                 target_column: str, action: str) -> None:
    db = database.SessionLocal()
    try:
        for tid in tag_ids:
            rel = db.scalar(
                select(UserVibeRelation).where(
                    UserVibeRelation.user_id == user_id,
                    UserVibeRelation.vibe_tag_id == tid,
                )
            )
            if rel is None:
                continue
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

Replace the body with the lazy-create version:

```python
def _apply_delta(user_id: int, tag_ids: list[int], delta: float,
                 target_column: str, action: str) -> None:
    db = database.SessionLocal()
    try:
        # Lazy-create user row if missing (V1.2: no cold-start pre-creates it)
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

- [ ] **Step 5: Run tests to verify all pass**

```bash
pytest tests/test_profile_calc.py -v
```
Expected: ALL tests pass — both the 6 pre-existing V1.0/V1.1 tests and the ~12 new V1.2 tests (`test_compute_level_zero_interactions`, `test_compute_level_sqrt_boundaries`, `test_level_info_*`, `test_compute_ui_stage_boundaries`, `test_dynamic_curiosity_delta_all_brackets`, `test_dynamic_core_delta_star_brackets`, `test_dynamic_core_delta_bomb_brackets`, `test_increment_interaction_creates_user_lazily`, `test_increment_interaction_crosses_sqrt_boundary`, `test_increment_interaction_no_level_up_within_bracket`, `test_apply_delta_lazy_creates_user_and_relation`, `test_apply_delta_does_not_duplicate_on_second_call`).

- [ ] **Step 6: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/services/profile_calc.py backend/tests/test_profile_calc.py
git commit -m "feat(backend): add level system and dynamic weight functions to profile_calc"
```
Expected: 36 commits.

---

## Task 4: Extend schemas with level fields and new request bodies

**Files:**
- Modify: `backend/app/schemas/analyze.py`
- Modify: `backend/app/schemas/action.py`
- Modify: `backend/app/schemas/profile.py`

This task contains no tests — schemas are exercised by the router tests in Task 5.

- [ ] **Step 1: Extend `backend/app/schemas/analyze.py`**

Current content:

```python
from pydantic import BaseModel, Field


class AnalyzeContext(BaseModel):
    page_title: str | None = None
    page_url: str | None = None


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=2, max_length=500)
    domain: str
    context: AnalyzeContext | None = None


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
```

Replace with:

```python
from pydantic import BaseModel, Field


class AnalyzeContext(BaseModel):
    page_title: str | None = None
    page_url: str | None = None


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=2, max_length=500)
    domain: str
    context: AnalyzeContext | None = None
    hesitation_ms: int | None = None


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
    interaction_count: int
    level: int
    level_title: str
    level_emoji: str
    next_level_at: int
    level_up: bool
    ui_stage: str
```

- [ ] **Step 2: Extend `backend/app/schemas/action.py`**

Current content:

```python
from typing import Literal

from pydantic import BaseModel


class ActionRequest(BaseModel):
    action: Literal["star", "bomb"]
    matched_tag_ids: list[int]
    text_hash: str | None = None


class ActionResponse(BaseModel):
    status: str
    updated_tags: int
```

Replace with:

```python
from typing import Literal

from pydantic import BaseModel


class ActionRequest(BaseModel):
    action: Literal["star", "bomb"]
    matched_tag_ids: list[int]
    text_hash: str | None = None
    read_ms: int | None = None


class ActionResponse(BaseModel):
    status: str
    updated_tags: int
    interaction_count: int
    level: int
    level_title: str
    level_emoji: str
    next_level_at: int
    level_up: bool
```

- [ ] **Step 3: Extend `backend/app/schemas/profile.py`**

Current content:

```python
from pydantic import BaseModel


class DominantTag(BaseModel):
    tag_id: int
    name: str


class RadarDimension(BaseModel):
    category: str
    category_label: str
    score: float
    dominant_tag: DominantTag


class RadarResponse(BaseModel):
    user_id: int
    dimensions: list[RadarDimension]
    total_analyze_count: int
    total_action_count: int
```

Replace with:

```python
from pydantic import BaseModel


class DominantTag(BaseModel):
    tag_id: int
    name: str


class RadarDimension(BaseModel):
    category: str
    category_label: str
    score: float
    dominant_tag: DominantTag


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

- [ ] **Step 4: Verify schemas import**

```bash
cd D:/qhyProject/vibe4.0/backend && source .venv/Scripts/activate
python -c "from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse; from app.schemas.action import ActionRequest, ActionResponse; from app.schemas.profile import RadarResponse; print('schemas ok')"
```
Expected: `schemas ok`

- [ ] **Step 5: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/schemas/analyze.py backend/app/schemas/action.py backend/app/schemas/profile.py
git commit -m "feat(backend): extend schemas with level fields and hesitation_ms/read_ms"
```
Expected: 37 commits.

---

## Task 5: Rewrite routers + test_vibe + test_profile

**Files:**
- Modify: `backend/app/routers/vibe.py` (analyze + action routes)
- Modify: `backend/app/routers/profile.py` (radar route)
- Modify: `backend/tests/test_vibe.py` (MAJOR: rewrite `_init_profile`, add new tests)
- Modify: `backend/tests/test_profile.py`

- [ ] **Step 1: Rewrite `backend/app/routers/vibe.py`**

Open the file. At the top, the current imports include (among others):

```python
from app.deps import get_current_user_id, get_db
from app.schemas.action import ActionRequest, ActionResponse
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse, MatchedTag
from app.services import llm_recommender, llm_roaster, llm_tagger, profile_calc
```

Add these additional imports:

```python
from sqlalchemy import select
from app.models.user import User
```

(If `select` is already imported, leave it. `User` is definitely new.)

Find the constants near the top of the file:

```python
CURIOSITY_DELTA = 0.5
STAR_DELTA = 10.0
BOMB_DELTA = -10.0
```

Replace with:

```python
FIRST_IMPRESSION_DELTA = 10.0
# Old constants (CURIOSITY_DELTA, STAR_DELTA, BOMB_DELTA) removed — now computed
# dynamically by profile_calc.dynamic_curiosity_delta / dynamic_core_delta.
```

Find the `analyze` function. Its current body starts with `try: result = await llm_tagger.analyze(...)` and ends with `return AnalyzeResponse(...)`. Replace the ENTIRE function body with:

```python
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    # 1. Tagger (cache-aware)
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

    # 2. Detect first-interaction BEFORE incrementing the counter
    user = db.scalar(select(User).where(User.id == user_id))
    is_first = (user is None) or (user.interaction_count == 0)

    # 3. Match score (may be 0 for first-time on empty vector — frontend hides it)
    score = profile_calc.compute_match_score(user_id=user_id, item_tags=item_tags)

    # 4. Roast (unchanged from V1.1)
    user_top_tag_names = profile_calc.get_top_core_tag_names(user_id=user_id, n=3)
    roast = await llm_roaster.generate_roast(
        text=payload.text,
        domain=payload.domain,
        item_tag_names=matched_tag_names,
        user_top_tag_names=user_top_tag_names,
    )

    # 5. Apply profile update — first-interaction gets strong core signal,
    #    subsequent calls get dynamic curiosity scaled by hesitation_ms.
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

Find the `action` function. Current:

```python
@router.post("/action", response_model=ActionResponse)
def action(
    payload: ActionRequest,
    user_id: int = Depends(get_current_user_id),
):
    delta = STAR_DELTA if payload.action == "star" else BOMB_DELTA
    profile_calc.apply_core_delta(
        user_id=user_id,
        tag_ids=payload.matched_tag_ids,
        delta=delta,
        action=payload.action,
    )
    return ActionResponse(status="ok", updated_tags=len(payload.matched_tag_ids))
```

Replace with:

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

The `recommend` route at the bottom of the file is UNCHANGED.

- [ ] **Step 2: Rewrite `backend/app/routers/profile.py`**

Open the file. Current content:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db
from app.models.action_log import ActionLog
from app.schemas.profile import RadarResponse
from app.services import profile_calc

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.get("/radar", response_model=RadarResponse)
def radar(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    data = profile_calc.compute_radar(user_id=user_id)
    total_analyze = db.scalar(
        select(func.count(ActionLog.id)).where(
            ActionLog.user_id == user_id,
            ActionLog.action == "analyze",
        )
    ) or 0
    total_action = db.scalar(
        select(func.count(ActionLog.id)).where(
            ActionLog.user_id == user_id,
            ActionLog.action.in_(["star", "bomb"]),
        )
    ) or 0
    return RadarResponse(
        user_id=user_id,
        dimensions=data["dimensions"],
        total_analyze_count=total_analyze,
        total_action_count=total_action,
    )
```

Replace with:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db
from app.models.action_log import ActionLog
from app.models.user import User
from app.schemas.profile import RadarResponse
from app.services import profile_calc

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


_EMPTY_DIMENSIONS = [
    {"category": c, "category_label": label, "score": 0.0,
     "dominant_tag": {"tag_id": 0, "name": "—"}}
    for c, label in [
        ("pace", "节奏"), ("mood", "情绪色调"), ("cognition", "智力负载"),
        ("narrative", "叙事质感"), ("world", "世界感"), ("intensity", "情感浓度"),
    ]
]


@router.get("/radar", response_model=RadarResponse)
def radar(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    user = db.scalar(select(User).where(User.id == user_id))
    interaction_count = user.interaction_count if user else 0

    info = profile_calc.level_info(interaction_count)
    ui_stage = profile_calc.compute_ui_stage(info["level"])

    # For zero-interaction users (welcome state), we return an empty radar
    # structure instead of calling compute_radar (which would KeyError on
    # the missing tag categories for a brand-new user). The frontend shows
    # the welcome page when interaction_count == 0 and never reads dimensions.
    if interaction_count == 0:
        dimensions = _EMPTY_DIMENSIONS
    else:
        data = profile_calc.compute_radar(user_id=user_id)
        dimensions = data["dimensions"]

    total_analyze = db.scalar(
        select(func.count(ActionLog.id)).where(
            ActionLog.user_id == user_id,
            ActionLog.action == "analyze",
        )
    ) or 0
    total_action = db.scalar(
        select(func.count(ActionLog.id)).where(
            ActionLog.user_id == user_id,
            ActionLog.action.in_(["star", "bomb"]),
        )
    ) or 0

    return RadarResponse(
        user_id=user_id,
        interaction_count=interaction_count,
        level=info["level"],
        level_title=info["title"],
        level_emoji=info["emoji"],
        next_level_at=info["next_level_at"],
        ui_stage=ui_stage,
        dimensions=dimensions,
        total_analyze_count=total_analyze,
        total_action_count=total_action,
    )
```

- [ ] **Step 3: Rewrite `_init_profile` helper in `test_vibe.py`**

Open `backend/tests/test_vibe.py`. Find the existing `_init_profile` helper:

```python
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
```

Replace with two helpers — `_init_profile` for tests that need an existing user WITH some core_weight (matching old cold-start result), and a no-op alternative for tests that want pristine state:

```python
def _prime_profile():
    """Prime user_id=1 with 6 tags at core_weight=15, mimicking V1.0 cold-start.

    Used by tests that want a pre-seeded profile to check star/bomb math.
    Does NOT touch interaction_count — it stays at 0 so tests can still
    verify first-interaction behavior if needed.
    """
    seed_all()
    db = database.SessionLocal()
    user = db.scalar(select(User).where(User.id == 1))
    if user is None:
        db.add(User(id=1, username="default", interaction_count=0))
        db.commit()
    for tid in [1, 5, 9, 13, 17, 21]:
        existing = db.scalar(
            select(UserVibeRelation).where(
                UserVibeRelation.user_id == 1,
                UserVibeRelation.vibe_tag_id == tid,
            )
        )
        if existing is None:
            db.add(UserVibeRelation(
                user_id=1, vibe_tag_id=tid,
                curiosity_weight=0.0, core_weight=15.0,
            ))
    db.commit()
    db.close()
```

**Delete** the old `_init_profile` function entirely.

Now find every call site of `_init_profile()` in the existing tests and change them to `_prime_profile()`:

- `test_analyze_returns_match_score_and_updates_curiosity` — change `_init_profile()` → `_prime_profile()`
- `test_analyze_second_call_hits_cache` — change `_init_profile()` → `_prime_profile()`
- `test_analyze_llm_parse_failure_returns_503` — change `_init_profile()` → `_prime_profile()`
- `test_analyze_roaster_failure_returns_empty_roast` — change `_init_profile()` → `_prime_profile()`
- `test_action_star_increments_core_weight` — change `_init_profile()` → `_prime_profile()`
- `test_action_bomb_decrements_core_weight` — change `_init_profile()` → `_prime_profile()`
- `test_recommend_happy_path_returns_3_cross_domain_items` — change `_init_profile()` → `_prime_profile()`
- `test_recommend_empty_tag_ids_rejected_by_pydantic` — change `_init_profile()` → `_prime_profile()`
- `test_recommend_invalid_tag_ids_returns_400` — change `_init_profile()` → `_prime_profile()`
- `test_recommend_all_same_domain_returns_503` — change `_init_profile()` → `_prime_profile()`
- `test_recommend_llm_parse_failure_returns_503` — change `_init_profile()` → `_prime_profile()`

All other `_init_profile()` calls (if any) — same treatment.

**Also update `test_action_bomb_decrements_core_weight`** — its assertion was `assert rel.core_weight == 5.0` (15 from cold-start + -10 from bomb). The math still holds because `_prime_profile` sets `core_weight=15.0` AND `/vibe/action` in V1.2 passes `read_ms=None` default → baseline −10. The final value is still 5. Leave the assertion alone.

**Also update `test_action_star_increments_core_weight`** — its assertion is `assert r2.core_weight == 10.0`. Tag 2 is NOT in the prime list (we only prime 1, 5, 9, 13, 17, 21), so `_prime_profile` doesn't create a row for tag 2. When the star action fires, `_apply_delta` will lazy-create tag 2's row with `core_weight = 0.0`, then add +10 → 10.0. Assertion still holds. Leave it.

- [ ] **Step 4: Add new V1.2 tests to `test_vibe.py`**

Append these tests to the end of `test_vibe.py`:

```python
def test_analyze_first_interaction_applies_first_impression_delta(monkeypatch):
    """First-ever analyze gives core_weight += 10 instead of curiosity += 0.5."""
    seed_all()
    # Do NOT call _prime_profile — start pristine
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_roaster(monkeypatch, "first impression")
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "my first highlight", "domain": "book"})
    assert r.status_code == 200
    body = r.json()
    assert body["level"] == 1
    assert body["level_up"] is True
    assert body["ui_stage"] == "learning"
    assert body["interaction_count"] == 1
    assert body["level_title"] == "初遇"
    assert body["level_emoji"] == "🌱"

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    assert rel.core_weight == 10.0
    assert rel.curiosity_weight == 0.0
    db.close()


def test_analyze_second_interaction_uses_curiosity(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    _install_fake_roaster(monkeypatch, "r")
    # First call (first-impression)
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    # Second call — baseline curiosity (no hesitation_ms sent)
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "second", "domain": "book"})
    body = r.json()
    assert body["interaction_count"] == 2
    assert body["level"] == 1
    assert body["level_up"] is False

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    assert rel.core_weight == 10.0  # unchanged from first
    assert rel.curiosity_weight == 0.5  # baseline applied on second
    db.close()


def test_analyze_impulsive_hesitation_gives_small_curiosity(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 2, "weight": 0.9}], "summary": "x"
    }))
    _install_fake_roaster(monkeypatch, "r")
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    client.post("/api/v1/vibe/analyze",
                json={"text": "quick", "domain": "book", "hesitation_ms": 100})

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 2,
        )
    )
    assert rel.curiosity_weight == pytest.approx(0.15)
    db.close()


def test_analyze_deliberate_hesitation_gives_bigger_curiosity(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 3, "weight": 0.9}], "summary": "x"
    }))
    _install_fake_roaster(monkeypatch, "r")
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    client.post("/api/v1/vibe/analyze",
                json={"text": "careful", "domain": "book", "hesitation_ms": 5000})

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 3,
        )
    )
    assert rel.curiosity_weight == pytest.approx(0.75)
    db.close()


def test_analyze_crosses_level_up_at_count_4(monkeypatch):
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
    assert body["ui_stage"] == "learning"


def test_action_star_read_ms_scales_core_delta(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "x"
    }))
    _install_fake_roaster(monkeypatch, "r")
    # First analyze → core_weight=10
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    # Careful star (10 second read) → delta=+15
    r = client.post("/api/v1/vibe/action", json={
        "action": "star",
        "matched_tag_ids": [1],
        "read_ms": 10000,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["interaction_count"] == 2
    assert "level" in body
    assert "level_title" in body

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    assert rel.core_weight == 25.0  # 10 (first-impression) + 15 (careful star)
    db.close()


def test_action_response_carries_level_fields(monkeypatch):
    seed_all()
    _install_fake_llm(monkeypatch, json.dumps({"tags": [{"tag_id": 1, "weight": 0.9}], "summary": "x"}))
    _install_fake_roaster(monkeypatch, "r")
    client.post("/api/v1/vibe/analyze", json={"text": "first", "domain": "book"})
    r = client.post("/api/v1/vibe/action", json={
        "action": "star",
        "matched_tag_ids": [1],
    })
    body = r.json()
    assert body["interaction_count"] == 2
    assert body["level"] == 1
    assert body["level_up"] is False
    assert body["level_title"] == "初遇"
    assert "next_level_at" in body
```

Also make sure `pytest` is imported at the top of `test_vibe.py`:

```python
import json

import pytest
```

- [ ] **Step 5: Update `backend/tests/test_profile.py`**

The existing test asserts specific shape. Find `test_radar_returns_6_dimensions` and extend it OR add a new test after it. Add the following new test at the end of `test_profile.py`:

```python
def test_radar_returns_level_fields_for_welcome_stage():
    """New user with no interactions gets welcome stage + level 0."""
    seed_all()
    # No _init_profile or _prime_profile — pristine state
    r = client.get("/api/v1/profile/radar")
    assert r.status_code == 200
    body = r.json()
    assert body["interaction_count"] == 0
    assert body["level"] == 0
    assert body["ui_stage"] == "welcome"
    assert body["level_title"] == "陌生人"
    assert body["level_emoji"] == "👤"
    assert body["next_level_at"] == 1
    assert len(body["dimensions"]) == 6  # empty dimensions still returned
```

The existing `test_radar_returns_6_dimensions` test uses `_init_profile()` which we deleted — we need to rewrite it to use `_prime_profile()` AND assert the new level fields. Find the existing test:

```python
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
    ...
```

Replace the `_init_profile` helper in this file with:

```python
def _prime_profile():
    """Prime user_id=1 with 6 tags at core_weight=15, mimicking V1.0 cold-start.
    Leaves interaction_count at 0 so /profile/radar returns non-welcome stage
    only if the caller bumps it manually."""
    seed_all()
    db = database.SessionLocal()
    user = db.scalar(select(User).where(User.id == 1))
    if user is None:
        db.add(User(id=1, username="default", interaction_count=5))  # pre-bumped so stage != welcome
        db.commit()
    else:
        user.interaction_count = 5
        db.commit()
    for tid in [1, 5, 9, 13, 17, 21]:
        existing = db.scalar(
            select(UserVibeRelation).where(
                UserVibeRelation.user_id == 1,
                UserVibeRelation.vibe_tag_id == tid,
            )
        )
        if existing is None:
            db.add(UserVibeRelation(
                user_id=1, vibe_tag_id=tid,
                curiosity_weight=0.0, core_weight=15.0,
            ))
    db.commit()
    db.close()
```

And rewrite `test_radar_returns_6_dimensions` to call `_prime_profile` and also assert level fields:

```python
def test_radar_returns_6_dimensions():
    _prime_profile()
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
    # V1.2 level fields
    assert body["interaction_count"] == 5
    assert body["level"] == 2
    assert body["ui_stage"] == "early"
```

Verify top-of-file imports include `UserVibeRelation`:

```python
from app.models.user_vibe_relation import UserVibeRelation
```

Add it if missing.

- [ ] **Step 6: Run full test suite to verify everything passes**

```bash
cd D:/qhyProject/vibe4.0/backend && source .venv/Scripts/activate && pytest tests/ -v
```
Expected: ~65 passing total. Breakdown:
- `test_llm_tagger.py`: 7
- `test_llm_roaster.py`: 6
- `test_llm_recommender.py`: 9
- `test_models.py`: 1
- `test_profile_calc.py`: ~18 (6 V1.0/V1.1 + 12 V1.2)
- `test_seed.py`: 2
- `test_vibe.py`: ~18 (11 V1.1 + 7 V1.2)
- `test_profile.py`: 2
- **Total: ~63-65** depending on how you count shared helpers.

If any test fails, read the failure carefully — common issues will be a missing `_prime_profile` call site, a missed `_init_profile` → `_prime_profile` rename, or a forgotten import.

- [ ] **Step 7: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add backend/app/routers/vibe.py backend/app/routers/profile.py backend/tests/test_vibe.py backend/tests/test_profile.py
git commit -m "feat(backend): integrate level system into analyze/action/radar routes"
git log --oneline | head -5
```
Expected: 38 commits. Backend V1.2 is now functionally complete.

---

## Task 6: Delete cold-start frontend + extend shared types + update background

**Files:**
- Delete: `extension/src/popup/coldStart.ts`
- Modify: `extension/src/shared/types.ts`
- Modify: `extension/src/background/index.ts`

- [ ] **Step 1: Delete the coldStart file**

```bash
cd D:/qhyProject/vibe4.0
rm extension/src/popup/coldStart.ts
```

- [ ] **Step 2: Rewrite `extension/src/shared/types.ts`**

Read the file first. Then apply these edits:

**Edit 1**: Extend `AnalyzeResult` with level fields. Current:

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

Change to:

```typescript
export interface AnalyzeResult {
  match_score: number;
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

**Edit 2**: Add a new `ActionResult` interface below `AnalyzeResult`:

```typescript
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
```

**Edit 3**: Extend `RadarResult` with level fields. Current:

```typescript
export interface RadarResult {
  user_id: number;
  dimensions: RadarDimension[];
  total_analyze_count: number;
  total_action_count: number;
}
```

Change to:

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

**Edit 4**: Remove cold-start types. Delete these interfaces entirely:

```typescript
export interface CardOption { ... }
export interface CategoryCard { ... }
export interface ColdStartCardsResult { ... }
export interface ColdStartSubmitResult { ... }
```

**Edit 5**: Update the `Msg` union — remove cold-start variants and extend analyze/action payloads. Current:

```typescript
export type Msg =
  | { type: "ANALYZE"; payload: { text: string; domain: Domain; pageTitle: string; pageUrl: string } }
  | { type: "ACTION"; payload: { action: "star" | "bomb"; matchedTagIds: number[]; textHash?: string } }
  | { type: "COLD_START_GET_CARDS" }
  | { type: "COLD_START_SUBMIT"; payload: { selectedTagIds: number[] } }
  | { type: "GET_RADAR" }
  | { type: "RECOMMEND"; payload: { text: string; sourceDomain: Domain; matchedTagIds: number[] } };
```

Change to:

```typescript
export type Msg =
  | { type: "ANALYZE"; payload: { text: string; domain: Domain; pageTitle: string; pageUrl: string; hesitationMs: number | null } }
  | { type: "ACTION"; payload: { action: "star" | "bomb"; matchedTagIds: number[]; textHash?: string; readMs: number | null } }
  | { type: "GET_RADAR" }
  | { type: "RECOMMEND"; payload: { text: string; sourceDomain: Domain; matchedTagIds: number[] } };
```

- [ ] **Step 3: Update `extension/src/background/index.ts`**

Read the file. Find the `routeApi` function. Current:

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

Replace with (remove two cold-start cases, add `hesitation_ms` to ANALYZE body, add `read_ms` to ACTION body):

```typescript
async function routeApi(msg: Msg): Promise<unknown> {
  switch (msg.type) {
    case "ANALYZE":
      return fetchJson("POST", "/vibe/analyze", {
        text: msg.payload.text,
        domain: msg.payload.domain,
        context: {
          page_title: msg.payload.pageTitle,
          page_url: msg.payload.pageUrl,
        },
        hesitation_ms: msg.payload.hesitationMs,
      });
    case "ACTION":
      return fetchJson("POST", "/vibe/action", {
        action: msg.payload.action,
        matched_tag_ids: msg.payload.matchedTagIds,
        text_hash: msg.payload.textHash,
        read_ms: msg.payload.readMs,
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

- [ ] **Step 4: Build to verify no TypeScript errors**

```bash
cd D:/qhyProject/vibe4.0/extension && npm run build
```
Expected: `Extension built to build`. If any TypeScript errors appear — typically "Property 'X' does not exist" — check that you updated VibeCard.ts references in Task 8 (VibeCard still uses the old types that Task 6 just changed, but Task 8 will fix that).

Actually — this is likely to FAIL because VibeCard.ts still uses the old `AnalyzeResult` shape without the level fields AND content/index.ts still calls `renderVibeCard` without `hesitationMs`. That's expected. **Skip the build verification at this step** — we'll run build again at the end of Task 9 after all frontend files are aligned.

- [ ] **Step 5: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/src/popup/coldStart.ts extension/src/shared/types.ts extension/src/background/index.ts
git commit -m "feat(ext): delete cold-start types/msgs and extend types with level fields"
```
Expected: 39 commits. Note: the commit includes the deleted `coldStart.ts` file (git records the deletion).

---

## Task 7: Content script timestamp capture

**Files:**
- Modify: `extension/src/content/index.ts`

This task captures `iconShownAt` and passes `hesitationMs` via the ANALYZE message. It does NOT touch `VibeCard.ts` — that's Task 8.

- [ ] **Step 1: Update `extension/src/content/index.ts`**

Read the file. At the top of the file, right after the existing `shadowRoot`, `currentIcon`, `currentCard` module-level variables, add one more:

```typescript
let shadowRoot: ShadowRoot | null = null;
let currentIcon: HTMLElement | null = null;
let currentCard: HTMLElement | null = null;
let iconShownAt: number | null = null;  // NEW
```

In `clearUi`, reset the new variable:

```typescript
function clearUi() {
  currentIcon?.remove();
  currentIcon = null;
  currentCard?.remove();
  currentCard = null;
  iconShownAt = null;  // NEW
}
```

Find the mouseup listener. It currently ends with a call to `renderFloatingIcon` — add the timestamp capture RIGHT AFTER the `renderFloatingIcon` call:

```typescript
document.addEventListener("mouseup", (e) => {
  if ((e.target as Element | null)?.closest("#vibe-radar-host")) return;
  const sel = window.getSelection();
  const text = sel?.toString().trim() ?? "";
  if (text.length < MIN_TEXT_LEN || text.length > MAX_TEXT_LEN) {
    clearUi();
    return;
  }

  const domain = detectDomain(location.href);
  if (!domain) return;

  const range = sel!.getRangeAt(0);
  const rect = range.getBoundingClientRect();

  clearUi();
  const root = ensureShadow();
  currentIcon = renderFloatingIcon(root, {
    x: rect.right + window.scrollX,
    y: rect.top + window.scrollY,
    onClick: () => onIconClick(text, domain),
  });
  iconShownAt = performance.now();  // NEW
});
```

Now find the `onIconClick` function. Its ANALYZE message currently reads:

```typescript
const msg: Msg = {
  type: "ANALYZE",
  payload: {
    text,
    domain,
    pageTitle: document.title,
    pageUrl: location.href,
  },
};
```

Change to:

```typescript
const hesitationMs = iconShownAt !== null
  ? Math.max(0, Math.round(performance.now() - iconShownAt))
  : null;

const msg: Msg = {
  type: "ANALYZE",
  payload: {
    text,
    domain,
    pageTitle: document.title,
    pageUrl: location.href,
    hesitationMs,
  },
};
```

Place the `hesitationMs` calculation right before the `const msg: Msg = ...` line.

- [ ] **Step 2: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/src/content/index.ts
git commit -m "feat(ext): capture iconShownAt and pass hesitationMs to analyze call"
```
Expected: 40 commits.

No build yet — TypeScript will still fail because VibeCard doesn't know about the new fields. Builds happen at the end of Task 9.

---

## Task 8: VibeCard stage-based rendering + read_ms capture + ActionResult type

**Files:**
- Modify: `extension/src/content/ui/VibeCard.ts`
- Modify: `extension/src/content/ui/styles.css`

- [ ] **Step 1: Rewrite `VibeCard.ts`**

Read the current file. The existing `renderVibeCard` function has this general shape:
- Takes props `{ parent, result, sourceDomain, text, onClose }`
- Creates `.vr-card` div
- Appends share button
- Appends score element
- Appends roast (V1.1) / summary fallback
- Appends tags
- Appends star/bomb buttons
- Appends "寻找同频代餐" link

For V1.2 we:
1. Import `ActionResult` type
2. Capture `cardShownAt = performance.now()` at function start
3. Branch score rendering on `result.ui_stage`
4. Pass `readMs` in the star/bomb click handlers' sendAction calls
5. Change `sendAction` to return an `ActionResult` (so the caller can check `level_up`)

Apply these edits in order.

**Edit 1**: Update imports at top of `VibeCard.ts`:

```typescript
import { copyPosterToClipboard, downloadPoster, generatePoster } from "./SharePoster";
import { renderRecommendCard } from "./RecommendCard";
import { send } from "../../shared/api";
import type { ActionResult, AnalyzeResult, Domain, Msg } from "../../shared/types";
```

(Add `ActionResult` to the type import.)

**Edit 2**: Start of `renderVibeCard` function — capture `cardShownAt`:

```typescript
export function renderVibeCard(props: VibeCardProps): HTMLElement {
  const { parent, result, sourceDomain, text, onClose } = props;
  const card = document.createElement("div");
  card.className = "vr-card";
  const cardShownAt = performance.now();  // NEW
```

**Edit 3**: The existing score element:

```typescript
const score = document.createElement("div");
score.className = "vr-score";
score.textContent = `${result.match_score}%`;
card.appendChild(score);
```

Replace with stage-based rendering:

```typescript
if (result.ui_stage === "learning") {
  // L1-L3: hide the numeric percentage; show a level badge instead
  const badge = document.createElement("div");
  badge.className = "vr-learning-badge";
  badge.innerHTML = `
    <div class="vr-learning-emoji">${result.level_emoji}</div>
    <div class="vr-learning-title">Lv.${result.level} ${result.level_title}</div>
    <div class="vr-learning-sub">学习中 · 第 ${result.interaction_count} 次</div>
  `;
  card.appendChild(badge);
} else {
  // L4+ show the percentage
  const score = document.createElement("div");
  score.className = "vr-score";
  score.textContent = `${result.match_score}%`;
  card.appendChild(score);

  if (result.ui_stage === "early") {
    // L4-L5: small level hint below the score
    const hint = document.createElement("div");
    hint.className = "vr-level-hint";
    hint.textContent = `${result.level_emoji} Lv.${result.level} ${result.level_title}`;
    card.appendChild(hint);
  }
  // "stable" (L6+) shows nothing extra
}
```

**Edit 4**: Rewrite the star and bomb click handlers to capture `readMs` and handle post-action level-up. Current:

```typescript
star.addEventListener("click", async () => {
  await sendAction("star", result);
  star.textContent = "✓ 已确权";
  setTimeout(onClose, 1500);
});

bomb.addEventListener("click", async () => {
  await sendAction("bomb", result);
  bomb.textContent = "✓ 已标记";
  setTimeout(onClose, 1500);
});
```

Replace with:

```typescript
star.addEventListener("click", async () => {
  const readMs = Math.max(0, Math.round(performance.now() - cardShownAt));
  try {
    const actionResult = await sendAction("star", result, readMs);
    star.textContent = "✓ 已确权";
    handlePostActionLevelUp(card, actionResult, onClose);
  } catch {
    star.textContent = "提交失败";
    setTimeout(onClose, 1500);
  }
});

bomb.addEventListener("click", async () => {
  const readMs = Math.max(0, Math.round(performance.now() - cardShownAt));
  try {
    const actionResult = await sendAction("bomb", result, readMs);
    bomb.textContent = "✓ 已标记";
    handlePostActionLevelUp(card, actionResult, onClose);
  } catch {
    bomb.textContent = "提交失败";
    setTimeout(onClose, 1500);
  }
});
```

**Edit 5**: Rewrite the `sendAction` helper at the bottom of `VibeCard.ts`. Current:

```typescript
async function sendAction(action: "star" | "bomb", result: AnalyzeResult) {
  const msg: Msg = {
    type: "ACTION",
    payload: {
      action,
      matchedTagIds: result.matched_tags.map((t) => t.tag_id),
      textHash: result.text_hash,
    },
  };
  try {
    await send(msg);
  } catch (e) {
    console.warn("[vibe-radar] action failed", e);
  }
}
```

Replace with:

```typescript
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
      readMs,
    },
  };
  return await send<ActionResult>(msg);
}
```

**Edit 6**: Add a new helper `handlePostActionLevelUp` at the bottom of `VibeCard.ts` (before the `buildShareDialog` helper). This handles level-up overlay when the action response carries `level_up: true`. It will import from `LevelUpOverlay` (which Task 9 creates). For Task 8, we leave this as a forward reference that Task 9 wires up:

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
  // Level-up overlay is added in Task 9. For now, fall through to normal close.
  setTimeout(onClose, 1500);
}
```

Task 9 will update this function to actually play the animation. This keeps Task 8 self-contained and compilable.

- [ ] **Step 2: Extend `styles.css`**

Append to `extension/src/content/ui/styles.css`:

```css
/* V1.2 learning stage — no numeric %, show level badge instead */
.vr-learning-badge {
  text-align: center;
  padding: 16px 8px 8px;
}
.vr-learning-emoji {
  font-size: 48px;
  line-height: 1;
  margin-bottom: 8px;
}
.vr-learning-title {
  font-size: 20px;
  font-weight: 700;
  color: #6c5ce7;
  margin-bottom: 4px;
}
.vr-learning-sub {
  font-size: 11px;
  color: #888;
}

/* V1.2 early stage — small level hint below the percentage */
.vr-level-hint {
  font-size: 11px;
  color: #999;
  margin-top: -4px;
  margin-bottom: 8px;
}
```

- [ ] **Step 3: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/src/content/ui/VibeCard.ts extension/src/content/ui/styles.css
git commit -m "feat(ext): stage-based VibeCard rendering + capture readMs on actions"
```
Expected: 41 commits.

No build yet — Task 9 finishes the loop.

---

## Task 9: LevelUpOverlay + content/index.ts wiring + VibeCard post-action

**Files:**
- Create: `extension/src/content/ui/LevelUpOverlay.ts`
- Modify: `extension/src/content/ui/styles.css`
- Modify: `extension/src/content/index.ts` (wire level-up on analyze response)
- Modify: `extension/src/content/ui/VibeCard.ts` (wire level-up on action response)

- [ ] **Step 1: Create `extension/src/content/ui/LevelUpOverlay.ts`**

```typescript
import type { ActionResult, AnalyzeResult } from "../../shared/types";

type LevelUpSource = AnalyzeResult | ActionResult;

const PREV_LEVEL_EMOJI: Record<number, string> = {
  0: "👤",
  1: "🌱",
  2: "🌿",
  3: "🌳",
  4: "🔍",
  5: "🎯",
  6: "🧠",
  7: "💞",
  8: "🔮",
  9: "👻",
  10: "💎",
};

function prevLevelEmoji(newLevel: number): string {
  const prev = Math.max(0, newLevel - 1);
  const capped = Math.min(prev, 10);
  return PREV_LEVEL_EMOJI[capped] ?? "👤";
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

- [ ] **Step 2: Append level-up animation CSS to `styles.css`**

Append to `extension/src/content/ui/styles.css`:

```css
/* V1.2 level-up celebration overlay */
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
  opacity: 0.9;
  animation: vr-old-fadeup 0.6s ease forwards;
}
@keyframes vr-old-fadeup {
  0%   { opacity: 0.9; transform: translateY(0) scale(1); }
  100% { opacity: 0;   transform: translateY(-30px) scale(0.6); }
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
  letter-spacing: 2px;
  animation: vr-title-fadein 0.4s ease 1.1s forwards;
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

- [ ] **Step 3: Wire level-up on analyze response in `content/index.ts`**

Open `extension/src/content/index.ts`. Add import at the top:

```typescript
import { playLevelUpAnimation } from "./ui/LevelUpOverlay";
```

Find the `try` block inside `onIconClick` that awaits the analyze result:

```typescript
try {
  const result = await send<AnalyzeResult>(msg);
  loading.remove();
  currentCard = renderVibeCard({
    parent: currentIcon,
    result,
    sourceDomain: domain,
    text,
    onClose: clearUi,
  });
} catch (e: any) {
  // ... error handling unchanged
}
```

Replace the success branch with level-up wiring:

```typescript
try {
  const result = await send<AnalyzeResult>(msg);
  loading.remove();

  if (result.level_up) {
    // Play celebration first, then render the real card
    const tempCard = document.createElement("div");
    tempCard.className = "vr-card";
    currentIcon.appendChild(tempCard);
    playLevelUpAnimation(tempCard, result, () => {
      tempCard.remove();
      currentCard = renderVibeCard({
        parent: currentIcon!,
        result,
        sourceDomain: domain,
        text,
        onClose: clearUi,
      });
    });
  } else {
    currentCard = renderVibeCard({
      parent: currentIcon,
      result,
      sourceDomain: domain,
      text,
      onClose: clearUi,
    });
  }
} catch (e: any) {
  // ... error handling unchanged
}
```

Note: `currentIcon!` is used inside the callback because TypeScript narrowing doesn't persist across the async boundary. The callback runs after `playLevelUpAnimation` finishes, and we checked `currentIcon` is non-null earlier in `onIconClick`.

- [ ] **Step 4: Wire level-up post-action in `VibeCard.ts`**

Open `extension/src/content/ui/VibeCard.ts`. Find the `handlePostActionLevelUp` helper created in Task 8 (currently stubbed). Import `playLevelUpAnimation` at the top:

```typescript
import { playLevelUpAnimation } from "./LevelUpOverlay";
```

Replace the stubbed function body:

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
  // Play level-up overlay ON TOP of the existing vibe card, then close
  playLevelUpAnimation(card, actionResult, () => {
    setTimeout(onClose, 400);
  });
}
```

- [ ] **Step 5: Build and verify**

```bash
cd D:/qhyProject/vibe4.0/extension && npm run build
ls -l build/content.js
```
Expected: `Extension built to build`. `content.js` should grow from ~24kb (V1.1) to ~28-32kb (CSS animation + LevelUpOverlay + learning stage markup).

If TypeScript errors appear, check that:
- `ActionResult` is imported in `VibeCard.ts`
- `playLevelUpAnimation` is imported in both `content/index.ts` and `VibeCard.ts`
- The `hesitationMs` field is in the ANALYZE msg payload in `content/index.ts`
- The `readMs` field is in the ACTION msg payload

- [ ] **Step 6: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/src/content/ui/LevelUpOverlay.ts extension/src/content/ui/styles.css extension/src/content/index.ts extension/src/content/ui/VibeCard.ts
git commit -m "feat(ext): add LevelUpOverlay and wire level-up celebrations on analyze/action"
```
Expected: 42 commits.

---

## Task 10: Popup welcome + radar level panel + SMOKE.md rewrite

**Files:**
- Create: `extension/src/popup/welcome.ts`
- Modify: `extension/src/popup/popup.ts`
- Modify: `extension/src/popup/radar.ts`
- Modify: `extension/src/popup/popup.css`
- Modify: `extension/SMOKE.md`

- [ ] **Step 1: Create `extension/src/popup/welcome.ts`**

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

- [ ] **Step 2: Rewrite `extension/src/popup/popup.ts`**

Replace the entire file content with:

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

The old file referenced `chrome.storage.local.profile_initialized` — that reference is gone. Any residual value in chrome.storage.local is simply ignored now.

- [ ] **Step 3: Rewrite `extension/src/popup/radar.ts`**

Read the current file first. Its existing signature is `renderRadar(root)` with no args — it called `send<RadarResult>` itself. V1.2 changes this: `popup.ts` pre-loads the data and passes it in, avoiding a double-call.

Replace the entire file content with:

```typescript
import * as echarts from "echarts";

import type { RadarResult } from "../shared/types";

export async function renderRadar(root: HTMLElement, data: RadarResult): Promise<void> {
  root.innerHTML = `
    <h2>你的审美雷达</h2>
    <div id="radar"></div>
    <div class="vr-level-panel">
      <div class="vr-level-current">${data.level_emoji} Lv.${data.level} ${data.level_title}</div>
      <div class="vr-level-bar">
        <div class="vr-level-fill" style="width: ${levelFillPercent(data)}%"></div>
      </div>
      <div class="vr-level-counts">
        已喂入 <b>${data.interaction_count}</b> 个信号 · 下一级还差 <b>${Math.max(0, data.next_level_at - data.interaction_count)}</b> 次
      </div>
    </div>
    <div class="stats">
      已鉴定 <b>${data.total_analyze_count}</b> 次 · 已确权 <b>${data.total_action_count}</b> 次
    </div>
  `;
  const chartRoot = root.querySelector("#radar") as HTMLElement;

  const chart = echarts.init(chartRoot);
  chart.setOption({
    radar: {
      indicator: data.dimensions.map((d) => ({
        name: d.category_label,
        max: 100,
      })),
      radius: "65%",
      axisName: { color: "#555", fontSize: 12 },
      splitArea: { show: true, areaStyle: { color: ["#f8f7ff", "#fff"] } },
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: data.dimensions.map((d) => d.score),
            name: "当前画像",
            areaStyle: { color: "rgba(108, 92, 231, 0.3)" },
            lineStyle: { color: "#6c5ce7" },
            itemStyle: { color: "#6c5ce7" },
          },
        ],
      },
    ],
  });
}

function levelFillPercent(data: RadarResult): number {
  if (data.next_level_at <= 0) return 100;
  const prev = data.level * data.level;
  const span = data.next_level_at - prev;
  if (span <= 0) return 100;
  const progressed = data.interaction_count - prev;
  return Math.min(100, Math.max(0, Math.round((progressed / span) * 100)));
}
```

The `levelFillPercent` function computes how far into the current level's bracket the user is. For example, at L2 (count=4), prev=4, next=9, span=5, progressed=0, fill=0%. At count=6, progressed=2, fill=40%.

- [ ] **Step 4: Append welcome + level panel styles to `popup.css`**

Open `extension/src/popup/popup.css` and append at the end:

```css
/* V1.2 welcome page */
.vr-welcome {
  text-align: center;
  padding: 20px 10px;
}
.vr-welcome-logo {
  font-size: 40px;
  color: #6c5ce7;
  margin-bottom: 8px;
  letter-spacing: 8px;
}
.vr-welcome h2 {
  margin: 0 0 8px;
  font-size: 20px;
  color: #6c5ce7;
}
.vr-welcome-tagline {
  color: #888;
  font-size: 13px;
  margin: 0 0 16px;
}
.vr-welcome-hint {
  color: #555;
  font-size: 12px;
  line-height: 1.6;
  margin: 0 0 14px;
}
.vr-welcome-sites {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.vr-welcome-sites li {
  padding: 8px 12px;
  background: #fff;
  border-radius: 8px;
  font-size: 12px;
  color: #555;
  border: 1px solid rgba(108, 92, 231, 0.1);
}

/* V1.2 level panel in radar view */
.vr-level-panel {
  margin: 12px 0 8px;
  padding: 12px;
  background: #fff;
  border-radius: 10px;
  border: 1px solid rgba(108, 92, 231, 0.12);
}
.vr-level-current {
  font-size: 16px;
  font-weight: 700;
  color: #6c5ce7;
  margin-bottom: 8px;
  text-align: center;
}
.vr-level-bar {
  width: 100%;
  height: 8px;
  background: #f0edff;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 6px;
}
.vr-level-fill {
  height: 100%;
  background: linear-gradient(90deg, #6c5ce7, #a29bfe);
  border-radius: 4px;
  transition: width 0.4s ease;
}
.vr-level-counts {
  font-size: 11px;
  color: #888;
  text-align: center;
}
```

- [ ] **Step 5: Rewrite `extension/SMOKE.md`**

Open `extension/SMOKE.md`. It currently has 10 steps (1-10 from V1.0 + V1.1). V1.2 needs:

- Insert a **Step 0** (database reset) before everything else
- Replace steps 1 (cold start) and 2 (popup reopens) with V1.2 welcome-based versions
- Modify step 3 (highlight-to-analyze) to mention the level-up animation and learning stage
- Add **Steps 11, 12, 13** for the new V1.2 behaviors (hesitation scaling, read-time scaling, level progression)
- Update prereq line and pass criteria to reference 13 steps

Replace the entire file content with:

```markdown
# V1.2 Manual Smoke Test

## Prereqs
1. Backend venv installed and active
2. `backend/.env` configured with a real LLM API key (needed for most steps; V1.1 added roast + recommendation calls, V1.2 is mostly backend-internal but still uses roast)
3. Chrome with developer mode enabled

## Step 0: Reset database (V1.2 required, one-time)
V1.2 changed the `users` table schema (added `interaction_count`). You MUST delete the old DB and re-seed before any smoke step:
```bash
cd D:/qhyProject/vibe4.0/backend
rm data/vibe_radar.db
source .venv/Scripts/activate
python -m app.services.seed
```
This rebuilds the schema and reinserts the 24 vibe tags. `user_id=1` will be lazy-created on first analyze.

## Start services
```bash
cd D:/qhyProject/vibe4.0/backend
source .venv/Scripts/activate
uvicorn app.main:app --reload --port 8000
```

```bash
cd D:/qhyProject/vibe4.0/extension
npm run build
```

Chrome → `chrome://extensions` → Developer mode → Load unpacked → `extension/build/`

---

## Steps

### 1. Welcome page (V1.2)
- Click the extension icon → popup opens
- Expected: you see a **welcome page** (no 18 cards, no radar) with logo, tagline "我会通过你的真实行为认识你", and a 4-item grid of supported sites
- Close the popup

### 2. First-interaction cold start (V1.2)
- Go to `https://book.douban.com/subject/1000000/` (any Douban book)
- Highlight 2-10 Chinese characters
- Click the purple icon
- Expected: a **level-up animation** plays for ~1.5 seconds showing:
  - Old emoji (👤) floating up and fading
  - Arrows (↓ ↓ ↓)
  - New emoji (🌱) popping in at larger size
  - Title "Lv.1 初遇"
  - Subtitle "🎉 你已经喂了 1 个信号"
- After the animation, the vibe card renders with:
  - **No percentage number** (learning stage)
  - A **learning badge** showing "🌱 Lv.1 初遇" + "学习中 · 第 1 次"
  - Normal roast text
  - Normal tags
  - Normal 💎/💣 buttons

### 3. Popup reopens with radar + level panel (V1.2)
- Open the popup again
- Expected: no longer shows welcome — instead shows a sparse radar chart (mostly zero values — you only had one interaction) AND a level panel at the bottom with:
  - "🌱 Lv.1 初遇"
  - A progress bar (mostly empty — 0/3 until L2)
  - "已喂入 1 个信号 · 下一级还差 3 次"

### 4. Highlight 3 more times → Lv.2 level-up (V1.2)
- Go back to a supported site, highlight and rate 3 more times
- On the 4th rate, expected: a new level-up animation plays showing L1→L2 transition, emoji 🌿, title "浅尝"
- After the animation, vibe card still shows no percentage (L2 is still "learning" stage)

### 5. Continue to count 16 → unlock percentage display (V1.2)
- Continue highlighting and rating until `interaction_count == 16`
- On the 16th rate, expected: level-up animation shows L3→L4 transition, emoji 🔍, title "入门"
- After the animation, vibe card now SHOWS the percentage number + a small "🔍 Lv.4 入门" hint below it. This is the first level where the match score is visible.

### 6. Highlight-to-analyze cache hit (from V1.1)
- Highlight the exact same text a second time → click icon
- Expected: cache_hit is true in the background worker log, response arrives faster

### 7. Backend-down handling (from V1.0)
- Stop uvicorn
- Highlight text → click icon
- Expected: error card shows "后端未运行，请先启动 FastAPI", disappears after 3s

### 8. Roast display (from V1.1)
- After rating something, expected: bold purple roast line is prominent, grey italic summary below

### 9. Cross-domain recommendation (from V1.1)
- Click "> 寻找同频代餐" link → 3 items with distinct domain emoji appear, none from source domain
- Click "换一批 ↻" → new items appear

### 10. Share poster (from V1.1)
- Click [📤] → dialog with 复制 / 下载 / 取消
- Copy → paste into mspaint → 1080x1080 purple gradient poster
- Download → PNG file

### 11. Impulsive click gives small curiosity delta (V1.2)
- Make sure `interaction_count >= 1` (not first-impression path)
- Highlight a text → IMMEDIATELY click the icon (aim for under 500ms between text selection and icon click)
- After rating, inspect the database:
```bash
cd D:/qhyProject/vibe4.0/backend
sqlite3 data/vibe_radar.db "SELECT action, delta FROM action_log ORDER BY id DESC LIMIT 5;"
```
- Expected: the most recent `analyze` row has `delta=0.15` (0.3× baseline)

### 12. Careful star gives bigger core delta (V1.2)
- Highlight text → click icon → wait at least 5 seconds reading the vibe card → click 💎
- Inspect DB:
```bash
sqlite3 data/vibe_radar.db "SELECT action, delta FROM action_log ORDER BY id DESC LIMIT 5;"
```
- Expected: the most recent `star` row has `delta=15.0` (1.5× baseline)

### 13. Level-up animation skip button (V1.2)
- Trigger any level-up (easiest: reset DB, then do first analyze)
- As soon as the level-up animation appears, click the × in the top-right corner
- Expected: the animation immediately fades out and the normal vibe card appears

## Pass criteria
All 13 steps complete without any JavaScript console errors in either the background worker or the content script.
```

- [ ] **Step 6: Build and run final extension build**

```bash
cd D:/qhyProject/vibe4.0/extension && npm run build
ls -l build/
ls -l build/popup/
```
Expected: all bundles present, popup/popup.js still ~2.8MB, content.js grown to ~28-32kb.

- [ ] **Step 7: Run the full backend test suite one final time**

```bash
cd D:/qhyProject/vibe4.0/backend && source .venv/Scripts/activate && pytest tests/ -v
```
Expected: ~65 tests passing, no regressions.

- [ ] **Step 8: Commit**

```bash
cd D:/qhyProject/vibe4.0
git add extension/src/popup/welcome.ts extension/src/popup/popup.ts extension/src/popup/radar.ts extension/src/popup/popup.css extension/SMOKE.md
git commit -m "feat(ext): popup welcome + radar level panel + SMOKE V1.2 rewrite"
git log --oneline | head -15
```
Expected: **43 commits total**, V1.2 complete.

---

## Post-implementation checklist

- [ ] `pytest tests/ -v` runs ~65 tests, all green
- [ ] `npm run build` succeeds with zero TypeScript errors
- [ ] Extension reloaded in Chrome, `backend/data/vibe_radar.db` deleted + re-seeded
- [ ] SMOKE step 0 completed (DB reset)
- [ ] SMOKE steps 1-13 pass
- [ ] `git log --oneline` shows 43 commits total (34 V1.0+V1.1 + 1 spec + 1 plan + 10 V1.2 impl commits = note: Task 1 also adds 1, so count may vary slightly)

---

## Appendix — V1.2 known limitations (carry forward)

1. **Level-up animation can be missed** — if the user dismisses the card before the 1.5s animation finishes via an unrelated click outside the host, the celebration is lost. The level change still commits to DB but the user never sees it. SP-C may add a "missed celebrations" queue.
2. **No recovery from first-impression mistake** — if the user's first highlight is an accidental wrong selection, the +10 core_weight on the wrong tags is locked in. Users would have to accumulate 💣 to offset. Not in V1.2 scope.
3. **`dynamic_core_delta` only scales action write** — the existing `_apply_delta` code path always commits the scaled value to DB, so undo/redo at different delta scales is not possible.
4. **L10+ UI** — the frontend shows level number beyond 10 correctly but keeps displaying "知己 / 💎" for title/emoji. A future theme unlock system (SP-C/D) could add more tiers.
5. **`hesitation_ms` relies on mouseup-then-click sequence** — double-click, triple-click, and keyboard-based selection (Shift+arrow) are captured as <500ms impulsive. Accept as lossy signal for V1.2.
6. **Database reset is manual** — no alembic. Users with V1.1 DB get a schema mismatch error on first V1.2 start until they `rm backend/data/vibe_radar.db`. SMOKE step 0 documents this prominently.
