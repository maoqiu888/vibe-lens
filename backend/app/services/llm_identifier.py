import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Awaitable, Callable

import httpx
from duckduckgo_search import DDGS
from sqlalchemy import select

from app import database
from app.config import settings
from app.models.analysis_cache import AnalysisCache
from app.models.vibe_tag import VibeTag

logger = logging.getLogger("vibe.identifier")

CACHE_TTL_DAYS = 7
NUM_TAGS = 24

# Signature: (text, domain, page_title, tag_pool, search_context) -> raw JSON string
LlmCallable = Callable[[str, str, str | None, list, str], Awaitable[str]]

_DOMAIN_LABEL = {"book": "书籍", "movie": "电影", "game": "游戏", "music": "音乐"}
SEARCH_TIMEOUT = 4.0
SEARCH_MAX_RESULTS = 3


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

【标题补全规则】
用户划词经常只划到标题的一部分（如"阿凡达:火与"→"阿凡达：火与灰烬"，"哈利波特与魔"→"哈利·波特与魔法石"）。你必须：
1. 结合网络搜索结果和预训练知识，将不完整的标题**补全为完整标题**
2. item_name 必须使用**完整的正式标题**，不要照搬用户划到的截断文字
3. 如果搜索结果能确认完整标题，直接采用

【网络搜索结果】（实时联网查询，优先级最高）：
{search_context}

【信息优先级】
1. **网络搜索结果**（最新、最准）→ 2. **页面标题**（用户当前页面）→ 3. **预训练知识**（可能过时）
如果搜索结果和你的记忆有冲突（年份、导演、类型等），**以搜索结果为准**。

【预训练知识激活】
你的训练数据覆盖了大量华语电影、英美电影、主流游戏、知名书籍和专辑。先搜记忆库再输出。把 {text} 和 {page_title} 当作查询，从训练知识里捞出匹配的作品。但如果网络搜索结果已经给出了准确信息，直接采用搜索结果。

【item_profile 输出要求】
- item_name: 必填。中文名加书名号（如果是具体作品）；描述短语（如果是评论片段）
- item_name_alt: 英文/原名，不知道就 null
- year: 整数年份。**优先从页面标题中提取**（如"(2026)"、"2025年"等）。如果页面标题没有年份且你的训练数据里没有确切信息，设为 null，不要猜
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


_DOMAIN_CONFLICT_KEYWORDS = {
    "movie": {"小说", "书籍", "图书", "文学", "长篇", "短篇"},
    "book": {"电影", "院线", "票房", "导演执导"},
    "game": {"电影", "小说", "书籍"},
    "music": {"电影", "小说", "书籍", "游戏"},
}

_DOMAIN_GENRE_LABEL = {
    "movie": "电影", "book": "书籍", "game": "游戏", "music": "音乐",
}


def _enforce_domain(profile: dict, domain: str) -> dict:
    """Post-process: if genre contradicts the user's domain, force-correct."""
    genre = (profile.get("genre") or "").lower()
    conflict_words = _DOMAIN_CONFLICT_KEYWORDS.get(domain, set())
    for word in conflict_words:
        if word in genre:
            domain_label = _DOMAIN_GENRE_LABEL.get(domain, domain)
            old_genre = profile["genre"]
            profile["genre"] = f"{domain_label}（原识别：{old_genre}）"
            if profile.get("confidence") == "high":
                profile["confidence"] = "medium"
            logger.warning(
                "DOMAIN ENFORCE | domain=%s conflicts with genre=%r → corrected",
                domain, old_genre,
            )
            break
    return profile


def _fill_profile_defaults(raw_profile: dict, text: str) -> dict:
    """Fill missing item_profile fields with sensible defaults."""
    profile = dict(_ITEM_PROFILE_DEFAULTS)  # start with defaults
    profile.update({k: v for k, v in raw_profile.items() if v is not None or k in ("year", "creator", "item_name_alt")})
    # item_name is required and must never be empty
    if not profile.get("item_name"):
        profile["item_name"] = text
    return profile


def _web_search(text: str, domain: str) -> str:
    """Search DuckDuckGo for item info. Returns formatted snippets or ''."""
    domain_label = _DOMAIN_LABEL.get(domain, domain)
    query = f"{text} {domain_label}"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=SEARCH_MAX_RESULTS))
        if not results:
            return ""
        snippets = []
        for r in results:
            snippets.append(f"- {r['title']}: {r['body']}")
        context = "\n".join(snippets)
        logger.info("WEB SEARCH | query=%r | %d results", query, len(results))
        return context
    except Exception as e:
        logger.warning("WEB SEARCH FAILED: %s", e)
        return ""


async def _async_web_search(text: str, domain: str) -> str:
    """Run blocking DuckDuckGo search in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _web_search, text, domain)


async def _default_llm_call(
    text: str,
    domain: str,
    page_title: str | None,
    tag_pool: list,
    search_context: str = "",
) -> str:
    """DeepSeek-compatible chat completion. Replaceable in tests."""
    prompt = PROMPT_TEMPLATE.format(
        domain=domain,
        page_title=page_title or "（无页面标题）",
        tag_pool_json=json.dumps(tag_pool, ensure_ascii=False),
        text=text,
        search_context=search_context or "（无搜索结果）",
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

        loop = asyncio.get_event_loop()
        tag_pool_future = loop.run_in_executor(None, _load_tag_pool)
        search_future = _async_web_search(text, domain)
        tag_pool, search_context = await asyncio.gather(
            tag_pool_future, search_future
        )
        raw = await llm_call(text, domain, page_title, tag_pool, search_context)
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
        item_profile = _enforce_domain(item_profile, domain)

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
