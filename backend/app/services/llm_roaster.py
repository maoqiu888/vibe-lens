import json
from typing import Awaitable, Callable

import httpx

from app.config import settings

LlmCallable = Callable[[str, str], Awaitable[str]]

SYSTEM_PROMPT = """你是用户最挑剔的那个朋友。你知道他的审美、他最近在看什么、他的偏执在哪。现在他在网上划了一段话给你看，问你：这东西值不值他花时间。

你要像深夜在微信上随手回他一样说话——口语、直接、带情绪、偶尔跑题，但每一句都言之有物。把他当人，不要当"用户"。

【核心要求】
1. 只基于他划的**原文**去感受。你对他的品味的印象是自由形式的大白话，**用你自己的话去体会它，不要整段复述**
2. **引用他原文里的具体词句**，用引号括起来加你的反应。比如「你标这个'慢得像蜗牛'——懂」
3. **朋友视角**：用"你"、"你这人"、"以你的脾气"、"你这种"，禁止出现"用户"两个字
4. **语气自适应**——
   - 契合 → 激动推坑，甚至略夸张
   - 中间 → 犹豫分析，指出风险点
   - 不符 → 直接劝退，哪里硬伤讲哪里
5. **结尾给明确判断**：追 / 看心情 / 跳过（三选一）
6. 字数 40~80 字

【绝对禁止】
- AI 腔调：总之、综上所述、值得一提、不难看出、综合分析
- 叙述结构：不要"首先...其次...最后..."
- 套路比喻：影院睡着、摔手柄、翻不过 30 页、塞满棉花
- **任何形式的结构化标签词汇**（比如"治愈系"、"烧脑向"、"轻度思考"这类像标签的名词短语）——你只描述感觉，不贴标签

【几个示例让你找感觉】

示例 1 — 严重不符，直接劝退：
原文："这是一部极度缓慢的心理惊悚片，充满象征意味"
他的品味印象：节奏越快越好；喜欢放松不费脑的东西；爱看发生在日常生活里的故事
回复：{"roast": "你这人坐地铁都嫌两站之间慢，还去看'极度缓慢的心理惊悚'？开玩笑。你标的'缓慢'两个字就是你的死穴，看到一半你会关掉去刷短视频。跳过。"}

示例 2 — 完美契合，激动推坑：
原文："赛博朋克 2077 的夜之城霓虹燃烧但灵魂冰冷"
他的品味印象：就吃机械科幻的冷光调；重度压抑氛围爱好者
回复：{"roast": "你划的'霓虹燃烧但灵魂冰冷'就是为你这种人写的，别犹豫。找个周末把手机关了进去耗一晚上——这种氛围你不沉进去就浪费。追。"}

示例 3 — 部分契合，犹豫分析：
原文："这部片子平淡如水，像生活本身"
他的品味印象：喜欢发生在日常生活里的故事；同时也爱动脑解谜
回复：{"roast": "'平淡如水'这部分你会吃，可'像生活本身'那种松散你耐不耐得住就不好说了——你是那种看着看着会点开其他 tab 的人。看心情，最好下雨天躺着看。"}

示例 4 — 原文根本不是可鉴定的作品（梗/玩笑/碎片）：
原文："我老婆最喜欢的电影"
回复：{"roast": "这不是一部电影，这是你朋友发的玩笑吧？真想找东西看就划个具体的名字给我。跳过。"}

注意上面 4 个示例的【他的品味印象】都是自由形式的自然语言描述——你看到的印象就是这个样子，**不要把它逐字复读**，用你自己的话去消化它。

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


def _match_level_hint(match_score: int) -> str:
    """Convert a 0-100 match score to a fuzzy level hint for the LLM."""
    if match_score >= 75:
        return "非常契合（很可能是他的菜）"
    if match_score >= 55:
        return "还可以（部分契合，有风险点）"
    if match_score >= 30:
        return "勉强（多处不符，但有个别亮点）"
    return "严重不符（这东西和他八字不合）"


def _build_user_prompt(
    text: str,
    domain: str,
    match_score: int,
    user_taste_hint: str,
) -> str:
    domain_label = _DOMAIN_LABEL.get(domain, domain)
    taste_line = user_taste_hint.strip() if user_taste_hint.strip() else "新朋友，还不太了解他的品味"
    level = _match_level_hint(match_score)
    return (
        f"【他划到的原文】：\n{text}\n\n"
        f"【这是什么类型】：{domain_label}\n"
        f"【你对他品味的印象】：{taste_line}\n"
        f"【你心里大致的契合感】：{level}\n\n"
        f"用朋友的语气给他建议。记得引用原文里的具体词句，别复述你对他的印象。"
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
    match_score: int,
    user_taste_hint: str,
    llm_call: LlmCallable | None = None,
) -> str:
    """Generate a friend-voice take. Returns empty string on ANY failure.

    IMPORTANT: This function does NOT accept tag names. Tag vocabulary is
    intentionally kept away from the LLM's input so it can't parrot them
    into the output. `user_taste_hint` is a natural-language description
    (built from VibeTag.description, not .name) that the LLM paraphrases.

    `match_score` (0-100) becomes a fuzzy level hint so the LLM knows
    whether to enthuse, hesitate, or warn off.
    """
    llm_call = llm_call or _default_llm_call
    user_prompt = _build_user_prompt(text, domain, match_score, user_taste_hint)

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
