import json

import pytest

from app.services import llm_roaster


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


async def test_generate_roast_happy_path():
    fake = FakeLLM(response=json.dumps({"roast": "快逃！你会在影院睡着。"}))
    result = await llm_roaster.generate_roast(
        text="一部极慢的心理惊悚片",
        domain="movie",
        item_tag_names=["黑暗压抑", "慢炖沉浸"],
        user_top_tag_names=["日常烟火", "治愈温暖", "轻度思考"],
        llm_call=fake,
    )
    assert result == "快逃！你会在影院睡着。"
    assert fake.calls == 1


async def test_user_prompt_contains_all_context():
    fake = FakeLLM(response=json.dumps({"roast": "x"}))
    await llm_roaster.generate_roast(
        text="《闪灵》",
        domain="movie",
        item_tag_names=["黑暗压抑"],
        user_top_tag_names=["日常烟火"],
        llm_call=fake,
    )
    p = fake.last_prompt
    # V1.2 prompt localizes domain to Chinese label ("电影" instead of "movie")
    assert "电影" in p
    assert "《闪灵》" in p
    assert "黑暗压抑" in p
    assert "日常烟火" in p


async def test_parse_failure_returns_empty_string():
    fake = FakeLLM(response="not json")
    result = await llm_roaster.generate_roast(
        text="x", domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert result == ""


async def test_llm_exception_returns_empty_string():
    fake = FakeLLM(raise_exc=RuntimeError("timeout"))
    result = await llm_roaster.generate_roast(
        text="x", domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert result == ""


async def test_missing_roast_field_returns_empty_string():
    fake = FakeLLM(response=json.dumps({"other": "x"}))
    result = await llm_roaster.generate_roast(
        text="x", domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert result == ""


async def test_empty_user_tags_still_works():
    """Cold-start users have no core_weight yet — roaster should still produce output."""
    fake = FakeLLM(response=json.dumps({"roast": "你是一张白纸"}))
    result = await llm_roaster.generate_roast(
        text="x", domain="book",
        item_tag_names=["治愈温暖"], user_top_tag_names=[],
        llm_call=fake,
    )
    assert result == "你是一张白纸"
    assert fake.last_prompt is not None
