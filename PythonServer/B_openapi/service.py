"""B의 공개 service 계층.

A/C는 관광공사 원본 응답을 직접 파싱하지 않고 이 모듈(또는 main.py의 HTTP
endpoint)만 사용한다 (A_backend_auth.md 5절, B_openapi.md 0절).

USE_MOCK 환경변수로 mock/실제 API를 전환한다. 실제 API로 바꿔도 함수
시그니처와 반환 타입(shared.schemas)은 그대로이므로 호출측 코드는 바뀌지
않는다 (B_openapi.md 12절 완료 조건).
"""

from __future__ import annotations

import asyncio
import html
import re

from shared.schemas import Congestion, CongestionTarget, DayRate, LocationReq, Place

from . import config, mock_data
from .client import (
    fetch_congestion_candidates,
    fetch_location_based_list,
    fetch_place_detail,
    fetch_place_intro,
)
from .exceptions import InvalidUpstreamPayloadError, UpstreamAPIError, UpstreamTimeoutError
from .matching import build_signgu_cd, extract_base_name, match_congestion_candidate

_TAG_RE = re.compile(r"<[^>]+>")


def _normalize_place(raw: dict) -> Place | None:
    try:
        return Place(
            content_id=str(raw["contentid"]),
            name=extract_base_name(raw["title"]),
            addr=raw.get("addr1", ""),
            map_x=float(raw["mapx"]),
            map_y=float(raw["mapy"]),
            dist=float(raw.get("dist", 0.0)),
            image=raw.get("firstimage") or None,
            content_type_id=raw.get("contenttypeid"),
        )
    except (KeyError, TypeError, ValueError):
        return None


async def get_places(req: LocationReq) -> list[Place]:
    """위치기반 주변 관광지 조회. 좌표는 이 함수 안에서만 사용하고 로그로
    남기지 않는다 (B_openapi.md 9절)."""

    if config.USE_MOCK:
        return mock_data.mock_places()

    raw_items = await fetch_location_based_list(req.map_x, req.map_y, req.radius)
    places = [p for p in (_normalize_place(r) for r in raw_items) if p is not None]
    return places


async def get_place_detail(content_id: str) -> Place | None:
    """content_id -> 관광공사 공통정보/소개정보 재조회 (B_openapi.md 8절).

    DB에서 상세정보를 가져오지 않고 항상 실시간으로 조회한다.
    """

    if config.USE_MOCK:
        return mock_data.mock_place_detail(content_id)

    try:
        raw = await fetch_place_detail(content_id)
    except InvalidUpstreamPayloadError:
        return None

    content_type_id = raw.get("contenttypeid")
    intro: dict = {}
    if content_type_id:
        # 소개정보가 실패해도 공통정보만으로 상세는 돌려준다.
        try:
            intro = await fetch_place_intro(content_id, str(content_type_id))
        except (UpstreamTimeoutError, UpstreamAPIError, InvalidUpstreamPayloadError):
            intro = {}

    return Place(
        content_id=str(raw.get("contentid", content_id)),
        name=extract_base_name(raw.get("title", "")),
        addr=raw.get("addr1", ""),
        map_x=float(raw.get("mapx", 0.0) or 0.0),
        map_y=float(raw.get("mapy", 0.0) or 0.0),
        dist=0.0,
        image=raw.get("firstimage") or None,
        content_type_id=content_type_id,
        overview=_clean_text(raw.get("overview")),
        use_time=_intro_field(intro, ("usetime", "opentime", "playtime")),
        rest_date=_intro_field(intro, ("restdate",)),
    )


def _clean_text(value) -> str | None:
    """관광공사 텍스트에 섞여 오는 <br> 같은 태그와 HTML 엔티티를 정리한다."""

    if not value:
        return None
    text = html.unescape(_TAG_RE.sub(" ", str(value)))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _intro_field(intro: dict, prefixes: tuple[str, ...]) -> str | None:
    """소개정보 필드 이름은 콘텐츠 유형마다 다르다.

    관광지(12)는 usetime/restdate이고, 다른 유형은 usetimeculture,
    restdatefood 처럼 접미사가 붙는다. 이름을 유형별로 하드코딩하지 않고
    접두사로 찾는다.
    """

    for key, value in intro.items():
        if key.lower().startswith(prefixes):
            cleaned = _clean_text(value)
            if cleaned:
                return cleaned
    return None


async def get_place_details(content_ids: list[str]) -> list[Place]:
    """최종 일정에 뽑힌 장소들만 상세정보를 병렬로 조회한다.

    관광지 1곳당 API 2회(공통정보+소개정보)가 나가므로 상한을 둔다.
    조회에 실패한 장소는 결과에서 빠지고, 순서는 요청 순서를 따른다.
    """

    unique_ids = list(dict.fromkeys(content_ids))[: config.MAX_DETAIL_BATCH]
    results = await asyncio.gather(
        *[get_place_detail(cid) for cid in unique_ids], return_exceptions=True
    )
    return [r for r in results if isinstance(r, Place)]


async def get_congestion_by_name(
    content_id: str, name: str, area_cd: str, l_dong_signgu_cd: str
) -> Congestion:
    """이름으로 예측 집중률 조회 + 매칭 규칙 적용.

    집중률 API는 content_id가 아니라 관광지 이름으로 조회하므로, 이름만
    있으면 상세조회 없이 바로 부를 수 있다.

    실제 API(tatsCnctrRatedList)는 관광지 1곳당 날짜별로 한 행씩
    (baseYmd/tAtsNm/cnctrRate) 내려준다. 같은 이름의 행들을 먼저 하나의
    후보로 묶은 다음에 매칭 규칙(matching.match_congestion_candidate)을
    적용해야 한다 - 날짜별 행 개수를 후보 개수로 착각하면 안 된다.
    """

    if config.USE_MOCK:
        return mock_data.mock_congestion(content_id)

    signgu_cd = build_signgu_cd(area_cd, l_dong_signgu_cd)
    raw_rows = await fetch_congestion_candidates(name, area_cd, signgu_cd)

    grouped: dict[str, list[dict]] = {}
    for row in raw_rows:
        name = extract_base_name(row.get("tAtsNm", ""))
        grouped.setdefault(name, []).append(row)
    candidates = [{"name": name, "daily": rows} for name, rows in grouped.items()]

    matched = match_congestion_candidate(candidates, name)
    if matched is None:
        return Congestion(content_id=content_id, name=name, daily=[], has_data=False)

    daily = [
        DayRate(date=row["baseYmd"], rate=float(row["cnctrRate"])) for row in matched["daily"]
    ]
    return Congestion(
        content_id=content_id,
        name=name,
        daily=daily,
        has_data=bool(daily),
    )


async def get_congestion_for_place(
    place: Place, area_cd: str, l_dong_signgu_cd: str
) -> Congestion:
    """Place를 이미 들고 있을 때 쓰는 편의 래퍼."""

    return await get_congestion_by_name(place.content_id, place.name, area_cd, l_dong_signgu_cd)


async def resolve_target_names(targets: list[CongestionTarget]) -> list[tuple[str, str]]:
    """이름이 없는 대상만 상세조회로 채운다.

    이름이 함께 오면 상세조회를 통째로 건너뛴다. 못 채운 대상은 집중률을
    조회할 방법이 없으므로 목록에서 뺀다(호출측은 "데이터 없음"으로 본다).

    순차 루프였던 것을 gather로 바꿨다 - 20곳이면 8초가 넘게 걸리던 구간이다.
    """

    unknown = [t for t in targets if not t.name]
    resolved: dict[str, str] = {}
    if unknown:
        details = await asyncio.gather(
            *[get_place_detail(t.content_id) for t in unknown], return_exceptions=True
        )
        for target, detail in zip(unknown, details):
            if isinstance(detail, Place):
                resolved[target.content_id] = detail.name

    pairs = []
    for t in targets:
        name = t.name or resolved.get(t.content_id)
        if name:
            pairs.append((t.content_id, name))
    return pairs


async def get_congestion_for_targets(
    targets: list[CongestionTarget], area_cd: str, l_dong_signgu_cd: str
) -> dict[str, Congestion]:
    """집중률 배치 조회.

    후보 수 제한을 상세조회 "전에" 적용한다. 예전에는 집중률에만 걸려 있어서
    50개가 오면 상세조회 50번이 그대로 나갔다 (B_openapi.md 5절 위반).
    """

    limited = targets[: config.MAX_CANDIDATES_FOR_CONGESTION]
    pairs = await resolve_target_names(limited)
    results = await asyncio.gather(
        *[get_congestion_by_name(cid, name, area_cd, l_dong_signgu_cd) for cid, name in pairs]
    )
    return {c.content_id: c for c in results}


async def get_congestion_for_places(
    places: list[Place], area_cd: str, l_dong_signgu_cd: str
) -> dict[str, Congestion]:
    """Place 목록을 이미 들고 있을 때 쓰는 편의 래퍼 (이름을 알므로 상세조회 없음)."""

    return await get_congestion_for_targets(
        [CongestionTarget(content_id=p.content_id, name=p.name) for p in places],
        area_cd,
        l_dong_signgu_cd,
    )
