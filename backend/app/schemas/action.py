from typing import Literal

from pydantic import BaseModel


class ActionRequest(BaseModel):
    action: Literal["star", "bomb"]
    matched_tag_ids: list[int]
    text_hash: str | None = None
    read_ms: int | None = None
    item_name: str | None = None
    domain: str | None = None
    match_score: int | None = None
    verdict: str | None = None


class ActionResponse(BaseModel):
    status: str
    updated_tags: int
    interaction_count: int
    level: int
    level_title: str
    level_emoji: str
    next_level_at: int
    level_up: bool
