"""일정 저장/조회/삭제 (A_backend_auth.md 5절).

저장 일정 상세 조회 흐름:
DB -> content_id 목록 조회 -> B의 실시간 관광정보 조회 -> 현재 관광공사
데이터와 결합 -> D에 반환. DB에서 관광공사 상세정보를 직접 가져오지 않는다.
"""

from __future__ import annotations

from pydantic import BaseModel

from shared.schemas import Place, SavedPlan, SavePlanRequest

from . import b_client, db
from .errors import PlanNotFoundError


class PlanDetailItem(BaseModel):
    content_id: str
    name: str
    order: int
    visit_time: str
    note: str | None
    current: Place | None  # B에서 재조회한 현재 관광지 정보. 조회 실패 시 None.


class PlanDetail(BaseModel):
    plan_id: int
    title: str
    travel_date: str
    items: list[PlanDetailItem]


def save_plan(user_id: int, req: SavePlanRequest) -> SavedPlan:
    plan_id = db.create_plan(user_id, req.title, req.travel_date, req.items)
    return SavedPlan(plan_id=plan_id, title=req.title, travel_date=req.travel_date, items=req.items)


def list_plans(user_id: int) -> list[SavedPlan]:
    return db.list_plans(user_id)


async def get_plan_detail(user_id: int, plan_id: int) -> PlanDetail:
    saved = db.get_plan(user_id, plan_id)
    if saved is None:
        raise PlanNotFoundError(f"plan_id={plan_id} 를 찾을 수 없습니다.")

    # 저장된 장소만, 한 번에(B가 병렬로) 조회한다.
    try:
        current_by_id = await b_client.get_place_details([i.content_id for i in saved.items])
    except b_client.BServiceError:
        # B 호출이 실패해도 저장된 기본 정보로는 화면을 계속 보여준다.
        current_by_id = {}

    detail_items: list[PlanDetailItem] = [
        PlanDetailItem(
            content_id=item.content_id, name=item.name, order=item.order,
            visit_time=item.visit_time, note=item.note,
            current=current_by_id.get(item.content_id),
        )
        for item in saved.items
    ]

    return PlanDetail(
        plan_id=saved.plan_id, title=saved.title, travel_date=saved.travel_date, items=detail_items
    )


def delete_plan(user_id: int, plan_id: int) -> None:
    deleted = db.delete_plan(user_id, plan_id)
    if not deleted:
        raise PlanNotFoundError(f"plan_id={plan_id} 를 찾을 수 없습니다.")
