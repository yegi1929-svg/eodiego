"""OpenAI 연동 검증. 실제 API는 부르지 않고 SDK 클라이언트를 가짜로 바꾼다."""

import asyncio
import importlib
import json
from types import SimpleNamespace

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from C_ai_planner import config, llm_client, llm_usage
from C_ai_planner.llm_client import (
    LLMInvalidOutputError,
    LLMQuotaExceededError,
    LLMTimeoutError,
    OpenAILLMClient,
    PlaceContext,
    _ItemNoteOut,
    _PlanTextOut,
)


class _FakeResponses:
    def __init__(self, parsed=None, error=None, usage=(900, 120)):
        self.parsed, self.error, self.usage = parsed, error, usage
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            output_parsed=self.parsed,
            usage=SimpleNamespace(input_tokens=self.usage[0], output_tokens=self.usage[1]),
        )


def _client(parsed=None, error=None):
    fake = _FakeResponses(parsed=parsed, error=error)
    return OpenAILLMClient("sk-test", client=SimpleNamespace(responses=fake)), fake


PLACES = [
    PlaceContext(content_id="1", name="신산공원", overview="도심 속 공원이다. " * 100, congestion_label="예측 집중률 보통"),
    PlaceContext(content_id="2", name="귤림서원", overview=None, congestion_label="혼잡도 미제공"),
]


def _parsed():
    return _PlanTextOut(
        title="도심 속 제주 산책", summary="가까운 명소를 여유롭게 둘러봅니다.",
        items=[_ItemNoteOut(content_id="1", note="도심 속 공원에서 쉬어가요."),
               _ItemNoteOut(content_id="2", note="  ")],
    )


def test_success_maps_notes_and_records_usage(mysql_db):
    client, fake = _client(parsed=_parsed())
    result = asyncio.run(client.generate_plan_text("20260920", None, PLACES))

    assert result.title == "도심 속 제주 산책"
    assert result.item_notes == {"1": "도심 속 공원에서 쉬어가요."}  # 빈 문구는 버린다

    snap = llm_usage.snapshot()
    assert snap["requests"] == 1
    assert snap["input_tokens"] == 900 and snap["output_tokens"] == 120


def test_request_uses_configured_model_structured_output_and_no_storage(mysql_db):
    client, fake = _client(parsed=_parsed())
    asyncio.run(client.generate_plan_text("20260920", None, PLACES))
    call = fake.calls[0]

    assert call["model"] == config.LLM_MODEL
    assert call["text_format"] is _PlanTextOut
    assert call["reasoning"] == {"effort": config.LLM_REASONING_EFFORT}
    assert call["max_output_tokens"] == config.LLM_MAX_OUTPUT_TOKENS
    assert call["store"] is False

    payload = json.loads(call["input"])
    overview = payload["places"][0]["overview"]
    # 소개문은 길이 상한을 둔다 (토큰 절약)
    assert len(overview) <= config.LLM_OVERVIEW_MAX_CHARS + 1
    assert payload["places"][1]["overview"] == ""
    # 키가 프롬프트에 섞이면 안 된다
    assert "sk-test" not in call["input"] and "sk-test" not in call["instructions"]


def test_daily_limit_blocks_before_calling_api(mysql_db, monkeypatch):
    monkeypatch.setattr(config, "LLM_DAILY_REQUEST_LIMIT", 2)
    client, fake = _client(parsed=_parsed())

    asyncio.run(client.generate_plan_text("20260920", None, PLACES))
    asyncio.run(client.generate_plan_text("20260920", None, PLACES))
    with pytest.raises(LLMQuotaExceededError):
        asyncio.run(client.generate_plan_text("20260920", None, PLACES))

    assert len(fake.calls) == 2  # 3번째는 API를 부르지 않았다
    assert llm_usage.snapshot()["remaining"] == 0


def _req():
    return httpx.Request("POST", "https://api.openai.com/v1/responses")


def test_provider_errors_are_mapped_and_still_count_against_limit(mysql_db):
    cases = [
        (openai.RateLimitError("rate", response=httpx.Response(429, request=_req()), body=None), LLMQuotaExceededError),
        (openai.APITimeoutError(request=_req()), LLMTimeoutError),
        (openai.AuthenticationError("auth", response=httpx.Response(401, request=_req()), body=None), LLMInvalidOutputError),
        (openai.APIConnectionError(request=_req()), LLMInvalidOutputError),
    ]
    for error, expected in cases:
        client, _ = _client(error=error)
        with pytest.raises(expected):
            asyncio.run(client.generate_plan_text("20260920", None, PLACES))
    # 실패한 요청도 제공사 한도를 깎으므로 예약 횟수에 포함된다.
    assert llm_usage.snapshot()["requests"] == len(cases)


def test_missing_parsed_output_is_invalid(mysql_db):
    client, _ = _client(parsed=None)
    with pytest.raises(LLMInvalidOutputError):
        asyncio.run(client.generate_plan_text("20260920", None, PLACES))


def test_get_llm_client_selects_openai_only_when_enabled_with_key(monkeypatch):
    monkeypatch.setattr(config, "USE_LLM", False)
    monkeypatch.setattr(config, "LLM_API_KEY", "sk-test")
    assert isinstance(llm_client.get_llm_client(), llm_client.MockLLMClient)

    monkeypatch.setattr(config, "USE_LLM", True)
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    assert isinstance(llm_client.get_llm_client(), llm_client.MockLLMClient)

    monkeypatch.setattr(config, "LLM_API_KEY", "sk-test")
    first = llm_client.get_llm_client()
    assert isinstance(first, OpenAILLMClient)
    assert llm_client.get_llm_client() is first  # 클라이언트를 요청마다 새로 만들지 않는다


def test_usage_survives_restart(mysql_db, isolate_llm, monkeypatch):
    assert llm_usage.try_reserve()
    reloaded = importlib.reload(llm_usage)
    monkeypatch.setattr(reloaded, "_today", lambda: isolate_llm)
    assert reloaded.snapshot()["requests"] == 1


def test_reserve_fails_closed_when_db_unavailable(monkeypatch):
    """한도를 확인할 수 없으면 부르지 않는다 - 모르고 계정 한도를 넘기지 않게."""
    from shared import database

    def broken_transaction():
        raise database.DatabaseConfigError("no db")

    monkeypatch.setattr(llm_usage.database, "transaction", broken_transaction)
    assert llm_usage.try_reserve() is False


def test_limit_is_enforced_in_a_single_insert_select(mysql_db, monkeypatch):
    """확인과 추가를 한 문장으로 해서, 상한에서 딱 멈춘다."""
    monkeypatch.setattr(config, "LLM_DAILY_REQUEST_LIMIT", 3)
    results = [llm_usage.try_reserve() for _ in range(5)]
    assert results == [True, True, True, False, False]
    assert llm_usage.snapshot()["requests"] == 3


def test_usage_endpoint(mysql_db):
    from C_ai_planner.main import app

    body = TestClient(app).get("/internal/llm-usage").json()
    assert body["requests"] == 0
    assert body["daily_limit"] == config.LLM_DAILY_REQUEST_LIMIT
    assert body["model"] == config.LLM_MODEL
