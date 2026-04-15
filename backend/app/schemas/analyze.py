from pydantic import BaseModel, Field


class AnalyzeContext(BaseModel):
    page_title: str | None = None
    page_url: str | None = None


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=2, max_length=500)
    domain: str  # "book" | "game" | "movie" | "music"
    context: AnalyzeContext | None = None
    hesitation_ms: int | None = None


class MatchedTag(BaseModel):
    tag_id: int
    name: str
    weight: float


class AnalyzeResponse(BaseModel):
    match_score: int
    summary: str
    roast: str = ""
    matched_tags: list[MatchedTag]
    text_hash: str
    cache_hit: bool
    interaction_count: int
    level: int
    level_title: str
    level_emoji: str
    next_level_at: int
    level_up: bool
    ui_stage: str
