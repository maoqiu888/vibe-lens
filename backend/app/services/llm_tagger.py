import hashlib
import json
from datetime import datetime, timedelta
from typing import Awaitable, Callable

import httpx
from sqlalchemy import select

from app import database
from app.config import settings
from app.models.analysis_cache import AnalysisCache
from app.models.vibe_tag import VibeTag

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

【关于 item_context 的详细要求】
- **必须非空**，绝对不准留空或写"无法确定"
- 优先级：
  a) 如果你从【页面标题】或【划到的文字】里**识别出一个真实存在的具体作品**（电影、游戏、书、音乐、专辑等），用你的训练知识写出：作品全名 + 年份 + 创作者 + 一句话真实内容梗概 + 它真正的调性（比如"名字听着压抑但其实幽默乐观"这种反差要明说）
  b) 如果识别不出具体作品但能推断是什么内容场景（比如一段评论、一段剧情描述），就总结这段文字在讲什么
  c) 如果连场景都推断不出（比如一句无意义的碎片），就老实说"这看起来只是一小段{domain}评论里的碎片，没能识别到具体作品"
- **不确信的时候用试探语气**（"看起来像..."、"应该是..."）而不是装成事实
- 长度 30-120 字，一段大白话
- 禁止瞎编具体事实（年份、主演、作者）——如果不确定就不提这些细节

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
