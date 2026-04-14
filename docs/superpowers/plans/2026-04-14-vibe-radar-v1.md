# Vibe-Radar V1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build V1.0 of Vibe-Radar — a Chrome extension that highlights text on supported content sites (Douban book/movie, Steam, NetEase music), sends it to a local FastAPI backend for LLM-based Vibe tagging, computes a personalized match score against the user's dual-weight profile, and lets the user confirm/reject the match with explicit star/bomb actions.

**Architecture:** FastAPI + SQLite backend on localhost:8000 exposing 5 REST endpoints. Chrome MV3 extension with three bundles (background service worker as API gateway, content script using Shadow DOM for UI injection, popup with ECharts radar chart). A single hardcoded user (`user_id=1`). LLM calls go through an `analysis_cache` table with a 7-day TTL. All spec details are in `docs/superpowers/specs/2026-04-14-vibe-radar-v1-design.md` — consult it whenever a task is ambiguous.

**Tech Stack:**
- Backend: Python 3.10+, FastAPI, SQLAlchemy 2.x, SQLite, httpx, numpy, pytest
- Extension: TypeScript, esbuild, Chrome Manifest V3
- Chart: ECharts (popup only)
- LLM: DeepSeek default (pluggable via env)

**Repo layout (to be created):**
```
vibe4.0/
├── backend/
├── extension/
├── docs/superpowers/{specs,plans}/
└── README.md
```

**Conventions:**
- Commit after every passing test group. Conventional Commits style (`feat:`, `test:`, `chore:`).
- **Database session access in tests and services:** Always use `from app import database; db = database.SessionLocal()` (attribute access), never `from app.database import SessionLocal`. The test fixture rebinds `database.SessionLocal` at runtime, and `from X import Y` at module top would capture the stale production binding and silently hit the dev DB.
- Backend: strict TDD — write failing test → run it → implement → run passing → commit.
- Extension: no automated tests in V1.0 — manual smoke via `extension/SMOKE.md` at the end. Commit after each task completes a buildable milestone.
- Use `pytest -x -v` when running tests so failures stop immediately.

**Prerequisites assumed already on the machine:**
- Python 3.10+ with `venv`
- Node.js 18+ with npm
- Chrome (for loading the unpacked extension)
- A DeepSeek (or other) LLM API key for the final smoke test; not needed for unit tests

**About git:** If the project root `D:/qhyProject/vibe4.0/` is not yet a git repo, initialize it in Task 0 before any other commits.

---

## Task 0: Initialize repo and root scaffold

**Files:**
- Create: `README.md`
- Create: `.gitignore`

- [ ] **Step 1: Initialize git repo (if not already)**

```bash
cd D:/qhyProject/vibe4.0
git init
git config user.email "dev@vibe-radar.local"
git config user.name "Vibe Radar Dev"
```

- [ ] **Step 2: Create root `.gitignore`**

Write to `D:/qhyProject/vibe4.0/.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.pytest_cache/
.coverage
htmlcov/

# Node
node_modules/
dist/
build/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Project-specific
backend/data/*.db
backend/.env
```

- [ ] **Step 3: Create minimal root `README.md`**

Write to `D:/qhyProject/vibe4.0/README.md`:

```markdown
# Vibe-Radar V1.0

Chrome extension + FastAPI backend for personalized "Vibe" matching on book/game/movie/music sites.

See `docs/superpowers/specs/2026-04-14-vibe-radar-v1-design.md` for the design.
See `docs/superpowers/plans/2026-04-14-vibe-radar-v1.md` for the implementation plan.

## Quick start

1. Start backend: `cd backend && uvicorn app.main:app --reload --port 8000`
2. Build extension: `cd extension && npm run build`
3. Chrome → Extensions → Developer mode → Load unpacked → pick `extension/build/`

See `extension/SMOKE.md` for the manual smoke test.
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore README.md docs/
git commit -m "chore: initialize repo with spec and plan"
```

---

## Task 1: Backend project scaffold

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/pyproject.toml` (minimal)
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/.env.example`

- [ ] **Step 1: Create `backend/requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
pydantic==2.9.2
pydantic-settings==2.5.2
httpx==0.27.2
numpy==2.1.1
python-dotenv==1.0.1
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 2: Create `backend/pyproject.toml`**

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
markers = [
    "integration: marks tests that hit real LLM API (deselect with '-m \"not integration\"')"
]
asyncio_mode = "auto"
addopts = "-m 'not integration'"
```

- [ ] **Step 3: Create `backend/.env.example`**

```
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-replace-me
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
DB_PATH=./data/vibe_radar.db
```

- [ ] **Step 4: Create `backend/app/__init__.py`**

Empty file:
```python
```

- [ ] **Step 5: Create `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "deepseek"
    llm_api_key: str = "sk-replace-me"
    llm_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com"
    db_path: str = "./data/vibe_radar.db"


settings = Settings()
```

- [ ] **Step 6: Create `backend/app/database.py`**

```python
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _make_engine(db_path: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )


engine = _make_engine(settings.db_path)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 7: Create `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Vibe-Radar", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # V1.0 dev-open; tighten in V1.1
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 8: Create `backend/tests/__init__.py`**

Empty file:
```python
```

- [ ] **Step 9: Create `backend/tests/conftest.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Each test runs against its own temp SQLite file.

    Why not `importlib.reload`? reload creates a fresh `Base` class whose
    metadata has no models registered. Models register against the original
    `Base` at import time, so we keep that `Base` alive and just swap
    `engine` / `SessionLocal` via attribute assignment.

    Corollary: all service code must access the session via
    `from app import database; database.SessionLocal()` (attribute lookup),
    not `from app.database import SessionLocal` (which would capture the
    production binding at import and skip this fixture).
    """
    from app import database
    from app.database import Base

    db_file = tmp_path / "test.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    TestSession = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, future=True
    )

    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "SessionLocal", TestSession)

    Base.metadata.create_all(test_engine)

    # Dependency override for FastAPI routes (only if app.deps exists —
    # it's created in Task 7, not present at Task 1).
    override_installed = False
    try:
        from app.deps import get_db
        from app.main import app

        def _override_get_db():
            db = TestSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_get_db
        override_installed = True
    except ImportError:
        pass

    try:
        yield
    finally:
        if override_installed:
            from app.deps import get_db
            from app.main import app
            app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(test_engine)
        test_engine.dispose()
```

- [ ] **Step 10: Install deps and run health test**

```bash
cd backend
python -m venv .venv
# Windows: . .venv/Scripts/activate
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate
pip install -r requirements.txt
python -c "from app.main import app; print('import ok')"
```
Expected: prints `import ok`

- [ ] **Step 11: Commit**

```bash
git add backend/
git commit -m "feat(backend): scaffold FastAPI + SQLAlchemy project"
```

---

## Task 2: SQLAlchemy models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/vibe_tag.py`
- Create: `backend/app/models/user_vibe_relation.py`
- Create: `backend/app/models/analysis_cache.py`
- Create: `backend/app/models/action_log.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_models.py`:

```python
from sqlalchemy import select

from app import database
from app.database import Base
from app.models.action_log import ActionLog
from app.models.analysis_cache import AnalysisCache
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.models.vibe_tag import VibeTag


def test_tables_are_created_and_basic_crud_works():
    Base.metadata.create_all(database.engine)
    db = database.SessionLocal()

    # users
    u = User(id=1, username="default")
    db.add(u)

    # vibe_tags (2 rows, each as the other's opposite)
    t1 = VibeTag(id=1, name="慢炖沉浸", category="pace", tier=1,
                 opposite_id=4, description="像在咖啡馆读一下午")
    t4 = VibeTag(id=4, name="爆裂快切", category="pace", tier=4,
                 opposite_id=1, description="密集刺激快切")
    db.add_all([t1, t4])
    db.flush()

    # user_vibe_relations
    r = UserVibeRelation(user_id=1, vibe_tag_id=1,
                         curiosity_weight=0.5, core_weight=15.0)
    db.add(r)

    # analysis_cache
    c = AnalysisCache(text_hash="abc", domain="book",
                      tags_json='{"tags":[]}', summary="s", hit_count=0)
    db.add(c)

    # action_log
    log = ActionLog(user_id=1, vibe_tag_id=1, action="cold_start",
                    delta=15.0, target_column="core")
    db.add(log)

    db.commit()

    assert db.scalar(select(User).where(User.id == 1)).username == "default"
    assert db.scalar(select(VibeTag).where(VibeTag.id == 1)).opposite_id == 4
    assert db.scalar(select(UserVibeRelation)).core_weight == 15.0
    assert db.scalar(select(AnalysisCache)).text_hash == "abc"
    assert db.scalar(select(ActionLog)).action == "cold_start"
    db.close()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && pytest tests/test_models.py -v
```
Expected: FAIL, `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Create `backend/app/models/__init__.py`**

```python
from app.models.action_log import ActionLog
from app.models.analysis_cache import AnalysisCache
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.models.vibe_tag import VibeTag

__all__ = ["User", "VibeTag", "UserVibeRelation", "AnalysisCache", "ActionLog"]
```

- [ ] **Step 4: Create `backend/app/models/user.py`**

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

- [ ] **Step 5: Create `backend/app/models/vibe_tag.py`**

```python
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VibeTag(Base):
    __tablename__ = "vibe_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32))
    tier: Mapped[int] = mapped_column(Integer)
    opposite_id: Mapped[int | None] = mapped_column(ForeignKey("vibe_tags.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text)
```

- [ ] **Step 6: Create `backend/app/models/user_vibe_relation.py`**

```python
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserVibeRelation(Base):
    __tablename__ = "user_vibe_relations"
    __table_args__ = (UniqueConstraint("user_id", "vibe_tag_id", name="uq_user_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    vibe_tag_id: Mapped[int] = mapped_column(ForeignKey("vibe_tags.id"))
    curiosity_weight: Mapped[float] = mapped_column(Float, default=0.0)
    core_weight: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **Step 7: Create `backend/app/models/analysis_cache.py`**

```python
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnalysisCache(Base):
    __tablename__ = "analysis_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(16))
    tags_json: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 8: Create `backend/app/models/action_log.py`**

```python
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ActionLog(Base):
    __tablename__ = "action_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    vibe_tag_id: Mapped[int] = mapped_column(ForeignKey("vibe_tags.id"))
    action: Mapped[str] = mapped_column(String(32))
    delta: Mapped[float] = mapped_column(Float)
    target_column: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 9: Run the test to verify it passes**

```bash
pytest tests/test_models.py -v
```
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add backend/app/models/ backend/tests/test_models.py
git commit -m "feat(backend): add SQLAlchemy models for users/tags/relations/cache/log"
```

---

## Task 3: Seed data (24 tags + cold-start cards)

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/seed_data.py` (the raw dicts — 24 tags + taglines/examples)
- Create: `backend/app/services/seed.py` (the idempotent loader)
- Create: `backend/tests/test_seed.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_seed.py`:

```python
from sqlalchemy import select

from app import database
from app.models.vibe_tag import VibeTag
from app.services.seed import seed_all


def test_seed_inserts_24_tags_with_opposite_relations():
    seed_all()
    db = database.SessionLocal()
    tags = db.scalars(select(VibeTag).order_by(VibeTag.id)).all()
    assert len(tags) == 24

    # 6 categories, each exactly 4 tiers
    from collections import Counter
    cat_count = Counter(t.category for t in tags)
    assert set(cat_count.keys()) == {"pace", "mood", "cognition", "narrative", "world", "intensity"}
    for cat, n in cat_count.items():
        assert n == 4, f"category {cat} has {n} tags, expected 4"

    # opposite relations: tier 1 <-> tier 4, tier 2 <-> tier 3 within same category
    by_id = {t.id: t for t in tags}
    for t in tags:
        opp = by_id[t.opposite_id]
        assert opp.category == t.category
        assert {t.tier, opp.tier} in ({1, 4}, {2, 3})

    db.close()


def test_seed_is_idempotent():
    seed_all()
    seed_all()  # second call must not duplicate
    db = database.SessionLocal()
    assert db.scalar(select(VibeTag).where(VibeTag.id == 1)).name == "慢炖沉浸"
    assert len(db.scalars(select(VibeTag)).all()) == 24
    db.close()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_seed.py -v
```
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services'`

- [ ] **Step 3: Create `backend/app/services/__init__.py`**

Empty file:
```python
```

- [ ] **Step 4: Create `backend/app/services/seed_data.py`**

```python
"""
Static seed data: 24 Vibe tags (6 categories × 4 tiers) and the 18
cold-start cards. All data written by hand; do not generate programmatically
so edits are greppable.
"""

# (category, tier, id, name, description)
TAGS = [
    ("pace", 1, 1,  "慢炖沉浸",   "节奏极慢，像咖啡馆读一下午般从容铺陈"),
    ("pace", 2, 2,  "张弛有度",   "节奏有呼吸感，快慢交替不让人疲惫"),
    ("pace", 3, 3,  "紧凑推进",   "节奏密，信息量大，几乎没有留白"),
    ("pace", 4, 4,  "爆裂快切",   "节奏爆炸，快切刺激停不下来"),

    ("mood", 1, 5,  "治愈温暖",   "整体暖色调，给人抚慰感"),
    ("mood", 2, 6,  "明亮轻快",   "基调愉悦，情绪轻盈"),
    ("mood", 3, 7,  "忧郁内省",   "底色偏冷，带着沉思和怅然"),
    ("mood", 4, 8,  "黑暗压抑",   "基调阴冷沉重，压得人喘不过气"),

    ("cognition", 1, 9,  "放空友好", "完全不费脑，可以边吃饭边享用"),
    ("cognition", 2, 10, "轻度思考", "有一点点挑战但不烧脑"),
    ("cognition", 3, 11, "烧脑解谜", "需要主动推理，有解谜乐趣"),
    ("cognition", 4, 12, "认知挑战", "抽象度高，需要反复咀嚼"),

    ("narrative", 1, 13, "白描克制", "文笔/镜头克制，点到即止"),
    ("narrative", 2, 14, "细腻抒情", "注重情感与细节的层层展开"),
    ("narrative", 3, 15, "奇观堆砌", "大量视觉/想象奇观，重感官冲击"),
    ("narrative", 4, 16, "解构实验", "叙事结构非常规，带有实验色彩"),

    ("world", 1, 17, "日常烟火", "日常生活场景为底色"),
    ("world", 2, 18, "奇幻异想", "架空奇幻或魔法设定"),
    ("world", 3, 19, "赛博机械", "赛博朋克/机械科幻调性"),
    ("world", 4, 20, "历史厚重", "有真实历史/年代的厚重感"),

    ("intensity", 1, 21, "轻食小品", "情感投入成本极低，像零食"),
    ("intensity", 2, 22, "有共鸣",   "情感适度，能引发共鸣"),
    ("intensity", 3, 23, "情感重击", "情感浓度高，会被打动甚至流泪"),
    ("intensity", 4, 24, "灵魂灼烧", "情感极致，会在心里留下烙印"),
]

CATEGORY_LABELS = {
    "pace": "节奏",
    "mood": "情绪色调",
    "cognition": "智力负载",
    "narrative": "叙事质感",
    "world": "世界感",
    "intensity": "情感浓度",
}

# Taglines and example works for cold-start cards (keyed by tag_id)
CARD_META = {
    1:  {"tagline": "像在咖啡馆读一下午",   "examples": ["《小森林》", "《海街日记》"]},
    2:  {"tagline": "快慢交替的呼吸感",     "examples": ["《请回答1988》", "《这个杀手不太冷》"]},
    3:  {"tagline": "信息密到不敢眨眼",     "examples": ["《权力的游戏》", "《三体》"]},
    4:  {"tagline": "心跳过载的爽感",       "examples": ["《疾速追杀》", "《DOOM》"]},

    5:  {"tagline": "被整个世界温柔相待",   "examples": ["《夏目友人帐》", "《星露谷物语》"]},
    6:  {"tagline": "阳光洒在脸上的轻快",   "examples": ["《歌舞青春》", "《动物森友会》"]},
    7:  {"tagline": "一个人靠窗发呆的下午", "examples": ["《海边的卡夫卡》", "《Celeste》"]},
    8:  {"tagline": "吞人的黑暗与寒意",     "examples": ["《沉默的羔羊》", "《血源诅咒》"]},

    9:  {"tagline": "脑子完全下班",         "examples": ["《吃豆人》", "综艺快乐大本营"]},
    10: {"tagline": "微微动脑但不累",       "examples": ["《纪念碑谷》"]},
    11: {"tagline": "我要亲手拼出真相",     "examples": ["《锈湖》", "《控制》"]},
    12: {"tagline": "烧脑到怀疑人生",       "examples": ["《盗梦空间》", "《芬奇堡密室》"]},

    13: {"tagline": "一个字多写都是罪",     "examples": ["海明威短篇", "《东京物语》"]},
    14: {"tagline": "情绪在细节里爬行",     "examples": ["《包法利夫人》", "《请以你的名字呼唤我》"]},
    15: {"tagline": "每一帧都在炸你眼球",   "examples": ["《沙丘》", "《赛博朋克2077》"]},
    16: {"tagline": "叙事像迷宫一样拆开",   "examples": ["《记忆碎片》", "《2666》"]},

    17: {"tagline": "柴米油盐也能写出诗",   "examples": ["《请回答1988》", "《人生复本》"]},
    18: {"tagline": "魔法与神话的异想",     "examples": ["《哈利波特》", "《塞尔达：旷野之息》"]},
    19: {"tagline": "霓虹与机械的冷光",     "examples": ["《攻壳机动队》", "《赛博朋克2077》"]},
    20: {"tagline": "厚重历史的重量",       "examples": ["《活着》", "《刺客信条2》"]},

    21: {"tagline": "像一颗糖心情就甜",     "examples": ["《萌宠成长记》"]},
    22: {"tagline": "偶尔会在心里点头",     "examples": ["《请回答1988》"]},
    23: {"tagline": "会被狠狠击中一次",     "examples": ["《你的名字》", "《最后生还者》"]},
    24: {"tagline": "灼伤灵魂的那种",       "examples": ["《入殓师》", "《蔚蓝》"]},
}


def compute_opposite(tag_id: int) -> int:
    """Within a category: tier 1↔4, tier 2↔3."""
    for cat, tier, tid, _, _ in TAGS:
        if tid == tag_id:
            target_tier = {1: 4, 2: 3, 3: 2, 4: 1}[tier]
            for c2, t2, tid2, _, _ in TAGS:
                if c2 == cat and t2 == target_tier:
                    return tid2
    raise ValueError(f"tag_id {tag_id} not found")
```

- [ ] **Step 5: Create `backend/app/services/seed.py`**

```python
from sqlalchemy import select

from app import database
from app.database import Base
from app.models.vibe_tag import VibeTag
from app.services.seed_data import TAGS, compute_opposite


def seed_all() -> None:
    """Idempotent: create schema and insert 24 tags if absent."""
    Base.metadata.create_all(database.engine)
    db = database.SessionLocal()
    try:
        existing = db.scalar(select(VibeTag).where(VibeTag.id == 1))
        if existing is not None:
            return
        for category, tier, tid, name, description in TAGS:
            db.add(VibeTag(
                id=tid,
                name=name,
                category=category,
                tier=tier,
                opposite_id=compute_opposite(tid),
                description=description,
            ))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
    print("Seeded 24 vibe tags.")
```

- [ ] **Step 6: Run the test**

```bash
pytest tests/test_seed.py -v
```
Expected: PASS (both tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/ backend/tests/test_seed.py
git commit -m "feat(backend): seed 24 vibe tags with opposite relations"
```

---

## Task 4: profile_calc service (pure functions)

**Files:**
- Create: `backend/app/services/profile_calc.py`
- Create: `backend/tests/test_profile_calc.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_profile_calc.py`:

```python
import pytest

from app import database
from app.models.action_log import ActionLog
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.services import profile_calc
from app.services.seed import seed_all


@pytest.fixture
def seeded_user():
    seed_all()
    db = database.SessionLocal()
    db.add(User(id=1, username="default"))
    for tag_id in range(1, 25):
        db.add(UserVibeRelation(user_id=1, vibe_tag_id=tag_id,
                                curiosity_weight=0.0, core_weight=0.0))
    db.commit()
    db.close()


def test_compute_match_score_zero_profile_returns_zero(seeded_user):
    score = profile_calc.compute_match_score(
        user_id=1, item_tags=[(1, 1.0)]
    )
    assert score == 0


def test_compute_match_score_perfect_match_is_100(seeded_user):
    db = database.SessionLocal()
    rel = db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=1).one()
    rel.core_weight = 15.0
    db.commit()
    db.close()

    score = profile_calc.compute_match_score(user_id=1, item_tags=[(1, 1.0)])
    assert score == 100


def test_core_weight_is_3x_curiosity_weight(seeded_user):
    """effective = core*1.0 + curiosity*0.3"""
    db = database.SessionLocal()
    r1 = db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=1).one()
    r2 = db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=2).one()
    r1.core_weight = 10.0
    r2.curiosity_weight = 10.0
    db.commit()
    db.close()

    # vs item pointing only at tag 1 vs only at tag 2
    s1 = profile_calc.compute_match_score(user_id=1, item_tags=[(1, 1.0)])
    s2 = profile_calc.compute_match_score(user_id=1, item_tags=[(2, 1.0)])
    assert s1 > s2


def test_apply_curiosity_delta_updates_weight_and_writes_log(seeded_user):
    profile_calc.apply_curiosity_delta(user_id=1, tag_ids=[1, 2], delta=0.5,
                                       action="analyze")
    db = database.SessionLocal()
    r1 = db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=1).one()
    assert r1.curiosity_weight == 0.5
    logs = db.query(ActionLog).filter_by(user_id=1).all()
    assert len(logs) == 2
    assert all(l.target_column == "curiosity" and l.action == "analyze" for l in logs)
    db.close()


def test_apply_core_delta_updates_weight_and_writes_log(seeded_user):
    profile_calc.apply_core_delta(user_id=1, tag_ids=[1], delta=10.0,
                                  action="star")
    db = database.SessionLocal()
    r1 = db.query(UserVibeRelation).filter_by(user_id=1, vibe_tag_id=1).one()
    assert r1.core_weight == 10.0
    log = db.query(ActionLog).filter_by(user_id=1).one()
    assert log.target_column == "core"
    assert log.delta == 10.0
    db.close()


def test_compute_radar_returns_6_dimensions(seeded_user):
    data = profile_calc.compute_radar(user_id=1)
    assert len(data["dimensions"]) == 6
    assert {d["category"] for d in data["dimensions"]} == {
        "pace", "mood", "cognition", "narrative", "world", "intensity"
    }
    for d in data["dimensions"]:
        assert 0 <= d["score"] <= 100
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_profile_calc.py -v
```
Expected: FAIL, no `app.services.profile_calc`

- [ ] **Step 3: Create `backend/app/services/profile_calc.py`**

```python
from datetime import datetime

import numpy as np
from sqlalchemy import select

from app import database
from app.models.action_log import ActionLog
from app.models.user_vibe_relation import UserVibeRelation
from app.models.vibe_tag import VibeTag
from app.services.seed_data import CATEGORY_LABELS

CORE_COEFF = 1.0
CURIOSITY_COEFF = 0.3
NUM_TAGS = 24


def _effective_vector(db, user_id: int) -> np.ndarray:
    rels = db.scalars(
        select(UserVibeRelation).where(UserVibeRelation.user_id == user_id)
    ).all()
    vec = np.zeros(NUM_TAGS + 1)  # index 0 unused; 1..24
    for r in rels:
        vec[r.vibe_tag_id] = r.core_weight * CORE_COEFF + r.curiosity_weight * CURIOSITY_COEFF
    return vec


def compute_match_score(user_id: int, item_tags: list[tuple[int, float]]) -> int:
    """Cosine similarity × 100, clamped to 0..100. Negative cosine → 0."""
    db = database.SessionLocal()
    try:
        user_vec = _effective_vector(db, user_id)
    finally:
        db.close()

    item_vec = np.zeros(NUM_TAGS + 1)
    for tag_id, weight in item_tags:
        if 1 <= tag_id <= NUM_TAGS:
            item_vec[tag_id] = weight

    un = np.linalg.norm(user_vec)
    inorm = np.linalg.norm(item_vec)
    if un == 0 or inorm == 0:
        return 0
    cos = float(np.dot(user_vec, item_vec) / (un * inorm))
    score = max(0, min(100, round(cos * 100)))
    return int(score)


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


def apply_curiosity_delta(user_id: int, tag_ids: list[int], delta: float,
                          action: str) -> None:
    _apply_delta(user_id, tag_ids, delta, "curiosity", action)


def apply_core_delta(user_id: int, tag_ids: list[int], delta: float,
                     action: str) -> None:
    _apply_delta(user_id, tag_ids, delta, "core", action)


def compute_radar(user_id: int) -> dict:
    db = database.SessionLocal()
    try:
        tags = db.scalars(select(VibeTag)).all()
        rels = db.scalars(
            select(UserVibeRelation).where(UserVibeRelation.user_id == user_id)
        ).all()
    finally:
        db.close()

    eff_by_tag: dict[int, float] = {}
    for r in rels:
        eff_by_tag[r.vibe_tag_id] = (
            r.core_weight * CORE_COEFF + r.curiosity_weight * CURIOSITY_COEFF
        )

    by_cat: dict[str, list[VibeTag]] = {}
    for t in tags:
        by_cat.setdefault(t.category, []).append(t)

    dimensions = []
    for cat in ["pace", "mood", "cognition", "narrative", "world", "intensity"]:
        cat_tags = sorted(by_cat[cat], key=lambda t: t.tier)
        numerator = sum(t.tier * max(0.0, eff_by_tag.get(t.id, 0.0)) for t in cat_tags)
        # max_possible = max tier (4) * max expected effective weight (~45: 15*1 + 100*0.3)
        max_possible = 4 * 45.0
        raw = min(1.0, numerator / max_possible) if max_possible else 0.0
        score = round(raw * 100, 1)
        dominant = max(cat_tags, key=lambda t: eff_by_tag.get(t.id, 0.0))
        dimensions.append({
            "category": cat,
            "category_label": CATEGORY_LABELS[cat],
            "score": score,
            "dominant_tag": {"tag_id": dominant.id, "name": dominant.name},
        })
    return {"dimensions": dimensions}
```

- [ ] **Step 4: Run the test**

```bash
pytest tests/test_profile_calc.py -v
```
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/profile_calc.py backend/tests/test_profile_calc.py
git commit -m "feat(backend): add profile_calc service with match score and radar"
```

---

## Task 5: LLM tagger service with cache

**Files:**
- Create: `backend/app/services/llm_tagger.py`
- Create: `backend/tests/test_llm_tagger.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_llm_tagger.py`:

```python
import json
from datetime import datetime, timedelta

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
    import pytest
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tags": [{"tag_id": 999, "weight": 0.5}], "summary": "s"
    }))
    with pytest.raises(llm_tagger.LlmParseError):
        await llm_tagger.analyze("text", "book", fake)


async def test_json_parse_failure_does_not_write_cache():
    import pytest
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
```

- [ ] **Step 2: Run test to verify failure**

```bash
pytest tests/test_llm_tagger.py -v
```
Expected: FAIL, no `app.services.llm_tagger`

- [ ] **Step 3: Create `backend/app/services/llm_tagger.py`**

```python
import hashlib
import json
from datetime import datetime, timedelta
from typing import Awaitable, Callable

import httpx
from sqlalchemy import select

from app.config import settings
from app import database
from app.models.analysis_cache import AnalysisCache
from app.models.vibe_tag import VibeTag

CACHE_TTL_DAYS = 7
NUM_TAGS = 24

# Callable signature any LLM backend must satisfy
LlmCallable = Callable[[str, str, list], Awaitable[str]]


class LlmParseError(Exception):
    pass


class LlmTimeoutError(Exception):
    pass


PROMPT_TEMPLATE = """你是一个内容品味分析器。下面给你一段关于【{domain}】的文字描述，
请从固定的 24 个元标签里选出最匹配的 1-5 个标签，并给每个 0-1 的权重。
同时用一句话（不超过 30 字）描述这段内容的核心 Vibe。

【标签池】（严格只能从这里选）：
{tag_pool_json}

【待分析文字】：
{text}

输出严格 JSON：{{"tags": [{{"tag_id": 11, "weight": 0.9}}, ...], "summary": "..."}}
不要输出任何解释。"""


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


async def _default_llm_call(text: str, domain: str, tag_pool: list) -> str:
    """DeepSeek-compatible chat completion. Replaceable in tests."""
    prompt = PROMPT_TEMPLATE.format(
        domain=domain,
        tag_pool_json=json.dumps(tag_pool, ensure_ascii=False),
        text=text,
    )
    url = f"{settings.llm_base_url}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException as e:
        raise LlmTimeoutError(str(e)) from e


async def analyze(text: str, domain: str,
                  llm_call: LlmCallable | None = None) -> dict:
    """Analyze text → {match_tags, summary, text_hash, cache_hit}."""
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
            cached.hit_count += 1
            db.commit()
            parsed = json.loads(cached.tags_json)
            return {
                "matched_tags": _enrich_tags(db, parsed["tags"]),
                "summary": cached.summary,
                "text_hash": text_hash,
                "cache_hit": True,
            }

        tag_pool = _load_tag_pool()
        raw = await llm_call(text, domain, tag_pool)
        try:
            parsed = json.loads(raw)
            raw_tags = parsed["tags"]
            summary = parsed["summary"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise LlmParseError(f"invalid LLM response: {e}") from e

        valid = [
            {"tag_id": t["tag_id"], "weight": float(t["weight"])}
            for t in raw_tags
            if isinstance(t.get("tag_id"), int) and 1 <= t["tag_id"] <= NUM_TAGS
        ]
        if not valid:
            raise LlmParseError("all tag_ids out of range")

        db.add(AnalysisCache(
            text_hash=text_hash,
            domain=domain,
            tags_json=json.dumps({"tags": valid, "summary": summary}, ensure_ascii=False),
            summary=summary,
            hit_count=0,
        ))
        db.commit()

        return {
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

- [ ] **Step 4: Run the test**

```bash
pytest tests/test_llm_tagger.py -v
```
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm_tagger.py backend/tests/test_llm_tagger.py
git commit -m "feat(backend): add LLM tagger with cache and tag_id validation"
```

---

## Task 6: Pydantic schemas

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/cold_start.py`
- Create: `backend/app/schemas/analyze.py`
- Create: `backend/app/schemas/action.py`
- Create: `backend/app/schemas/profile.py`

- [ ] **Step 1: Create `backend/app/schemas/__init__.py`**

Empty file:
```python
```

- [ ] **Step 2: Create `backend/app/schemas/cold_start.py`**

```python
from pydantic import BaseModel, Field


class CardOption(BaseModel):
    tag_id: int
    name: str
    tier: int
    tagline: str
    examples: list[str]


class CategoryCard(BaseModel):
    category: str
    category_label: str
    options: list[CardOption]


class ColdStartCardsResponse(BaseModel):
    cards: list[CategoryCard]


class ColdStartSubmitRequest(BaseModel):
    selected_tag_ids: list[int] = Field(min_length=6, max_length=6)


class ColdStartSubmitResponse(BaseModel):
    status: str
    profile_initialized: bool
    already_initialized: bool = False
```

- [ ] **Step 3: Create `backend/app/schemas/analyze.py`**

```python
from pydantic import BaseModel, Field


class AnalyzeContext(BaseModel):
    page_title: str | None = None
    page_url: str | None = None


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=2, max_length=500)
    domain: str  # "book" | "game" | "movie" | "music"
    context: AnalyzeContext | None = None


class MatchedTag(BaseModel):
    tag_id: int
    name: str
    weight: float


class AnalyzeResponse(BaseModel):
    match_score: int
    summary: str
    matched_tags: list[MatchedTag]
    text_hash: str
    cache_hit: bool
```

- [ ] **Step 4: Create `backend/app/schemas/action.py`**

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

- [ ] **Step 5: Create `backend/app/schemas/profile.py`**

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

- [ ] **Step 6: Verify schemas import cleanly**

```bash
python -c "from app.schemas.cold_start import ColdStartCardsResponse; from app.schemas.analyze import AnalyzeRequest; from app.schemas.action import ActionRequest; from app.schemas.profile import RadarResponse; print('ok')"
```
Expected: prints `ok`

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat(backend): add Pydantic schemas for all endpoints"
```

---

## Task 7: Dependency providers

**Files:**
- Create: `backend/app/deps.py`

- [ ] **Step 1: Create `backend/app/deps.py`**

```python
from typing import Generator

from sqlalchemy.orm import Session

from app import database

DEFAULT_USER_ID = 1  # V1.0 single-user hardcoded


def get_db() -> Generator[Session, None, None]:
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_id() -> int:
    return DEFAULT_USER_ID
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/deps.py
git commit -m "feat(backend): add dependency providers (db session, current user)"
```

---

## Task 8: Cold-start router

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/cold_start.py`
- Create: `backend/tests/test_cold_start.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_cold_start.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.main import app
from app.models.action_log import ActionLog
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
from app.services.seed import seed_all

client = TestClient(app)


def _ensure_user():
    seed_all()
    db = database.SessionLocal()
    if db.scalar(select(User).where(User.id == 1)) is None:
        db.add(User(id=1, username="default"))
        db.commit()
    db.close()


def test_get_cards_returns_6_categories_each_with_3_options():
    _ensure_user()
    r = client.get("/api/v1/cold-start/cards")
    assert r.status_code == 200
    body = r.json()
    assert len(body["cards"]) == 6
    for card in body["cards"]:
        assert len(card["options"]) == 3
        tiers = [o["tier"] for o in card["options"]]
        assert 1 in tiers
        assert 4 in tiers


def test_submit_6_valid_tags_initializes_profile():
    _ensure_user()
    # One tag per category (ids 1,5,9,13,17,21 = tier 1 of each)
    r = client.post("/api/v1/cold-start/submit",
                    json={"selected_tag_ids": [1, 5, 9, 13, 17, 21]})
    assert r.status_code == 200
    assert r.json()["profile_initialized"] is True

    db = database.SessionLocal()
    rels = db.scalars(
        select(UserVibeRelation).where(UserVibeRelation.user_id == 1)
    ).all()
    assert len(rels) == 24
    by_tag = {r.vibe_tag_id: r for r in rels}
    for tid in [1, 5, 9, 13, 17, 21]:
        assert by_tag[tid].core_weight == 15.0
    logs = db.scalars(select(ActionLog).where(ActionLog.action == "cold_start")).all()
    assert len(logs) == 6
    db.close()


def test_submit_with_duplicate_category_is_rejected():
    _ensure_user()
    # tags 1 and 4 are both "pace" category
    r = client.post("/api/v1/cold-start/submit",
                    json={"selected_tag_ids": [1, 4, 9, 13, 17, 21]})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "COLD_START_INVALID_SELECTION"


def test_submit_with_wrong_count_is_rejected():
    _ensure_user()
    r = client.post("/api/v1/cold-start/submit",
                    json={"selected_tag_ids": [1, 5, 9]})
    assert r.status_code == 422  # pydantic validation


def test_resubmit_returns_already_initialized():
    _ensure_user()
    client.post("/api/v1/cold-start/submit",
                json={"selected_tag_ids": [1, 5, 9, 13, 17, 21]})
    r = client.post("/api/v1/cold-start/submit",
                    json={"selected_tag_ids": [2, 6, 10, 14, 18, 22]})
    assert r.status_code == 200
    assert r.json()["already_initialized"] is True

    # Weights from the first submit must be preserved
    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    assert rel.core_weight == 15.0
    db.close()
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/test_cold_start.py -v
```
Expected: FAIL, 404s because the router doesn't exist yet

- [ ] **Step 3: Create `backend/app/routers/__init__.py`**

Empty file:
```python
```

- [ ] **Step 4: Create `backend/app/routers/cold_start.py`**

```python
import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db
from app.models.action_log import ActionLog
from app.models.user_vibe_relation import UserVibeRelation
from app.models.vibe_tag import VibeTag
from app.schemas.cold_start import (
    CardOption,
    CategoryCard,
    ColdStartCardsResponse,
    ColdStartSubmitRequest,
    ColdStartSubmitResponse,
)
from app.services.seed_data import CARD_META, CATEGORY_LABELS

router = APIRouter(prefix="/api/v1/cold-start", tags=["cold-start"])

CATEGORY_ORDER = ["pace", "mood", "cognition", "narrative", "world", "intensity"]
COLD_START_DELTA = 15.0


@router.get("/cards", response_model=ColdStartCardsResponse)
def get_cards(db: Session = Depends(get_db)):
    cards: list[CategoryCard] = []
    for cat in CATEGORY_ORDER:
        tags = db.scalars(
            select(VibeTag).where(VibeTag.category == cat).order_by(VibeTag.tier)
        ).all()
        middle_choice = random.choice([t for t in tags if t.tier in (2, 3)])
        chosen = [t for t in tags if t.tier in (1, 4)] + [middle_choice]
        chosen.sort(key=lambda t: t.tier)
        options = [
            CardOption(
                tag_id=t.id,
                name=t.name,
                tier=t.tier,
                tagline=CARD_META[t.id]["tagline"],
                examples=CARD_META[t.id]["examples"],
            )
            for t in chosen
        ]
        cards.append(CategoryCard(
            category=cat,
            category_label=CATEGORY_LABELS[cat],
            options=options,
        ))
    return ColdStartCardsResponse(cards=cards)


@router.post("/submit", response_model=ColdStartSubmitResponse)
def submit(
    payload: ColdStartSubmitRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    # Already initialized? short-circuit
    existing_count = db.scalar(
        select(UserVibeRelation).where(UserVibeRelation.user_id == user_id)
    )
    if existing_count is not None:
        return ColdStartSubmitResponse(
            status="ok",
            profile_initialized=True,
            already_initialized=True,
        )

    selected = db.scalars(
        select(VibeTag).where(VibeTag.id.in_(payload.selected_tag_ids))
    ).all()
    if len(selected) != 6 or {t.category for t in selected} != set(CATEGORY_ORDER):
        raise HTTPException(
            status_code=400,
            detail={"error": {
                "code": "COLD_START_INVALID_SELECTION",
                "message": "must select exactly one tag from each of the 6 categories",
            }},
        )

    # Initialize 24 rows, 6 of them with core_weight = +15
    all_tags = db.scalars(select(VibeTag)).all()
    selected_ids = set(payload.selected_tag_ids)
    for t in all_tags:
        db.add(UserVibeRelation(
            user_id=user_id,
            vibe_tag_id=t.id,
            curiosity_weight=0.0,
            core_weight=COLD_START_DELTA if t.id in selected_ids else 0.0,
        ))
    for tid in selected_ids:
        db.add(ActionLog(
            user_id=user_id,
            vibe_tag_id=tid,
            action="cold_start",
            delta=COLD_START_DELTA,
            target_column="core",
        ))
    db.commit()

    return ColdStartSubmitResponse(status="ok", profile_initialized=True)
```

- [ ] **Step 5: Register router and error handler in `main.py`**

Edit `backend/app/main.py`:

```python
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import cold_start

app = FastAPI(title="Vibe-Radar", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exc_handler(_: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code,
                        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}})


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(cold_start.router)
```

- [ ] **Step 6: Run the test**

```bash
pytest tests/test_cold_start.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/ backend/app/main.py backend/tests/test_cold_start.py
git commit -m "feat(backend): add cold-start router with cards and submit"
```

---

## Task 9: Vibe analyze + action router

**Files:**
- Create: `backend/app/routers/vibe.py`
- Create: `backend/tests/test_vibe.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_vibe.py`:

```python
import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database
from app.main import app
from app.models.action_log import ActionLog
from app.models.user import User
from app.models.user_vibe_relation import UserVibeRelation
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


def _install_fake_llm(monkeypatch, response):
    async def fake(text, domain, tag_pool):
        return response
    from app.services import llm_tagger
    monkeypatch.setattr(llm_tagger, "_default_llm_call", fake)


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

    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    assert rel.curiosity_weight == 0.5
    db.close()


def test_analyze_second_call_hits_cache(monkeypatch):
    _init_profile()
    _install_fake_llm(monkeypatch, json.dumps({
        "tags": [{"tag_id": 1, "weight": 0.9}], "summary": "slow"
    }))
    client.post("/api/v1/vibe/analyze",
                json={"text": "same text", "domain": "book"})
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "same text", "domain": "book"})
    assert r.json()["cache_hit"] is True


def test_analyze_llm_parse_failure_returns_503(monkeypatch):
    _init_profile()
    _install_fake_llm(monkeypatch, "garbage")
    r = client.post("/api/v1/vibe/analyze",
                    json={"text": "x", "domain": "book"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "LLM_PARSE_FAIL"


def test_action_star_increments_core_weight(monkeypatch):
    _init_profile()
    r = client.post("/api/v1/vibe/action",
                    json={"action": "star", "matched_tag_ids": [2, 3]})
    assert r.status_code == 200
    assert r.json()["updated_tags"] == 2

    db = database.SessionLocal()
    r2 = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 2,
        )
    )
    assert r2.core_weight == 10.0
    logs = db.scalars(select(ActionLog).where(ActionLog.action == "star")).all()
    assert len(logs) == 2
    db.close()


def test_action_bomb_decrements_core_weight(monkeypatch):
    _init_profile()
    r = client.post("/api/v1/vibe/action",
                    json={"action": "bomb", "matched_tag_ids": [1]})
    assert r.status_code == 200
    db = database.SessionLocal()
    rel = db.scalar(
        select(UserVibeRelation).where(
            UserVibeRelation.user_id == 1,
            UserVibeRelation.vibe_tag_id == 1,
        )
    )
    # Started at 15 (cold start), bomb = -10 → 5
    assert rel.core_weight == 5.0
    db.close()
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/test_vibe.py -v
```
Expected: FAIL, router missing

- [ ] **Step 3: Create `backend/app/routers/vibe.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_current_user_id, get_db
from app.schemas.action import ActionRequest, ActionResponse
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse, MatchedTag
from app.services import llm_tagger, profile_calc

router = APIRouter(prefix="/api/v1/vibe", tags=["vibe"])

CURIOSITY_DELTA = 0.5
STAR_DELTA = 10.0
BOMB_DELTA = -10.0


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

- [ ] **Step 4: Register router in `backend/app/main.py`**

Add these two lines after the existing `from app.routers import cold_start`:

```python
from app.routers import vibe
```

And after `app.include_router(cold_start.router)`:

```python
app.include_router(vibe.router)
```

- [ ] **Step 5: Run the test**

```bash
pytest tests/test_vibe.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/vibe.py backend/app/main.py backend/tests/test_vibe.py
git commit -m "feat(backend): add vibe analyze and action routers"
```

---

## Task 10: Profile radar router

**Files:**
- Create: `backend/app/routers/profile.py`
- Create: `backend/tests/test_profile.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_profile.py`:

```python
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
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/test_profile.py -v
```
Expected: FAIL, 404

- [ ] **Step 3: Create `backend/app/routers/profile.py`**

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

- [ ] **Step 4: Register router in `backend/app/main.py`**

Add to the imports:
```python
from app.routers import profile
```

And after the existing `app.include_router(vibe.router)`:
```python
app.include_router(profile.router)
```

- [ ] **Step 5: Run the test**

```bash
pytest tests/test_profile.py -v
```
Expected: PASS

- [ ] **Step 6: Run the full backend test suite**

```bash
pytest -v
```
Expected: all tests from tasks 2-10 pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/profile.py backend/app/main.py backend/tests/test_profile.py
git commit -m "feat(backend): add profile radar router"
```

---

## Task 11: Extension project scaffold

**Files:**
- Create: `extension/package.json`
- Create: `extension/tsconfig.json`
- Create: `extension/build.mjs`
- Create: `extension/manifest.json`
- Create: `extension/src/assets/icon.svg`

- [ ] **Step 1: Create `extension/package.json`**

```json
{
  "name": "vibe-radar",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "build": "node build.mjs",
    "watch": "node build.mjs --watch"
  },
  "devDependencies": {
    "esbuild": "^0.23.1",
    "typescript": "^5.6.2",
    "@types/chrome": "^0.0.270"
  },
  "dependencies": {
    "echarts": "^5.5.1"
  }
}
```

- [ ] **Step 2: Create `extension/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "allowSyntheticDefaultImports": true,
    "lib": ["ES2020", "DOM"],
    "types": ["chrome"],
    "baseUrl": "src"
  },
  "include": ["src/**/*.ts"]
}
```

- [ ] **Step 3: Create `extension/build.mjs`**

```javascript
import esbuild from "esbuild";
import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";

const watch = process.argv.includes("--watch");
const outdir = "build";

// Plugin: inline a CSS file as a string export at build time
const inlineCss = {
  name: "inline-css",
  setup(build) {
    build.onResolve({ filter: /\.css\?inline$/ }, (args) => ({
      path: join(dirname(args.importer), args.path.replace("?inline", "")),
      namespace: "inline-css",
    }));
    build.onLoad({ filter: /.*/, namespace: "inline-css" }, async (args) => {
      const css = await readFile(args.path, "utf8");
      return { contents: `export default ${JSON.stringify(css)};`, loader: "js" };
    });
  },
};

await mkdir(outdir, { recursive: true });
await mkdir(join(outdir, "popup"), { recursive: true });

// Copy static assets
await cp("manifest.json", join(outdir, "manifest.json"));
await cp("src/assets", join(outdir, "assets"), { recursive: true });
await cp("src/popup/popup.html", join(outdir, "popup/popup.html"));
if (existsSync("src/popup/popup.css")) {
  await cp("src/popup/popup.css", join(outdir, "popup/popup.css"));
}

const ctx = {
  bundle: true,
  format: "iife",
  target: "chrome114",
  plugins: [inlineCss],
  logLevel: "info",
};

await Promise.all([
  esbuild.build({
    ...ctx,
    entryPoints: ["src/background/index.ts"],
    outfile: join(outdir, "background.js"),
  }),
  esbuild.build({
    ...ctx,
    entryPoints: ["src/content/index.ts"],
    outfile: join(outdir, "content.js"),
  }),
  esbuild.build({
    ...ctx,
    entryPoints: ["src/popup/popup.ts"],
    outfile: join(outdir, "popup/popup.js"),
  }),
]);

if (watch) {
  // Simple rebuild loop via esbuild context (omitted for brevity)
  console.log("Built once. Re-run `npm run build` after edits.");
}

console.log("Extension built to", outdir);
```

- [ ] **Step 4: Create `extension/manifest.json`**

```json
{
  "manifest_version": 3,
  "name": "Vibe-Radar",
  "version": "1.0.0",
  "description": "潜意识审美鉴定器",
  "permissions": ["storage", "activeTab"],
  "host_permissions": [
    "http://localhost:8000/*",
    "https://book.douban.com/*",
    "https://movie.douban.com/*",
    "https://store.steampowered.com/*",
    "https://music.163.com/*"
  ],
  "background": { "service_worker": "background.js" },
  "content_scripts": [
    {
      "matches": [
        "https://book.douban.com/*",
        "https://movie.douban.com/*",
        "https://store.steampowered.com/*",
        "https://music.163.com/*"
      ],
      "js": ["content.js"],
      "run_at": "document_idle"
    }
  ],
  "action": {
    "default_popup": "popup/popup.html",
    "default_icon": "assets/icon.svg"
  }
}
```

- [ ] **Step 5: Create `extension/src/assets/icon.svg`**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <circle cx="32" cy="32" r="28" fill="#6C5CE7"/>
  <circle cx="32" cy="32" r="18" fill="none" stroke="#fff" stroke-width="2" opacity="0.6"/>
  <circle cx="32" cy="32" r="10" fill="none" stroke="#fff" stroke-width="2"/>
  <circle cx="32" cy="32" r="3" fill="#fff"/>
</svg>
```

- [ ] **Step 6: Install deps**

```bash
cd extension
npm install
```
Expected: creates `node_modules/`

- [ ] **Step 7: Commit**

```bash
git add extension/package.json extension/tsconfig.json extension/build.mjs extension/manifest.json extension/src/assets/
git commit -m "chore(ext): scaffold extension with esbuild and manifest"
```

---

## Task 12: Shared types and API helper

**Files:**
- Create: `extension/src/shared/types.ts`
- Create: `extension/src/shared/api.ts`
- Create: `extension/src/shared/constants.ts`

- [ ] **Step 1: Create `extension/src/shared/types.ts`**

```typescript
export type Domain = "book" | "game" | "movie" | "music";

export interface MatchedTag {
  tag_id: number;
  name: string;
  weight: number;
}

export interface AnalyzeResult {
  match_score: number;
  summary: string;
  matched_tags: MatchedTag[];
  text_hash: string;
  cache_hit: boolean;
}

export interface CardOption {
  tag_id: number;
  name: string;
  tier: number;
  tagline: string;
  examples: string[];
}

export interface CategoryCard {
  category: string;
  category_label: string;
  options: CardOption[];
}

export interface ColdStartCardsResult {
  cards: CategoryCard[];
}

export interface ColdStartSubmitResult {
  status: string;
  profile_initialized: boolean;
  already_initialized?: boolean;
}

export interface RadarDimension {
  category: string;
  category_label: string;
  score: number;
  dominant_tag: { tag_id: number; name: string };
}

export interface RadarResult {
  user_id: number;
  dimensions: RadarDimension[];
  total_analyze_count: number;
  total_action_count: number;
}

export type Msg =
  | { type: "ANALYZE"; payload: { text: string; domain: Domain; pageTitle: string; pageUrl: string } }
  | { type: "ACTION"; payload: { action: "star" | "bomb"; matchedTagIds: number[]; textHash?: string } }
  | { type: "COLD_START_GET_CARDS" }
  | { type: "COLD_START_SUBMIT"; payload: { selectedTagIds: number[] } }
  | { type: "GET_RADAR" };

export type MsgResponse<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string } };
```

- [ ] **Step 2: Create `extension/src/shared/api.ts`**

```typescript
import type { Msg, MsgResponse } from "./types";

export function send<T>(msg: Msg): Promise<T> {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (resp: MsgResponse<T>) => {
      if (chrome.runtime.lastError) {
        return reject(new Error(`BACKEND_DOWN: ${chrome.runtime.lastError.message}`));
      }
      if (!resp) {
        return reject(new Error("BACKEND_DOWN: no response"));
      }
      if (resp.ok) resolve(resp.data);
      else reject(new Error(`${resp.error.code}: ${resp.error.message}`));
    });
  });
}

export const API_BASE = "http://localhost:8000/api/v1";
```

- [ ] **Step 3: Create `extension/src/shared/constants.ts`**

```typescript
import type { Domain } from "./types";

export const DOMAIN_RULES: Array<{ test: RegExp; domain: Domain }> = [
  { test: /^https?:\/\/book\.douban\.com\//, domain: "book" },
  { test: /^https?:\/\/movie\.douban\.com\//, domain: "movie" },
  { test: /^https?:\/\/store\.steampowered\.com\//, domain: "game" },
  { test: /^https?:\/\/music\.163\.com\//, domain: "music" },
];

export const MIN_TEXT_LEN = 2;
export const MAX_TEXT_LEN = 200;
```

- [ ] **Step 4: Commit**

```bash
git add extension/src/shared/
git commit -m "feat(ext): add shared types, API send wrapper, constants"
```

---

## Task 13: Background service worker

**Files:**
- Create: `extension/src/background/index.ts`

- [ ] **Step 1: Create `extension/src/background/index.ts`**

```typescript
import { API_BASE } from "../shared/api";
import type { Msg, MsgResponse } from "../shared/types";

async function fetchJson<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let code = "HTTP_ERROR";
    let message = `${r.status}`;
    try {
      const j = await r.json();
      if (j?.error) {
        code = j.error.code || code;
        message = j.error.message || message;
      }
    } catch {
      /* ignore */
    }
    const err = new Error(message);
    (err as any).code = code;
    throw err;
  }
  return r.json();
}

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

chrome.runtime.onMessage.addListener(
  (msg: Msg, _sender, sendResponse: (r: MsgResponse<unknown>) => void) => {
    (async () => {
      try {
        const data = await routeApi(msg);
        sendResponse({ ok: true, data });
      } catch (e: any) {
        sendResponse({
          ok: false,
          error: {
            code: e?.code || "BACKEND_DOWN",
            message: e?.message || "unknown error",
          },
        });
      }
    })();
    return true; // keep message channel open for async
  }
);
```

- [ ] **Step 2: Verify build succeeds**

```bash
cd extension && npm run build
```
Expected: `Extension built to build`

- [ ] **Step 3: Commit**

```bash
git add extension/src/background/
git commit -m "feat(ext): add background service worker as API gateway"
```

---

## Task 14: Content script — domain + Shadow DOM + mouseup

**Files:**
- Create: `extension/src/content/domain.ts`
- Create: `extension/src/content/ui/styles.css`
- Create: `extension/src/content/ui/FloatingIcon.ts`
- Create: `extension/src/content/ui/VibeCard.ts`
- Create: `extension/src/content/index.ts`

- [ ] **Step 1: Create `extension/src/content/domain.ts`**

```typescript
import { DOMAIN_RULES } from "../shared/constants";
import type { Domain } from "../shared/types";

export function detectDomain(url: string): Domain | null {
  return DOMAIN_RULES.find((r) => r.test.test(url))?.domain ?? null;
}
```

- [ ] **Step 2: Create `extension/src/content/ui/styles.css`**

```css
:host { all: initial; }

.vr-root {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  color: #1a1a1a;
  position: absolute;
  pointer-events: none;
}

.vr-floating-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6c5ce7, #a29bfe);
  box-shadow: 0 2px 8px rgba(108, 92, 231, 0.4);
  cursor: pointer;
  pointer-events: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  transition: transform 0.15s ease;
}
.vr-floating-icon:hover { transform: scale(1.1); }

.vr-card {
  position: absolute;
  top: 36px;
  left: 0;
  width: 320px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
  padding: 16px;
  pointer-events: auto;
  font-size: 13px;
  line-height: 1.5;
}

.vr-score {
  font-size: 32px;
  font-weight: 700;
  color: #6c5ce7;
}

.vr-summary {
  margin: 8px 0 12px;
  color: #555;
}

.vr-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 12px; }
.vr-tag {
  padding: 2px 8px;
  background: #f0edff;
  color: #6c5ce7;
  border-radius: 10px;
  font-size: 11px;
}

.vr-actions { display: flex; gap: 8px; }
.vr-btn {
  flex: 1;
  padding: 8px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: transform 0.1s;
}
.vr-btn:hover { transform: translateY(-1px); }
.vr-btn.star { background: #ffeaa7; color: #b8860b; }
.vr-btn.bomb { background: #ffe0e0; color: #d63031; }

.vr-loading { color: #888; padding: 8px 0; }
.vr-error { color: #d63031; padding: 8px 0; }
```

- [ ] **Step 3: Create `extension/src/content/ui/FloatingIcon.ts`**

```typescript
export interface FloatingIconProps {
  x: number;
  y: number;
  onClick: () => void;
}

export function renderFloatingIcon(root: ShadowRoot, props: FloatingIconProps): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "vr-root";
  wrap.style.left = `${props.x}px`;
  wrap.style.top = `${props.y - 32}px`;

  const icon = document.createElement("div");
  icon.className = "vr-floating-icon";
  icon.textContent = "◉";
  icon.addEventListener("click", (e) => {
    e.stopPropagation();
    props.onClick();
  });
  wrap.appendChild(icon);

  root.appendChild(wrap);
  return wrap;
}
```

- [ ] **Step 4: Create `extension/src/content/ui/VibeCard.ts`**

```typescript
import { send } from "../../shared/api";
import type { AnalyzeResult, Msg } from "../../shared/types";

export interface VibeCardProps {
  parent: HTMLElement;
  result: AnalyzeResult;
  onClose: () => void;
}

export function renderVibeCard(props: VibeCardProps): HTMLElement {
  const { parent, result, onClose } = props;
  const card = document.createElement("div");
  card.className = "vr-card";

  const score = document.createElement("div");
  score.className = "vr-score";
  score.textContent = `${result.match_score}%`;
  card.appendChild(score);

  const summary = document.createElement("div");
  summary.className = "vr-summary";
  summary.textContent = result.summary;
  card.appendChild(summary);

  const tagsWrap = document.createElement("div");
  tagsWrap.className = "vr-tags";
  for (const t of result.matched_tags) {
    const pill = document.createElement("span");
    pill.className = "vr-tag";
    pill.textContent = t.name;
    tagsWrap.appendChild(pill);
  }
  card.appendChild(tagsWrap);

  const actions = document.createElement("div");
  actions.className = "vr-actions";

  const star = document.createElement("button");
  star.className = "vr-btn star";
  star.textContent = "💎 懂我";
  star.addEventListener("click", async () => {
    await sendAction("star", result);
    star.textContent = "✓ 已确权";
    setTimeout(onClose, 1500);
  });

  const bomb = document.createElement("button");
  bomb.className = "vr-btn bomb";
  bomb.textContent = "💣 踩雷";
  bomb.addEventListener("click", async () => {
    await sendAction("bomb", result);
    bomb.textContent = "✓ 已标记";
    setTimeout(onClose, 1500);
  });

  actions.appendChild(star);
  actions.appendChild(bomb);
  card.appendChild(actions);

  parent.appendChild(card);
  return card;
}

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

- [ ] **Step 5: Create `extension/src/content/index.ts`**

```typescript
import { send } from "../shared/api";
import { MAX_TEXT_LEN, MIN_TEXT_LEN } from "../shared/constants";
import type { AnalyzeResult, Domain, Msg } from "../shared/types";
import { detectDomain } from "./domain";
import { renderFloatingIcon } from "./ui/FloatingIcon";
import { renderVibeCard } from "./ui/VibeCard";
import INLINE_CSS from "./ui/styles.css?inline";

let shadowRoot: ShadowRoot | null = null;
let currentIcon: HTMLElement | null = null;
let currentCard: HTMLElement | null = null;

function ensureShadow(): ShadowRoot {
  if (shadowRoot) return shadowRoot;
  const host = document.createElement("div");
  host.id = "vibe-radar-host";
  host.style.cssText = "position:absolute;top:0;left:0;z-index:2147483647;";
  const root = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = INLINE_CSS;
  root.appendChild(style);
  document.body.appendChild(host);
  shadowRoot = root;
  return root;
}

function clearUi() {
  currentIcon?.remove();
  currentIcon = null;
  currentCard?.remove();
  currentCard = null;
}

async function onIconClick(text: string, domain: Domain) {
  if (!currentIcon) return;
  // Show loading state inside the icon's wrap
  const loading = document.createElement("div");
  loading.className = "vr-card vr-loading";
  loading.textContent = "鉴定中…";
  currentIcon.appendChild(loading);

  const msg: Msg = {
    type: "ANALYZE",
    payload: {
      text,
      domain,
      pageTitle: document.title,
      pageUrl: location.href,
    },
  };

  try {
    const result = await send<AnalyzeResult>(msg);
    loading.remove();
    currentCard = renderVibeCard({
      parent: currentIcon,
      result,
      onClose: clearUi,
    });
  } catch (e: any) {
    loading.className = "vr-card vr-error";
    loading.textContent = e?.message?.startsWith("BACKEND_DOWN")
      ? "后端未运行，请先启动 FastAPI"
      : `鉴定失败: ${e?.message ?? "未知错误"}`;
    setTimeout(clearUi, 3000);
  }
}

document.addEventListener("mouseup", () => {
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
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") clearUi();
});

document.addEventListener("mousedown", (e) => {
  // Click outside the shadow host → hide
  if (currentIcon && !(e.target as Element).closest("#vibe-radar-host")) {
    clearUi();
  }
});
```

- [ ] **Step 6: Build and verify no type errors**

```bash
cd extension && npm run build
```
Expected: `Extension built to build`

- [ ] **Step 7: Commit**

```bash
git add extension/src/content/
git commit -m "feat(ext): add content script with Shadow DOM, floating icon, vibe card"
```

---

## Task 15: Popup — cold start flow

**Files:**
- Create: `extension/src/popup/popup.html`
- Create: `extension/src/popup/popup.css`
- Create: `extension/src/popup/coldStart.ts`
- Create: `extension/src/popup/popup.ts`

- [ ] **Step 1: Create `extension/src/popup/popup.html`**

```html
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Vibe-Radar</title>
    <link rel="stylesheet" href="popup.css" />
  </head>
  <body>
    <div id="root"></div>
    <script src="popup.js"></script>
  </body>
</html>
```

- [ ] **Step 2: Create `extension/src/popup/popup.css`**

```css
body {
  width: 400px;
  margin: 0;
  font-family: -apple-system, "PingFang SC", sans-serif;
  background: #faf9ff;
  color: #1a1a1a;
}

#root { padding: 16px; }

h2 { margin: 0 0 12px; font-size: 18px; color: #6c5ce7; }
.subtitle { color: #888; font-size: 12px; margin-bottom: 16px; }

.category {
  margin-bottom: 16px;
}
.category-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 6px;
}
.options { display: flex; gap: 6px; }
.option {
  flex: 1;
  padding: 10px 8px;
  background: #fff;
  border: 2px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  text-align: center;
  font-size: 12px;
  transition: all 0.15s;
}
.option:hover { transform: translateY(-2px); }
.option.selected {
  border-color: #6c5ce7;
  background: #f0edff;
}
.option-name { font-weight: 600; margin-bottom: 4px; }
.option-tagline { color: #888; font-size: 11px; }
.option-examples { color: #aaa; font-size: 10px; margin-top: 3px; }

.submit {
  width: 100%;
  padding: 12px;
  background: #ccc;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 14px;
  cursor: not-allowed;
  margin-top: 8px;
}
.submit.enabled {
  background: linear-gradient(135deg, #6c5ce7, #a29bfe);
  cursor: pointer;
}

#radar { width: 100%; height: 360px; }
.stats {
  margin-top: 12px;
  padding: 8px;
  background: #fff;
  border-radius: 8px;
  font-size: 12px;
  color: #555;
}

.error { color: #d63031; padding: 12px; }
```

- [ ] **Step 3: Create `extension/src/popup/coldStart.ts`**

```typescript
import { send } from "../shared/api";
import type { CategoryCard, ColdStartCardsResult, ColdStartSubmitResult } from "../shared/types";

type Selections = Record<string, number>;

export async function renderColdStart(root: HTMLElement, onDone: () => void) {
  root.innerHTML = `
    <h2>Vibe-Radar 冷启动</h2>
    <div class="subtitle">每行挑一张最像你的，让我先认识你</div>
    <div id="cards"></div>
    <button class="submit" id="submit">请先完成 6 个选择</button>
  `;

  const cardsRoot = root.querySelector("#cards") as HTMLElement;
  const submitBtn = root.querySelector("#submit") as HTMLButtonElement;
  const selections: Selections = {};

  try {
    const data = await send<ColdStartCardsResult>({ type: "COLD_START_GET_CARDS" });
    for (const card of data.cards) {
      cardsRoot.appendChild(renderCategoryCard(card, selections, () =>
        updateSubmit(submitBtn, selections)
      ));
    }
  } catch (e: any) {
    cardsRoot.innerHTML = `<div class="error">加载失败: ${e?.message ?? "未知"}</div>`;
    return;
  }

  submitBtn.addEventListener("click", async () => {
    if (Object.keys(selections).length !== 6) return;
    const ids = Object.values(selections);
    try {
      await send<ColdStartSubmitResult>({
        type: "COLD_START_SUBMIT",
        payload: { selectedTagIds: ids },
      });
      await chrome.storage.local.set({ profile_initialized: true });
      onDone();
    } catch (e: any) {
      submitBtn.textContent = `提交失败: ${e?.message ?? "未知"}`;
    }
  });
}

function renderCategoryCard(card: CategoryCard, selections: Selections, onChange: () => void): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "category";
  wrap.innerHTML = `<div class="category-label">${card.category_label}</div>`;
  const opts = document.createElement("div");
  opts.className = "options";
  for (const o of card.options) {
    const el = document.createElement("div");
    el.className = "option";
    el.innerHTML = `
      <div class="option-name">${o.name}</div>
      <div class="option-tagline">${o.tagline}</div>
      <div class="option-examples">${o.examples.join(" · ")}</div>
    `;
    el.addEventListener("click", () => {
      opts.querySelectorAll(".option").forEach((n) => n.classList.remove("selected"));
      el.classList.add("selected");
      selections[card.category] = o.tag_id;
      onChange();
    });
    opts.appendChild(el);
  }
  wrap.appendChild(opts);
  return wrap;
}

function updateSubmit(btn: HTMLButtonElement, selections: Selections) {
  const done = Object.keys(selections).length === 6;
  btn.classList.toggle("enabled", done);
  btn.textContent = done ? "开始鉴定" : `还差 ${6 - Object.keys(selections).length} 个`;
}
```

- [ ] **Step 4: Create `extension/src/popup/popup.ts` (placeholder — radar added next task)**

```typescript
import { renderColdStart } from "./coldStart";

async function main() {
  const root = document.getElementById("root")!;
  const { profile_initialized } = await chrome.storage.local.get("profile_initialized");

  if (!profile_initialized) {
    await renderColdStart(root, () => main());
  } else {
    // Radar rendering added in Task 16
    const mod = await import("./radar");
    await mod.renderRadar(root);
  }
}

main();
```

- [ ] **Step 5: Build (will fail due to missing radar module — that's OK, we'll fix next task)**

Skip build until Task 16 so we can commit this chunk.

- [ ] **Step 6: Commit**

```bash
git add extension/src/popup/popup.html extension/src/popup/popup.css extension/src/popup/coldStart.ts extension/src/popup/popup.ts
git commit -m "feat(ext): add popup cold-start UI (6 categories × 3 cards)"
```

---

## Task 16: Popup — radar chart

**Files:**
- Create: `extension/src/popup/radar.ts`

- [ ] **Step 1: Create `extension/src/popup/radar.ts`**

```typescript
import * as echarts from "echarts";

import { send } from "../shared/api";
import type { RadarResult } from "../shared/types";

export async function renderRadar(root: HTMLElement) {
  root.innerHTML = `
    <h2>你的审美雷达</h2>
    <div id="radar"></div>
    <div class="stats" id="stats"></div>
  `;
  const chartRoot = root.querySelector("#radar") as HTMLElement;
  const statsRoot = root.querySelector("#stats") as HTMLElement;

  let data: RadarResult;
  try {
    data = await send<RadarResult>({ type: "GET_RADAR" });
  } catch (e: any) {
    chartRoot.innerHTML = `<div class="error">加载失败: ${e?.message ?? "未知"}</div>`;
    return;
  }

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

  statsRoot.innerHTML = `
    已鉴定 <b>${data.total_analyze_count}</b> 次 ·
    已确权 <b>${data.total_action_count}</b> 次
  `;
}
```

- [ ] **Step 2: Build**

```bash
cd extension && npm run build
```
Expected: `Extension built to build`

- [ ] **Step 3: Commit**

```bash
git add extension/src/popup/radar.ts
git commit -m "feat(ext): add popup radar chart with ECharts"
```

---

## Task 17: Manual smoke test + root docs

**Files:**
- Create: `extension/SMOKE.md`
- Modify: `README.md`

- [ ] **Step 1: Create `extension/SMOKE.md`**

```markdown
# V1.0 Manual Smoke Test

## Prereqs
1. Backend running: `cd backend && uvicorn app.main:app --reload --port 8000`
2. Extension built: `cd extension && npm run build`
3. Extension loaded in Chrome via `chrome://extensions` → Load unpacked → `extension/build/`
4. `backend/.env` configured with a real LLM API key (only needed for step 4)

## Steps

### 1. Cold start
- Click extension icon → popup shows 18 cards (6 categories × 3 each)
- Click one card per category → bottom button reads "开始鉴定" and becomes purple
- Click → popup switches to radar chart view
- Expected: 6-axis radar, 4 categories at ~0, 6 categories at ~42 (one tier-1 each, core_weight=15)

### 2. Popup reopens to radar
- Close popup, reopen → goes directly to radar view (not cold-start)
- `chrome.storage.local.profile_initialized` should be `true`

### 3. Highlight-to-analyze — basic
- Go to `https://book.douban.com/subject/1000000/` (any Douban book)
- Highlight 2-10 Chinese characters in any review
- Expected: a round purple icon appears at the top-right of the selection
- Click the icon → rounded card appears below with:
  - Large match score percentage
  - One-line AI summary
  - Purple pill-shaped tags
  - 💎 懂我 / 💣 踩雷 buttons

### 4. Star/Bomb flow
- Click 💎 → button text becomes "✓ 已确权" → card fades after 1.5s
- Open popup → radar values should have shifted (same-tag categories +10)

### 5. Cache hit
- Highlight the exact same text a second time → click icon again
- Check background service worker console: should log `cache_hit: true` (visible in network response)
- Observably, response arrives faster than the first call

### 6. Backend-down handling
- Stop uvicorn
- Highlight text → click icon
- Expected: card shows "后端未运行，请先启动 FastAPI" and disappears after 3s

### 7. Out-of-whitelist sites
- Go to `https://www.baidu.com/`
- Highlight any text
- Expected: no icon appears (content script not injected)

## Pass criteria
All 7 steps complete without any JavaScript console errors in either the background worker or the content script.
```

- [ ] **Step 2: Update `README.md`**

Replace with:

```markdown
# Vibe-Radar V1.0

Chrome extension + FastAPI backend for personalized "Vibe" matching on
book / game / movie / music sites. Highlights text → extracts Vibe tags via
LLM → scores against your dual-weight profile → lets you confirm with
💎/💣 buttons.

## Quick start

### Backend
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate  # or .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # fill in your LLM API key
python -m app.services.seed     # first time only
uvicorn app.main:app --reload --port 8000
pytest                          # run tests
```

### Extension
```bash
cd extension
npm install
npm run build
```
Then Chrome → `chrome://extensions` → Developer mode → Load unpacked → pick `extension/build/`.

## Docs
- Design spec: `docs/superpowers/specs/2026-04-14-vibe-radar-v1-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-14-vibe-radar-v1.md`
- Manual smoke test: `extension/SMOKE.md`

## Scope
V1.0 is a single-user local dev build (`user_id=1` hardcoded, no auth).
Recommendation pool / JWT / deployment deferred to V1.1+.
```

- [ ] **Step 3: Run the complete backend test suite one more time**

```bash
cd backend && pytest -v
```
Expected: all tests pass

- [ ] **Step 4: Final build check**

```bash
cd ../extension && npm run build
```
Expected: `Extension built to build`

- [ ] **Step 5: Execute the smoke test manually**

Follow `extension/SMOKE.md` steps 1-7. Each step must pass before committing.

- [ ] **Step 6: Commit**

```bash
cd ..
git add extension/SMOKE.md README.md
git commit -m "docs: add manual smoke test and project README"
```

---

## Post-implementation checklist

- [ ] Backend `pytest -v` all green (tasks 2-10 combined ≈ 20 tests)
- [ ] Extension `npm run build` succeeds without errors
- [ ] All 7 smoke test steps pass
- [ ] `git log --oneline` shows roughly 17 commits following conventional commits
- [ ] `docs/superpowers/plans/2026-04-14-vibe-radar-v1.md` checkboxes all ticked

---

## Appendix: Known V1.0 Limitations

These are **intentionally not fixed** in V1.0 — document them here so they don't get re-raised as bugs:

1. **Single user only**: `user_id=1` is hardcoded. Running two browser profiles against the same backend will corrupt the profile.
2. **No weight clamping**: `core_weight` can grow without bound if you keep hitting 💎. V1.1 will clip to `[-100, 100]`.
3. **No whitelist fallback**: if a site doesn't match the 4 configured domains, the content script isn't injected and there's no UI path to analyze text.
4. **No iframe support**: selections inside cross-origin iframes are ignored.
5. **LLM failure gives no retry button**: user must re-highlight text to retry.
6. **Popup always fetches fresh radar**: no caching, no live updates between rapid star/bomb clicks.
7. **No e2e tests on the extension**: smoke test is manual only.
