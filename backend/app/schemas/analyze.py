from pydantic import BaseModel, Field


class AnalyzeContext(BaseModel):
    page_title: str | None = None
    page_url: str | None = None


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=2, max_length=500)
    domain: str  # "book" | "game" | "movie" | "music"
    context: AnalyzeContext | None = None


class MatchedTag(BaseModel):
    tag_id: int
    name: str
    weight: float


class AnalyzeResponse(BaseModel):
    match_score: int
    summary: str
    matched_tags: list[MatchedTag]
    text_hash: str
    cache_hit: bool
