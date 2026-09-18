"""B(한국관광공사 연동)를 호출하는 모듈.

D는 관광공사 API를 직접 호출하지 않는다 - 반드시 B를 거친다
(D_frontend.md 11, 14절). 좌표는 이 함수 안에서만 쓰고 로그로 남기지 않는다.
"""

from __future__ import annotations

from .. import config
from . import _http


async def regions() -> list[dict]:
    resp = await _http.request("B", config.B_BASE_URL, "GET", "/internal/regions")
    return resp.json()


async def nearby(map_x: float, map_y: float, radius: int | None = None) -> list[dict]:
    """radius가 None이면 보내지 않는다 - 공통 계약(LocationReq)의 기본 반경이 쓰인다."""
    body: dict = {"map_x": map_x, "map_y": map_y}
    if radius is not None:
        body["radius"] = radius
    resp = await _http.request(
        "B", config.B_BASE_URL, "POST", "/internal/places/nearby", json=body,
    )
    return resp.json()


async def congestion(targets, area_cd: str = "50", l_dong_signgu_cd: str = "110") -> dict:
    """targets: CongestionTarget 목록. 이름이 있으면 B가 상세조회를 건너뛴다."""

    resp = await _http.request(
        "B", config.B_BASE_URL, "POST", "/internal/congestion",
        json={
            "targets": [
                t if isinstance(t, dict) else {"content_id": t.content_id, "name": t.name}
                for t in targets
            ],
            "area_cd": area_cd,
            "l_dong_signgu_cd": l_dong_signgu_cd,
        },
    )
    return resp.json()
