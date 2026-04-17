import json

import pytest

from app.services import llm_judge


class FakeLLM:
    def __init__(self, response=None, raise_exc=None):
        self.response = response
        self.raise_exc = raise_exc
        self.calls = 0

    async def __call__(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
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
    fake = FakeLLM(response=json.dumps({
        "adjustment": 8,
        "reasons": ["科幻偏好吻合", "节奏偏慢有风险", "整体适合你的审美"],
        "verdict": "追",
        "roast": "夜之城简直为你量身打造，值得追，68%",
    }))
    result = await llm_judge.judge(
        text="赛博朋克 2077", domain="game",
        item_profile=_SAMPLE_PROFILE, base_score=60,
        user_personality_summary="偏好机械科幻和冷光调",
        user_top_tag_descriptions=["喜欢赛博机械美学"],
        llm_call=fake,
    )
    assert result["final_score"] == 68
    assert len(result["reasons"]) == 3
    assert result["verdict"] == "追"
    assert "夜之城" in result["roast"]
    assert fake.calls == 1


async def test_score_clamping_high():
    fake = FakeLLM(response=json.dumps({
        "adjustment": 30, "reasons": ["a", "b", "c"],
        "verdict": "追", "roast": "test",
    }))
    result = await llm_judge.judge(
        text="x", domain="game", item_profile=_SAMPLE_PROFILE,
        base_score=90, user_personality_summary="x",
        user_top_tag_descriptions=[], llm_call=fake,
    )
    assert result["final_score"] == 100


async def test_score_clamping_low():
    fake = FakeLLM(response=json.dumps({
        "adjustment": -25, "reasons": ["a", "b", "c"],
        "verdict": "跳过", "roast": "test",
    }))
    result = await llm_judge.judge(
        text="x", domain="game", item_profile=_SAMPLE_PROFILE,
        base_score=10, user_personality_summary="x",
        user_top_tag_descriptions=[], llm_call=fake,
    )
    assert result["final_score"] == 0


async def test_reasons_padded_if_fewer():
    fake = FakeLLM(response=json.dumps({
        "adjustment": 0, "reasons": ["only one"],
        "verdict": "看心情", "roast": "test",
    }))
    result = await llm_judge.judge(
        text="x", domain="game", item_profile=_SAMPLE_PROFILE,
        base_score=50, user_personality_summary="x",
        user_top_tag_descriptions=[], llm_call=fake,
    )
    assert len(result["reasons"]) == 3


async def test_invalid_verdict_defaults():
    fake = FakeLLM(response=json.dumps({
        "adjustment": 5, "reasons": ["a", "b", "c"],
        "verdict": "随便看看", "roast": "test",
    }))
    result = await llm_judge.judge(
        text="x", domain="game", item_profile=_SAMPLE_PROFILE,
        base_score=50, user_personality_summary="x",
        user_top_tag_descriptions=[], llm_call=fake,
    )
    assert result["verdict"] == "看心情"


async def test_graceful_degradation_on_exception():
    fake = FakeLLM(raise_exc=RuntimeError("timeout"))
    result = await llm_judge.judge(
        text="x", domain="game", item_profile=_SAMPLE_PROFILE,
        base_score=65, user_personality_summary="x",
        user_top_tag_descriptions=[], llm_call=fake,
    )
    assert result["final_score"] == 65
    assert result["verdict"] == "看心情"
    assert result["roast"] == ""
    assert "匹配分析暂时不可用" in result["reasons"]


async def test_graceful_degradation_on_json_failure():
    fake = FakeLLM(response="not json")
    result = await llm_judge.judge(
        text="x", domain="game", item_profile=_SAMPLE_PROFILE,
        base_score=42, user_personality_summary="x",
        user_top_tag_descriptions=[], llm_call=fake,
    )
    assert result["final_score"] == 42
    assert result["roast"] == ""


async def test_missing_roast_returns_empty():
    fake = FakeLLM(response=json.dumps({
        "adjustment": 5, "reasons": ["a", "b", "c"],
        "verdict": "追",
    }))
    result = await llm_judge.judge(
        text="x", domain="game", item_profile=_SAMPLE_PROFILE,
        base_score=50, user_personality_summary="x",
        user_top_tag_descriptions=[], llm_call=fake,
    )
    assert result["roast"] == ""
    assert result["final_score"] == 55


async def test_user_prompt_contains_key_info():
    fake = FakeLLM(response=json.dumps({
        "adjustment": 0, "reasons": ["a", "b", "c"],
        "verdict": "追", "roast": "test",
    }))
    result = await llm_judge.judge(
        text="赛博朋克 2077", domain="game",
        item_profile=_SAMPLE_PROFILE, base_score=60,
        user_personality_summary="深度思考者",
        user_top_tag_descriptions=["喜欢赛博美学"],
        llm_call=fake,
    )
    assert fake.calls == 1
