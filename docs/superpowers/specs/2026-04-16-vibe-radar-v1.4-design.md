# Vibe-Radar V1.4 SP-F Design — 3-Agent Chain Architecture

> Status: Approved in brainstorming
> Date: 2026-04-16
> Scope: Replace the 2-call tagger+roaster pipeline with a 3-Agent chain (识别官→匹配官→朋友) for dramatically improved item identification, match accuracy, and voice quality
> Parent specs: V1.0–V1.3

---

## 1. Context and Motivation

### 1.1 Why V1.3's architecture can't deliver

V1.0–V1.3 used a 2-LLM-call pipeline:
- **Call 1 (tagger):** extract 24 tags + item_context + summary from the highlighted text
- **Call 2 (roaster):** generate a friend-voice recommendation

After 4 rounds of prompt iterations in V1.3, the user identified three structural failures that prompt engineering cannot fix:

1. **Tagger does 3 jobs poorly.** It simultaneously identifies the item, extracts 24 tags, AND writes a natural-language context summary. With competing objectives in one prompt, each task gets diluted. Result: "我，许可" gets misidentified as a review fragment; "挽救计划" gets matched to the book instead of the movie.

2. **Match score is purely mathematical.** Cosine similarity on a 24-dim vector gives a cold number with no explanation. The user sees "65%" but has no idea *why*. The roaster tries to infer a narrative from the score, but it wasn't part of the matching process — it's reverse-engineering an explanation.

3. **Roaster has insufficient context.** It receives raw text + a taste hint + a match score, but doesn't know *what specific aspects of the item match or clash with the user's personality*. It can't say "the director's pacing style conflicts with your preference for fast cuts" because nobody told it about the director.

### 1.2 The fix: 3-Agent chain with separation of concerns

Each agent does **one thing** and does it well:

| Agent | Role | Core Question | Inputs | Output |
|---|---|---|---|---|
| **Agent 1: 识别官** | Item identification + tag extraction | "What IS this?" | text, domain, page_title | `item_profile` (structured JSON) + 24 tags |
| **Agent 2: 匹配官** | Personality-aware match scoring | "Would THIS USER like it?" | item_profile, cosine base_score, user personality | `final_score`, 3 reasons, verdict |
| **Agent 3: 朋友** | Natural language voice | "How to tell them?" | item_profile, final_score, reasons, verdict, user personality, original text | 60-120 char friend-voice recommendation |

**Key architectural choice (方案 β from brainstorming):** The existing 24-tag cosine similarity is **preserved as a base score**. Agent 2 adjusts it by ±15 based on deeper personality analysis. This keeps the math backbone (radar chart, weight accumulation, level system, MBTI seeding) intact while layering LLM judgment on top.

### 1.3 Non-goals

- Agent debate/discussion pattern (V1.4 is a sequential pipeline, not a multi-agent debate)
- External API calls (no Douban API, no web search — pure pretrained knowledge)
- Items database / dedup (SP-C, deferred)
- Fourth agent (e.g., "反驳官" for adversarial review)
- LLM provider switch (stays on DeepSeek)
- Frontend architectural changes beyond VibeCard layout tweaks

---

## 2. Data Flow

```
User highlights "我，许可" on movie.douban.com
    │
    ▼
[Content Script] → chrome.runtime.sendMessage(ANALYZE)
    │
    ▼
[Background] → POST /api/v1/vibe/analyze
    │
    ▼
[analyze route — Step 1]
    │  Check analysis_cache by text_hash
    │  Cache HIT (with item_profile)? → skip Agent 1
    │  Cache MISS? → call Agent 1
    │
    ▼
┌─── Agent 1: 识别官 ──────────────────────────────┐
│  LLM Call (temperature 0.5, timeout 12s)          │
│  Input: text + domain + page_title + 24 tag pool  │
│  Output: item_profile JSON + tags + summary       │
│  Cache: write to analysis_cache (7-day TTL)       │
└──────────────────────────────────────────────────┘
    │
    ▼
[analyze route — Step 2]
    │  compute_match_score(user_vec, item_tags) → base_score
    │
    ▼
[analyze route — Step 3]
    │  Build user context: personality.summary || tag descriptions
    │
    ▼
┌─── Agent 2: 匹配官 ──────────────────────────────┐
│  LLM Call (temperature 0.3, timeout 8s)           │
│  Input: item_profile + base_score + user context  │
│  Output: final_score, reasons[3], verdict         │
│  NOT cached                                       │
└──────────────────────────────────────────────────┘
    │
    ▼
┌─── Agent 3: 朋友 ────────────────────────────────┐
│  LLM Call (temperature 0.9, timeout 8s)           │
│  Input: item_profile + final_score + reasons      │
│         + verdict + user context + original text  │
│  Output: 60-120 char friend-voice string          │
│  NOT cached                                       │
└──────────────────────────────────────────────────┘
    │
    ▼
[analyze route — Step 4]
    │  apply_curiosity_delta or first_impression
    │  increment_interaction
    │  build AnalyzeResponse
    │
    ▼
← HTTP 200 JSON response to extension
```

---

## 3. Agent 1 — 识别官 (replaces `llm_tagger`)

### 3.1 Service: `backend/app/services/llm_identifier.py`

**New file.** Replaces `llm_tagger.py`. The old tagger file is deleted.

```python
async def identify(
    text: str,
    domain: str,
    page_title: str | None = None,
    llm_call: LlmCallable | None = None,
) -> dict:
    """Returns {item_profile: dict, matched_tags: list, summary: str,
               text_hash: str, cache_hit: bool}."""
```

### 3.2 Output: `item_profile`

```json
{
  "item_name": "《我，许可》",
  "item_name_alt": null,
  "year": 2024,
  "creator": "导演：刘抒鸣",
  "genre": "华语剧情片",
  "plot_gist": "一个普通人许可在城市中挣扎求存的故事，探讨个体在社会压力下的身份认同和自我救赎。",
  "tone": "写实、克制、偏沉重但有微光，不是纯压抑向",
  "name_vs_reality": "名字'我，许可'听着像个人名，容易被当作评论碎片，但其实是一部完整的院线电影。",
  "confidence": "high"
}
```

Field contracts:
- `item_name`: always non-empty. Chinese name with 书名号 if a specific work; descriptive phrase otherwise ("一段关于慢节奏电影的评论")
- `item_name_alt`: English/original name if known, else null
- `year`: integer if known, else null
- `creator`: director/author/developer/artist if known, else null
- `genre`: free-form short genre label, 2-8 chars
- `plot_gist`: 1-3 sentences, real plot content. Must use pretrained knowledge, not guess from the title.
- `tone`: adjective-chain describing the actual emotional tone. Must flag name-vs-reality mismatches.
- `name_vs_reality`: explicit if the title is misleading. Empty string if title is straightforward.
- `confidence`: "high" (≥60% sure this is a real identified work), "medium" (30-60%), "low" (<30%, best-effort guess)

### 3.3 Tags + summary

The identify function ALSO returns `matched_tags` and `summary` — same structure as V1.3's tagger. These feed into:
- `compute_match_score` for the cosine base_score
- `apply_curiosity_delta` / `apply_core_delta` for profile updates
- Radar chart dimensions
- The cache (`analysis_cache.tags_json` stores `{tags, summary, item_profile}`)

### 3.4 Prompt design principles

- **Domain priority rule**: "用户在 {domain} 页面 → 优先识别 {domain} 类型的作品"
- **Default assumption**: "划的文字绝大概率是一个具体作品的标题"
- **Pretrained knowledge activation**: "你的训练数据覆盖了大量华语电影、英美电影、主流游戏、知名书籍和专辑。先搜记忆库再输出。"
- **禁止摆烂表述**: ban "无法确定", "识别不出", "碎片", "没头没尾"
- **Confidence-calibrated language**: high → assertive; medium → tentative; low → explicit "best guess" prefix
- **Temperature 0.5**: higher than V1.3's 0.2 to encourage broader knowledge retrieval

### 3.5 Cache behavior

- Same `analysis_cache` table, same `text_hash` key (SHA256 of text+domain)
- `tags_json` stores the full `{tags, summary, item_profile}` JSON
- 7-day TTL
- Old cache entries without `item_profile` → treated as cache miss (regenerated)
- Cache hit returns `item_profile` + `matched_tags` + `summary` without calling LLM

### 3.6 Error handling

- LLM timeout (>12s) → raise `LlmTimeoutError` (propagates to router → 503)
- JSON parse failure → raise `LlmParseError` (propagates to router → 503)
- item_profile fields missing → fill with sensible defaults (`item_name` = text, `confidence` = "low", etc.)
- **No silent fallback** — if Agent 1 fails, the entire analyze request fails with 503. User sees "鉴定失败，请重试".

---

## 4. Agent 2 — 匹配官 (new service)

### 4.1 Service: `backend/app/services/llm_matcher.py`

**New file.**

```python
async def compute_match(
    item_profile: dict,
    base_score: int,
    user_personality_summary: str,
    user_top_tag_descriptions: list[str],
    llm_call: LlmCallable | None = None,
) -> dict:
    """Returns {final_score: int, reasons: list[str], verdict: str}.

    final_score is base_score adjusted by ±15, clamped to [0, 100].
    reasons is exactly 3 strings.
    verdict is one of "追", "看心情", "跳过".

    On any LLM failure, returns a degraded result:
    {final_score: base_score, reasons: ["匹配分析暂时不可用"], verdict: "看心情"}
    """
```

### 4.2 Score adjustment rules

- `final_score = clamp(base_score + adjustment, 0, 100)`
- `adjustment` ∈ [-15, +15] — enforced by prompt AND by post-processing clamp
- If LLM returns an adjustment outside this range, clamp it
- If LLM returns a `final_score` directly instead of an adjustment, compute `adjustment = final_score - base_score` and clamp

### 4.3 Reasons structure

Exactly 3 reasons, each 15-40 chars:
1. One **match point** (what about this item aligns with the user)
2. One **risk point** (what might not work)
3. One **overall judgment** (synthesizing the above into a verdict explanation)

If LLM returns fewer than 3, pad with generic phrases. If more than 3, truncate.

### 4.4 Verdict

One of exactly 3 values: `"追"` / `"看心情"` / `"跳过"`. If LLM returns anything else, map to the closest one or default to `"看心情"`.

### 4.5 Prompt design principles

- Temperature 0.3 (analytical, not creative — accuracy over diversity)
- System prompt positions Agent 2 as a "匹配分析官" — dispassionate, evidence-based
- User prompt passes: full item_profile JSON, base_score, user personality summary, top-2 tag descriptions
- The prompt tells the LLM: "底分偏低不代表一定差（可能用户标签信号不足）。底分偏高也不代表完美（可能有性格层面的隐含冲突）。你的工作是用理解补数学的缺陷。"

### 4.6 Failure behavior

- LLM timeout/exception → return `{final_score: base_score, reasons: ["匹配分析暂时不可用"], verdict: "看心情"}`
- JSON parse failure → same degraded return
- **Does NOT propagate exceptions** — Agent 2 failure is graceful. The user still gets a score (the cosine base_score) and a recommendation (defaulted to "看心情").

---

## 5. Agent 3 — 朋友 (replaces `llm_roaster`)

### 5.1 Service: `backend/app/services/llm_advisor.py`

**New file.** Replaces `llm_roaster.py`. The old roaster file is deleted.

```python
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
```

### 5.2 Prompt design principles

- Temperature 0.9 (creative, divergent — voice variety)
- System prompt is the "挑剔朋友" persona (inherited from V1.3's roaster rewrite)
- **Key difference from V1.3**: Agent 3 now receives **structured facts** from Agent 1 (item_profile) and **structured reasoning** from Agent 2 (reasons + verdict + final_score). It does NOT need to guess what the item is or why it matches.
- Agent 3's ONLY job: translate facts + reasoning into natural friend voice
- Must reference specific details from item_profile (director, plot, tone)
- Must use reasons as the logical backbone of its advice
- Must end with verdict + final_score%
- Same "no tag vocabulary leak" and "no AI tone" bans as V1.3

### 5.3 Failure behavior

Same as current roaster: any exception → return `""`. Frontend falls back to displaying summary as primary copy.

---

## 6. Router Changes

### 6.1 `POST /api/v1/vibe/analyze` — rewritten pipeline

```python
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload, db, user_id):
    # Step 1: Agent 1 — Identify (cached)
    page_title = payload.context.page_title if payload.context else None
    identification = await llm_identifier.identify(
        payload.text, payload.domain, page_title=page_title
    )
    item_profile = identification["item_profile"]
    matched_tags = identification["matched_tags"]

    # Step 2: Cosine base score
    item_tags = [(t["tag_id"], t["weight"]) for t in matched_tags]
    base_score = profile_calc.compute_match_score(user_id=user_id, item_tags=item_tags)

    # Step 3: User context
    user_personality = db.scalar(select(UserPersonality).where(...))
    if user_personality and user_personality.summary:
        user_hint = user_personality.summary
    else:
        user_hint = "；".join(profile_calc.get_top_core_tag_descriptions(user_id, n=2))

    # Step 4: Agent 2 — Match (uncached)
    match_result = await llm_matcher.compute_match(
        item_profile=item_profile,
        base_score=base_score,
        user_personality_summary=user_hint,
        user_top_tag_descriptions=profile_calc.get_top_core_tag_descriptions(user_id, n=2),
    )

    # Step 5: Agent 3 — Advise (uncached)
    roast = await llm_advisor.advise(
        text=payload.text,
        domain=payload.domain,
        item_profile=item_profile,
        final_score=match_result["final_score"],
        reasons=match_result["reasons"],
        verdict=match_result["verdict"],
        user_personality_summary=user_hint,
    )

    # Step 6: Profile update (unchanged from V1.2/V1.3)
    # ... first_impression / curiosity_delta / increment_interaction ...

    return AnalyzeResponse(
        match_score=match_result["final_score"],  # Agent 2's adjusted score
        verdict=match_result["verdict"],           # NEW
        reasons=match_result["reasons"],           # NEW
        summary=identification["summary"],
        roast=roast,                               # Agent 3's output
        matched_tags=[MatchedTag(**t) for t in matched_tags],
        text_hash=identification["text_hash"],
        cache_hit=identification["cache_hit"],
        # ... existing level fields unchanged ...
    )
```

### 6.2 Schema changes

```python
# schemas/analyze.py — AnalyzeResponse gains:
class AnalyzeResponse(BaseModel):
    match_score: int          # NOW: Agent 2's final_score (was: cosine raw)
    verdict: str              # NEW: "追" | "看心情" | "跳过"
    reasons: list[str]        # NEW: 3 match/risk/summary reasons
    summary: str
    roast: str = ""
    matched_tags: list[MatchedTag]
    text_hash: str
    cache_hit: bool
    # ... existing level/interaction fields unchanged ...
```

---

## 7. File Changes Summary

### New files
| File | Purpose |
|---|---|
| `backend/app/services/llm_identifier.py` | Agent 1 — item identification + tag extraction |
| `backend/app/services/llm_matcher.py` | Agent 2 — personality-aware match scoring |
| `backend/app/services/llm_advisor.py` | Agent 3 — friend-voice recommendation |
| `backend/tests/test_llm_identifier.py` | Agent 1 tests |
| `backend/tests/test_llm_matcher.py` | Agent 2 tests |
| `backend/tests/test_llm_advisor.py` | Agent 3 tests |

### Deleted files
| File | Reason |
|---|---|
| `backend/app/services/llm_tagger.py` | Replaced by `llm_identifier.py` |
| `backend/app/services/llm_roaster.py` | Replaced by `llm_advisor.py` |
| `backend/tests/test_llm_tagger.py` | Replaced by `test_llm_identifier.py` |
| `backend/tests/test_llm_roaster.py` | Replaced by `test_llm_advisor.py` |

### Modified files
| File | Changes |
|---|---|
| `backend/app/routers/vibe.py` | Rewrite analyze pipeline to 3-Agent chain |
| `backend/app/schemas/analyze.py` | Add `verdict`, `reasons` fields |
| `backend/tests/test_vibe.py` | Update all analyze-related tests for new pipeline |
| `extension/src/shared/types.ts` | Add `verdict`, `reasons` to `AnalyzeResult` |
| `extension/src/content/ui/VibeCard.ts` | Add verdict badge, remove summary grey text |
| `extension/src/content/ui/styles.css` | Verdict badge styles |
| `extension/SMOKE.md` | Update smoke steps |

### Unchanged
- `llm_recommender.py` — cross-domain recommendations stay as-is
- `llm_personality_agent.py` — MBTI cold-start stays as-is
- `profile_calc.py` — all math stays (cosine, levels, dynamic weights)
- All popup files, SharePoster, RecommendCard, LevelUpOverlay
- 24-tag vocabulary, seed data, database schema (except analysis_cache content format)

---

## 8. Error Handling Matrix

| Scenario | Location | Behavior |
|---|---|---|
| Agent 1 timeout (>12s) | llm_identifier | Raise `LlmTimeoutError` → router → 503 `LLM_TIMEOUT` |
| Agent 1 JSON parse fail | llm_identifier | Raise `LlmParseError` → router → 503 `LLM_PARSE_FAIL` |
| Agent 1 item_profile missing fields | llm_identifier | Fill defaults (item_name=text, confidence="low") |
| Agent 2 timeout/fail | llm_matcher | Graceful degrade: return base_score as final_score, verdict="看心情", reasons=["暂不可用"] |
| Agent 3 timeout/fail | llm_advisor | Return `""` → frontend shows summary fallback |
| All 3 agents succeed but item unrecognized (confidence="low") | pipeline | Proceed normally — Agent 2/3 work with the low-confidence profile |
| Cache hit on Agent 1 | llm_identifier | Skip LLM call, Agent 2+3 still run (because user-specific) |

**Failure asymmetry by design:**
- Agent 1 failure = **hard fail** (503). Without knowing what the item IS, nothing downstream works.
- Agent 2 failure = **soft fail**. User gets the raw cosine score (still meaningful) and a default verdict.
- Agent 3 failure = **soft fail**. User sees summary as fallback copy.

---

## 9. Testing Strategy

### Backend (pytest)

**New test files:**
- `test_llm_identifier.py` (~10 tests): FakeLLM injection, item_profile structure validation, domain priority, confidence levels, cache behavior (hit/miss/expired/old-format), tag extraction, page_title passthrough
- `test_llm_matcher.py` (~8 tests): FakeLLM injection, score clamping (±15), reasons structure (exactly 3), verdict validation (only 3 allowed values), graceful degradation on failure, base_score passthrough on degradation
- `test_llm_advisor.py` (~6 tests): FakeLLM injection, output is non-empty string, failure returns "", prompt contains item_profile facts + reasons + verdict

**Modified test files:**
- `test_vibe.py`: Update `_install_fake_llm` helper for new 4-arg identifier signature; update all analyze tests for new response fields (verdict, reasons); add 3 new tests for the 3-Agent pipeline integration

**Deleted test files:**
- `test_llm_tagger.py` (replaced by `test_llm_identifier.py`)
- `test_llm_roaster.py` (replaced by `test_llm_advisor.py`)

**Expected total:** ~93 → ~95 tests (delete ~20 tagger/roaster tests, add ~24 identifier/matcher/advisor tests, +3 integration)

### Frontend (manual SMOKE.md)

New/updated steps:
- Step verifying 3-Agent pipeline produces item_profile with real knowledge
- Step verifying final_score differs from base_score (Agent 2 adjustment visible)
- Step verifying verdict badge appears on VibeCard
- Step verifying roast text references specific item_profile details (director/plot/tone)

---

## 10. Implementation Estimate

~8 tasks:

1. **T1:** Create `llm_identifier.py` (Agent 1) + tests
2. **T2:** Create `llm_matcher.py` (Agent 2) + tests
3. **T3:** Create `llm_advisor.py` (Agent 3) + tests
4. **T4:** Rewrite `vibe.py analyze` to 3-Agent pipeline + extend schemas
5. **T5:** Delete old `llm_tagger.py` + `llm_roaster.py` + update test_vibe.py
6. **T6:** Frontend shared types (verdict + reasons fields) + background
7. **T7:** VibeCard verdict badge + remove summary grey text + CSS
8. **T8:** SMOKE.md + final verify

~800 lines new, ~400 lines deleted, ~200 lines modified.

---

## 11. Known Limitations

1. **3 serial LLM calls = 4-6s latency.** Acceptable for a local dev tool. If latency becomes a problem, Agent 2+3 could be parallelized (they don't depend on each other's output... wait, Agent 3 depends on Agent 2's output. So they must be serial. Accept the latency.)
2. **DeepSeek knowledge cutoff.** Very recent releases (2025-2026) may not be in DeepSeek's training data. Agent 1 will output `confidence: "low"` and a best-effort guess. The pipeline still works, just less precisely.
3. **±15 score adjustment is a heuristic.** If users consistently feel the adjusted score is wrong, the range may need tuning. Start with ±15 and collect feedback.
4. **No Agent debate.** V1.4 is a unidirectional pipeline. If Agent 1 misidentifies an item, Agent 2 and 3 build on that error. A future "verifier" agent could cross-check, but that's V1.5+ territory.
5. **Cost ~¥0.003/analyze.** Triple the V1.3 cost. Acceptable for single-user local use. Would need optimization (e.g., combining Agent 2+3 into one call) for multi-user deployment.
