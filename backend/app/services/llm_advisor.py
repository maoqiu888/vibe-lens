import json
import logging
from typing import Awaitable, Callable

import httpx

from app.config import settings

logger = logging.getLogger("vibe.advisor")

LlmCallable = Callable[[str, str], Awaitable[str]]

SYSTEM_PROMPT = """你是用户最挑剔的那个朋友。你知道他的审美、他最近在看什么、他的偏执在哪。现在他在网上划了一段话给你看，问你：这东西值不值他花时间。

你要像深夜在微信上随手回他一样说话——口语、直接、带情绪、偶尔跑题，但每一句都言之有物。把他当人，不要当"用户"。

【你收到的信息】
1. **item_profile**：识别官已经用预训练知识精确识别了这个作品——名称、类型、剧情、调性全在里面。这是真相，直接用。
2. **匹配分析**：匹配官已经给出了 final_score、3 条理由（匹配点/风险点/综合判断）和 verdict（追/看心情/跳过）。这是你判断的逻辑骨架。
3. **原文**：用户亲手划出的那段文字。
4. **对他品味的印象**：自然语言描述。

【你的唯一任务】
把上面的结构化事实和推理，翻译成一段自然的朋友语气建议。你不需要自己判断——识别官和匹配官已经判断完了，你只负责"怎么说"。

【核心规则】
1. **item_profile 是真相**——引用里面的具体细节（导演、剧情、调性）
2. **reasons 是逻辑骨架**——你的建议要体现这 3 条理由，但用朋友的口吻重新表达
3. **verdict + final_score 是结尾**——结尾给出 verdict 和 final_score%
4. **引用原文里的具体词句**加你的反应
5. **朋友视角**：用"你"、"你这人"、"以你的脾气"，禁止出现"用户"二字
6. **字数 60~120 字**

【绝对禁止】
- 不准瞎猜："听着像..."——item_profile 就是答案
- 抽象标签词汇泄露（"治愈系"、"烧脑向"、"轻度思考"这类标签名）
- AI 腔调：总之、综上所述、值得一提、不难看出
- 叙述结构：禁止"首先...其次...最后..."

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
    item_profile: dict,
    final_score: int,
    reasons: list[str],
    verdict: str,
    user_personality_summary: str,
) -> str:
    domain_label = _DOMAIN_LABEL.get(domain, domain)
    taste_line = user_personality_summary.strip() if user_personality_summary.strip() else "新朋友，还不太了解他的品味"
    profile_json = json.dumps(item_profile, ensure_ascii=False, indent=2)
    reasons_text = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(reasons))
    return (
        f"【item_profile——作品真实信息】\n{profile_json}\n\n"
        f"【匹配分析结果】\n"
        f"  final_score: {final_score}/100\n"
        f"  verdict: {verdict}\n"
        f"  reasons:\n{reasons_text}\n\n"
        f"【他划到的原文】：{text}\n\n"
        f"【这是什么类型】：{domain_label}\n"
        f"【你对他品味的印象】：{taste_line}\n\n"
        f"基于以上所有信息，用朋友语气给他建议。结尾带上 verdict 和 final_score%。"
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
    llm_call = llm_call or _default_llm_call
    user_prompt = _build_user_prompt(
        text, domain, item_profile, final_score,
        reasons, verdict, user_personality_summary,
    )
    logger.info(
        "ADVISOR CALL | text=%r | final_score=%d | verdict=%s",
        text[:60], final_score, verdict,
    )

    try:
        raw = await llm_call(SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.warning("ADVISOR FAILED: %s", e)
        return ""

    try:
        parsed = json.loads(raw)
        roast = parsed.get("roast", "")
        if not isinstance(roast, str):
            return ""
        logger.info("ADVISOR OUTPUT: %s", roast[:200])
        return roast
    except json.JSONDecodeError:
        logger.warning("ADVISOR JSON PARSE FAIL: %s", raw[:200])
        return ""
