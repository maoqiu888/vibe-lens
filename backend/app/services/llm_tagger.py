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
    """Analyze text -> {matched_tags, summary, text_hash, cache_hit}."""
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

        # Drop any expired entry sharing this hash so the unique index frees up.
        stale = db.scalar(
            select(AnalysisCache).where(AnalysisCache.text_hash == text_hash)
        )
        if stale is not None:
            db.delete(stale)
            db.commit()

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
