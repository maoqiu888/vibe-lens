from pydantic import BaseModel, Field, field_validator

# Canonical 12 Chinese constellation names
VALID_CONSTELLATIONS = {
    "白羊座", "金牛座", "双子座", "巨蟹座",
    "狮子座", "处女座", "天秤座", "天蝎座",
    "射手座", "摩羯座", "水瓶座", "双鱼座",
}


class PersonalityRequest(BaseModel):
    mbti: str | None = Field(default=None, max_length=4)
    constellation: str | None = Field(default=None, max_length=16)

    @field_validator("mbti")
    @classmethod
    def _validate_mbti(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip().upper()
        if len(v) != 4:
            raise ValueError("MBTI must be exactly 4 letters")
        pairs = [(v[0], "IE"), (v[1], "NS"), (v[2], "TF"), (v[3], "PJ")]
        for letter, allowed in pairs:
            if letter not in allowed:
                raise ValueError(f"invalid MBTI letter at position: {letter}")
        return v

    @field_validator("constellation")
    @classmethod
    def _validate_constellation(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if v not in VALID_CONSTELLATIONS:
            raise ValueError("constellation must be one of the 12 canonical names")
        return v


class PersonalityResponse(BaseModel):
    status: str
    seeded_tag_count: int
    summary: str
