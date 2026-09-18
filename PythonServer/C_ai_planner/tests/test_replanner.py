import pytest

from shared.schemas import Congestion, DayRate, Place, Plan, PlanItem

from C_ai_planner.replanner import NoReplacementCandidateError, apply_replacement, find_replacement


def make_place(cid, name, dist, map_x=126.5, map_y=33.45) -> Place:
    return Place(content_id=cid, name=name, addr="addr", map_x=map_x, map_y=map_y, dist=dist, image=None)


def make_congestion(cid, name, rate) -> Congestion:
    if rate is None:
        return Congestion(content_id=cid, name=name, has_data=False, daily=[])
    return Congestion(content_id=cid, name=name, has_data=True, daily=[DayRate(date="20260828", rate=rate)])


def base_plan():
    return Plan(
        title="t", travel_date="20260828",
        items=[PlanItem(content_id="A", name="A", order=1, visit_time="10:00", note=None)],
        summary="s",
    )


def test_find_replacement_prefers_under_threshold():
    target = make_place("A", "A", 0)
    candidates = [make_place("B", "B", 100), make_place("C", "C", 200)]
    congestion_map = {"B": make_congestion("B", "B", 90.0), "C": make_congestion("C", "C", 20.0)}
    result = find_replacement(base_plan(), target, candidates, congestion_map, "20260828")
    assert result.place.content_id == "C"


def test_find_replacement_falls_back_to_no_data():
    target = make_place("A", "A", 0)
    candidates = [make_place("B", "B", 100)]
    congestion_map = {"B": make_congestion("B", "B", None)}
    result = find_replacement(base_plan(), target, candidates, congestion_map, "20260828")
    assert result.place.content_id == "B"
    assert result.has_data is False


def test_find_replacement_raises_when_no_candidate():
    target = make_place("A", "A", 0)
    congestion_map = {"B": make_congestion("B", "B", 95.0)}
    with pytest.raises(NoReplacementCandidateError):
        find_replacement(base_plan(), target, [make_place("B", "B", 100)], congestion_map, "20260828")


def test_find_replacement_excludes_existing_plan_items():
    target = make_place("A", "A", 0)
    congestion_map = {"A": make_congestion("A", "A", 10.0)}
    with pytest.raises(NoReplacementCandidateError):
        find_replacement(base_plan(), target, [make_place("A", "A", 0)], congestion_map, "20260828")


def test_apply_replacement_preserves_order_and_time():
    plan = base_plan()
    target = make_place("A", "A", 0)
    congestion_map = {"B": make_congestion("B", "B", 20.0)}
    replacement = find_replacement(plan, target, [make_place("B", "B", 100)], congestion_map, "20260828")
    new_plan = apply_replacement(plan, "A", replacement, "테스트 사유")
    assert new_plan.items[0].content_id == "B"
    assert new_plan.items[0].order == 1
    assert new_plan.items[0].visit_time == "10:00"
    assert "테스트 사유" in new_plan.summary
