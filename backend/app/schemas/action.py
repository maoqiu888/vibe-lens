from typing import Literal

from pydantic import BaseModel


class ActionRequest(BaseModel):
    action: Literal["star", "bomb"]
    matched_tag_ids: list[int]
    text_hash: str | None = None


class ActionResponse(BaseModel):
    status: str
    updated_tags: int
