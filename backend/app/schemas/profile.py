from pydantic import BaseModel


class DominantTag(BaseModel):
    tag_id: int
    name: str


class RadarDimension(BaseModel):
    category: str
    category_label: str
    score: float
    dominant_tag: DominantTag


class RadarResponse(BaseModel):
    user_id: int
    interaction_count: int
    level: int
    level_title: str
    level_emoji: str
    next_level_at: int
    ui_stage: str
    has_personality: bool
    dimensions: list[RadarDimension]
    total_analyze_count: int
    total_action_count: int
