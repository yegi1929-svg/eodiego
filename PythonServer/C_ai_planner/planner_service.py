"""C의 공개 service 계층: 규칙 기반 생성 + LLM 설명 보강 + 검증 (11, 13절)."""

from __future__ import annotations

import logging

from shared.schemas import Plan, PlanItem, PlanRequest, ReplanRequest, ReplanResponse

from . import b_client, config
from .llm_client import LLMClient, PlaceContext, get_llm_client, safe_generate_plan_text
from .replanner import (
    NoReplacementCandidateError,
    apply_replacement,
    find_replacement,
    replan_reason_text,
)
from .rules import build_candidates, default_summary, schedule_visits

logger = logging.getLogger(__name__)


async def generate_plan(req: PlanRequest, llm_client: LLMClient | None = None) -> Plan:
    """PlanRequest -> 후보 조회 -> 규칙 기반 일정 -> LLM 설명 보강 -> Plan.

    (13절 완료 조건 파이프라인)
    """

    llm_client = llm_client or get_llm_client()

    places = await b_client.get_nearby_places(req.map_x, req.map_y)
    congestion_map = await b_client.get_congestion_map(places)

    ordered = build_candidates(places, congestion_map, req.travel_date, req.place_count)
    items = schedule_visits(ordered, req.start_time, req.end_time)

    # 상세정보는 후보 전체가 아니라 최종 일정에 뽑힌 장소만 조회한다.
    await _attach_details(items)

    allowed_ids = {i.content_id for i in items}
    # RAG 근거 자료: 방금 실시간으로 조회한 뽑힌 장소의 소개문 + 예측 집중률 라벨.
    # (추가 관광공사 호출 없음 - 위에서 붙인 상세정보를 그대로 쓴다)
    contexts = [
        PlaceContext(
            content_id=i.content_id,
            name=i.name,
            overview=i.detail.overview if i.detail else None,
            congestion_label=i.congestion_label,
        )
        for i in items
    ]

    llm_text = await safe_generate_plan_text(
        llm_client, req.travel_date, req.theme, contexts, allowed_ids
    )

    if llm_text is None:
        title = f"{req.travel_date} 추천 일정"
        summary = default_summary()
    else:
        title = llm_text.title
        summary = llm_text.summary
        for item in items:
            if item.content_id in llm_text.item_notes:
                item.note = llm_text.item_notes[item.content_id]

    return Plan(title=title, travel_date=req.travel_date, items=items, summary=summary)


async def _attach_details(items: list[PlanItem]) -> None:
    """일정 항목에 상세정보(소개문/운영시간/휴무일)를 붙인다.

    상세정보는 보조 정보라서 조회에 실패해도 일정 생성 자체는 막지 않는다.
    """

    if not items:
        return
    try:
        details = await b_client.get_place_details([i.content_id for i in items])
    except b_client.BServiceError:
        logger.warning("상세정보 조회 실패 - 상세정보 없이 일정을 반환합니다.")
        return
    for item in items:
        item.detail = details.get(item.content_id)


async def replan(req: ReplanRequest) -> ReplanResponse:
    """기존 Plan에서 target_content_id 하나만 교체한다 (6, 7절).

    사유 문구는 LLM을 쓰지 않는다 (replanner.replan_reason_text).
    """

    target_item = next((i for i in req.plan.items if i.content_id == req.target_content_id), None)
    if target_item is None:
        raise ValueError(f"target_content_id={req.target_content_id} 가 plan에 없습니다.")

    # target의 실제 좌표가 필요하다. 일정 생성 때 붙여둔 상세정보가 있으면
    # 그대로 쓰고, 없을 때만 B에 조회한다 (관광지당 API 2회 절약).
    target_place = target_item.detail
    if target_place is None:
        details = await b_client.get_place_details([req.target_content_id])
        target_place = details.get(req.target_content_id)
    if target_place is None:
        raise ValueError("교체 대상 관광지 상세 정보를 가져오지 못했습니다.")

    # 대체 후보는 어차피 MAX_REPLAN_DISTANCE_DELTA_M 밖이면 버려지므로,
    # 그보다 넓게 검색해 집중률 조회 호출을 낭비하지 않는다.
    candidate_places = await b_client.get_nearby_places(
        target_place.map_x, target_place.map_y, radius=int(config.MAX_REPLAN_DISTANCE_DELTA_M)
    )
    congestion_map = await b_client.get_congestion_map(candidate_places)

    try:
        replacement = find_replacement(
            req.plan, target_place, candidate_places, congestion_map, req.plan.travel_date
        )
    except NoReplacementCandidateError:
        raise

    reason_text = replan_reason_text(
        target_item.name, replacement.place.name, target_item.congestion_label
    )

    new_plan = apply_replacement(req.plan, req.target_content_id, replacement, reason_text)

    # 새로 들어온 장소만 상세정보를 조회한다. 나머지는 기존 상세정보를 유지.
    await _attach_details(
        [i for i in new_plan.items if i.content_id == replacement.place.content_id]
    )

    return ReplanResponse(
        plan=new_plan,
        replaced_content_id=replacement.place.content_id,
        replacement_reason=reason_text,
    )
