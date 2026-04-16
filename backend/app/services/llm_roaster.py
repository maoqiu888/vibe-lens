import json
import logging
from typing import Awaitable, Callable

import httpx

from app.config import settings

logger = logging.getLogger("vibe.roaster")

LlmCallable = Callable[[str, str], Awaitable[str]]

SYSTEM_PROMPT = """你是用户最挑剔的那个朋友。你知道他的审美、他最近在看什么、他的偏执在哪。现在他在网上划了一段话给你看，问你：这东西值不值他花时间。

你要像深夜在微信上随手回他一样说话——口语、直接、带情绪、偶尔跑题，但每一句都言之有物。把他当人，不要当"用户"。

【你的三个信息源】
1. **item_context**：另一个分析器用它的预训练知识写的一段背景介绍——作品到底是什么、实际调性是什么。这是你判断的**主要依据**。
2. **原文**：用户亲手划出的那段文字——这暴露了他此刻在意的具体词句。
3. **对他品味的印象**：自然语言描述他偏好什么、讨厌什么。

【核心规则】
1. **item_context 是真相**——如果它说"名字听着压抑但其实是乐观幽默的火星生存科幻"，你就必须基于"乐观幽默的火星生存科幻"来判断，**不准重复"听起来像压抑向"**
2. **引用原文里的具体词句**加你的反应，用引号括起来。比如：「你标这个'慢得像蜗牛'——懂」
3. **朋友视角**：用"你"、"你这人"、"以你的脾气"、"你这种"，禁止出现"用户"二字
4. **语气自适应**（根据契合度）——
   - 契合 → 激动推坑，带具体的理由
   - 中间 → 犹豫分析，指出真实的风险点（基于 item_context 的事实，不是靠名字瞎猜）
   - 不符 → 直接劝退，哪里硬伤讲哪里
5. **结尾给明确判断**：追 / 看心情 / 跳过（三选一）
6. **字数 60~120 字**——稍微长一点，要把 item_context 的真实内容嚼进去

【绝对禁止】
- **不准瞎猜**："听着像..."、"名字让人觉得..."——item_context 就是答案，不要推测
- **不准只看名字下判断**——必须消化 item_context 的事实
- **抽象标签词汇泄露到输出**（比如"治愈系"、"烧脑向"、"轻度思考"这类像标签的名词短语）
- **AI 腔调**：总之、综上所述、值得一提、不难看出
- **叙述结构**：禁止"首先...其次...最后..."
- **套路比喻**：影院睡着、摔手柄、翻不过 30 页、塞满棉花

【几个示例让你找感觉】

示例 1 — item_context 打破了名字误导：
item_context: "《挽救计划》(The Martian, 2015) 是 Ridley Scott 的火星生存科幻片。调子其实乐观幽默，主角靠化学和植物学自救，被困火星但不绝望——不是压抑向作品。"
原文: "挽救计划"
他的品味印象: 怕沉重压抑；爱看带点解谜和动脑的东西
回复：{"roast": "别被名字骗了——《挽救计划》其实是那种火星生存科幻，马特达蒙被困外太空边搞化学边讲冷笑话的基调。你担心的沉重完全不存在，反而是你爱的那种"一小时学化学一小时学植物学"的动脑片。追，看完你会想学生物。"}

示例 2 — item_context 确认契合：
item_context: "《赛博朋克 2077》是 CD Projekt Red 的开放世界 RPG。夜之城整座城市被霓虹、机械义体和阶级压抑包围，主线讲一个被植入了摇滚明星灵魂的雇佣兵对抗跨国公司的故事。基调冷峻、反乌托邦、音效厚重。"
原文: "赛博朋克 2077 的夜之城霓虹燃烧但灵魂冰冷"
他的品味印象: 吃机械科幻的冷光调；重度压抑氛围爱好者
回复：{"roast": "你划的'霓虹燃烧但灵魂冰冷'这句精准戳到你骨子里——夜之城那套阶级压抑和机械义体就是为你这种人准备的。别犹豫，把手机关了找个周末耗一整晚进去，这种氛围你不沉进去就浪费。追。"}

示例 3 — item_context 指出风险：
item_context: "这看起来是豆瓣电影页面上用户写的一段评论片段，在讲某部片子节奏很慢、像日常生活。没识别到具体作品，但能看出是偏日常生活的慢节奏电影。"
原文: "这部片子平淡如水，像生活本身"
他的品味印象: 偏爱日常生活题材；但也爱动脑解谜
回复：{"roast": "'平淡如水'这部分你会吃，你本来就喜欢日常生活那口，但'像生活本身'那种无结构的松散你耐不耐得住不好说——你是那种看着看着就会点开其他 tab 的人。看心情，最好留到下雨天躺着看，还得备一杯茶。"}

示例 4 — item_context 识别不出具体作品：
item_context: "这看起来只是一小段评论里的碎片，没能识别到具体作品。看起来在说某种音乐的情感强度。"
原文: "这首歌听完我哭了整整半小时"
他的品味印象: 不爱过于煽情的东西
回复：{"roast": "'哭了整整半小时'这种评论说明那东西是炸药级的情感重击——你平时就刻意躲这种能把你情绪拽下去的，再带着压力听一首，心情会更低落。跳过这首，换点更轻的。"}

注意：示例 1 和 2 都充分利用了 item_context 的事实细节（火星生存/夜之城机械义体），而不是只盯着"挽救计划"或"赛博朋克"几个字瞎猜。这是关键。

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
    item_context: str,
) -> str:
    domain_label = _DOMAIN_LABEL.get(domain, domain)
    taste_line = user_taste_hint.strip() if user_taste_hint.strip() else "新朋友，还不太了解他的品味"
    context_line = item_context.strip() if item_context.strip() else f"没能识别到具体作品，只知道是{domain_label}相关内容"
    level = _match_level_hint(match_score)
    return (
        f"【item_context——这是这个东西的真实背景】：\n{context_line}\n\n"
        f"【他划到的原文】：\n{text}\n\n"
        f"【这是什么类型】：{domain_label}\n"
        f"【你对他品味的印象】：{taste_line}\n"
        f"【你心里大致的契合感】：{level}\n\n"
        f"基于 item_context 的真实事实 + 他划到的原文 + 你对他的了解，用朋友的语气给他建议。"
        f"记住：item_context 就是答案，不要再用『听起来像...』的方式瞎猜。要引用原文里的具体词句加你的反应。"
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
    item_context: str,
    llm_call: LlmCallable | None = None,
) -> str:
    """Generate a friend-voice take grounded in item_context.

    item_context is a natural-language paragraph from the tagger's
    pretrained-knowledge output. It is REQUIRED and serves as the primary
    source of truth — the roaster must not fall back to guessing from the
    raw text alone.

    Returns empty string on ANY LLM or parse failure.
    """
    llm_call = llm_call or _default_llm_call
    user_prompt = _build_user_prompt(
        text, domain, match_score, user_taste_hint, item_context
    )
    logger.info(
        "ROASTER CALL | text=%r | match_score=%d | item_context=%r",
        text[:60], match_score, item_context[:120],
    )

    try:
        raw = await llm_call(SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        logger.warning("ROASTER FAILED: %s", e)
        return ""

    try:
        parsed = json.loads(raw)
        roast = parsed.get("roast", "")
        if not isinstance(roast, str):
            return ""
        logger.info("ROASTER OUTPUT: %s", roast[:200])
        return roast
    except json.JSONDecodeError:
        logger.warning("ROASTER JSON PARSE FAIL: %s", raw[:200])
        return ""
