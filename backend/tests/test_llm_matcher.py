import json

import pytest

from app.services import llm_matcher


class FakeLLM:
    """Matches llm_matcher._default_llm_call signature: (system_prompt, user_prompt) -> str."""

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
    """Agent 2 returns final_score, 3 reasons, and verdict."""
    fake = FakeLLM(response=json.dumps({
        "adjustment": 8,
        "reasons": [
            "赛博朋克的冷峻调性和你的科幻偏好高度吻合",
            "开放世界 RPG 节奏偏慢，你可能中途失去耐心",
            "整体而言这部作品的氛围非常适合你的审美",
        ],
        "verdict": "追",
    }))
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=60,
        user_personality_summary="这个朋友偏好机械科幻和冷光调",
        user_top_tag_descriptions=["喜欢赛博机械美学", "偏好黑暗压抑氛围"],
        llm_call=fake,
    )
    assert result["final_score"] == 68  # 60 + 8
    assert len(result["reasons"]) == 3
    assert result["verdict"] == "追"
    assert fake.calls == 1


async def test_score_clamping_adjustment_too_large():
    """Adjustment > +15 is clamped to +15."""
    fake = FakeLLM(response=json.dumps({
        "adjustment": 30,
        "reasons": ["a", "b", "c"],
        "verdict": "追",
    }))
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=90,
        user_personality_summary="x",
        user_top_tag_descriptions=[],
        llm_call=fake,
    )
    # adjustment clamped to +15, then final 90+15=105 clamped to 100
    assert result["final_score"] == 100


async def test_score_clamping_adjustment_too_negative():
    """Adjustment < -15 is clamped to -15."""
    fake = FakeLLM(response=json.dumps({
        "adjustment": -25,
        "reasons": ["a", "b", "c"],
        "verdict": "跳过",
    }))
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=10,
        user_personality_summary="x",
        user_top_tag_descriptions=[],
        llm_call=fake,
    )
    # adjustment clamped to -15, then 10-15=-5 clamped to 0
    assert result["final_score"] == 0


async def test_exactly_3_reasons_padded_if_fewer():
    """If LLM returns fewer than 3 reasons, pad to 3."""
    fake = FakeLLM(response=json.dumps({
        "adjustment": 0,
        "reasons": ["only one"],
        "verdict": "看心情",
    }))
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=50,
        user_personality_summary="x",
        user_top_tag_descriptions=[],
        llm_call=fake,
    )
    assert len(result["reasons"]) == 3


async def test_verdict_validation_defaults_to_kan_xinqing():
    """Unknown verdict value maps to '看心情'."""
    fake = FakeLLM(response=json.dumps({
        "adjustment": 5,
        "reasons": ["a", "b", "c"],
        "verdict": "随便看看",
    }))
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=50,
        user_personality_summary="x",
        user_top_tag_descriptions=[],
        llm_call=fake,
    )
    assert result["verdict"] == "看心情"


async def test_graceful_degradation_on_exception():
    """LLM exception → degraded result with base_score passthrough."""
    fake = FakeLLM(raise_exc=RuntimeError("timeout"))
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=65,
        user_personality_summary="x",
        user_top_tag_descriptions=[],
        llm_call=fake,
    )
    assert result["final_score"] == 65
    assert result["verdict"] == "看心情"
    assert "匹配分析暂时不可用" in result["reasons"]


async def test_graceful_degradation_on_json_parse_failure():
    """Invalid JSON → degraded result."""
    fake = FakeLLM(response="not json at all")
    result = await llm_matcher.compute_match(
        item_profile=_SAMPLE_PROFILE,
        base_score=42,
        user_personality_summary="x",
        user_top_tag_descriptions=[],
        llm_call=fake,
    )
    assert result["final_score"] == 42
    assert result["verdict"] == "看心情"


async def test_base_score_passthrough_on_degradation():
    """Degraded result always uses base_score as final_score, unmodified."""
    fake = FakeLLM(raise_exc=Exception("any error"))
    for score in [0, 50, 100]:
        result = await llm_matcher.compute_match(
            item_profile=_SAMPLE_PROFILE,
            base_score=score,
            user_personality_summary="x",
            user_top_tag_descriptions=[],
            llm_call=fake,
        )
        assert result["final_score"] == score
