import json
from typing import Awaitable, Callable

import httpx

from app.config import settings

LlmCallable = Callable[[str, str], Awaitable[str]]

SYSTEM_PROMPT = """你是 Vibe-Radar 的"赛博毒舌鉴定官"。你看到一个物品和用户的喜好画像，要给出极其精准、刻薄或强烈安利的短评。

【人设与语气】
1. 极具网感、毒舌、一针见血，像极其懂行且脾气古怪的资深评测家
2. 绝对不要用 AI 腔调（"总之"、"综上所述"、"值得一提"禁用）
3. 冲突就狠狠劝退 + 指出致命雷点；契合就给出致命推坑理由
4. 字数严格控制在 30~50 字之间
5. 每一条都要用不同的比喻和切入角度，避免套路化的陈词滥调。禁止重复使用"影院睡着"、"摔手柄"、"翻不过 30 页"、"塞满棉花"这类固定短语。用户的品味是独一无二的，你的点评也必须是。

【输出格式】
严格 JSON，不要 markdown 代码块：
{"roast": "你的点评"}
"""


def _build_user_prompt(
    text: str,
    domain: str,
    item_tag_names: list[str],
    user_top_tag_names: list[str],
) -> str:
    item_tags_str = "、".join(item_tag_names) if item_tag_names else "暂无"
    user_tags_str = "、".join(user_top_tag_names) if user_top_tag_names else "暂无（新用户）"
    return (
        f"【物品 ({domain})】：{text}\n"
        f"【物品的 vibe 标签】：{item_tags_str}\n"
        f"【该用户当前的主导审美】：{user_tags_str}\n\n"
        f"请开始你的毒舌鉴定。"
    )


async def _default_llm_call(system_prompt: str, user_prompt: str) -> str:
    """DeepSeek-compatible chat completion. Replaceable in tests."""
    url = f"{settings.llm_base_url}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.9,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def generate_roast(
    text: str,
    domain: str,
    item_tag_names: list[str],
    user_top_tag_names: list[str],
    llm_call: LlmCallable | None = None,
) -> str:
    """Generate a 30-50 char roast. Returns empty string on ANY failure.

    The caller (vibe/analyze router) must never fail because of a roaster failure —
    this function swallows all exceptions and parse errors and returns "" so the
    frontend can fall back to displaying `summary` as primary copy.
    """
    llm_call = llm_call or _default_llm_call
    user_prompt = _build_user_prompt(text, domain, item_tag_names, user_top_tag_names)

    try:
        raw = await llm_call(SYSTEM_PROMPT, user_prompt)
    except Exception:
        return ""

    try:
        parsed = json.loads(raw)
        roast = parsed.get("roast", "")
        if not isinstance(roast, str):
            return ""
        return roast
    except json.JSONDecodeError:
        return ""
