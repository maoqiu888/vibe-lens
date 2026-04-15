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
    fake = FakeLLM(response=json.dumps({"roast": "快逃！你会睡着。"}))
    result = await llm_roaster.generate_roast(
        text="一部极慢的心理惊悚片",
        domain="movie",
        match_score=25,
        user_taste_hint="节奏越快越好；爱看发生在日常生活里的故事",
        llm_call=fake,
    )
    assert result == "快逃！你会睡着。"
    assert fake.calls == 1


async def test_user_prompt_contains_text_and_taste_hint():
    fake = FakeLLM(response=json.dumps({"roast": "x"}))
    await llm_roaster.generate_roast(
        text="《闪灵》的走廊很压抑",
        domain="movie",
        match_score=72,
        user_taste_hint="爱看机械科幻的冷光调",
        llm_call=fake,
    )
    p = fake.last_prompt
    # Raw original text must be visible
    assert "《闪灵》的走廊很压抑" in p
    # Domain label localized to Chinese
    assert "电影" in p
    # Natural-language taste hint passed through
    assert "爱看机械科幻的冷光调" in p


async def test_user_prompt_does_not_leak_tag_names():
    """CRITICAL: the roaster must not see any internal tag names.

    This test guards against regression — if someone tries to pass tag names
    through the taste hint or domain, this test will catch it as long as
    the assertion matches the V1.2 internal 24-tag vocabulary.
    """
    fake = FakeLLM(response=json.dumps({"roast": "x"}))
    await llm_roaster.generate_roast(
        text="some random text",
        domain="book",
        match_score=50,
        user_taste_hint="这个人喜欢慢慢读的东西",  # natural language, no tag names
        llm_call=fake,
    )
    p = fake.last_prompt
    forbidden_tag_names = [
        "慢炖沉浸", "张弛有度", "紧凑推进", "爆裂快切",
        "治愈温暖", "明亮轻快", "忧郁内省", "黑暗压抑",
        "放空友好", "轻度思考", "烧脑解谜", "认知挑战",
        "白描克制", "细腻抒情", "奇观堆砌", "解构实验",
        "日常烟火", "奇幻异想", "赛博机械", "历史厚重",
        "轻食小品", "有共鸣", "情感重击", "灵魂灼烧",
    ]
    for tag_name in forbidden_tag_names:
        assert tag_name not in p, f"tag name '{tag_name}' leaked into user prompt"


async def test_match_level_hint_brackets():
    """Four fuzzy brackets: 严重不符 / 勉强 / 还可以 / 非常契合."""
    assert "严重不符" in llm_roaster._match_level_hint(0)
    assert "严重不符" in llm_roaster._match_level_hint(29)
    assert "勉强" in llm_roaster._match_level_hint(30)
    assert "勉强" in llm_roaster._match_level_hint(54)
    assert "还可以" in llm_roaster._match_level_hint(55)
    assert "还可以" in llm_roaster._match_level_hint(74)
    assert "非常契合" in llm_roaster._match_level_hint(75)
    assert "非常契合" in llm_roaster._match_level_hint(100)


async def test_parse_failure_returns_empty_string():
    fake = FakeLLM(response="not json")
    result = await llm_roaster.generate_roast(
        text="x", domain="movie",
        match_score=50, user_taste_hint="",
        llm_call=fake,
    )
    assert result == ""


async def test_llm_exception_returns_empty_string():
    fake = FakeLLM(raise_exc=RuntimeError("timeout"))
    result = await llm_roaster.generate_roast(
        text="x", domain="movie",
        match_score=50, user_taste_hint="",
        llm_call=fake,
    )
    assert result == ""


async def test_missing_roast_field_returns_empty_string():
    fake = FakeLLM(response=json.dumps({"other": "x"}))
    result = await llm_roaster.generate_roast(
        text="x", domain="movie",
        match_score=50, user_taste_hint="",
        llm_call=fake,
    )
    assert result == ""


async def test_empty_taste_hint_still_works():
    """New user with no profile — roaster should still produce output."""
    fake = FakeLLM(response=json.dumps({"roast": "你是一张白纸"}))
    result = await llm_roaster.generate_roast(
        text="some text", domain="book",
        match_score=0, user_taste_hint="",
        llm_call=fake,
    )
    assert result == "你是一张白纸"
    assert fake.last_prompt is not None
    # Empty hint should degrade to a "new friend" fallback in the prompt
    assert "新朋友" in fake.last_prompt
