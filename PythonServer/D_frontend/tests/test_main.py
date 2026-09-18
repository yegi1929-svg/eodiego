from fastapi.testclient import TestClient

from D_frontend import main
from D_frontend.api_client.errors import UpstreamUnavailableError

client = TestClient(main.app)


def test_login_success_forwards_cookie(monkeypatch):
    async def fake_login(username, password):
        return {"user_id": 1, "username": username}, "token-abc"

    monkeypatch.setattr(main.auth_client, "login", fake_login)
    resp = client.post("/ui/auth/login", json={"username": "alice", "password": "pw"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert "session_id" in resp.cookies


def test_places_nearby_empty_result():
    async def fake_nearby(map_x, map_y, radius):
        return []

    import D_frontend.main as m

    orig = m.places_client.nearby
    m.places_client.nearby = fake_nearby
    try:
        resp = client.post("/ui/places/nearby", json={"map_x": 126.5, "map_y": 33.45, "radius": 1000})
        body = resp.json()
        assert body["status"] == "empty"
    finally:
        m.places_client.nearby = orig


def test_places_nearby_upstream_failure_returns_friendly_message():
    async def failing_nearby(map_x, map_y, radius):
        raise UpstreamUnavailableError("B", "boom")

    import D_frontend.main as m

    orig = m.places_client.nearby
    m.places_client.nearby = failing_nearby
    try:
        resp = client.post("/ui/places/nearby", json={"map_x": 126.5, "map_y": 33.45, "radius": 1000})
        body = resp.json()
        assert body["status"] == "error"
        assert "관광지 정보를 불러오지 못했습니다" in body["data"]["message"]
    finally:
        m.places_client.nearby = orig


def test_generate_plan_wraps_display_context():
    async def fake_generate_plan(req):
        return {
            "title": "제주 1일 코스", "travel_date": "20260828", "summary": "s",
            "items": [{"content_id": "1", "order": 1, "visit_time": "10:00", "name": "보덕사", "note": "예측 집중률 높음"}],
        }

    import D_frontend.main as m

    orig = m.plans_client.generate_plan
    m.plans_client.generate_plan = fake_generate_plan
    try:
        resp = client.post(
            "/ui/plan/generate",
            json={"map_x": 126.5, "map_y": 33.45, "travel_date": "20260828", "start_time": "10:00", "end_time": "18:00", "place_count": 3},
        )
        body = resp.json()
        assert body["status"] == "success"
        assert body["data"]["items"][0]["high_congestion"] is True
    finally:
        m.plans_client.generate_plan = orig


def test_save_plan_requires_login_error_is_friendly():
    from D_frontend.api_client.errors import UpstreamRejectedError

    async def failing_save(token, req):
        raise UpstreamRejectedError("A", 401, "AUTH_REQUIRED", "로그인이 필요합니다.")

    import D_frontend.main as m

    orig = m.plans_client.save_plan
    m.plans_client.save_plan = failing_save
    try:
        resp = client.post(
            "/ui/plans",
            json={"title": "t", "travel_date": "20260828", "items": []},
        )
        body = resp.json()
        assert body["status"] == "error"
    finally:
        m.plans_client.save_plan = orig


def test_regions_returns_list_from_b():
    async def fake_regions():
        return [{"code": "jeju-si", "name": "제주시", "map_x": 126.5312, "map_y": 33.4996}]

    import D_frontend.main as m

    orig = m.places_client.regions
    m.places_client.regions = fake_regions
    try:
        body = client.get("/ui/regions").json()
        assert body["status"] == "success"
        assert body["data"][0]["name"] == "제주시"
        assert body["data"][0]["map_x"] == 126.5312
    finally:
        m.places_client.regions = orig


def test_regions_upstream_failure_returns_friendly_message():
    async def failing_regions():
        raise UpstreamUnavailableError("B", "boom")

    import D_frontend.main as m

    orig = m.places_client.regions
    m.places_client.regions = failing_regions
    try:
        body = client.get("/ui/regions").json()
        assert body["status"] == "error"
        assert "여행 지역 목록을 불러오지 못했습니다" in body["data"]["message"]
        assert body["data"]["retryable"] is True
    finally:
        m.places_client.regions = orig


def test_regions_empty_returns_empty_envelope():
    async def empty_regions():
        return []

    import D_frontend.main as m

    orig = m.places_client.regions
    m.places_client.regions = empty_regions
    try:
        body = client.get("/ui/regions").json()
        assert body["status"] == "empty"
    finally:
        m.places_client.regions = orig


# --- 500 대신 봉투로 응답하는지 -----------------------------------------------

def test_me_returns_envelope_when_a_is_down():
    """화면 최초 진입 API. 여기서 500이 나면 첫 화면부터 계약이 깨진다."""
    async def failing_me(token):
        raise UpstreamUnavailableError("A", "boom")

    import D_frontend.main as m

    orig = m.auth_client.me
    m.auth_client.me = failing_me
    try:
        resp = client.get("/ui/auth/me")
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"
    finally:
        m.auth_client.me = orig


def test_logout_clears_cookie_even_when_a_is_down():
    async def failing_logout(token):
        raise UpstreamUnavailableError("A", "boom")

    import D_frontend.main as m

    orig = m.auth_client.logout
    m.auth_client.logout = failing_logout
    try:
        resp = client.post("/ui/auth/logout", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
    finally:
        m.auth_client.logout = orig


def test_malformed_bodies_are_validation_errors_not_500():
    assert client.post("/ui/auth/login", json={}).status_code == 422
    assert client.post("/ui/auth/register", json={}).status_code == 422
    assert client.post("/ui/places/congestion", json={}).status_code == 422


def test_save_plan_without_login_tells_screen_to_show_login():
    from D_frontend.api_client.errors import UpstreamRejectedError

    async def failing_save(token, req):
        raise UpstreamRejectedError("A", 401, "AUTH_REQUIRED", "로그인이 필요합니다.")

    import D_frontend.main as m

    orig = m.plans_client.save_plan
    m.plans_client.save_plan = failing_save
    try:
        body = client.post("/ui/plans", json={"title": "t", "travel_date": "20260828", "items": []}).json()
        assert body["data"]["code"] == "AUTH_REQUIRED"
    finally:
        m.plans_client.save_plan = orig


def test_congestion_forwards_names_to_b():
    """이름을 그대로 B에 넘겨야 상세 재조회가 생략된다."""
    captured = {}

    async def fake_congestion(targets, area_cd, l_dong_signgu_cd):
        captured["targets"] = targets
        return {"1": {"content_id": "1", "name": "성산일출봉", "daily": [{"date": "20260828", "rate": 90.0}], "has_data": True}}

    import D_frontend.main as m

    orig = m.places_client.congestion
    m.places_client.congestion = fake_congestion
    try:
        body = client.post("/ui/places/congestion", json={
            "travel_date": "20260828",
            "targets": [{"content_id": "1", "name": "성산일출봉"}],
        }).json()
        assert body["status"] == "success"
        assert captured["targets"][0].name == "성산일출봉"
        assert body["data"]["1"]["is_high"] is True
    finally:
        m.places_client.congestion = orig


# --- 배포 대비: 쿠키 속성 / 게이트웨이 -----------------------------------------

def test_login_cookie_has_max_age(monkeypatch):
    """max_age가 없으면 세션 쿠키가 되어 브라우저를 닫을 때마다 로그아웃된다."""
    async def fake_login(username, password):
        return {"user_id": 1, "username": username}, "token-abc"

    import D_frontend.main as m

    monkeypatch.setattr(m.auth_client, "login", fake_login)
    resp = client.post("/ui/auth/login", json={"username": "a", "password": "pw"})
    set_cookie = resp.headers["set-cookie"]
    assert "Max-Age=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/" in set_cookie


def test_login_cookie_is_secure_when_configured(monkeypatch):
    async def fake_login(username, password):
        return {"user_id": 1, "username": username}, "token-abc"

    import D_frontend.main as m

    monkeypatch.setattr(m.auth_client, "login", fake_login)
    monkeypatch.setattr(m.config, "COOKIE_SECURE", True)
    resp = client.post("/ui/auth/login", json={"username": "a", "password": "pw"})
    assert "secure" in resp.headers["set-cookie"].lower()


def test_gateway_token_blocks_direct_calls(monkeypatch):
    """배포하면 D 주소가 공개된다 - 화면을 거치지 않은 호출은 막아야 한다."""
    import D_frontend.main as m

    monkeypatch.setattr(m.config, "GATEWAY_TOKEN", "s3cret")

    denied = client.get("/ui/auth/me")
    assert denied.status_code == 403
    assert denied.json()["data"]["code"] == "FORBIDDEN"

    wrong = client.get("/ui/auth/me", headers={"x-bff-token": "wrong"})
    assert wrong.status_code == 403


def test_gateway_token_allows_proxied_calls(monkeypatch):
    async def fake_me(token):
        return None

    import D_frontend.main as m

    monkeypatch.setattr(m.config, "GATEWAY_TOKEN", "s3cret")
    monkeypatch.setattr(m.auth_client, "me", fake_me)
    ok = client.get("/ui/auth/me", headers={"x-bff-token": "s3cret"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "success"


def test_gateway_check_is_off_when_token_unset(monkeypatch):
    """로컬 개발에서는 토큰 없이 그대로 동작해야 한다."""
    async def fake_me(token):
        return None

    import D_frontend.main as m

    monkeypatch.setattr(m.config, "GATEWAY_TOKEN", "")
    monkeypatch.setattr(m.auth_client, "me", fake_me)
    assert client.get("/ui/auth/me").status_code == 200


def test_places_client_does_not_send_null_radius(monkeypatch):
    """반경을 null로 보내면 B의 계약 검증(422)에 걸린다 - 없으면 아예 빼야 한다."""
    from D_frontend.api_client import _http, places

    captured = {}

    class _Resp:
        def json(self):
            return []

    async def fake_request(service, base_url, method, path, *, json=None, cookies=None):
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(_http, "request", fake_request)
    import asyncio

    asyncio.run(places.nearby(126.5, 33.5))
    assert "radius" not in captured["json"]
    asyncio.run(places.nearby(126.5, 33.5, 3000))
    assert captured["json"]["radius"] == 3000
