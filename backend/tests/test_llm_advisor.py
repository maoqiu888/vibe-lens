import json

import pytest

from app.services import llm_advisor


class FakeLLM:
    """Matches llm_advisor._default_llm_call signature: (system_prompt, user_prompt) -> str."""

    def __init__(self, response=None, raise_exc=None):
        self.response = response
        self.raise_exc = raise_exc
        self.calls = 0
        self.last_system = None
        self.last_user = None

    async def __call__(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        self.last_system = system_prompt
        self.last_user = user_prompt
        if self.raise_exc:
            raise self.raise_exc
        return self.response


_SAMPLE_PROFILE = {
    "item_name": "《赛博朋克 2077》",
    "item_name_alt": "Cyberpunk 2077",
    "year": 2020,
    "creator": "CD Projekt Red",
    "genre": "开放世界 RPG",
    "plot_gist": "夜之城里一个雇佣兵对抗跨国公司。",
    "tone": "冷峻、反乌托邦",
    "name_vs_reality": "",
    "confidence": "high",
}


async def test_happy_path():
    """Agent 3 returns a non-empty friend-voice recommendation."""
    fake = FakeLLM(response=json.dumps({
        "roast": "夜之城那套冷峻反乌托邦简直为你量身打造，找个周末一口气沉进去，追。68%",
    }))
    result = await llm_advisor.advise(
        text="赛博朋克 2077",
        domain="game",
        item_profile=_SAMPLE_PROFILE,
        final_score=68,
        reasons=["科幻偏好吻合", "节奏偏慢有风险", "整体适合你的审美"],
        verdict="追",
        user_personality_summary="偏好机械科幻和冷光调",
        llm_call=fake,
    )
    assert isinstance(result, str)
    assert len(result) > 0
    assert fake.calls == 1


async def test_prompt_contains_item_profile_facts():
    """The user prompt must include item_profile details for grounded output."""
    fake = FakeLLM(response=json.dumps({"roast": "test"}))
    await llm_advisor.advise(
        text="赛博朋克 2077",
        domain="game",
        item_profile=_SAMPLE_PROFILE,
        final_score=68,
        reasons=["r1", "r2", "r3"],
        verdict="追",
        user_personality_summary="x",
        llm_call=fake,
    )
    p = fake.last_user
    assert "赛博朋克 2077" in p or "《赛博朋克 2077》" in p
    assert "CD Projekt Red" in p
    assert "夜之城" in p


async def test_prompt_contains_reasons_and_verdict():
    """Reasons and verdict from Agent 2 must be in the prompt."""
    fake = FakeLLM(response=json.dumps({"roast": "test"}))
    await llm_advisor.advise(
        text="x",
        domain="game",
        item_profile=_SAMPLE_PROFILE,
        final_score=68,
        reasons=["科幻偏好吻合", "节奏偏慢有风险", "整体适合你的审美"],
        verdict="追",
        user_personality_summary="x",
        llm_call=fake,
    )
    p = fake.last_user
    assert "科幻偏好吻合" in p
    assert "节奏偏慢有风险" in p
    assert "追" in p


async def test_prompt_contains_user_personality():
    """User personality summary must appear in the prompt."""
    fake = FakeLLM(response=json.dumps({"roast": "test"}))
    await llm_advisor.advise(
        text="x",
        domain="game",
        item_profile=_SAMPLE_PROFILE,
        final_score=68,
        reasons=["r1", "r2", "r3"],
        verdict="追",
        user_personality_summary="这个人偏好深度思考和独处",
        llm_call=fake,
    )
    assert "深度思考" in fake.last_user


async def test_failure_returns_empty_string():
    """Any LLM exception -> return ''."""
    fake = FakeLLM(raise_exc=RuntimeError("timeout"))
    result = await llm_advisor.advise(
        text="x",
        domain="game",
        item_profile=_SAMPLE_PROFILE,
        final_score=68,
        reasons=["r1", "r2", "r3"],
        verdict="追",
        user_personality_summary="x",
        llm_call=fake,
    )
    assert result == ""


async def test_missing_roast_field_returns_empty_string():
    """JSON without 'roast' key -> return ''."""
    fake = FakeLLM(response=json.dumps({"other": "x"}))
    result = await llm_advisor.advise(
        text="x",
        domain="game",
        item_profile=_SAMPLE_PROFILE,
        final_score=68,
        reasons=["r1", "r2", "r3"],
        verdict="追",
        user_personality_summary="x",
        llm_call=fake,
    )
    assert result == ""
