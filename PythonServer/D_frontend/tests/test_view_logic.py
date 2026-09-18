from D_frontend import view_logic
from D_frontend.api_client.errors import UpstreamRejectedError, UpstreamUnavailableError


def test_congestion_label_no_data():
    assert view_logic.congestion_label(None, has_data=False) == "혼잡도 예측 정보 없음"


def test_congestion_label_high():
    assert view_logic.congestion_label(90.0, has_data=True) == "예측 집중률 높음"


def test_congestion_label_never_says_realtime():
    for rate in (0.0, 50.0, 100.0, None):
        label = view_logic.congestion_label(rate, has_data=rate is not None)
        assert "실시간" not in label
        assert "지금" not in label


def test_is_high_congestion_respects_threshold():
    assert view_logic.is_high_congestion(70.0, True) is True
    assert view_logic.is_high_congestion(69.9, True) is False
    assert view_logic.is_high_congestion(95.0, False) is False


def test_plan_display_context_flags_high_congestion_item():
    plan = {
        "title": "t", "summary": "s", "travel_date": "20260828",
        "items": [
            {"content_id": "1", "order": 1, "visit_time": "10:00", "name": "A", "note": "예측 집중률 높음"},
            {"content_id": "2", "order": 2, "visit_time": "12:00", "name": "B", "note": "예측 집중률 낮음"},
        ],
    }
    result = view_logic.plan_display_context(plan)
    assert result["items"][0]["high_congestion"] is True
    assert "replan_prompt" in result["items"][0]
    assert result["items"][1]["high_congestion"] is False
    assert "replan_prompt" not in result["items"][1]


def test_plan_display_context_missing_note_falls_back():
    plan = {
        "title": "t", "summary": "s", "travel_date": "20260828",
        "items": [{"content_id": "1", "order": 1, "visit_time": "10:00", "name": "A", "note": None}],
    }
    result = view_logic.plan_display_context(plan)
    assert result["items"][0]["note"] == "혼잡도 예측 정보 없음"


def test_error_context_session_expired_message():
    exc = UpstreamRejectedError("A", 401, "SESSION_EXPIRED", "만료됨")
    ctx = view_logic.error_context("generic", exc)
    assert "다시 로그인" in ctx["message"]


def test_error_context_timeout_is_retryable():
    exc = UpstreamUnavailableError("B", "timeout")
    ctx = view_logic.error_context("places_nearby", exc)
    assert ctx["retryable"] is True
    assert "관광지 정보를 불러오지 못했습니다" in ctx["message"]


# --- 에러 코드 전달 / 집중률 분리 ---------------------------------------------

def test_error_context_carries_code_for_auth_required():
    """화면이 "로그인 필요"와 "서버 오류"를 구분할 수 있어야 한다."""
    exc = UpstreamRejectedError("A", 401, "AUTH_REQUIRED", "로그인이 필요합니다.")
    ctx = view_logic.error_context("plan_save", exc)
    assert ctx["code"] == "AUTH_REQUIRED"
    assert "로그인" in ctx["message"]


def test_error_context_duplicate_user_is_not_a_login_message():
    exc = UpstreamRejectedError("A", 409, "DUPLICATE_USER", "중복")
    ctx = view_logic.error_context("register", exc)
    assert "이미 사용 중인 아이디" in ctx["message"]
    assert "비밀번호" not in ctx["message"]


def test_error_context_without_code_uses_context_message():
    exc = UpstreamUnavailableError("B", "boom")
    ctx = view_logic.error_context("places_nearby", exc)
    assert ctx["code"] is None
    assert "관광지 정보를 불러오지 못했습니다" in ctx["message"]


def test_plan_display_context_uses_explicit_congestion_fields():
    """note가 LLM 문구로 덮여도 집중률 판정이 살아 있어야 한다."""
    plan = {
        "title": "t", "summary": "s", "travel_date": "20260828",
        "items": [{
            "content_id": "1", "order": 1, "visit_time": "10:00", "name": "성산일출봉",
            "note": "성산일출봉 방문을 추천합니다.",
            "congestion_label": "예측 집중률 높음", "high_congestion": True,
        }],
    }
    item = view_logic.plan_display_context(plan)["items"][0]
    assert item["high_congestion"] is True
    assert item["congestion_label"] == "예측 집중률 높음"
    assert item["note"] == "성산일출봉 방문을 추천합니다."
    assert "replan_prompt" in item


def test_plan_display_context_passes_selected_place_detail():
    detail = {"content_id": "1", "name": "A", "addr": "제주", "map_x": 1.0, "map_y": 1.0, "dist": 0.0,
              "use_time": "상시 개방", "rest_date": "연중무휴", "overview": "소개"}
    plan = {
        "title": "t", "summary": "s", "travel_date": "20260920",
        "items": [
            {"content_id": "1", "order": 1, "visit_time": "10:00", "name": "A", "note": "n", "detail": detail},
            {"content_id": "2", "order": 2, "visit_time": "11:00", "name": "B", "note": "n"},
        ],
    }
    items = view_logic.plan_display_context(plan)["items"]
    assert items[0]["detail"]["use_time"] == "상시 개방"
    assert items[1]["detail"] is None
