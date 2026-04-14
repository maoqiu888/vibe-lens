# Vibe-Radar V1.1 Iteration Design — Roast + Cross-Media Pivot + Share Poster

> Status: Approved in brainstorming
> Date: 2026-04-14
> Scope: Incremental iteration on V1.0 (which is live and smoke-tested)
> Parent spec: `docs/superpowers/specs/2026-04-14-vibe-radar-v1-design.md`

---

## 1. Context and Scope

V1.0 delivered the baseline: highlight-to-rate, 24 closed Vibe tags, dual-weight profile, cold-start, radar chart. The user is running it and identified three UX gaps:

1. **The single match score feels flat** — no personality, no explanation of *why* the score is what it is.
2. **No discovery loop** — a 73% on a movie has no "what next" action; the insight is a dead end.
3. **No social surface** — the result is private, users can't share it, so the product has no viral surface.

V1.1 addresses all three through **three focused additions** that do not alter the V1.0 architecture:

- **F1 — Roast commentary**: A second LLM call generates 30-50 char snarky commentary scoped to *this user × this item*, displayed as the VibeCard's primary copy. Objective `summary` stays as grey secondary text.
- **F2 — Cross-domain "same-frequency" recommendations**: A lazy-triggered route that, given an item and the user's profile, returns 3 recommendations from 3 *different* domains (no same-domain items). LLM-only, zero candidate pool.
- **F3 — Share poster**: A "share" icon on the VibeCard that generates a 1080×1080 PNG via Canvas 2D (not html2canvas — shadow DOM quirks) and offers copy-to-clipboard OR file-download.

### 1.1 Non-goals

- Radar overlap comparison (floated by user, explicitly cut — adds complexity without matching the chosen interaction scope)
- Profile drift alerts (F4, deferred pending F1-F3 retention data)
- Persisting recommendation results to DB (V1.1 is stateless — pure display)
- Extended domain whitelist (still `book / movie / game / music`)
- Multi-user / auth / deployment (still V1.0 constraints — `user_id=1` hardcoded)

### 1.2 Guiding decisions (locked during brainstorming)

| Decision | Choice | Rationale |
|---|---|---|
| Closed vs open tag vocabulary | Keep closed 24 tags | Radar, profile, opposite-mapping all depend on it |
| Roast architecture | Separate `llm_roaster` service, NOT inlined in `llm_tagger` | Cache-friendly (tagger stays cacheable by text+domain); roast is per-user so uncached |
| Recommendation trigger | Lazy (user clicks "find same-frequency") | Controls LLM cost; matches user's "waiting for result" mental model |
| Cross-domain policy | Hard enforced — no same-domain items | "Wormhole feel" is the whole point |
| Poster rendering | Canvas 2D hand-drawn (not html2canvas) | Shadow DOM compatibility |
| Poster format | 1:1 square 1080×1080 | Broadest platform support (WeChat, Weibo, Xiaohongshu) |
| Poster delivery | Both clipboard copy AND file download | User chooses |

---

## 2. Architecture Changes

### 2.1 Backend file additions

```
backend/app/
├── services/
│   ├── llm_roaster.py        # NEW — roast only, no tag extraction, uncached
│   └── llm_recommender.py    # NEW — cross-domain recommendation, uncached
├── schemas/
│   └── recommend.py          # NEW — RecommendRequest / RecommendResponse
└── routers/
    └── vibe.py               # EXTEND — analyze now returns `roast`; add POST /recommend
```

Additional test files:

```
backend/tests/
├── test_llm_roaster.py       # NEW — FakeLLM injection, prompt assembly, failure fallback
├── test_llm_recommender.py   # NEW — cross-domain filtering, multi-domain guarantee
└── test_vibe.py              # EXTEND — new assertions for `roast` field; new tests for /recommend
```

### 2.2 Frontend file additions

```
extension/src/
├── content/
│   └── ui/
│       ├── VibeCard.ts          # EXTEND — roast display, share button, recommend link
│       ├── RecommendCard.ts     # NEW — 3-item cross-domain sub-card, "re-roll" button
│       ├── SharePoster.ts       # NEW — Canvas 2D poster generation + clipboard/download
│       └── styles.css           # EXTEND — new classes for roast, recommend, poster dialog
└── shared/
    └── types.ts                 # EXTEND — AnalyzeResult.roast; new RecommendResult type; new Msg variants
```

### 2.3 API contract

#### 2.3.1 `POST /api/v1/vibe/analyze` — extended response

```json
{
  "match_score": 73,
  "summary": "节奏极慢的心理惊悚片。",
  "roast": "快逃！你那点日常烟火气会被这部电影的幽闭恐惧碾成粉末。",
  "matched_tags": [
    {"tag_id": 19, "name": "赛博机械", "weight": 0.9},
    {"tag_id": 8,  "name": "黑暗压抑", "weight": 0.7}
  ],
  "text_hash": "abc...",
  "cache_hit": false
}
```

**New field:** `roast: str`. Always present (never null). On `llm_roaster` failure, it is `""` and the frontend falls back to displaying `summary` as the primary copy.

The existing `analysis_cache` table stores `tags_json` and `summary` only. `roast` is NEVER cached (user-dependent). On a cache hit for tags, `llm_roaster` still runs a fresh call to generate the roast.

#### 2.3.2 `POST /api/v1/vibe/recommend` — new endpoint

```json
// Request
{
  "text": "赛博朋克 2077 的夜之城霓虹燃烧但灵魂冰冷",
  "source_domain": "movie",
  "matched_tag_ids": [19, 8]
}

// Response (success)
{
  "items": [
    {"domain": "game",  "name": "《逃生》",           "reason": "同样的幽闭窒息感，但你亲手拿着摄像机"},
    {"domain": "book",  "name": "《幽灵之家》",       "reason": "同样心理压抑，但慢炖文学形式"},
    {"domain": "music", "name": "Ben Frost - Aurora", "reason": "黑暗环境音，闭眼听完就能理解那种冷"}
  ]
}
```

**Self-contained request:** The frontend already has all needed data from the preceding `/analyze` response — `text` (original highlighted string), `matched_tag_ids` (from `matched_tags[].tag_id`), and `source_domain`. There is NO cache lookup in this route — it does not depend on `analysis_cache` freshness. This keeps `/recommend` decoupled from the tagger cache and eliminates the "cache expired between analyze and recommend" edge case.

**Backend use of fields:**
- `text` → passed to the recommender prompt as `{item_text}` for grounding
- `matched_tag_ids` → looked up in `vibe_tags` to get `item_tag_names`
- `source_domain` → prompt's `{source_domain}` + cross-domain filter
- Invalid `matched_tag_ids` (outside 1-24 or non-existent) → 400 `{code: "INVALID_TAG_IDS"}`

**Cross-domain enforcement:** Server-side filter. The LLM is told in the prompt to avoid `source_domain`, but if it disobeys, the backend drops any item where `item.domain == source_domain`. If filtering leaves fewer than 2 items, return 503 `{error: {code: "NO_CROSS_DOMAIN"}}`.

**No caching:** Every request hits the LLM. User pays a fresh ~¥0.001 per click. The "换一批" (re-roll) button re-calls this route.

---

## 3. LLM Prompts

### 3.1 `llm_roaster` prompt

Lifted from the user's brainstorming submission, adapted to fit V1.0's closed vocabulary:

**System prompt (constant):**
```
你是 Vibe-Radar 的"赛博毒舌鉴定官"。你看到一个物品和用户的喜好画像，要给出极其精准、刻薄或强烈安利的短评。

【人设与语气】
1. 极具网感、毒舌、一针见血，像极其懂行且脾气古怪的资深评测家
2. 绝对不要用 AI 腔调（"总之"、"综上所述"、"值得一提"禁用）
3. 冲突就狠狠劝退 + 指出致命雷点；契合就给出致命推坑理由
4. 字数严格控制在 30~50 字之间
5. 根据物品类型调整比喻：电影用"影院睡着"、游戏用"摔手柄"、书用"翻不过 30 页"、音乐用"耳机里塞满棉花"

【输出格式】
严格 JSON，不要 markdown 代码块：
{"roast": "你的点评"}
```

**User prompt template:**
```
【物品 ({domain})】：{text}
【物品的 vibe 标签】：{item_tag_names}
【该用户当前的主导审美】：{user_top_tag_names}

请开始你的毒舌鉴定。
```

Where:
- `domain` is one of `book|movie|game|music`
- `text` is the highlighted text (already truncated to ≤500 chars)
- `item_tag_names` is a comma-joined list of the closed-vocabulary tag names that `llm_tagger` selected (e.g., `"赛博机械, 黑暗压抑"`)
- `user_top_tag_names` is the top 3 tag names by `core_weight` for this user (e.g., `"日常烟火, 甜宠治愈, 轻度思考"`)

**Call parameters:**
- `temperature=0.7` (humor/divergence)
- `timeout=8` seconds
- `response_format={"type": "json_object"}`

**Failure behavior:** Any exception (timeout, parse error, empty response) is caught at the router level. The analyze response still succeeds, but `roast = ""` and the frontend falls back to displaying `summary` as primary copy.

### 3.2 `llm_recommender` prompt

**System prompt (constant):**
```
你是 Vibe-Radar 的"跨界代餐官"。用户给你一个物品和他的审美画像，你要推荐 3 个【非当前类型】的东西（书/游戏/电影/音乐），每条有一个不按常理出牌但精准的理由。

【规则】
1. 严格跨域：当前物品是电影就禁止推荐电影，是游戏就禁止推荐游戏，以此类推
2. 3 条必须来自 3 个不同的域（book / movie / game / music 选 3 个，排除当前域）
3. 每条 reason 15-25 字，要毒舌幽默，不能套话
4. 推荐真实存在的作品/游戏/专辑，别瞎编
5. name 字段要包含书名号/专辑名，例如 "《逃生》" 或 "Ben Frost - Aurora"

【输出格式】
严格 JSON，不要 markdown 代码块：
{"items": [{"domain": "book|game|movie|music", "name": "xxx", "reason": "xxx"}, ...]}
```

**User prompt template:**
```
【用户看到的物品 ({source_domain})】：{item_text}
【物品的 vibe】：{item_tag_names}
【用户主导审美】：{user_top_tag_names}

禁止推荐 {source_domain} 类型。请给 3 条跨域代餐。
```

**Call parameters:**
- `temperature=0.8` (higher divergence for creativity)
- `timeout=10` seconds
- `response_format={"type": "json_object"}`

**Post-processing:**
1. Parse JSON, validate `items` is a list
2. For each item, validate `domain` ∈ `{book, movie, game, music}`, `name` is non-empty string, `reason` is non-empty string
3. Filter: drop any item where `domain == source_domain`
4. Filter: drop duplicates (same `name`)
5. If fewer than 2 items remain → raise `RecommendEmptyError` → router returns 503 `{code: "NO_CROSS_DOMAIN"}`
6. Return up to 3 items (if LLM gave more, take first 3 after filtering)

---

## 4. Frontend Changes

### 4.1 VibeCard layout

Current V1.0 card:
```
┌─────────────────────────────┐
│    73%                      │
│    节奏极慢的心理惊悚片...   │  (summary, 灰色)
│    [赛博机械] [黑暗压抑]    │
│    💎 懂我  💣 踩雷         │
└─────────────────────────────┘
```

V1.1 card:
```
┌─────────────────────────────┐
│                        [📤] │  ← share icon, top-right
│    73%                      │
│    快逃！你那点日常烟火气... │  ← roast (粗体紫字, 主角)
│    节奏极慢的心理惊悚片       │  ← summary (降级为灰色小字)
│    [赛博机械] [黑暗压抑]    │
│    💎 懂我  💣 踩雷         │
│    > 寻找同频代餐 ↓         │  ← recommend trigger link
└─────────────────────────────┘
```

**Roast display logic:** `roast.trim() !== "" ? roast : summary` — if roast is empty (LLM failed), promote summary to primary copy and hide the secondary line entirely.

**Recommend link behavior:** Click → the link is replaced in-place with a loading state (same ping animation as the main loading card, scaled down), then `RecommendCard` is appended below the VibeCard.

### 4.2 RecommendCard

Rendered as a separate DOM element appended below VibeCard inside the same Shadow host. Layout:

```
┌─────────────────────────────┐
│   📚 《幽灵之家》            │
│   同样心理压抑，但慢炖文学    │
│   ────────────────────────  │
│   🎮 《逃生》                │
│   幽闭窒息，但你拿着摄像机    │
│   ────────────────────────  │
│   🎵 Ben Frost - Aurora     │
│   黑暗环境音，闭眼听完就懂    │
│                              │
│         [ 换一批 ↻ ]        │
└─────────────────────────────┘
```

Domain icons:
- `book` → 📚
- `movie` → 🎬
- `game` → 🎮
- `music` → 🎵

**"换一批" button:** Disables itself while the request is in flight (shows a spinning indicator), calls `/recommend` with the same `text` + `source_domain` + `matched_tag_ids`, replaces the items in place. On error, shows "代餐官去冲咖啡了，稍后再试". Consecutive calls may return different items because `temperature=0.8` — this is the intended behavior.

**Dismissal:** Clicking outside the shadow host (existing behavior) clears both VibeCard and RecommendCard.

### 4.3 SharePoster (Canvas 2D)

Click `[📤]` → pop a mini dialog inside the VibeCard with two buttons:
```
┌─────────────────────────┐
│  生成分享海报            │
│  [ 📋 复制 ] [ 💾 下载 ] │
│  [ 取消 ]                │
└─────────────────────────┘
```

Both buttons first call `generatePoster(result)` which synchronously builds an `HTMLCanvasElement` of size 1080×1080.

**Canvas layout** (all coordinates relative to 1080×1080):

| Element | Position / Size | Style |
|---|---|---|
| Background | Full canvas | Linear gradient `#6c5ce7 → #a29bfe`, 135° |
| Concentric-circle watermark | Bottom-left, 180×180, semi-transparent white | Echoes the extension logo |
| "Vibe-Radar" wordmark | Top-left, 60px white bold | Font stack: `system-ui, "PingFang SC", sans-serif` |
| Score percentage | Center, 260×180 area | `280px bold white`, format: `{n}%` |
| Matched tag pills | Below score, 80px row | White 12% opacity pill bg, `36px white` text, wrap if needed |
| Roast text | Below tags, 60% width centered, 56px font | White, bold, auto-wrap at ~14 Chinese chars per line, max 3 lines |
| Source line | Below roast, `来自 {domain_label} · 被我划了` | 32px semi-transparent white |
| URL footer | Bottom, `vibe-radar.local` | 28px semi-transparent white |

**Helper functions:**
- `drawWrappedText(ctx, text, x, y, maxWidth, lineHeight)` — breaks CJK text by char count (not word boundaries — CJK doesn't have spaces)
- `drawRoundedRect(ctx, x, y, w, h, r)` — for tag pills
- `drawConcentric(ctx, cx, cy, radii[])` — for watermark

**Delivery:**

```typescript
// Clipboard
async function copyPoster(canvas: HTMLCanvasElement) {
  const blob = await new Promise<Blob>(r => canvas.toBlob(b => r(b!), "image/png"));
  await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
  // show toast "已复制到剪贴板"
}

// Download
function downloadPoster(canvas: HTMLCanvasElement) {
  const link = document.createElement("a");
  link.download = `vibe-radar-${Date.now()}.png`;
  link.href = canvas.toDataURL("image/png");
  link.click();
}
```

**Failure modes:**
- Clipboard API unsupported or permission denied → toast `"剪贴板权限被拒，请用下载按钮"`, auto-switch to download path
- Canvas.toBlob returns null → toast `"海报生成失败，请重试"`

### 4.4 Message protocol additions

```typescript
type Msg =
  | { type: "ANALYZE"; payload: { ... } }        // existing, response schema extends
  | { type: "ACTION"; payload: { ... } }          // existing
  | { type: "COLD_START_GET_CARDS" }              // existing
  | { type: "COLD_START_SUBMIT"; payload: {...} } // existing
  | { type: "GET_RADAR" }                         // existing
  | { type: "RECOMMEND"; payload: { text: string; sourceDomain: Domain; matchedTagIds: number[] } };  // NEW
```

Background `routeApi` adds a case for `RECOMMEND` → `POST /api/v1/vibe/recommend`.

### 4.5 Types additions

```typescript
// AnalyzeResult gains a field
export interface AnalyzeResult {
  match_score: number;
  summary: string;
  roast: string;          // NEW — may be ""
  matched_tags: MatchedTag[];
  text_hash: string;
  cache_hit: boolean;
}

// New type
export interface RecommendItem {
  domain: Domain;
  name: string;
  reason: string;
}

export interface RecommendResult {
  items: RecommendItem[];
}
```

---

## 5. Error handling matrix

| Scenario | Location | Behavior |
|---|---|---|
| `llm_roaster` timeout or parse failure | analyze router | Swallow exception, set `roast=""` in response, analyze still 200 |
| `llm_recommender` timeout | /recommend router | 503 `{code: "LLM_TIMEOUT"}` |
| `llm_recommender` returns invalid JSON | /recommend router | 503 `{code: "LLM_PARSE_FAIL"}` |
| `llm_recommender` returns all-same-domain items | /recommend router | After filter → empty → 503 `{code: "NO_CROSS_DOMAIN"}` |
| `/recommend` called with invalid `matched_tag_ids` (out of 1-24 or empty) | /recommend router | 400 `{code: "INVALID_TAG_IDS"}` |
| Canvas.toBlob returns null | SharePoster | Toast error, user retries |
| Clipboard API unavailable | SharePoster | Toast, auto-fallback to download |

---

## 6. Testing strategy

### 6.1 Backend (pytest)

**New test files:**
- `test_llm_roaster.py`: FakeLLM injection, assert prompt contains user_top_tag_names, assert failure returns `""`, assert timeout raises LlmTimeoutError which router swallows
- `test_llm_recommender.py`:
  - Happy path: LLM returns 3 cross-domain items → all pass through
  - LLM returns 1 item where `domain == source_domain` → filtered, 2 remain → pass
  - LLM returns all items of `source_domain` → filter → empty → RecommendEmptyError
  - LLM returns invalid JSON → LlmParseError
  - LLM returns items with missing fields → dropped
  - Duplicate `name` → deduped

**Extended:**
- `test_vibe.py`: add assertions that `r.json()["roast"]` exists and is a string in success cases; add one test where the injected fake roaster raises, assert response has `roast == ""` and status 200

**New router tests** for `/recommend`:
- Invalid tag_ids (empty list or out-of-range) returns 400
- Happy path returns 3 items with 3 distinct domains, none == source_domain
- LLM failure returns 503 with correct error code

Target: maintain ≥85% services coverage, ≥70% routers. Current 27 tests should grow to ~40.

### 6.2 Frontend (manual — SMOKE.md extension)

Add three steps to `extension/SMOKE.md`:

```
### 8. Roast display
- Highlight text on 豆瓣电影 → click icon
- Expected: bold purple roast text is the largest non-number element; grey summary below it
- If backend `llm_roaster` is flaky, roast should fall back to summary (no empty card)

### 9. Cross-domain recommendation
- On the vibe card, click "> 寻找同频代餐"
- Expected: loading ping animation, then 3 items appear, each with a distinct domain icon
- None of the 3 items should be from the same domain as the current page (e.g., on movie.douban.com, no 🎬 items)
- Click "换一批" → a new set appears

### 10. Share poster
- Click the [📤] share icon on the vibe card
- Expected: mini dialog with 复制 / 下载 buttons
- Click 复制 → paste into any image-accepting target (e.g., WeChat desktop, mspaint) → 1080×1080 gradient poster appears
- Click 下载 → PNG file downloads with filename starting "vibe-radar-"
```

---

## 7. Delivery

All changes commit to `master` branch. Expected commit sequence roughly:

1. `feat(backend): add llm_roaster service`
2. `feat(backend): integrate roaster into analyze route`
3. `feat(backend): add llm_recommender service`
4. `feat(backend): add /vibe/recommend route`
5. `feat(ext): add roast display to VibeCard`
6. `feat(ext): add cross-domain recommend card`
7. `feat(ext): add share poster via Canvas 2D`
8. `docs: extend SMOKE.md with V1.1 manual checks`

Rough LOC estimate: ~600 lines added, ~50 lines modified.

---

## 8. Future gaps to watch (not in V1.1 scope)

- **Roast personality mode** — add a config toggle for "温柔模式" vs "毒舌模式" vs "硬核模式"
- **Recommendation memory** — right now every `/recommend` call is fresh; users might want "don't suggest what I've already seen" tracking
- **Poster theme picker** — allow users to choose between a few color schemes
- **F4 Profile drift alerts** — deferred, reassess after V1.1 retention data

These are explicitly NOT in V1.1 scope. If they come up, they're V1.2.
