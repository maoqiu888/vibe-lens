from typing import Literal

from pydantic import BaseModel, Field

Domain = Literal["book", "movie", "game", "music"]


class RecommendRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    source_domain: Domain
    matched_tag_ids: list[int] = Field(min_length=1, max_length=10)


class RecommendItem(BaseModel):
    domain: Domain
    name: str
    reason: str


class RecommendResponse(BaseModel):
    items: list[RecommendItem]
