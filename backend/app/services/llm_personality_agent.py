import json
from typing import Awaitable, Callable

import httpx

from app.config import settings

LlmCallable = Callable[[str, str], Awaitable[str]]

MAX_TAG_SEEDS = 8
WEIGHT_MIN = -15.0
WEIGHT_MAX = 15.0
SUMMARY_MIN_LEN = 30
SUMMARY_MAX_LEN = 400


class PersonalityAgentEmptyError(Exception):
    """Raised when neither MBTI nor constellation is supplied."""


_SYSTEM_PROMPT_TEMPLATE = """你是 Vibe-Radar 的"性格翻译官"。用户给你他的 MBTI 和/或星座，你要做两件事：

1. 从固定的 24 个"品味标签池"里选出最多 8 个对他显著的标签，并给每个 -15 到 +15 的权重（正数 = 他会喜欢这种内容，负数 = 他会讨厌）。只给你确信的；不确信的不要出现。
2. 用 100-200 字的自然大白话描述这个人的审美倾向和性格，像在跟一个不认识他的朋友介绍他。描述里不要提 MBTI、星座的术语缩写，也不要用品味标签池里的词汇——你只是在用日常语言描述。

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


def _load_tag_pool_json() -> str:
    from sqlalchemy import select

    from app import database
    from app.models.vibe_tag import VibeTag

    db = database.SessionLocal()
    try:
        tags = db.scalars(select(VibeTag).order_by(VibeTag.id)).all()
        return json.dumps(
            [
                {"id": t.id, "name": t.name, "description": t.description}
                for t in tags
            ],
            ensure_ascii=False,
        )
    finally:
        db.close()


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


async def analyze_personality(
    mbti: str | None,
    constellation: str | None,
    llm_call: LlmCallable | None = None,
) -> dict:
    """Return {tag_seeds: [...], personality_summary: str}.

    Raises PersonalityAgentEmptyError iff both mbti and constellation are None.
    On any LLM or parse failure, returns {"tag_seeds": [], "personality_summary": ""}.
    """
    if not mbti and not constellation:
        raise PersonalityAgentEmptyError("neither mbti nor constellation supplied")

    llm_call = llm_call or _default_llm_call
    tag_pool_json = _load_tag_pool_json()
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(tag_pool_json=tag_pool_json)
    user_prompt = _build_user_prompt(mbti, constellation)

    try:
        raw = await llm_call(system_prompt, user_prompt)
    except Exception:
        return {"tag_seeds": [], "personality_summary": ""}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"tag_seeds": [], "personality_summary": ""}

    raw_seeds = parsed.get("tag_seeds", [])
    if not isinstance(raw_seeds, list):
        raw_seeds = []

    valid_seeds: list[dict] = []
    seen_tag_ids: set[int] = set()
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
        clamped = max(WEIGHT_MIN, min(WEIGHT_MAX, float(weight)))
        valid_seeds.append({"tag_id": tag_id, "weight": clamped})
        seen_tag_ids.add(tag_id)
        if len(valid_seeds) >= MAX_TAG_SEEDS:
            break

    summary = parsed.get("personality_summary", "")
    if not isinstance(summary, str):
        summary = ""
    summary = summary.strip()
    if len(summary) < SUMMARY_MIN_LEN:
        summary = ""
    elif len(summary) > SUMMARY_MAX_LEN:
        summary = summary[:SUMMARY_MAX_LEN]

    return {"tag_seeds": valid_seeds, "personality_summary": summary}
