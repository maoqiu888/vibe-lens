import json
import logging
from typing import Awaitable, Callable

import httpx

from app.config import settings

logger = logging.getLogger("vibe.matcher")

LlmCallable = Callable[[str, str], Awaitable[str]]

VALID_VERDICTS = {"追", "看心情", "跳过"}

SYSTEM_PROMPT = """你是一个匹配分析官。你的工作是判断一个内容作品和用户之间的契合度。

你会收到：
1. item_profile：作品的结构化信息（名称、类型、剧情、调性等）
2. base_score：数学模型算出的底分（0-100）
3. 用户的性格摘要和品味偏好描述

你需要输出：
1. adjustment：在 [-15, +15] 范围内的分数调整值。正数表示你认为底分偏低了（这人会比数学算的更喜欢），负数表示底分偏高了。
2. reasons：恰好 3 条理由，每条 15-40 字：
   - 第 1 条：一个**匹配点**（这个作品哪里契合用户）
   - 第 2 条：一个**风险点**（哪里可能不合）
   - 第 3 条：一个**综合判断**（把前两点合起来给结论）
3. verdict：三选一："追" / "看心情" / "跳过"

【重要】
- 底分偏低不代表一定差（可能用户标签信号不足）
- 底分偏高也不代表完美（可能有性格层面的隐含冲突）
- 你的工作是用理解补数学的缺陷

【输出格式】严格 JSON，不要 markdown 代码块：
{"adjustment": 8, "reasons": ["匹配点...", "风险点...", "综合判断..."], "verdict": "追"}
"""

GENERIC_REASON = "综合来看，可以根据心情决定"


def _build_user_prompt(
    item_profile: dict,
    base_score: int,
    user_personality_summary: str,
    user_top_tag_descriptions: list[str],
) -> str:
    desc_text = "；".join(user_top_tag_descriptions) if user_top_tag_descriptions else "暂无品味标签"
    return (
        f"【作品信息】\n{json.dumps(item_profile, ensure_ascii=False, indent=2)}\n\n"
        f"【数学底分】{base_score}/100\n\n"
        f"【用户性格摘要】{user_personality_summary or '新朋友，还不太了解'}\n\n"
        f"【用户品味标签描述】{desc_text}\n\n"
        f"请输出你的 adjustment、reasons 和 verdict。"
    )


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _degraded_result(base_score: int) -> dict:
    return {
        "final_score": base_score,
        "reasons": ["匹配分析暂时不可用"],
        "verdict": "看心情",
    }


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
        "temperature": 0.3,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def compute_match(
    item_profile: dict,
    base_score: int,
    user_personality_summary: str,
    user_top_tag_descriptions: list[str],
    llm_call: LlmCallable | None = None,
) -> dict:
    """Returns {final_score: int, reasons: list[str], verdict: str}.

    final_score is base_score adjusted by +/-15, clamped to [0, 100].
    reasons is exactly 3 strings.
    verdict is one of "追", "看心情", "跳过".

    On any LLM failure, returns a degraded result:
    {final_score: base_score, reasons: ["匹配分析暂时不可用"], verdict: "看心情"}
    """
    llm_call = llm_call or _default_llm_call
    user_prompt = _build_user_prompt(
        item_profile, base_score,
        user_personality_summary, user_top_tag_descriptions,
    )
    logger.info(
        "MATCHER CALL | item=%s | base_score=%d",
        item_profile.get("item_name", "?")[:40], base_score,
    )

    try:
        raw = await llm_call(SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.warning("MATCHER FAILED: %s", e)
        return _degraded_result(base_score)

    try:
        parsed = json.loads(raw)
        adjustment = int(parsed.get("adjustment", 0))
        reasons = parsed.get("reasons", [])
        verdict = parsed.get("verdict", "看心情")
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning("MATCHER JSON PARSE FAIL: %s", e)
        return _degraded_result(base_score)

    # Clamp adjustment to [-15, +15]
    adjustment = _clamp(adjustment, -15, 15)
    final_score = _clamp(base_score + adjustment, 0, 100)

    # Ensure exactly 3 reasons
    if not isinstance(reasons, list):
        reasons = []
    reasons = [str(r) for r in reasons]
    while len(reasons) < 3:
        reasons.append(GENERIC_REASON)
    reasons = reasons[:3]

    # Validate verdict
    if verdict not in VALID_VERDICTS:
        verdict = "看心情"

    return {
        "final_score": final_score,
        "reasons": reasons,
        "verdict": verdict,
    }
