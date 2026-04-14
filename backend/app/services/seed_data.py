"""
Static seed data: 24 Vibe tags (6 categories × 4 tiers) and the 18
cold-start cards. All data written by hand; do not generate programmatically
so edits are greppable.
"""

# (category, tier, id, name, description)
TAGS = [
    ("pace", 1, 1,  "慢炖沉浸",   "节奏极慢，像咖啡馆读一下午般从容铺陈"),
    ("pace", 2, 2,  "张弛有度",   "节奏有呼吸感，快慢交替不让人疲惫"),
    ("pace", 3, 3,  "紧凑推进",   "节奏密，信息量大，几乎没有留白"),
    ("pace", 4, 4,  "爆裂快切",   "节奏爆炸，快切刺激停不下来"),

    ("mood", 1, 5,  "治愈温暖",   "整体暖色调，给人抚慰感"),
    ("mood", 2, 6,  "明亮轻快",   "基调愉悦，情绪轻盈"),
    ("mood", 3, 7,  "忧郁内省",   "底色偏冷，带着沉思和怅然"),
    ("mood", 4, 8,  "黑暗压抑",   "基调阴冷沉重，压得人喘不过气"),

    ("cognition", 1, 9,  "放空友好", "完全不费脑，可以边吃饭边享用"),
    ("cognition", 2, 10, "轻度思考", "有一点点挑战但不烧脑"),
    ("cognition", 3, 11, "烧脑解谜", "需要主动推理，有解谜乐趣"),
    ("cognition", 4, 12, "认知挑战", "抽象度高，需要反复咀嚼"),

    ("narrative", 1, 13, "白描克制", "文笔/镜头克制，点到即止"),
    ("narrative", 2, 14, "细腻抒情", "注重情感与细节的层层展开"),
    ("narrative", 3, 15, "奇观堆砌", "大量视觉/想象奇观，重感官冲击"),
    ("narrative", 4, 16, "解构实验", "叙事结构非常规，带有实验色彩"),

    ("world", 1, 17, "日常烟火", "日常生活场景为底色"),
    ("world", 2, 18, "奇幻异想", "架空奇幻或魔法设定"),
    ("world", 3, 19, "赛博机械", "赛博朋克/机械科幻调性"),
    ("world", 4, 20, "历史厚重", "有真实历史/年代的厚重感"),

    ("intensity", 1, 21, "轻食小品", "情感投入成本极低，像零食"),
    ("intensity", 2, 22, "有共鸣",   "情感适度，能引发共鸣"),
    ("intensity", 3, 23, "情感重击", "情感浓度高，会被打动甚至流泪"),
    ("intensity", 4, 24, "灵魂灼烧", "情感极致，会在心里留下烙印"),
]

CATEGORY_LABELS = {
    "pace": "节奏",
    "mood": "情绪色调",
    "cognition": "智力负载",
    "narrative": "叙事质感",
    "world": "世界感",
    "intensity": "情感浓度",
}

# Taglines and example works for cold-start cards (keyed by tag_id)
CARD_META = {
    1:  {"tagline": "像在咖啡馆读一下午",   "examples": ["《小森林》", "《海街日记》"]},
    2:  {"tagline": "快慢交替的呼吸感",     "examples": ["《请回答1988》", "《这个杀手不太冷》"]},
    3:  {"tagline": "信息密到不敢眨眼",     "examples": ["《权力的游戏》", "《三体》"]},
    4:  {"tagline": "心跳过载的爽感",       "examples": ["《疾速追杀》", "《DOOM》"]},

    5:  {"tagline": "被整个世界温柔相待",   "examples": ["《夏目友人帐》", "《星露谷物语》"]},
    6:  {"tagline": "阳光洒在脸上的轻快",   "examples": ["《歌舞青春》", "《动物森友会》"]},
    7:  {"tagline": "一个人靠窗发呆的下午", "examples": ["《海边的卡夫卡》", "《Celeste》"]},
    8:  {"tagline": "吞人的黑暗与寒意",     "examples": ["《沉默的羔羊》", "《血源诅咒》"]},

    9:  {"tagline": "脑子完全下班",         "examples": ["《吃豆人》", "综艺快乐大本营"]},
    10: {"tagline": "微微动脑但不累",       "examples": ["《纪念碑谷》"]},
    11: {"tagline": "我要亲手拼出真相",     "examples": ["《锈湖》", "《控制》"]},
    12: {"tagline": "烧脑到怀疑人生",       "examples": ["《盗梦空间》", "《芬奇堡密室》"]},

    13: {"tagline": "一个字多写都是罪",     "examples": ["海明威短篇", "《东京物语》"]},
    14: {"tagline": "情绪在细节里爬行",     "examples": ["《包法利夫人》", "《请以你的名字呼唤我》"]},
    15: {"tagline": "每一帧都在炸你眼球",   "examples": ["《沙丘》", "《赛博朋克2077》"]},
    16: {"tagline": "叙事像迷宫一样拆开",   "examples": ["《记忆碎片》", "《2666》"]},

    17: {"tagline": "柴米油盐也能写出诗",   "examples": ["《请回答1988》", "《人生复本》"]},
    18: {"tagline": "魔法与神话的异想",     "examples": ["《哈利波特》", "《塞尔达：旷野之息》"]},
    19: {"tagline": "霓虹与机械的冷光",     "examples": ["《攻壳机动队》", "《赛博朋克2077》"]},
    20: {"tagline": "厚重历史的重量",       "examples": ["《活着》", "《刺客信条2》"]},

    21: {"tagline": "像一颗糖心情就甜",     "examples": ["《萌宠成长记》"]},
    22: {"tagline": "偶尔会在心里点头",     "examples": ["《请回答1988》"]},
    23: {"tagline": "会被狠狠击中一次",     "examples": ["《你的名字》", "《最后生还者》"]},
    24: {"tagline": "灼伤灵魂的那种",       "examples": ["《入殓师》", "《蔚蓝》"]},
}


def compute_opposite(tag_id: int) -> int:
    """Within a category: tier 1↔4, tier 2↔3."""
    for cat, tier, tid, _, _ in TAGS:
        if tid == tag_id:
            target_tier = {1: 4, 2: 3, 3: 2, 4: 1}[tier]
            for c2, t2, tid2, _, _ in TAGS:
                if c2 == cat and t2 == target_tier:
                    return tid2
    raise ValueError(f"tag_id {tag_id} not found")
