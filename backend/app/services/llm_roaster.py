import json
from typing import Awaitable, Callable

import httpx

from app.config import settings

LlmCallable = Callable[[str, str], Awaitable[str]]

SYSTEM_PROMPT = """你是 Vibe-Radar 的"品味分析官"。用户给你一段他在网上选中的文字（通常是某个物品的评论/描述/简介），物品的域（电影/游戏/书/音乐），以及用户当前的审美主导标签。

【核心原则】
1. 用户选中的那段文字是你判断的**主要依据**——仔细读它，从中提取具体细节，不要只看标签就下判断
2. 结合用户的审美画像，判断这个物品对这个**具体用户**是否契合
3. **语气动态切换**，根据匹配质量选择：
   - 完美契合 → 热情安利，带具体的推坑理由
   - 部分契合 → 中立分析，指出亮点和风险
   - 严重不符 → 狠狠劝退，指出致命雷点
   **不要每次都毒舌**——毒舌只适合"用户和物品严重不符"的场景

【必须做的】
1. **引用或指代原文里的具体细节**（比如"你划到的'慢得像蜗牛'这一句"），不要空洞地说"这很黑暗"
2. 用用户的审美画像作为参考系，明确说"你既然是偏 X 的人，那..."
3. 最后给一个明确的**行动建议**：追 / 酌情 / 跳过

【禁止】
- 套路化短语（"影院睡着"、"摔手柄"、"翻不过 30 页"、"塞满棉花"、"吞人的黑暗"）
- AI 腔调（"总之"、"综上所述"、"值得一提"）
- 只复述标签而不引用原文细节
- 无脑毒舌（只在用户和物品严重不符时才用毒舌语气）

【字数】40~80 字之间。

【输出格式】
严格 JSON，不要 markdown 代码块：
{"roast": "你的点评"}
"""


_DOMAIN_LABEL = {
    "book": "书",
    "movie": "电影",
    "game": "游戏",
    "music": "音乐",
}


def _build_user_prompt(
    text: str,
    domain: str,
    item_tag_names: list[str],
    user_top_tag_names: list[str],
) -> str:
    domain_label = _DOMAIN_LABEL.get(domain, domain)
    item_tags_str = "、".join(item_tag_names) if item_tag_names else "暂无"
    user_tags_str = "、".join(user_top_tag_names) if user_top_tag_names else "暂无（新用户）"
    return (
        f"【用户选中的原文】：\n{text}\n\n"
        f"【物品域】：{domain_label}\n"
        f"【从原文识别到的 vibe 标签】：{item_tags_str}\n"
        f"【该用户的审美主导】：{user_tags_str}\n\n"
        f"请基于用户选中的原文内容，结合他的审美画像，给出你的分析和建议。"
        f"记住：要引用原文具体细节，语气根据契合度动态调整，不要永远毒舌。"
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
