import hashlib
import time
from types import SimpleNamespace

from shared.testing import make_unique_name
from shared import database
from shared.schemas import Place

from A_backend import auth, b_client, config

PASSWORD = "password123"


def _register_and_login(client, username=None):
    username = username or make_unique_name("user")
    client.post("/auth/register", json={"username": username, "password": PASSWORD})
    client.post("/auth/login", json={"username": username, "password": PASSWORD})
    return client.get("/auth/me").json()["user_id"]


def _sample_plan_payload():
    return {
        "title": "제주 1일 코스",
        "travel_date": "20260828",
        "items": [
            {"content_id": "126508", "name": "보덕사", "order": 1, "visit_time": "10:00", "note": None},
            {"content_id": "126509", "name": "제주민속자연사박물관", "order": 2, "visit_time": "12:00", "note": None},
        ],
    }


def test_guest_cannot_save_plan_requires_login(client):
    resp = client.post("/plans", json=_sample_plan_payload())
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_REQUIRED"


def test_save_and_list_plan(client):
    _register_and_login(client)
    save_resp = client.post("/plans", json=_sample_plan_payload())
    assert save_resp.status_code == 201
    plan_id = save_resp.json()["plan_id"]

    list_resp = client.get("/plans")
    assert list_resp.status_code == 200
    saved = next(p for p in list_resp.json() if p["plan_id"] == plan_id)
    # 순서와 항목이 그대로 저장/조회되는지 (plan_item.item_order)
    assert [i["content_id"] for i in saved["items"]] == ["126508", "126509"]
    assert [i["order"] for i in saved["items"]] == [1, 2]


def test_get_plan_detail_merges_live_place_info(client, monkeypatch):
    _register_and_login(client)
    save_resp = client.post("/plans", json=_sample_plan_payload())
    plan_id = save_resp.json()["plan_id"]

    calls = []

    async def fake_get_place_details(content_ids):
        calls.append(list(content_ids))
        return {
            cid: Place(content_id=cid, name="현재이름", addr="현재주소", map_x=1.0, map_y=1.0, dist=0.0, image=None)
            for cid in content_ids
        }

    monkeypatch.setattr(b_client, "get_place_details", fake_get_place_details)

    detail_resp = client.get(f"/plans/{plan_id}")
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body["items"][0]["current"]["name"] == "현재이름"
    # 장소마다 따로 부르지 않고 저장된 장소를 한 번에 조회해야 한다.
    assert len(calls) == 1
    assert calls[0] == [i["content_id"] for i in body["items"]]


def test_get_plan_detail_survives_b_failure(client, monkeypatch):
    _register_and_login(client)
    save_resp = client.post("/plans", json=_sample_plan_payload())
    plan_id = save_resp.json()["plan_id"]

    async def failing_get_place_details(content_ids):
        raise b_client.BServiceError("boom")

    monkeypatch.setattr(b_client, "get_place_details", failing_get_place_details)

    detail_resp = client.get(f"/plans/{plan_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["items"][0]["current"] is None


def test_delete_plan_records_deletion_instead_of_deleting(client):
    """앱 계정은 DELETE 권한이 없다 - 삭제 기록을 추가하고 조회에서 뺀다."""
    _register_and_login(client)
    plan_id = client.post("/plans", json=_sample_plan_payload()).json()["plan_id"]

    assert client.delete(f"/plans/{plan_id}").status_code == 204

    get_resp = client.get(f"/plans/{plan_id}")
    assert get_resp.status_code == 404
    assert get_resp.json()["error"]["code"] == "NOT_FOUND"
    assert all(p["plan_id"] != plan_id for p in client.get("/plans").json())

    with database.transaction() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM `plan` WHERE `plan_id` = %s", (plan_id,))
        assert cur.fetchone()["n"] == 1  # 원본은 남아 있고
        cur.execute("SELECT COUNT(*) AS n FROM `plan_deletion` WHERE `plan_id` = %s", (plan_id,))
        assert cur.fetchone()["n"] == 1  # 삭제 기록이 추가됐다

    # 두 번 삭제하면 이미 없는 일정이다.
    assert client.delete(f"/plans/{plan_id}").status_code == 404


def test_nonexistent_plan_id_returns_404(client):
    _register_and_login(client)
    resp = client.get("/plans/999999999")
    assert resp.status_code == 404


def test_expired_session_is_rejected(client, monkeypatch):
    _register_and_login(client)
    # 세션 만료 시각이 지난 것처럼 인증 모듈의 시계만 앞으로 돌린다.
    future = time.time() + config.SESSION_TTL_SECONDS + 60
    monkeypatch.setattr(auth, "time", SimpleNamespace(time=lambda: future))

    resp = client.get("/plans")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "SESSION_EXPIRED"


def test_cannot_access_other_users_plan(client):
    _register_and_login(client)
    plan_id = client.post("/plans", json=_sample_plan_payload()).json()["plan_id"]
    client.post("/auth/logout")

    _register_and_login(client)
    assert client.get(f"/plans/{plan_id}").status_code == 404
    # 남의 일정은 삭제 기록도 남길 수 없다.
    assert client.delete(f"/plans/{plan_id}").status_code == 404


# --- 세션이 프로세스 메모리가 아니라 DB에 있는지 --------------------------------


def test_session_is_persisted_in_db(client):
    """서버를 재시작해도 로그인이 유지되려면 세션이 DB에 있어야 한다."""
    user_id = _register_and_login(client)
    with database.transaction() as cur:
        cur.execute("SELECT `token_hash`, `expires_at` FROM `session` WHERE `user_id` = %s", (user_id,))
        rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0]["expires_at"] is not None


def test_session_token_is_not_stored_in_plaintext(client):
    """DB가 유출돼도 저장된 값만으로 로그인할 수 없어야 한다."""
    _register_and_login(client)
    token = client.cookies.get("session_id")
    assert token
    with database.transaction() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM `session` WHERE `token_hash` = %s", (token,))
        assert cur.fetchone()["n"] == 0
        cur.execute(
            "SELECT COUNT(*) AS n FROM `session` WHERE `token_hash` = %s",
            (hashlib.sha256(token.encode()).hexdigest(),),
        )
        assert cur.fetchone()["n"] == 1


def test_logout_records_revocation(client):
    """앱 계정은 DELETE 권한이 없다 - 세션을 지우지 않고 폐기 기록을 추가한다."""
    _register_and_login(client)
    token_hash = hashlib.sha256(client.cookies.get("session_id").encode()).hexdigest()
    client.post("/auth/logout")

    with database.transaction() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM `session` WHERE `token_hash` = %s", (token_hash,))
        assert cur.fetchone()["n"] == 1
        cur.execute("SELECT COUNT(*) AS n FROM `session_revocation` WHERE `token_hash` = %s", (token_hash,))
        assert cur.fetchone()["n"] == 1


def test_logout_with_unknown_cookie_does_not_add_records(client):
    """아무 쿠키 값으로 로그아웃을 불러 기록을 쌓을 수 없어야 한다."""
    fake = make_unique_name("fake")
    client.cookies.set("session_id", fake)
    client.post("/auth/logout")
    with database.transaction() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM `session_revocation` WHERE `token_hash` = %s",
            (hashlib.sha256(fake.encode()).hexdigest(),),
        )
        assert cur.fetchone()["n"] == 0
