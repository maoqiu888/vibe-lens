from pydantic import BaseModel, Field


class CardOption(BaseModel):
    tag_id: int
    name: str
    tier: int
    tagline: str
    examples: list[str]


class CategoryCard(BaseModel):
    category: str
    category_label: str
    options: list[CardOption]


class ColdStartCardsResponse(BaseModel):
    cards: list[CategoryCard]


class ColdStartSubmitRequest(BaseModel):
    selected_tag_ids: list[int] = Field(min_length=6, max_length=6)


class ColdStartSubmitResponse(BaseModel):
    status: str
    profile_initialized: bool
    already_initialized: bool = False
