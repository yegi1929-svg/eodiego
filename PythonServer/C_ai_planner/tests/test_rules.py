from shared.schemas import Congestion, DayRate, Place

from C_ai_planner.rules import (
    attach_congestion,
    congestion_level_label,
    rate_for_date,
    schedule_visits,
    select_diverse,
)
from C_ai_planner.rules import order_by_route, score_candidates


def make_place(cid, name, dist, map_x=126.5, map_y=33.45, stay=60, category=None) -> Place:
    return Place(
        content_id=cid, name=name, addr="addr", map_x=map_x, map_y=map_y,
        dist=dist, image=None, expected_stay_minutes=stay, category=category,
    )


def test_rate_for_date_found():
    c = Congestion(content_id="1", name="A", has_data=True, daily=[DayRate(date="20260828", rate=80.0)])
    assert rate_for_date(c, "20260828") == 80.0


def test_rate_for_date_not_found():
    c = Congestion(content_id="1", name="A", has_data=True, daily=[DayRate(date="20260827", rate=80.0)])
    assert rate_for_date(c, "20260828") is None


def test_congestion_level_label_no_data():
    assert congestion_level_label(None) == "혼잡도 미제공"


def test_congestion_level_label_high():
    assert congestion_level_label(90.0) == "예측 집중률 높음"


def test_congestion_level_label_low():
    assert congestion_level_label(10.0) == "예측 집중률 낮음"


def test_attach_congestion_missing_data_not_excluded():
    place = make_place("1", "A", 100)
    candidates = attach_congestion([place], congestion_map={}, travel_date="20260828")
    assert len(candidates) == 1
    assert candidates[0].has_data is False


def test_select_diverse_returns_fewer_when_not_enough_candidates():
    places = [make_place(str(i), f"P{i}", i * 100) for i in range(2)]
    candidates = score_candidates(attach_congestion(places, {}, "20260828"))
    selected = select_diverse(candidates, place_count=5)
    assert len(selected) == 2  # place_count보다 후보가 적은 경우


def test_schedule_visits_stops_at_end_time():
    places = [make_place(str(i), f"P{i}", i * 100, stay=90) for i in range(5)]
    ordered = order_by_route(score_candidates(attach_congestion(places, {}, "20260828")))
    items = schedule_visits(ordered, "10:00", "12:00")
    # 90분씩이므로 10:00, 11:30 두 개만 담기고 그 다음은 end_time을 넘겨 제외된다.
    assert len(items) == 2
    assert items[0].visit_time == "10:00"
    assert items[1].visit_time == "11:30"
