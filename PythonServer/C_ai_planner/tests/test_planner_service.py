"""일정 생성/재추천이 B를 어떻게 부르는지 검증한다.

핵심: 상세정보(관광지당 관광공사 API 2회)는 후보 전체가 아니라 최종 일정에
뽑힌 장소만 조회해야 한다.
"""

import asyncio

from shared.schemas import Congestion, Place, Plan, PlanItem, PlanRequest, ReplanRequest

from C_ai_planner import b_client, planner_service


def _place(i: int, dist: float | None = None, x: float = 126.5, y: float = 33.5) -> Place:
    return Place(
        content_id=str(i), name=f"장소{i}", addr="제주", map_x=x + i * 0.001, map_y=y,
        dist=dist if dist is not None else 100.0 * (i + 1),
    )


def _detail(cid: str) -> Place:
    return Place(
        content_id=cid, name=f"장소{cid}", addr="제주", map_x=126.5, map_y=33.5, dist=0.0,
        overview="소개문", use_time="상시 개방", rest_date="연중무휴",
    )


def _install_fakes(monkeypatch, candidates, detail_error=None):
    calls = {"nearby": [], "details": []}

    async def fake_nearby(map_x, map_y, radius=None):
        calls["nearby"].append(radius)
        return candidates

    async def fake_congestion(places, area_cd="50", l_dong_signgu_cd="110"):
        return {p.content_id: Congestion(content_id=p.content_id, name=p.name, daily=[], has_data=False) for p in places}

    async def fake_details(content_ids):
        calls["details"].append(list(content_ids))
        if detail_error:
            raise detail_error
        return {cid: _detail(cid) for cid in content_ids}

    monkeypatch.setattr(b_client, "get_nearby_places", fake_nearby)
    monkeypatch.setattr(b_client, "get_congestion_map", fake_congestion)
    monkeypatch.setattr(b_client, "get_place_details", fake_details)
    return calls


def _request(place_count: int) -> PlanRequest:
    return PlanRequest(
        map_x=126.5, map_y=33.5, travel_date="20260920",
        start_time="09:00", end_time="18:00", place_count=place_count,
    )


def test_generate_plan_fetches_details_only_for_selected_places(monkeypatch):
    candidates = [_place(i) for i in range(20)]
    calls = _install_fakes(monkeypatch, candidates)

    plan = asyncio.run(planner_service.generate_plan(_request(place_count=3)))

    assert len(plan.items) == 3
    # 후보 20곳이 아니라 뽑힌 3곳만, 한 번에 조회한다.
    assert len(calls["details"]) == 1
    assert sorted(calls["details"][0]) == sorted(i.content_id for i in plan.items)
    assert all(i.detail is not None and i.detail.use_time == "상시 개방" for i in plan.items)


def test_generate_plan_does_not_pin_search_radius(monkeypatch):
    """반경은 공통 계약(LocationReq)의 기본값 한 곳에서 정한다 - C가 따로 값을 박지 않는다."""
    calls = _install_fakes(monkeypatch, [_place(i) for i in range(5)])
    asyncio.run(planner_service.generate_plan(_request(place_count=3)))
    assert calls["nearby"] == [None]


def test_generate_plan_survives_detail_failure(monkeypatch):
    calls = _install_fakes(
        monkeypatch, [_place(i) for i in range(5)], detail_error=b_client.BServiceError("boom")
    )
    plan = asyncio.run(planner_service.generate_plan(_request(place_count=3)))
    assert len(plan.items) == 3
    assert all(i.detail is None for i in plan.items)
    assert len(calls["details"]) == 1


def test_generate_plan_with_no_candidates_skips_detail_lookup(monkeypatch):
    calls = _install_fakes(monkeypatch, [])
    plan = asyncio.run(planner_service.generate_plan(_request(place_count=3)))
    assert plan.items == []
    assert calls["details"] == []


def test_replan_reuses_target_detail_and_fetches_only_replacement(monkeypatch):
    # 교체 후보: 기존 일정(1, 2)과 겹치지 않는 가까운 장소 3
    candidates = [_place(1), _place(2), _place(3, dist=50.0)]
    calls = _install_fakes(monkeypatch, candidates)

    plan = Plan(
        title="t", travel_date="20260920", summary="s",
        items=[
            PlanItem(content_id="1", name="장소1", order=1, visit_time="09:00", detail=_detail("1")),
            PlanItem(content_id="2", name="장소2", order=2, visit_time="10:00", detail=_detail("2")),
        ],
    )
    resp = asyncio.run(planner_service.replan(ReplanRequest(plan=plan, target_content_id="1", reason="예측 집중률 높음")))

    assert resp.replaced_content_id == "3"
    # 대상 좌표는 기존 상세정보를 재사용하고, 새로 들어온 장소만 상세조회한다.
    assert calls["details"] == [["3"]]
    # 대체 후보 검색은 교체 허용 거리까지만 본다.
    assert calls["nearby"] == [int(planner_service.config.MAX_REPLAN_DISTANCE_DELTA_M)]

    by_id = {i.content_id: i for i in resp.plan.items}
    assert by_id["3"].detail is not None
    assert by_id["2"].detail is not None
    assert by_id["3"].congestion_label is not None


def test_replan_fetches_target_detail_when_missing(monkeypatch):
    candidates = [_place(1), _place(3, dist=50.0)]
    calls = _install_fakes(monkeypatch, candidates)
    plan = Plan(
        title="t", travel_date="20260920", summary="s",
        items=[PlanItem(content_id="1", name="장소1", order=1, visit_time="09:00")],
    )
    asyncio.run(planner_service.replan(ReplanRequest(plan=plan, target_content_id="1", reason="r")))
    assert calls["details"][0] == ["1"]


def test_b_client_omits_radius_so_contract_default_applies(monkeypatch):
    """반경을 안 주면 요청 본문에 계약 기본값(5000)이 실린다 - None을 보내면 422."""
    captured = {}

    class _Resp:
        status_code = 200

        def json(self):
            return []

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None):
            captured["json"] = json
            return _Resp()

    monkeypatch.setattr(b_client.httpx, "AsyncClient", _Client)
    asyncio.run(b_client.get_nearby_places(126.5, 33.5))
    assert captured["json"]["radius"] == 5000
