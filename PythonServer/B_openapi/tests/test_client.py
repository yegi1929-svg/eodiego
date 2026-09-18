"""실제 tatsCnctrRatedList 응답 예시(사용자 제공)를 기준으로 한 회귀 테스트.

요청 예:
  GET https://apis.data.go.kr/B551011/TatsCnctrRateService/tatsCnctrRatedList
      ?serviceKey=...&pageNo=1&numOfRows=10&MobileOS=ETC&MobileApp=AppTest
      &areaCd=50&signguCd=50110&tAtsNm=신산공원&_type=json

응답 예 (10개 날짜, 신산공원 하나):
  {"response": {"header": {"resultCode": "0000", "resultMsg": "OK"},
    "body": {"items": {"item": [
      {"baseYmd": "20260902", ..., "tAtsNm": "신산공원", "cnctrRate": "42.33"},
      ...
    ]}, "numOfRows": 10, "pageNo": 1, "totalCount": 30}}}
"""

import asyncio

import httpx
import pytest

from B_openapi import client, config, service
from shared.schemas import Place

SAMPLE_ITEMS = [
    {"baseYmd": "20260902", "areaCd": "50", "areaNm": "제주특별자치도", "signguCd": "50110", "signguNm": "제주시", "tAtsNm": "신산공원", "cnctrRate": "42.33"},
    {"baseYmd": "20260903", "areaCd": "50", "areaNm": "제주특별자치도", "signguCd": "50110", "signguNm": "제주시", "tAtsNm": "신산공원", "cnctrRate": "41.7"},
    {"baseYmd": "20260904", "areaCd": "50", "areaNm": "제주특별자치도", "signguCd": "50110", "signguNm": "제주시", "tAtsNm": "신산공원", "cnctrRate": "57.68"},
    {"baseYmd": "20260905", "areaCd": "50", "areaNm": "제주특별자치도", "signguCd": "50110", "signguNm": "제주시", "tAtsNm": "신산공원", "cnctrRate": "86.63"},
]

SAMPLE_PAYLOAD = {
    "response": {
        "header": {"resultCode": "0000", "resultMsg": "OK"},
        "body": {"items": {"item": SAMPLE_ITEMS}, "numOfRows": 10, "pageNo": 1, "totalCount": 30},
    }
}


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _FakeAsyncClient:
    is_closed = False

    def __init__(self, captured: dict, payload: dict, status_code: int = 200, **kwargs):
        self._captured = captured
        self._payload = payload
        self._status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None, timeout=None):
        self._captured["url"] = url
        self._captured["params"] = params
        return _FakeResponse(self._payload, self._status_code)


def test_fetch_congestion_candidates_sends_expected_params(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(client, "_shared_client", None)
    monkeypatch.setattr(client.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient(captured, SAMPLE_PAYLOAD))
    monkeypatch.setattr(config, "KTO_SERVICE_KEY", "TEST_KEY")

    items = asyncio.run(client.fetch_congestion_candidates("신산공원", "50", "50110"))

    assert captured["url"] == f"{config.KTO_CONGESTION_BASE_URL}/tatsCnctrRatedList"
    assert captured["params"]["tAtsNm"] == "신산공원"
    assert captured["params"]["areaCd"] == "50"
    assert captured["params"]["signguCd"] == "50110"
    assert captured["params"]["serviceKey"] == "TEST_KEY"
    assert len(items) == 4
    assert items[0]["cnctrRate"] == "42.33"


def test_result_code_error_raises_upstream_api_error(monkeypatch):
    error_payload = {"response": {"header": {"resultCode": "30", "resultMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}}}
    monkeypatch.setattr(client, "_shared_client", None)
    monkeypatch.setattr(client.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient({}, error_payload))

    from B_openapi.exceptions import UpstreamAPIError

    with pytest.raises(UpstreamAPIError):
        asyncio.run(client.fetch_congestion_candidates("신산공원", "50", "50110"))


def test_get_congestion_for_place_groups_daily_rows_from_real_shape(monkeypatch):
    async def fake_fetch(t_ats_nm, area_cd, signgu_cd):
        return SAMPLE_ITEMS

    monkeypatch.setattr(config, "USE_MOCK", False)
    monkeypatch.setattr(service, "fetch_congestion_candidates", fake_fetch)

    place = Place(content_id="1", name="신산공원", addr="", map_x=126.5, map_y=33.5, dist=0.0, image=None)
    congestion = asyncio.run(service.get_congestion_for_place(place, "50", "110"))

    assert congestion.has_data is True
    assert len(congestion.daily) == 4
    assert congestion.daily[0].date == "20260902"
    assert congestion.daily[0].rate == 42.33
    assert congestion.daily[3].rate == 86.63


# --- 실제 API에서 관측한 응답 형태 회귀 테스트 -------------------------------

EMPTY_PAYLOAD = {
    "response": {
        "header": {"resultCode": "0000", "resultMsg": "OK"},
        # 결과 0건이면 items가 dict가 아니라 빈 문자열로 온다.
        "body": {"items": "", "numOfRows": 0, "pageNo": 1, "totalCount": 0},
    }
}

GATEWAY_ERROR_PAYLOAD = {
    "responseTime": "2026-09-04T11:46:29.977",
    "resultCode": "11",
    "resultMsg": "NO_MANDATORY_REQUEST_PARAMETERS_ERROR1(areaCd)",
}

SINGLE_ITEM_PAYLOAD = {
    "response": {
        "header": {"resultCode": "0000", "resultMsg": "OK"},
        # 결과가 1건이면 item이 list가 아니라 dict로 온다.
        "body": {"items": {"item": SAMPLE_ITEMS[0]}, "numOfRows": 1, "pageNo": 1, "totalCount": 1},
    }
}


def test_empty_items_string_returns_empty_list(monkeypatch):
    monkeypatch.setattr(client, "_shared_client", None)
    monkeypatch.setattr(client.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient({}, EMPTY_PAYLOAD))
    assert asyncio.run(client.fetch_congestion_candidates("없는곳", "50", "50110")) == []
    assert asyncio.run(client.fetch_location_based_list(126.5, 33.5, 1000)) == []


def test_empty_items_string_on_detail_raises_payload_error(monkeypatch):
    monkeypatch.setattr(client, "_shared_client", None)
    monkeypatch.setattr(client.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient({}, EMPTY_PAYLOAD))

    from B_openapi.exceptions import InvalidUpstreamPayloadError

    with pytest.raises(InvalidUpstreamPayloadError):
        asyncio.run(client.fetch_place_detail("9999"))


def test_top_level_result_code_error_raises(monkeypatch):
    """필수 파라미터 누락은 최상위 resultCode로 온다 - 데이터 없음으로 삼키면 안 된다."""
    monkeypatch.setattr(client, "_shared_client", None)
    monkeypatch.setattr(client.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient({}, GATEWAY_ERROR_PAYLOAD))

    from B_openapi.exceptions import UpstreamAPIError

    with pytest.raises(UpstreamAPIError):
        asyncio.run(client.fetch_congestion_candidates("신산공원", "50", "50110"))


def test_single_item_dict_is_wrapped_in_list(monkeypatch):
    monkeypatch.setattr(client, "_shared_client", None)
    monkeypatch.setattr(client.httpx, "AsyncClient", lambda **kw: _FakeAsyncClient({}, SINGLE_ITEM_PAYLOAD))
    items = asyncio.run(client.fetch_congestion_candidates("신산공원", "50", "50110"))
    assert len(items) == 1
    assert items[0]["tAtsNm"] == "신산공원"
