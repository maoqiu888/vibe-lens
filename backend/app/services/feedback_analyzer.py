"""Background task: analyze match_feedback entries and adjust user weights.

Run periodically (e.g., every 5 minutes) via:
    python -m app.services.feedback_analyzer

Or called from FastAPI startup as a background task.
"""
import asyncio
import json
import logging

import httpx
from sqlalchemy import select

from app import database
from app.config import settings
from app.models.match_feedback import MatchFeedback
from app.models.vibe_tag import VibeTag
from app.services import profile_calc

logger = logging.getLogger("vibe.feedback_analyzer")

BATCH_SIZE = 10

SYSTEM_PROMPT = """你是一个用户画像分析师。你会收到一批用户对内容匹配结果的反馈数据。

每条反馈包含：
- item_name：作品名
- domain：类型（电影/书/游戏/音乐）
- match_score：系统给的匹配分
- verdict：系统给的结论（追/看心情/跳过）
- feedback：用户反馈（accurate=太准了 / inaccurate=差点意思）
- matched_tag_ids：匹配到的标签 ID

你的任务是分析这批反馈，输出权重调整建议：
- 如果用户说"太准了"→ 相关标签的权重应该加强
- 如果用户说"差点意思"→ 需要分析是哪些标签权重偏高或偏低

输出格式（严格 JSON）：
{"adjustments": [{"tag_id": 1, "delta": 2.0}, {"tag_id": 5, "delta": -1.5}]}

delta 范围 [-5.0, +5.0]。只输出需要调整的标签。如果没有明确的调整依据，输出空列表。
"""


def _build_feedback_prompt(feedbacks: list[dict], tag_names: dict[int, str]) -> str:
    lines = []
    for fb in feedbacks:
        tag_ids = [int(x) for x in fb["matched_tag_ids"].split(",") if x.strip()]
        tag_list = ", ".join(tag_names.get(tid, f"#{tid}") for tid in tag_ids)
        lines.append(
            f"- {fb['item_name']}({fb['domain']}) | 分数{fb['match_score']} "
            f"| 结论:{fb['verdict']} | 用户:{fb['feedback']} | 标签:[{tag_list}]"
        )
    return "【反馈数据】\n" + "\n".join(lines)


async def _llm_analyze(prompt: str) -> dict:
    url = f"{settings.llm_base_url}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])


async def process_pending_feedback():
    """Process unanalyzed feedback entries in batches."""
    db = database.SessionLocal()
    try:
        pending = db.scalars(
            select(MatchFeedback)
            .where(MatchFeedback.analyzed == False)  # noqa: E712
            .order_by(MatchFeedback.created_at)
            .limit(BATCH_SIZE)
        ).all()

        if not pending:
            logger.info("FEEDBACK ANALYZER | no pending feedback")
            return 0

        tags = db.scalars(select(VibeTag)).all()
        tag_names = {t.id: t.name for t in tags}

        user_groups: dict[int, list] = {}
        for fb in pending:
            user_groups.setdefault(fb.user_id, []).append(fb)

        total_adjustments = 0
        for user_id, fbs in user_groups.items():
            fb_dicts = [
                {
                    "item_name": fb.item_name,
                    "domain": fb.domain,
                    "match_score": fb.match_score,
                    "verdict": fb.verdict,
                    "feedback": fb.feedback,
                    "matched_tag_ids": fb.matched_tag_ids,
                }
                for fb in fbs
            ]

            try:
                prompt = _build_feedback_prompt(fb_dicts, tag_names)
                result = await _llm_analyze(prompt)
                adjustments = result.get("adjustments", [])

                for adj in adjustments:
                    tag_id = adj.get("tag_id")
                    delta = adj.get("delta", 0)
                    if not isinstance(tag_id, int) or not (1 <= tag_id <= 24):
                        continue
                    delta = max(-5.0, min(5.0, float(delta)))
                    if abs(delta) < 0.1:
                        continue
                    profile_calc.apply_core_delta(
                        user_id=user_id,
                        tag_ids=[tag_id],
                        delta=delta,
                        action="feedback_adjust",
                    )
                    total_adjustments += 1

                logger.info(
                    "FEEDBACK ANALYZER | user=%d | %d feedbacks → %d adjustments",
                    user_id, len(fbs), len(adjustments),
                )
            except Exception as e:
                logger.warning("FEEDBACK ANALYZER FAILED for user %d: %s", user_id, e)

            for fb in fbs:
                fb.analyzed = True
            db.commit()

        return total_adjustments
    finally:
        db.close()


async def run():
    count = await process_pending_feedback()
    print(f"Processed feedback, {count} weight adjustments applied")


if __name__ == "__main__":
    asyncio.run(run())
