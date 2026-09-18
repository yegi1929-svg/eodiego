"""LLM 설명 생성 (C_ai_planner.md 8, 9, 10절).

LLM은 오직 "자연어 설명"만 만든다: 일정 제목, 전체 설명, 관광지별 추천
이유. 관광지 선정/실제 집중률 값 판단/최종 후보 검증은 절대 LLM에게 맡기지
않는다. 재추천 사유는 내용이 정해져 있어 LLM 없이 템플릿으로 만든다
(replanner.replan_reason_text).

환각 방지 (RAG):
- 근거 자료는 이번 요청에서 관광공사 API로 실시간 조회한 값만 넣는다
  (최종 일정에 뽑힌 장소의 소개문 + 예측 집중률 라벨). 저장된 데이터는 쓰지 않는다.
- 출력은 구조화 출력(JSON 스키마)으로 강제한다.
- LLM이 돌려준 content_id는 실제 일정 항목과 대조하고, 근거 자료에 없는 숫자가
  들어간 문구는 버린다.
- LLM이 실패(timeout/오류/한도 초과/검증 실패)해도 규칙 기반 결과 + 기본 문구로
  계속 동작한다 - LLM은 single point of failure가 아니다.
"""

from __future__ import annotations

import abc
import asyncio
import json
import logging
import re

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from . import config, llm_usage

logger = logging.getLogger(__name__)


class PlaceContext(BaseModel):
    """LLM에 근거 자료로 넘기는 장소 정보. 이번 요청에서 실시간으로 조회한 값이다."""

    content_id: str
    name: str
    overview: str | None = None
    congestion_label: str | None = None


class LLMPlanText(BaseModel):
    title: str
    summary: str
    item_notes: dict[str, str] = {}  # content_id -> 추천 이유


class LLMTimeoutError(Exception):
    pass


class LLMInvalidOutputError(Exception):
    pass


class LLMQuotaExceededError(Exception):
    """하루 요청 상한 도달(우리 상한) 또는 제공사 429."""


class LLMClient(abc.ABC):
    @abc.abstractmethod
    async def generate_plan_text(
        self, travel_date: str, theme: str | None, places: list[PlaceContext]
    ) -> LLMPlanText:
        ...


class MockLLMClient(LLMClient):
    """실제 LLM 없이도 C/D 개발이 가능하도록 하는 결정론적 구현."""

    async def generate_plan_text(
        self, travel_date: str, theme: str | None, places: list[PlaceContext]
    ) -> LLMPlanText:
        theme_txt = f"{theme} 테마로 " if theme else ""
        title = f"{travel_date} {theme_txt}추천 일정".strip()
        summary = f"{theme_txt}주변 관광지를 예측 집중률과 이동 거리를 고려해 구성했습니다."
        item_notes = {p.content_id: f"{p.name} 방문을 추천합니다." for p in places}
        return LLMPlanText(title=title, summary=summary, item_notes=item_notes)


# --- OpenAI ------------------------------------------------------------------


class _ItemNoteOut(BaseModel):
    content_id: str
    note: str


class _PlanTextOut(BaseModel):
    """구조화 출력 스키마. 모델은 이 형태의 JSON만 돌려줄 수 있다."""

    title: str
    summary: str
    items: list[_ItemNoteOut]


_INSTRUCTIONS = """\
너는 제주 여행 일정 서비스의 안내 문구 작성기다. 입력 JSON의 places 자료로 일정 제목, 요약, 장소별 추천 문구를 한국어 존댓말로 쓴다.

반드시 지킬 규칙:
- places 자료에 있는 사실만 쓴다. 자료에 없는 역사, 위치, 시설, 요금, 운영시간, 교통, 음식 정보를 지어내지 않는다.
- 숫자(연도, 시간, 요금, 거리, 인원, 퍼센트 등)를 쓰지 않는다.
- "실시간", "지금 붐빈다" 같은 표현을 쓰지 않는다. 혼잡 정보는 예측값이며, 필요하면 congestion 값의 표현만 그대로 쓴다.
- overview가 비어 있는 장소는 이름만으로 짧고 일반적인 한 문장을 쓴다.
- items에는 입력 places의 content_id를 그대로 쓰고, 입력에 없는 장소를 추가하지 않는다.
- title은 20자 이내, summary는 1~2문장, note는 장소마다 1문장(60자 이내)으로 쓴다.
"""


def _truncate(text: str | None, limit: int) -> str:
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def build_llm_input(theme: str | None, places: list[PlaceContext]) -> str:
    """근거 자료를 모델 입력 문자열로 만든다. 소개문은 길이 상한을 둔다(토큰 절약)."""

    payload = {
        "theme": theme,
        "places": [
            {
                "content_id": p.content_id,
                "name": p.name,
                "congestion": p.congestion_label or "",
                "overview": _truncate(p.overview, config.LLM_OVERVIEW_MAX_CHARS),
            }
            for p in places
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


class OpenAILLMClient(LLMClient):
    """OpenAI Responses API + 구조화 출력.

    하루 요청 상한(config.LLM_DAILY_REQUEST_LIMIT)을 넘기면 API를 부르지 않는다.
    SDK 자동 재시도도 한도를 깎으므로 기본은 재시도 없음(config.LLM_MAX_RETRIES).
    """

    def __init__(self, api_key: str, client: AsyncOpenAI | None = None):
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            timeout=config.LLM_TIMEOUT_SECONDS,
            max_retries=config.LLM_MAX_RETRIES,
        )

    async def generate_plan_text(
        self, travel_date: str, theme: str | None, places: list[PlaceContext]
    ) -> LLMPlanText:
        if not llm_usage.try_reserve():
            raise LLMQuotaExceededError("오늘 LLM 요청 상한에 도달")

        try:
            response = await self._client.responses.parse(
                model=config.LLM_MODEL,
                instructions=_INSTRUCTIONS,
                input=build_llm_input(theme, places),
                text_format=_PlanTextOut,
                reasoning={"effort": config.LLM_REASONING_EFFORT},
                max_output_tokens=config.LLM_MAX_OUTPUT_TOKENS,
                store=False,  # 요청/응답을 OpenAI 쪽에 보관하지 않는다.
            )
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError("LLM 응답 지연") from exc
        except openai.RateLimitError as exc:
            # OpenAI는 요청 한도 초과(rate_limit_exceeded)와 크레딧 부족
            # (insufficient_quota)을 모두 429로 준다. 코드를 남겨야 구분된다.
            raise LLMQuotaExceededError(f"제공사 429 code={getattr(exc, 'code', None)}") from exc
        except (openai.OpenAIError, ValidationError) as exc:
            # 인증 실패, 잘못된 요청, 연결 오류, 스키마 불일치 등
            raise LLMInvalidOutputError(
                f"LLM 호출 실패: {type(exc).__name__} code={getattr(exc, 'code', None)}"
            ) from exc

        usage = getattr(response, "usage", None)
        if usage is not None:
            llm_usage.record_tokens(usage.input_tokens or 0, usage.output_tokens or 0)
            logger.info("LLM %s 토큰 입력=%s 출력=%s", config.LLM_MODEL, usage.input_tokens, usage.output_tokens)

        parsed = response.output_parsed
        if parsed is None:  # 거절, 출력 상한에 걸려 잘림 등
            raise LLMInvalidOutputError("구조화 출력 없음")

        return LLMPlanText(
            title=parsed.title.strip(),
            summary=parsed.summary.strip(),
            item_notes={i.content_id: i.note.strip() for i in parsed.items if i.note.strip()},
        )


_openai_client: OpenAILLMClient | None = None


def get_llm_client() -> LLMClient:
    """USE_LLM=true 이고 키가 있으면 OpenAI, 아니면 결정론적 스텁."""

    global _openai_client
    if config.USE_LLM and config.LLM_API_KEY:
        if _openai_client is None:
            _openai_client = OpenAILLMClient(config.LLM_API_KEY)
        return _openai_client
    return MockLLMClient()


# --- 검증 --------------------------------------------------------------------

_NUMBER_RE = re.compile(r"\d+")


def _numbers(text: str | None) -> set[str]:
    return set(_NUMBER_RE.findall(text or ""))


def _has_unsupported_numbers(text: str, allowed: set[str]) -> bool:
    """근거 자료에 없는 숫자가 문구에 들어갔는지. 숫자는 가장 흔한 환각 형태다."""

    return any(n not in allowed for n in _numbers(text))


async def safe_generate_plan_text(
    client: LLMClient,
    travel_date: str,
    theme: str | None,
    places: list[PlaceContext],
    allowed_content_ids: set[str],
) -> LLMPlanText | None:
    """LLM 결과를 검증하고, 실패/부정확하면 None을 반환해 호출측이 기본
    문구로 fallback 하도록 한다 (10절)."""

    if not places:
        return None  # 쓸 장소가 없으면 요청 한도를 쓰지 않는다.

    try:
        result = await asyncio.wait_for(
            client.generate_plan_text(travel_date, theme, places),
            timeout=config.LLM_TIMEOUT_SECONDS + 1,
        )
    except (asyncio.TimeoutError, LLMTimeoutError, LLMInvalidOutputError, LLMQuotaExceededError) as exc:
        logger.warning("LLM 문구 생성 실패 -> 기본 문구 사용: %s", exc or type(exc).__name__)
        return None

    sources = {p.content_id: p for p in places}

    # 제목/요약: 자료 전체(+여행 날짜)에 없는 숫자가 있으면 통째로 버린다.
    all_numbers = _numbers(travel_date) | _numbers(theme)
    for p in places:
        all_numbers |= _numbers(p.name) | _numbers(p.overview)
    if not result.title or not result.summary:
        logger.warning("LLM 제목/요약 비어 있음 -> 기본 문구 사용")
        return None
    if _has_unsupported_numbers(result.title, all_numbers) or _has_unsupported_numbers(
        result.summary, all_numbers
    ):
        logger.warning("LLM 제목/요약에 근거 없는 숫자 -> 기본 문구 사용")
        return None

    notes: dict[str, str] = {}
    for cid, note in result.item_notes.items():
        # LLM이 존재하지 않는 content_id를 만들어냈으면 그 항목만 버린다.
        if cid not in allowed_content_ids or cid not in sources:
            continue
        place = sources[cid]
        if _has_unsupported_numbers(note, _numbers(place.name) | _numbers(place.overview)):
            logger.info("근거 없는 숫자가 든 추천 문구 제외: content_id=%s", cid)
            continue
        notes[cid] = note
    result.item_notes = notes
    return result
