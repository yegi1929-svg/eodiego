"""A가 B의 실시간 관광정보 조회 계약을 호출하는 클라이언트.

A는 관광공사 응답을 직접 파싱하지 않는다 (A_backend_auth.md 5절).
저장 일정 상세 조회 시 DB의 content_id 목록으로 B를 호출해 현재 관광지
정보와 결합한다.
"""

from __future__ import annotations

import httpx

from shared.schemas import Place

from . import config


class BServiceError(Exception):
    pass


async def get_place_details(content_ids: list[str]) -> dict[str, Place]:
    """저장된 일정의 장소들을 한 번에 조회한다. content_id -> Place.

    장소마다 따로 부르면 순차 호출이 되고, 상세정보는 관광지당 관광공사
    API 2회라서 방문지가 몇 곳만 돼도 타임아웃에 걸린다. B가 병렬로 처리한다.
    """

    if not content_ids:
        return {}
    async with httpx.AsyncClient(base_url=config.B_BASE_URL, timeout=config.B_TIMEOUT_SECONDS) as client:
        try:
            resp = await client.post("/internal/places/details", json={"content_ids": content_ids})
        except httpx.HTTPError as exc:
            raise BServiceError(f"B 서비스 호출 실패: {exc}") from exc

    if resp.status_code >= 400:
        raise BServiceError(f"B 서비스 오류: {resp.status_code}")
    return {p["content_id"]: Place(**p) for p in resp.json()}
