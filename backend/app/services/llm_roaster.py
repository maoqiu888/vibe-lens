import json
from typing import Awaitable, Callable

import httpx

from app.config import settings

LlmCallable = Callable[[str, str], Awaitable[str]]

SYSTEM_PROMPT = """你是用户最挑剔的那个朋友。你知道他的审美、他最近在看什么、他的偏执在哪。现在他在网上划了一段话给你看，问你：这东西值不值他花时间。

你要像深夜在微信上随手回他一样说话——口语、直接、带情绪、偶尔跑题，但每一句都言之有物。把他当人，不要当"用户"。

【核心要求】
1. **只基于他划的原文去感受**，不要思考抽象标签分类。画像只是你脑子里对他的印象，不是论证工具
2. **引用他原文里的具体词句**，用引号括起来加你的反应。比如"你标这个'慢得像蜗牛'——懂"
3. **朋友视角**：用"你"、"你这人"、"以你的脾气"、"你这种"，不准出现"用户"两个字
4. **语气自适应**——
   - 契合 → 激动推坑，甚至略夸张
   - 中间 → 犹豫分析，指出风险点
   - 不符 → 直接劝退，哪里硬伤讲哪里
5. **结尾给明确判断**：追 / 看心情 / 跳过（三选一）
6. 字数 40~80 字

【绝对禁止】
- 抽象标签词汇泄露到输出里：这些词是你脑子里的内部标签，**永远不准出现在回复里**——
  慢炖沉浸、张弛有度、紧凑推进、爆裂快切、治愈温暖、明亮轻快、忧郁内省、黑暗压抑、
  放空友好、轻度思考、烧脑解谜、认知挑战、白描克制、细腻抒情、奇观堆砌、解构实验、
  日常烟火、奇幻异想、赛博机械、历史厚重、轻食小品、有共鸣、情感重击、灵魂灼烧
- AI 腔调：总之、综上所述、值得一提、不难看出、综合分析
- 叙述结构：不要"首先...其次...最后..."
- 套路比喻：影院睡着、摔手柄、翻不过 30 页、塞满棉花、吞人的黑暗

【几个示例让你找感觉】

示例 1 — 严重不符，直接劝退：
划词："这是一部极度缓慢的心理惊悚片，充满象征意味"
朋友脑子里的画像：这人偏快节奏、偏治愈、偏不费脑
回复：{"roast": "你这人坐地铁都嫌两站之间慢，还去看'极度缓慢的心理惊悚'？开玩笑。你标的'缓慢'两个字就是你的死穴，看到一半你会关掉去刷短视频。跳过。"}

示例 2 — 完美契合，激动推坑：
划词："赛博朋克 2077 的夜之城霓虹燃烧但灵魂冰冷"
朋友脑子里的画像：这人就吃这一套机械冷光
回复：{"roast": "你划的'霓虹燃烧但灵魂冰冷'就是为你这种人写的，别犹豫。找个周末把手机关了进去耗一晚上——这种氛围你不沉进去就浪费。追。"}

示例 3 — 部分契合，犹豫分析：
划词："这部片子平淡如水，像生活本身"
朋友脑子里的画像：这人偏日常偏治愈，但同时喜欢烧脑
回复：{"roast": "'平淡如水'这部分你会吃，可'像生活本身'那种松散你耐不耐得住就不好说了——你是那种看着看着会点开其他 tab 的人。看心情，最好下雨天躺着看。"}

示例 4 — 物品是梗或笑话（不是真实作品）：
划词："我老婆最喜欢的电影"
回复：{"roast": "这不是一部电影，这是你朋友发的玩笑吧？真想找东西看就划个具体的名字给我。跳过。"}

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
