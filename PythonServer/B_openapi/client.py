"""한국관광공사 실제 OpenAPI 호출 (B_openapi.md 5, 6, 9절).

- 모든 호출에 timeout을 둔다.
- retry는 무한 재시도하지 않는다 (config.MAX_RETRY 만큼만).
- timeout / HTTP 오류 / 정상+데이터없음을 명확히 구분해서 예외를 던진다.
- 브라우저 좌표는 여기서도 로그로 남기지 않는다.

base URL/응답 형식은 팀이 확정했다:
  - 국문 관광정보 서비스: config.KTO_BASE_URL (KorService2)
  - 관광지 예측 집중률 서비스: config.KTO_CONGESTION_BASE_URL (TatsCnctrRateService),
    operation=tatsCnctrRatedList. 실제 응답 예:
        {"response": {"header": {"resultCode": "0000", "resultMsg": "OK"},
          "body": {"items": {"item": [
            {"baseYmd": "20260902", "areaCd": "50", "areaNm": "제주특별자치도",
             "signguCd": "50110", "signguNm": "제주시", "tAtsNm": "신산공원",
             "cnctrRate": "42.33"}, ...
          ]}, "numOfRows": 10, "pageNo": 1, "totalCount": 30}}}
    이 API는 공공데이터포털 관례대로 HTTP 200이어도 body.header.resultCode가
    "0000"이 아니면 API 레벨 오류다 - _check_result_header()에서 이를
    UpstreamAPIError로 변환한다.

TODO: locationBasedList2/detailCommon2의 정확한 응답 필드는 실제 국문
관광정보 서비스 명세를 받는 대로 확정한다 (지금은 TourAPI4.0의 통상적인
필드명을 기준으로 한 골격). 값이 다르면 이 파일만 수정하면 되고
service.py 이상은 영향받지 않는다.
"""

from __future__ import annotations

import httpx

from . import config, metrics
from .exceptions import InvalidUpstreamPayloadError, UpstreamAPIError, UpstreamTimeoutError


_shared_client: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    """관광공사 API 호출용 공유 클라이언트.

    호출마다 AsyncClient를 새로 만들면 TLS 핸드셰이크를 매번 다시 한다.
    실측으로 8건 병렬 기준 1.22초 -> 0.16초 차이가 났다. 동시 연결 수는
    상대 서버를 두드리지 않도록 제한해 둔다.
    """

    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=config.REQUEST_TIMEOUT_SECONDS,
            limits=httpx.Limits(
                max_connections=config.MAX_CONCURRENT_UPSTREAM,
                max_keepalive_connections=config.MAX_CONCURRENT_UPSTREAM,
            ),
        )
    return _shared_client


async def close_client() -> None:
    """서버 종료 시 연결 정리."""

    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
    _shared_client = None


def _check_result_header(payload: dict) -> None:
    """공공데이터포털 관례: HTTP 200이어도 resultCode!="0000"이면 API 오류.

    resultCode가 오는 위치가 두 가지다 - 둘 다 확인해야 한다.
      - 정상/서비스 오류: {"response": {"header": {"resultCode": "0000", ...}}}
      - 게이트웨이 오류:  {"resultCode": "11",
                          "resultMsg": "NO_MANDATORY_REQUEST_PARAMETERS_ERROR1(areaCd)"}
    최상위 형태를 놓치면 필수 파라미터 누락이 "데이터 없음"으로 둔갑한다.
    """

    header = payload.get("response", {})
    header = header.get("header", {}) if isinstance(header, dict) else {}

    for source in (header, payload):
        if not isinstance(source, dict):
            continue
        result_code = source.get("resultCode")
        if result_code is not None and result_code != "0000":
            result_msg = source.get("resultMsg", "알 수 없는 오류")
            raise UpstreamAPIError(f"관광공사 API 오류 [{result_code}] {result_msg}")


def _extract_items(payload: dict) -> list[dict]:
    """response.body.items.item 을 항상 list로 꺼낸다.

    실제 API는 결과가 0건이면 items를 dict가 아니라 빈 문자열로 내려준다:
        {"body": {"items": "", "numOfRows": 0, "totalCount": 0}}
    그대로 .get()을 부르면 AttributeError가 나므로 여기서 흡수한다.
    결과가 1건이면 item이 dict, 여러 건이면 list다.
    """

    body = payload.get("response", {})
    body = body.get("body", {}) if isinstance(body, dict) else {}
    items = body.get("items") if isinstance(body, dict) else None
    if not isinstance(items, dict):  # "" 또는 None = 결과 없음
        return []

    item = items.get("item", [])
    if isinstance(item, list):
        return item
    return [item] if item else []


async def _get_with_retry(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    last_exc: Exception | None = None
    operation = url.rstrip("/").rsplit("/", 1)[-1]  # URL 전체는 남기지 않는다.
    for attempt in range(config.MAX_RETRY + 1):
        # 실패한 시도도 일일 한도를 소모하므로 요청 직전에 센다.
        metrics.record(operation)
        try:
            resp = await client.get(url, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS)
        except httpx.TimeoutException as exc:
            last_exc = exc
            continue
        except httpx.HTTPError as exc:
            raise UpstreamAPIError(f"요청 실패: {exc}") from exc

        if resp.status_code >= 500:
            # 서버 오류만 재시도 대상으로 삼는다 (4xx는 재시도해도 동일).
            last_exc = UpstreamAPIError(
                f"관광공사 API {resp.status_code}", status_code=resp.status_code
            )
            continue

        if resp.status_code >= 400:
            raise UpstreamAPIError(
                f"관광공사 API {resp.status_code}", status_code=resp.status_code
            )

        try:
            payload = resp.json()
        except ValueError as exc:
            raise InvalidUpstreamPayloadError("잘못된 JSON 응답") from exc

        _check_result_header(payload)
        return payload

    if isinstance(last_exc, httpx.TimeoutException):
        raise UpstreamTimeoutError("관광공사 API timeout") from last_exc
    if last_exc:
        raise last_exc
    raise UpstreamAPIError("알 수 없는 오류")


async def fetch_location_based_list(map_x: float, map_y: float, radius: int) -> list[dict]:
    """위치기반 관광지 검색. 반환값은 원본에 가까운 dict 목록(정규화는 service.py)."""

    params = {
        "serviceKey": config.KTO_SERVICE_KEY,
        "mapX": map_x,
        "mapY": map_y,
        "radius": radius,
        "numOfRows": config.KTO_NUM_OF_ROWS,
        "pageNo": 1,
        "MobileOS": "ETC",
        "MobileApp": "TourPlanner",
        "_type": "json",
    }
    # 유형을 좁히지 않으면 음식점/숙박이 대부분이라 예측 집중률이 붙지 않는다.
    if config.KTO_CONTENT_TYPE_ID:
        params["contentTypeId"] = config.KTO_CONTENT_TYPE_ID
    payload = await _get_with_retry(_client(), f"{config.KTO_BASE_URL}/locationBasedList2", params)
    return _extract_items(payload)


async def fetch_congestion_candidates(t_ats_nm: str, area_cd: str, signgu_cd: str) -> list[dict]:
    """예측 집중률 API 조회. tAtsNm/areaCd/signguCd 조합 (B_openapi.md 3절).

    반환값은 원본 그대로의 dict 목록이다. 각 dict는 하루치 행이다
    (baseYmd/tAtsNm/cnctrRate 등) - 같은 관광지라도 날짜 수만큼 여러 행이
    온다. 날짜별로 묶는 것은 service.py가 한다.
    """

    params = {
        "serviceKey": config.KTO_SERVICE_KEY,
        "pageNo": 1,
        "numOfRows": config.CONGESTION_NUM_OF_ROWS,
        "MobileOS": "ETC",
        "MobileApp": "TourPlanner",
        "tAtsNm": t_ats_nm,
        "areaCd": area_cd,
        "signguCd": signgu_cd,
        "_type": "json",
    }
    payload = await _get_with_retry(
        _client(), f"{config.KTO_CONGESTION_BASE_URL}/tatsCnctrRatedList", params
    )
    return _extract_items(payload)


async def fetch_place_detail(content_id: str) -> dict:
    """content_id 기반 공통정보/소개정보 조회 (B_openapi.md 8절)."""

    params = {
        "serviceKey": config.KTO_SERVICE_KEY,
        "contentId": content_id,
        "MobileOS": "ETC",
        "MobileApp": "TourPlanner",
        "_type": "json",
    }
    payload = await _get_with_retry(_client(), f"{config.KTO_BASE_URL}/detailCommon2", params)
    items = _extract_items(payload)
    if not items:
        raise InvalidUpstreamPayloadError(f"content_id={content_id} 상세정보 없음")
    return items[0]


async def fetch_place_intro(content_id: str, content_type_id: str) -> dict:
    """소개정보 (운영시간/휴무일 등). 공통정보에는 이 필드들이 없다.

    요청 하나에 contentId 하나만 받으므로 관광지마다 따로 호출해야 한다.
    필드 이름은 콘텐츠 유형마다 다르다 (관광지는 usetime/restdate).
    """

    params = {
        "serviceKey": config.KTO_SERVICE_KEY,
        "contentId": content_id,
        "contentTypeId": content_type_id,
        "MobileOS": "ETC",
        "MobileApp": "TourPlanner",
        "_type": "json",
    }
    payload = await _get_with_retry(_client(), f"{config.KTO_BASE_URL}/detailIntro2", params)
    items = _extract_items(payload)
    return items[0] if items else {}
