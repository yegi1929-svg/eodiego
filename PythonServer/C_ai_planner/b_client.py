"""C가 B의 HTTP 계약을 호출하는 얇은 클라이언트.

C는 관광공사 원본 API를 직접 호출하지 않고 B의 service를 통해서만
Place/Congestion을 얻는다 (역할 분리를 A_backend_auth.md 5절과 동일하게
C에도 적용).
"""

from __future__ import annotations

import httpx

from shared.schemas import Congestion, LocationReq, Place

from . import config


class BServiceError(Exception):
    pass


async def get_nearby_places(map_x: float, map_y: float, radius: int | None = None) -> list[Place]:
    """radius를 주지 않으면 공통 계약(LocationReq)의 기본 반경을 쓴다 (제주 추천 탭과 동일)."""

    if radius is None:
        req = LocationReq(map_x=map_x, map_y=map_y)
    else:
        req = LocationReq(map_x=map_x, map_y=map_y, radius=radius)
    async with httpx.AsyncClient(base_url=config.B_BASE_URL, timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.post("/internal/places/nearby", json=req.model_dump())
        except httpx.HTTPError as exc:
            raise BServiceError(f"B 서비스 호출 실패: {exc}") from exc
    if resp.status_code >= 400:
        raise BServiceError(f"B 서비스 오류: {resp.status_code}")
    return [Place(**item) for item in resp.json()]


async def get_place_details(content_ids: list[str]) -> dict[str, Place]:
    """최종 일정에 뽑힌 장소들의 상세정보. content_id -> Place."""

    if not content_ids:
        return {}
    async with httpx.AsyncClient(base_url=config.B_BASE_URL, timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.post("/internal/places/details", json={"content_ids": content_ids})
        except httpx.HTTPError as exc:
            raise BServiceError(f"B 서비스 호출 실패: {exc}") from exc
    if resp.status_code >= 400:
        raise BServiceError(f"B 서비스 오류: {resp.status_code}")
    return {p["content_id"]: Place(**p) for p in resp.json()}


async def get_congestion_map(
    places: list[Place], area_cd: str = "50", l_dong_signgu_cd: str = "110"
) -> dict[str, Congestion]:
    """이미 조회해 둔 Place의 이름을 함께 넘겨 B의 상세 재조회를 생략시킨다."""

    if not places:
        return {}
    async with httpx.AsyncClient(base_url=config.B_BASE_URL, timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.post(
                "/internal/congestion",
                json={
                    "targets": [{"content_id": p.content_id, "name": p.name} for p in places],
                    "area_cd": area_cd,
                    "l_dong_signgu_cd": l_dong_signgu_cd,
                },
            )
        except httpx.HTTPError as exc:
            raise BServiceError(f"B 서비스 호출 실패: {exc}") from exc
    if resp.status_code >= 400:
        raise BServiceError(f"B 서비스 오류: {resp.status_code}")
    return {cid: Congestion(**data) for cid, data in resp.json().items()}
