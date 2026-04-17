import json
from typing import Awaitable, Callable

import httpx

from app.services.llm_config_reader import get_llm_settings

LlmCallable = Callable[[str, str], Awaitable[str]]

VALID_DOMAINS = {"book", "movie", "game", "music"}


class LlmParseError(Exception):
    pass


class LlmTimeoutError(Exception):
    pass


class RecommendEmptyError(Exception):
    """Raised when cross-domain filtering leaves fewer than 2 items."""
    pass


SYSTEM_PROMPT = """你是 Vibe-Radar 的"跨界代餐官"。用户给你一个物品和他的审美画像，你要推荐 3 个【非当前类型】的东西（书/游戏/电影/音乐），每条有一个不按常理出牌但精准的理由。

【规则】
1. 严格跨域：当前物品是电影就禁止推荐电影，是游戏就禁止推荐游戏，以此类推
2. 3 条必须来自 3 个不同的域（book / movie / game / music 选 3 个，排除当前域）
3. 每条 reason 15-25 字，要毒舌幽默，不能套话
4. 推荐真实存在的作品/游戏/专辑，别瞎编
5. name 字段要包含书名号/专辑名，例如 "《逃生》" 或 "Ben Frost - Aurora"

【输出格式】
严格 JSON，不要 markdown 代码块：
{"items": [{"domain": "book|game|movie|music", "name": "xxx", "reason": "xxx"}, ...]}
"""


def _build_user_prompt(
    text: str,
    source_domain: str,
    item_tag_names: list[str],
    user_top_tag_names: list[str],
) -> str:
    item_tags_str = "、".join(item_tag_names) if item_tag_names else "暂无"
    user_tags_str = "、".join(user_top_tag_names) if user_top_tag_names else "暂无（新用户）"
    return (
        f"【用户看到的物品 ({source_domain})】：{text}\n"
        f"【物品的 vibe】：{item_tags_str}\n"
        f"【用户主导审美】：{user_tags_str}\n\n"
        f"禁止推荐 {source_domain} 类型。请给 3 条跨域代餐。"
    )


async def _default_llm_call(system_prompt: str, user_prompt: str) -> str:
    cfg = get_llm_settings()
    url = f"{cfg['base_url']}/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.8,
    }
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException as e:
        raise LlmTimeoutError(str(e)) from e


async def recommend(
    text: str,
    source_domain: str,
    item_tag_names: list[str],
    user_top_tag_names: list[str],
    llm_call: LlmCallable | None = None,
) -> list[dict]:
    """Return 1-3 cross-domain recommendation items.

    Raises:
        LlmTimeoutError: upstream timeout
        LlmParseError: invalid JSON or structure
        RecommendEmptyError: after filtering, fewer than 2 valid items remain
    """
    llm_call = llm_call or _default_llm_call
    user_prompt = _build_user_prompt(text, source_domain, item_tag_names, user_top_tag_names)

    try:
        raw = await llm_call(SYSTEM_PROMPT, user_prompt)
    except LlmTimeoutError:
        raise
    except httpx.TimeoutException as e:
        raise LlmTimeoutError(str(e)) from e

    try:
        parsed = json.loads(raw)
        raw_items = parsed["items"]
        if not isinstance(raw_items, list):
            raise ValueError("items not a list")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise LlmParseError(f"invalid LLM response: {e}") from e

    seen_names: set[str] = set()
    filtered: list[dict] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        domain = item.get("domain")
        name = item.get("name")
        reason = item.get("reason")
        if not isinstance(domain, str) or domain not in VALID_DOMAINS:
            continue
        if domain == source_domain:
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(reason, str) or not reason.strip():
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        filtered.append({"domain": domain, "name": name, "reason": reason})
        if len(filtered) == 3:
            break

    if len(filtered) < 2:
        raise RecommendEmptyError(f"only {len(filtered)} valid items after filtering")

    return filtered
