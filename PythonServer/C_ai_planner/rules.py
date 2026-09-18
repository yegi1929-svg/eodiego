"""규칙 기반 일정 생성 로직 (C_ai_planner.md 0, 3, 4절).

원칙: "규칙/데이터는 코드가 판단하고, LLM은 설명만 붙인다." 이 파일은
LLM을 전혀 참조하지 않는다 - LLM이 죽어도 이 모듈만으로 완결된 Plan을
만들 수 있어야 한다 (10절 fallback 요건).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from shared.schemas import Congestion, Place, PlanItem

from . import config


def rate_for_date(congestion: Congestion, travel_date: str) -> float | None:
    """daily 목록에서 travel_date와 일치하는 예측 집중률을 찾는다.

    없으면 None. has_data=False와는 별개로, has_data=True인데도 그 날짜만
    없는 경우도 여기서 자연스럽게 None으로 처리된다.
    """

    for day in congestion.daily:
        if day.date == travel_date:
            return day.rate
    return None


def congestion_level_label(rate: float | None) -> str:
    """note 기본값에 쓰이는 라벨. "실시간 혼잡" 표현은 절대 쓰지 않는다."""

    if rate is None:
        return "혼잡도 미제공"
    if rate >= config.CONGESTION_THRESHOLD:
        return "예측 집중률 높음"
    if rate >= config.CONGESTION_THRESHOLD * 0.5:
        return "예측 집중률 보통"
    return "예측 집중률 낮음"


class Candidate:
    """일정 선정 과정에서 쓰는 내부 작업 단위. Pydantic 모델이 아니라 순수
    파이썬 객체로 둬서 규칙 계산 중간값(score 등)을 자유롭게 담는다."""

    __slots__ = ("place", "rate", "has_data", "score")

    def __init__(self, place: Place, rate: float | None, has_data: bool):
        self.place = place
        self.rate = rate
        self.has_data = has_data
        self.score = 0.0

    def __repr__(self) -> str:  # pragma: no cover - 디버그 편의용
        return f"Candidate({self.place.name}, rate={self.rate}, score={self.score:.2f})"


def attach_congestion(
    places: list[Place], congestion_map: dict[str, Congestion], travel_date: str
) -> list[Candidate]:
    """C_ai_planner.md 4절: 집중률 없으면 무조건 제외하지 않는다."""

    candidates = []
    for place in places:
        congestion = congestion_map.get(place.content_id)
        if congestion is None or not congestion.has_data:
            candidates.append(Candidate(place, rate=None, has_data=False))
            continue
        rate = rate_for_date(congestion, travel_date)
        candidates.append(Candidate(place, rate=rate, has_data=rate is not None))
    return candidates


def score_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """거리 + 예측 집중률을 함께 고려해 정렬한다 (3절: 단순 dist 오름차순만
    쓰지 않는다). 점수가 낮을수록 우선순위가 높다.

    - 거리는 0~1로 정규화(최대 거리 기준)한다.
    - 집중률 데이터가 없으면 거리만으로 평가한다.
    - 집중률이 있으면 거리 60% + 집중률 40% 가중치로 합산한다.
    """

    if not candidates:
        return []

    max_dist = max((c.place.dist for c in candidates), default=1.0) or 1.0
    for c in candidates:
        dist_score = c.place.dist / max_dist
        if c.rate is None:
            c.score = dist_score
        else:
            rate_score = c.rate / 100.0
            c.score = dist_score * 0.6 + rate_score * 0.4
    return sorted(candidates, key=lambda c: c.score)


def select_diverse(candidates: list[Candidate], place_count: int) -> list[Candidate]:
    """관광지 유형 중복을 어느 정도 피하면서 place_count개를 선택한다
    (3절: "관광지 유형/중복 고려"). 후보가 place_count보다 적으면 있는 만큼만
    반환한다."""

    selected: list[Candidate] = []
    seen_categories: set[str] = set()

    for c in candidates:
        if len(selected) >= place_count:
            break
        category = c.place.category
        if category and category in seen_categories and len(candidates) - len(selected) > (
            place_count - len(selected)
        ):
            # 대체 후보가 충분할 때만 같은 카테고리 중복을 피한다.
            continue
        selected.append(c)
        if category:
            seen_categories.add(category)

    if len(selected) < place_count:
        # 다양성 필터로 부족해졌으면 남은 후보로 채운다.
        remaining = [c for c in candidates if c not in selected]
        selected.extend(remaining[: place_count - len(selected)])

    return selected[:place_count]


def haversine_m(p1: Place, p2: Place) -> float:
    r = 6371000.0
    lat1, lat2 = math.radians(p1.map_y), math.radians(p2.map_y)
    dlat = lat2 - lat1
    dlon = math.radians(p2.map_x - p1.map_x)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def order_by_route(selected: list[Candidate]) -> list[Candidate]:
    """이동거리를 고려한 단순 최근접 이웃(nearest-neighbor) 정렬.

    MVP 범위이므로 완전한 TSP 최적화는 하지 않는다 (3절).
    """

    if len(selected) <= 2:
        return selected

    remaining = list(selected)
    ordered = [remaining.pop(0)]
    while remaining:
        last = ordered[-1].place
        nxt = min(remaining, key=lambda c: haversine_m(last, c.place))
        ordered.append(nxt)
        remaining.remove(nxt)
    return ordered


def schedule_visits(
    ordered: list[Candidate], start_time: str, end_time: str
) -> list[PlanItem]:
    """시작~종료 시간 안에서 방문 시간을 배치한다.

    체류시간(Place.expected_stay_minutes, 없으면 기본값)을 누적하다가
    end_time을 넘기면 더 이상 담지 않는다 (방문 시간 범위 초과 방지).
    """

    fmt = "%H:%M"
    clock = datetime.strptime(start_time, fmt)
    end = datetime.strptime(end_time, fmt)

    items: list[PlanItem] = []
    for order, cand in enumerate(ordered, start=1):
        stay = cand.place.expected_stay_minutes or config.DEFAULT_STAY_MINUTES
        if clock >= end:
            break
        visit_time = clock.strftime(fmt)
        label = congestion_level_label(cand.rate)
        items.append(
            PlanItem(
                content_id=cand.place.content_id,
                name=cand.place.name,
                order=order,
                visit_time=visit_time,
                note=label,
                # note는 뒤에서 LLM 설명으로 덮일 수 있으므로 따로 남긴다.
                congestion_label=label,
                high_congestion=cand.rate is not None and cand.rate >= config.CONGESTION_THRESHOLD,
            )
        )
        clock += timedelta(minutes=stay)

    return items


def build_candidates(
    places: list[Place],
    congestion_map: dict[str, Congestion],
    travel_date: str,
    place_count: int,
) -> list[Candidate]:
    """4~7절 파이프라인: 집중률 결합 -> 정렬 -> 다양성 선택 -> 동선 정렬."""

    attached = attach_congestion(places, congestion_map, travel_date)
    scored = score_candidates(attached)
    selected = select_diverse(scored, place_count)
    return order_by_route(selected)


def default_summary() -> str:
    """LLM 없이도 쓸 수 있는 기본 문구 (10절)."""

    return "선택한 날짜의 예측 집중률과 이동 거리를 고려해 구성한 일정입니다."
