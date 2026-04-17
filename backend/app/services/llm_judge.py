import json
import logging
import re
from typing import Awaitable, Callable

import httpx

from app.services.llm_config_reader import get_llm_settings

logger = logging.getLogger("vibe.judge")

LlmCallable = Callable[[str, str], Awaitable[str]]

VALID_VERDICTS = {"追", "看心情", "跳过"}
GENERIC_REASON = "综合来看，可以根据心情决定"

_DOMAIN_LABEL = {"book": "书", "movie": "电影", "game": "游戏", "music": "音乐"}

SYSTEM_PROMPT = """你身兼两职：**匹配分析官**和用户最挑剔的**朋友**。

你会收到一个作品的结构化信息（item_profile）、数学模型算出的底分、用户的品味画像，以及用户划到的原文。

你要完成两件事，一次性输出：

━━━ 第一职责：匹配分析 ━━━

1. adjustment：在 [-15, +15] 范围内的分数调整值。正数 = 底分偏低了（这人会比数学算的更喜欢），负数 = 底分偏高了。
2. reasons：恰好 3 条理由，每条 15-40 字：
   - 第 1 条：一个**匹配点**（这个作品哪里契合用户）
   - 第 2 条：一个**风险点**（哪里可能不合）
   - 第 3 条：一个**综合判断**
3. verdict：三选一："追" / "看心情" / "跳过"

【分析要点】
- 底分偏低不代表一定差（可能标签信号不足）
- 底分偏高不代表完美（可能有性格层面的隐含冲突）

━━━ 第二职责：朋友点评 ━━━

基于你刚才的分析，用朋友口吻写一段 60-120 字的建议。

【朋友语气规则】
- 像深夜微信随手回复——口语、直接、带情绪
- 引用 item_profile 里的具体细节（导演、剧情、调性）
- 体现你刚才分析的 3 条理由，但用朋友口吻重新表达
- 结尾自然收束，用中文说结论和分数
- 禁止出现"用户"二字

【多样性——最重要的规则】
每次点评必须用**完全不同的开头、句式和节奏**。以下是几种风格示例（仅参考，不要照搬）：
- 直接从作品切入："《XXX》这片子……"
- 反问开场："你确定你能坐得住这种片？"
- 感叹开场："嘿，这个有意思。"
- 调侃开场："又来了，你总挑这种……"
- 场景代入："想象一下你周末窝沙发上看这个——"

禁止每次都用"你这人"开头。禁止每次都出现"以你的脾气"。这两个短语**最多三次点评出现一次**。

【绝对禁止】
- "听着像..."——item_profile 就是答案，不准瞎猜
- 标签词汇泄露："治愈系"、"烧脑向"、"轻度思考"等内部标签名
- AI 腔调：总之、综上所述、值得一提、不难看出
- 叙述结构："首先...其次...最后..."
- 英文字段名：verdict、final_score、adjustment、reasons、item_profile
- 重复套路：禁止连续两次用相同的开头句式或相同的转折词

━━━ 输出格式 ━━━

严格 JSON，不要 markdown 代码块：
{"adjustment": 8, "reasons": ["匹配点...", "风险点...", "综合判断..."], "verdict": "追", "roast": "你的朋友点评"}
"""


def _build_user_prompt(
    text: str,
    domain: str,
    item_profile: dict,
    base_score: int,
    user_personality_summary: str,
    user_top_tag_descriptions: list[str],
) -> str:
    domain_label = _DOMAIN_LABEL.get(domain, domain)
    desc_text = "；".join(user_top_tag_descriptions) if user_top_tag_descriptions else "暂无品味标签"
    taste_line = user_personality_summary.strip() if user_personality_summary.strip() else "新朋友，还不太了解他的品味"
    profile_json = json.dumps(item_profile, ensure_ascii=False, indent=2)
    return (
        f"【作品信息】\n{profile_json}\n\n"
        f"【类型】{domain_label}\n"
        f"【数学底分】{base_score}/100\n\n"
        f"【用户性格摘要】{taste_line}\n"
        f"【用户品味标签描述】{desc_text}\n\n"
        f"【他划到的原文】{text}\n\n"
        f"请同时输出 adjustment、reasons、verdict 和 roast。"
    )


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _degraded_result(base_score: int) -> dict:
    return {
        "final_score": base_score,
        "reasons": ["匹配分析暂时不可用"],
        "verdict": "看心情",
        "roast": "",
    }


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
        "temperature": 0.7,
    }
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    async with httpx.AsyncClient(timeout=12.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def judge(
    text: str,
    domain: str,
    item_profile: dict,
    base_score: int,
    user_personality_summary: str,
    user_top_tag_descriptions: list[str],
    llm_call: LlmCallable | None = None,
) -> dict:
    """Single LLM call that combines matching + friend-voice advice.

    Returns {final_score, reasons, verdict, roast}.
    On any failure, returns degraded result with base_score passthrough.
    """
    llm_call = llm_call or _default_llm_call
    user_prompt = _build_user_prompt(
        text, domain, item_profile, base_score,
        user_personality_summary, user_top_tag_descriptions,
    )
    logger.info(
        "JUDGE CALL | item=%s | base_score=%d",
        item_profile.get("item_name", "?")[:40], base_score,
    )

    try:
        raw = await llm_call(SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.warning("JUDGE FAILED: %s", e)
        return _degraded_result(base_score)

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("JUDGE JSON PARSE FAIL: %s", e)
        return _degraded_result(base_score)

    # --- Match analysis ---
    try:
        adjustment = int(parsed.get("adjustment", 0))
    except (TypeError, ValueError):
        adjustment = 0
    adjustment = _clamp(adjustment, -15, 15)
    final_score = _clamp(base_score + adjustment, 0, 100)

    reasons = parsed.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = []
    reasons = [str(r) for r in reasons]
    while len(reasons) < 3:
        reasons.append(GENERIC_REASON)
    reasons = reasons[:3]

    verdict = parsed.get("verdict", "看心情")
    if verdict not in VALID_VERDICTS:
        verdict = "看心情"

    # --- Friend-voice roast ---
    roast = parsed.get("roast", "")
    if not isinstance(roast, str):
        roast = ""

    # Post-process: replace any wrong score with the actual final_score
    if roast:
        roast = re.sub(r'-?\d{1,3}%', f'{final_score}%', roast)
        roast = re.sub(r'分数?-?\d{1,3}分', f'{final_score}分', roast)

    logger.info(
        "JUDGE OUTPUT | final=%d | verdict=%s | roast=%s",
        final_score, verdict, roast[:80],
    )

    return {
        "final_score": final_score,
        "reasons": reasons,
        "verdict": verdict,
        "roast": roast,
    }
