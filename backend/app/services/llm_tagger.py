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

logger = logging.getLogger("vibe.tagger")

CACHE_TTL_DAYS = 7
NUM_TAGS = 24

# Signature: (text, domain, page_title, tag_pool) -> raw JSON string
LlmCallable = Callable[[str, str, str | None, list], Awaitable[str]]


class LlmParseError(Exception):
    pass


class LlmTimeoutError(Exception):
    pass


PROMPT_TEMPLATE = """你是一个内容品味分析器。用户在一个【{domain}】类型的页面划了一段文字给你。

【页面标题】：{page_title}
【用户划到的文字】：{text}

你需要做三件事：

1. 从固定的 24 个元标签里选出最匹配的 1-5 个标签，并给每个 0-1 的权重。
2. 用一句话（不超过 30 字）客观描述这段内容的核心 Vibe。
3. **最关键：输出一个 item_context 字段**，用你的预训练知识介绍这个物品到底是什么。

【关于 item_context —— 最重要的字段，认真读完】

**默认假设**：用户在一个 {domain} 页面上划的文字，**绝大概率是一个具体作品的标题、片段或关键情节描述**。不是随便的碎片。你必须把自己调到"我一定认得出这是什么"的模式。

**你的训练数据**覆盖了大量的华语电影、英美电影、主流游戏、知名书籍和专辑。当你看到一个 1-10 字的短标题出现在 {domain} 页面上，**先假设它是某部作品**，再调用你的知识。

【硬规则：必须做的】
1. **先搜索你的记忆库**。把 {text} 和 {page_title} 当作查询，从你的训练知识里捞出匹配的作品。华语短标题也要尽力识别，不要默认是"不认识"。
2. 识别到了 → 写出：**作品全名 + 年份（如果知道）+ 创作者 + 真实的剧情/题材 + 它真正的调性（如果名字容易误导读者，必须明说反差）**
3. 对自己判断**确信度高**时（≥60% 认识这部作品）→ **直接陈述事实**，不要用"看起来像"、"应该是"这种退缩语气
4. **确信度低**时，也依然要给出你最好的猜测，并用"可能是"、"看起来像"标注不确定。**但仍然要写出你能推断的东西**，不要写"我识别不出来"这种话。
5. 禁止输出"无法确定"、"识别不出"、"看起来只是碎片"、"没头没尾"这种放弃性表述。
6. 长度 60-150 字。

【真的真的识别不出来怎么办】
只在**以下两种极端场景**下才能走降级：
- 选中的文字是一段**明显的普通评论**（"这部片子真好看"、"我哭了"），没有任何作品标识 → 描述这段评论的情绪
- 选中的文字**不到 2 个字符**或是随机字符 → 描述用户可能在看什么
即便在降级场景下，**你也要主动推测**："在豆瓣电影页面看到这种评论，大概率是一部催泪向的剧情片..."

【禁止】
- 禁止瞎编具体事实（比如造一个不存在的年份或演员）—— 如果不确定细节就不写细节，但**一定要写整体认识**
- 禁止使用"碎片"、"没头没尾"、"识别不出"、"无法确定" 这些摆烂词

【标签池】（你只能在 tag_id 里引用这些 id）：
{tag_pool_json}

【输出格式】严格 JSON，不要 markdown 代码块：
{{"tags": [{{"tag_id": 11, "weight": 0.9}}, ...], "summary": "...", "item_context": "..."}}

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
        "TAGGER CALL | text=%r | domain=%s | page_title=%r",
        text[:80], domain, (page_title or "")[:80],
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            logger.info("TAGGER RAW RESPONSE: %s", content[:500])
            return content
    except httpx.TimeoutException as e:
        raise LlmTimeoutError(str(e)) from e


async def analyze(
    text: str,
    domain: str,
    page_title: str | None = None,
    llm_call: LlmCallable | None = None,
) -> dict:
    """Analyze text → {matched_tags, summary, item_context, text_hash, cache_hit}.

    item_context is a natural-language paragraph the LLM writes using its
    pretrained knowledge. Never empty. Never falls back. Old cached entries
    without item_context are treated as cache miss and regenerated.
    """
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
            cached_item_context = parsed.get("item_context", "")
            # V1.3.1: treat old cache entries without item_context as cache miss
            # so users always get the enriched LLM context.
            if cached_item_context:
                cached.hit_count += 1
                db.commit()
                return {
                    "matched_tags": _enrich_tags(db, parsed["tags"]),
                    "summary": cached.summary,
                    "item_context": cached_item_context,
                    "text_hash": text_hash,
                    "cache_hit": True,
                }

        tag_pool = _load_tag_pool()
        raw = await llm_call(text, domain, page_title, tag_pool)
        try:
            parsed = json.loads(raw)
            raw_tags = parsed["tags"]
            summary = parsed["summary"]
            item_context = parsed.get("item_context", "")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise LlmParseError(f"invalid LLM response: {e}") from e

        valid = [
            {"tag_id": t["tag_id"], "weight": float(t["weight"])}
            for t in raw_tags
            if isinstance(t.get("tag_id"), int) and 1 <= t["tag_id"] <= NUM_TAGS
        ]
        if not valid:
            raise LlmParseError("all tag_ids out of range")

        # item_context fallback — if LLM ignored instructions and returned empty,
        # synthesize a minimal one from summary so downstream roaster still gets
        # something. This honors "no degradation" while staying safe.
        if not isinstance(item_context, str):
            item_context = ""
        item_context = item_context.strip()
        if not item_context:
            item_context = f"看起来是{domain}里的一段内容。{summary}"

        # Drop any expired entry sharing this hash so the unique index frees up.
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
                {"tags": valid, "summary": summary, "item_context": item_context},
                ensure_ascii=False,
            ),
            summary=summary,
            hit_count=0,
        ))
        db.commit()

        return {
            "matched_tags": _enrich_tags(db, valid),
            "summary": summary,
            "item_context": item_context,
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
