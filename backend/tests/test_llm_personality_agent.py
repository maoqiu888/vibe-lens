import json

import httpx
import pytest

from app.services import llm_personality_agent
from app.services.seed import seed_all


class FakeLLM:
    def __init__(self, response=None, raise_exc=None):
        self.response = response
        self.raise_exc = raise_exc
        self.calls = 0
        self.last_prompt = None

    async def __call__(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        self.last_prompt = user_prompt
        if self.raise_exc:
            raise self.raise_exc
        return self.response


async def test_both_inputs_happy_path():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [
            {"tag_id": 11, "weight": 15},
            {"tag_id": 12, "weight": 10},
            {"tag_id": 9, "weight": -10},
        ],
        "personality_summary": (
            "这个朋友是典型的深度思考者，逻辑敏锐但情感上其实柔软。"
            "喜欢独处但不排斥有趣的人。看东西偏爱能引发思考的内容。"
        ),
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="INTP",
        constellation="双鱼座",
        llm_call=fake,
    )
    assert fake.calls == 1
    assert "INTP" in fake.last_prompt
    assert "双鱼座" in fake.last_prompt
    assert len(result["tag_seeds"]) == 3
    assert result["tag_seeds"][0] == {"tag_id": 11, "weight": 15.0}
    assert result["personality_summary"].startswith("这个朋友")


async def test_mbti_only_still_works():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [{"tag_id": 1, "weight": 5}],
        "personality_summary": "一个简约派。" * 10,
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="ISTJ",
        constellation=None,
        llm_call=fake,
    )
    assert "ISTJ" in fake.last_prompt
    assert "双鱼座" not in fake.last_prompt
    assert len(result["tag_seeds"]) == 1


async def test_empty_inputs_raise_empty_error():
    with pytest.raises(llm_personality_agent.PersonalityAgentEmptyError):
        await llm_personality_agent.analyze_personality(
            mbti=None,
            constellation=None,
            llm_call=FakeLLM(response="unused"),
        )


async def test_llm_exception_returns_empty_result():
    seed_all()
    fake = FakeLLM(raise_exc=RuntimeError("boom"))
    result = await llm_personality_agent.analyze_personality(
        mbti="ENFP",
        constellation=None,
        llm_call=fake,
    )
    assert result == {"tag_seeds": [], "personality_summary": ""}


async def test_json_parse_failure_returns_empty_result():
    seed_all()
    fake = FakeLLM(response="not valid json")
    result = await llm_personality_agent.analyze_personality(
        mbti="ENFP",
        constellation=None,
        llm_call=fake,
    )
    assert result == {"tag_seeds": [], "personality_summary": ""}


async def test_weight_out_of_range_is_clamped():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [
            {"tag_id": 1, "weight": 30},
            {"tag_id": 2, "weight": -100},
            {"tag_id": 3, "weight": 5},
        ],
        "personality_summary": "这个人喜欢简单的东西。" * 3,
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="ISFJ", constellation=None, llm_call=fake,
    )
    weights = {s["tag_id"]: s["weight"] for s in result["tag_seeds"]}
    assert weights[1] == 15.0
    assert weights[2] == -15.0
    assert weights[3] == 5.0


async def test_more_than_8_seeds_truncated():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [{"tag_id": i, "weight": 5} for i in range(1, 15)],
        "personality_summary": "一个贪心的人。" * 5,
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="ENTP", constellation=None, llm_call=fake,
    )
    assert len(result["tag_seeds"]) == 8


async def test_duplicate_tag_ids_deduped():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [
            {"tag_id": 5, "weight": 10},
            {"tag_id": 5, "weight": -10},
            {"tag_id": 6, "weight": 8},
        ],
        "personality_summary": "这个人比较简单。" * 4,
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="ISFP", constellation=None, llm_call=fake,
    )
    ids = [s["tag_id"] for s in result["tag_seeds"]]
    assert ids.count(5) == 1
    assert 6 in ids
    first_five = next(s for s in result["tag_seeds"] if s["tag_id"] == 5)
    assert first_five["weight"] == 10.0


async def test_invalid_tag_id_dropped():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [
            {"tag_id": 100, "weight": 15},
            {"tag_id": 0, "weight": 10},
            {"tag_id": 15, "weight": 8},
        ],
        "personality_summary": "这个人偏好奇观。" * 4,
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="ESFP", constellation=None, llm_call=fake,
    )
    assert len(result["tag_seeds"]) == 1
    assert result["tag_seeds"][0]["tag_id"] == 15


async def test_empty_summary_returns_blank_summary():
    seed_all()
    fake = FakeLLM(response=json.dumps({
        "tag_seeds": [{"tag_id": 1, "weight": 5}],
        "personality_summary": "太短了",
    }))
    result = await llm_personality_agent.analyze_personality(
        mbti="INTJ", constellation=None, llm_call=fake,
    )
    assert result["personality_summary"] == ""
    assert len(result["tag_seeds"]) == 1
