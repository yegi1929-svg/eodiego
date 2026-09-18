"""부분 재추천 로직 (C_ai_planner.md 6, 7절).

기본 정책: 전체 일정을 다시 만들지 않고 혼잡한 관광지 한 곳만 교체한다.
"""

from __future__ import annotations

from shared.schemas import Congestion, Place, Plan, PlanItem

from . import config
from .rules import Candidate, haversine_m, attach_congestion, congestion_level_label, score_candidates


class NoReplacementCandidateError(Exception):
    """대체 후보가 없을 때 (7절 "대체 후보 없음" 케이스)."""


def find_replacement(
    plan: Plan,
    target_place: Place,
    candidate_places: list[Place],
    congestion_map: dict[str, Congestion],
    travel_date: str,
) -> Candidate:
    """7절 재추천 후보 선정 기준을 순서대로 적용한다.

    1. 기존 일정과 중복되지 않음
    2. 선택 날짜 집중률이 기준 이하
    3. 이동거리가 과도하지 않음 (기존 관광지 기준 반경 이내)
    4. 집중률 데이터가 없으면 fallback 후보로 사용
    """

    existing_ids = {item.content_id for item in plan.items}

    pool = [p for p in candidate_places if p.content_id not in existing_ids]
    pool = [p for p in pool if haversine_m(target_place, p) <= config.MAX_REPLAN_DISTANCE_DELTA_M]

    attached = attach_congestion(pool, congestion_map, travel_date)

    under_threshold = [c for c in attached if c.rate is not None and c.rate < config.CONGESTION_THRESHOLD]
    if under_threshold:
        return score_candidates(under_threshold)[0]

    no_data_fallback = [c for c in attached if not c.has_data]
    if no_data_fallback:
        return score_candidates(no_data_fallback)[0]

    raise NoReplacementCandidateError(f"target_content_id={target_place.content_id} 대체 후보 없음")


def replan_reason_text(old_name: str, new_name: str, old_congestion_label: str | None) -> str:
    """재추천 사유 문구. LLM을 쓰지 않는다.

    내용이 정해진 문장이라 LLM이 더할 것이 없고, 호출마다 하루 요청 한도만
    깎인다. 사유는 요청 문자열이 아니라 교체 대상의 실제 집중률 라벨로 정한다 -
    "보통"인 곳을 바꿨는데 "집중률이 높아"라고 쓰면 사실과 다르다.
    """

    if old_congestion_label == "예측 집중률 높음":
        return f"{old_name}의 예측 집중률이 높아 {new_name}(으)로 대체했습니다."
    return f"{old_name} 대신 {new_name}을(를) 추천합니다."


def apply_replacement(plan: Plan, target_content_id: str, replacement: Candidate, reason_text: str) -> Plan:
    """대상 항목만 교체하고 나머지 순서/시간은 그대로 유지한다."""

    new_items: list[PlanItem] = []
    for item in plan.items:
        if item.content_id != target_content_id:
            new_items.append(item)
            continue
        label = congestion_level_label(replacement.rate)
        new_items.append(
            PlanItem(
                content_id=replacement.place.content_id,
                name=replacement.place.name,
                order=item.order,
                visit_time=item.visit_time,
                note=label,
                # 새 항목도 집중률을 note와 별도로 들고 있어야 화면이 판단할 수 있다.
                congestion_label=label,
                high_congestion=replacement.rate is not None
                and replacement.rate >= config.CONGESTION_THRESHOLD,
            )
        )

    return Plan(
        title=plan.title,
        travel_date=plan.travel_date,
        items=new_items,
        summary=plan.summary + f" ({reason_text})",
    )
