import asyncio

from C_ai_planner.llm_client import (
    LLMClient,
    LLMInvalidOutputError,
    LLMPlanText,
    LLMQuotaExceededError,
    LLMTimeoutError,
    MockLLMClient,
    PlaceContext,
    safe_generate_plan_text,
)
from C_ai_planner.replanner import replan_reason_text


class _FixedClient(LLMClient):
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, 0

    async def generate_plan_text(self, travel_date, theme, places):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def _places(*pairs):
    return [PlaceContext(content_id=cid, name=name, overview=overview) for cid, name, overview in pairs]


def test_mock_llm_client_succeeds():
    result = asyncio.run(
        safe_generate_plan_text(MockLLMClient(), "20260828", "자연", _places(("1", "성산일출봉", None)), {"1"})
    )
    assert result is not None
    assert "1" in result.item_notes


def test_llm_timeout_falls_back_to_none():
    client = _FixedClient(error=LLMTimeoutError("timeout"))
    assert asyncio.run(safe_generate_plan_text(client, "20260828", None, _places(("1", "A", None)), {"1"})) is None


def test_llm_quota_and_invalid_output_fall_back_to_none():
    for err in (LLMQuotaExceededError("limit"), LLMInvalidOutputError("bad")):
        client = _FixedClient(error=err)
        assert asyncio.run(safe_generate_plan_text(client, "20260828", None, _places(("1", "A", None)), {"1"})) is None


def test_llm_invalid_content_id_is_dropped_not_trusted():
    client = _FixedClient(LLMPlanText(
        title="제목", summary="설명",
        item_notes={"REAL": "좋아요", "FAKE_ID_NOT_A_CANDIDATE": "존재하지 않는 관광지 이유"},
    ))
    result = asyncio.run(safe_generate_plan_text(client, "20260828", None, _places(("REAL", "실제", None)), {"REAL"}))
    assert result is not None
    assert "FAKE_ID_NOT_A_CANDIDATE" not in result.item_notes
    assert "REAL" in result.item_notes


def test_note_with_numbers_not_in_source_is_dropped():
    """자료에 없는 운영시간/요금 같은 숫자는 가장 흔한 환각 형태다."""
    client = _FixedClient(LLMPlanText(
        title="제주 산책", summary="여유로운 하루입니다.",
        item_notes={"1": "입장료 3000원으로 저렴해요.", "2": "도심 속 공원이에요."},
    ))
    places = _places(("1", "A", "조용한 절이다."), ("2", "B", "도심 속 공원이다."))
    result = asyncio.run(safe_generate_plan_text(client, "20260828", None, places, {"1", "2"}))
    assert "1" not in result.item_notes
    assert result.item_notes["2"] == "도심 속 공원이에요."


def test_note_with_numbers_from_source_is_kept():
    client = _FixedClient(LLMPlanText(
        title="제주 산책", summary="여유로운 하루입니다.",
        item_notes={"1": "88 서울올림픽 성화 기념물이 있어요."},
    ))
    places = _places(("1", "신산공원", "88 서울올림픽 성화의 국내 도착을 기념하는 기념물이 있다."))
    result = asyncio.run(safe_generate_plan_text(client, "20260828", None, places, {"1"}))
    assert "1" in result.item_notes


def test_title_with_unsupported_number_falls_back_entirely():
    client = _FixedClient(LLMPlanText(title="제주 3일 완벽 코스", summary="설명", item_notes={}))
    result = asyncio.run(safe_generate_plan_text(client, "20260828", None, _places(("1", "A", None)), {"1"}))
    assert result is None


def test_no_places_skips_llm_call():
    """쓸 장소가 없으면 하루 요청 한도를 쓰지 않는다."""
    client = _FixedClient(LLMPlanText(title="t", summary="s"))
    assert asyncio.run(safe_generate_plan_text(client, "20260828", None, [], set())) is None
    assert client.calls == 0


def test_replan_reason_uses_actual_congestion_label():
    """'보통'인 곳을 바꿨는데 '집중률이 높아'라고 쓰면 사실과 다르다."""
    assert "높아" in replan_reason_text("A", "B", "예측 집중률 높음")
    normal = replan_reason_text("A", "B", "예측 집중률 보통")
    assert "높아" not in normal and "A" in normal and "B" in normal
    assert "높아" not in replan_reason_text("A", "B", None)
