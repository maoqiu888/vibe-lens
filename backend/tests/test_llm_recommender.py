import json

import pytest

from app.services import llm_recommender


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


def _make_response(items):
    return json.dumps({"items": items})


async def test_happy_path_three_cross_domain_items():
    fake = FakeLLM(response=_make_response([
        {"domain": "game",  "name": "《逃生》",    "reason": "幽闭窒息，你拿着摄像机"},
        {"domain": "book",  "name": "《幽灵之家》", "reason": "慢炖心理压抑"},
        {"domain": "music", "name": "Ben Frost",   "reason": "黑暗环境音"},
    ]))
    items = await llm_recommender.recommend(
        text="《闪灵》", source_domain="movie",
        item_tag_names=["黑暗压抑"], user_top_tag_names=["烧脑解谜"],
        llm_call=fake,
    )
    assert len(items) == 3
    assert {i["domain"] for i in items} == {"game", "book", "music"}
    assert all(i["domain"] != "movie" for i in items)


async def test_same_domain_items_are_filtered():
    fake = FakeLLM(response=_make_response([
        {"domain": "movie", "name": "《沉默的羔羊》", "reason": "嘿嘿同域"},
        {"domain": "game",  "name": "《逃生》",       "reason": "跨域"},
        {"domain": "book",  "name": "《幽灵之家》",   "reason": "跨域"},
    ]))
    items = await llm_recommender.recommend(
        text="x", source_domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert len(items) == 2
    assert all(i["domain"] != "movie" for i in items)


async def test_all_same_domain_raises():
    fake = FakeLLM(response=_make_response([
        {"domain": "movie", "name": "a", "reason": "x"},
        {"domain": "movie", "name": "b", "reason": "y"},
    ]))
    with pytest.raises(llm_recommender.RecommendEmptyError):
        await llm_recommender.recommend(
            text="x", source_domain="movie",
            item_tag_names=[], user_top_tag_names=[],
            llm_call=fake,
        )


async def test_duplicate_names_are_deduped():
    fake = FakeLLM(response=_make_response([
        {"domain": "game", "name": "《逃生》", "reason": "a"},
        {"domain": "game", "name": "《逃生》", "reason": "duplicate"},
        {"domain": "book", "name": "《幽灵之家》", "reason": "b"},
    ]))
    items = await llm_recommender.recommend(
        text="x", source_domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert len(items) == 2
    names = [i["name"] for i in items]
    assert names.count("《逃生》") == 1


async def test_invalid_domain_items_dropped():
    fake = FakeLLM(response=_make_response([
        {"domain": "podcast", "name": "???", "reason": "bogus domain"},
        {"domain": "game", "name": "《逃生》", "reason": "valid"},
        {"domain": "book", "name": "《幽灵》", "reason": "valid"},
    ]))
    items = await llm_recommender.recommend(
        text="x", source_domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert len(items) == 2


async def test_missing_fields_are_dropped():
    fake = FakeLLM(response=_make_response([
        {"domain": "game", "name": "《逃生》"},
        {"domain": "book", "name": "《幽灵》", "reason": "valid"},
        {"domain": "music", "name": "Ben Frost", "reason": "valid"},
    ]))
    items = await llm_recommender.recommend(
        text="x", source_domain="movie",
        item_tag_names=[], user_top_tag_names=[],
        llm_call=fake,
    )
    assert len(items) == 2
    assert all("reason" in i and i["reason"] for i in items)


async def test_json_parse_failure_raises():
    fake = FakeLLM(response="not json")
    with pytest.raises(llm_recommender.LlmParseError):
        await llm_recommender.recommend(
            text="x", source_domain="movie",
            item_tag_names=[], user_top_tag_names=[],
            llm_call=fake,
        )


async def test_timeout_wraps_to_timeout_error():
    import httpx
    fake = FakeLLM(raise_exc=httpx.TimeoutException("slow"))
    with pytest.raises(llm_recommender.LlmTimeoutError):
        await llm_recommender.recommend(
            text="x", source_domain="movie",
            item_tag_names=[], user_top_tag_names=[],
            llm_call=fake,
        )


async def test_prompt_contains_source_domain_exclusion():
    fake = FakeLLM(response=_make_response([
        {"domain": "book", "name": "x", "reason": "y"},
        {"domain": "game", "name": "a", "reason": "b"},
    ]))
    await llm_recommender.recommend(
        text="《闪灵》", source_domain="movie",
        item_tag_names=["黑暗压抑"], user_top_tag_names=["烧脑解谜"],
        llm_call=fake,
    )
    assert "movie" in fake.last_prompt
    assert "禁止" in fake.last_prompt or "排除" in fake.last_prompt or "不要" in fake.last_prompt
