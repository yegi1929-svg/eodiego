"""B 서비스 진입점.

A/C가 내부적으로 호출하는 HTTP 계약 (A_backend_auth.md 5절: "필요한 경우
B에게 내부 service 호출 계약을 정의해 둔다"). 좌표가 포함된 요청은 반드시
POST JSON body로 받는다 (query string 금지 - B_openapi.md 9절).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.schemas import (
    Congestion,
    CongestionTarget,
    ErrorResponse,
    LocationReq,
    Place,
    PlaceDetailsRequest,
    Region,
)

from . import client, config, metrics, region, service
from .exceptions import InvalidUpstreamPayloadError, UpstreamAPIError, UpstreamTimeoutError

def _wire_logging() -> None:
    """uvicorn은 자기 로거("uvicorn.error" 등)에만 핸들러를 단다.

    우리 로거는 root로 propagate 되는데 root에 핸들러가 없어서 INFO 로그가
    조용히 버려진다(WARNING만 lastResort로 stderr에 찍힌다). uvicorn의
    핸들러를 빌려 붙여서 관광공사 호출 로그가 실제로 남게 한다.
    """

    app_logger = logging.getLogger("B_openapi")
    if app_logger.handlers:
        return
    uvicorn_logger = logging.getLogger("uvicorn.error")
    for handler in uvicorn_logger.handlers:
        app_logger.addHandler(handler)
    if not app_logger.handlers:
        app_logger.addHandler(logging.StreamHandler())
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _wire_logging()
    yield
    await client.close_client()  # 공유 HTTP 연결 정리


app = FastAPI(title="B - 한국관광공사 OpenAPI 연동 서비스", lifespan=_lifespan)


def _to_error_response(exc: Exception) -> ErrorResponse:
    if isinstance(exc, UpstreamTimeoutError):
        return ErrorResponse(error={"code": "UPSTREAM_TIMEOUT", "message": "관광공사 API 응답이 지연되고 있습니다."})
    if isinstance(exc, UpstreamAPIError):
        return ErrorResponse(error={"code": "UPSTREAM_ERROR", "message": "관광공사 API 호출에 실패했습니다."})
    if isinstance(exc, InvalidUpstreamPayloadError):
        return ErrorResponse(error={"code": "UPSTREAM_ERROR", "message": "관광공사 API 응답 형식이 올바르지 않습니다."})
    return ErrorResponse(error={"code": "INTERNAL_ERROR", "message": "내부 오류가 발생했습니다."})


@app.get("/internal/regions", response_model=list[Region])
async def regions():
    """지역 선택지 + 대표 좌표. 화면이 좌표를 들고 있지 않게 하기 위한 것이다."""
    return region.list_regions()


@app.post("/internal/places/nearby", response_model=list[Place])
async def places_nearby(req: LocationReq):
    """좌표는 요청 처리에만 쓰고 로그로 남기지 않는다."""
    try:
        return await service.get_places(req)
    except (UpstreamTimeoutError, UpstreamAPIError, InvalidUpstreamPayloadError) as exc:
        raise HTTPException(status_code=502, detail=_to_error_response(exc).model_dump()) from exc


@app.post("/internal/places/details", response_model=list[Place])
async def place_details(req: PlaceDetailsRequest):
    """최종 일정에 뽑힌 장소들만 상세정보(소개문/운영시간/휴무일)를 한 번에 조회.

    장소별 조회는 병렬로 돌고, 실패한 장소는 결과에서 빠진다.
    """
    return await service.get_place_details(req.content_ids)


@app.get("/internal/places/{content_id}", response_model=Place | None)
async def place_detail(content_id: str):
    try:
        place = await service.get_place_detail(content_id)
    except (UpstreamTimeoutError, UpstreamAPIError) as exc:
        raise HTTPException(status_code=502, detail=_to_error_response(exc).model_dump()) from exc
    if place is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "관광지를 찾을 수 없습니다."}})
    return place


class CongestionBatchRequest(BaseModel):
    """targets 로 이름까지 주면 상세조회를 건너뛴다 (관광지당 2회 -> 1회).

    content_ids 는 이름을 모르는 호출측을 위한 하위 호환 경로다.
    """

    targets: list[CongestionTarget] = []
    content_ids: list[str] = []
    area_cd: str = "50"
    l_dong_signgu_cd: str = "110"

    def to_targets(self) -> list[CongestionTarget]:
        if self.targets:
            return self.targets
        return [CongestionTarget(content_id=cid) for cid in self.content_ids]


@app.post("/internal/congestion", response_model=dict[str, Congestion])
async def congestion_batch(req: CongestionBatchRequest):
    try:
        return await service.get_congestion_for_targets(
            req.to_targets(), req.area_cd, req.l_dong_signgu_cd
        )
    except (UpstreamTimeoutError, UpstreamAPIError) as exc:
        raise HTTPException(status_code=502, detail=_to_error_response(exc).model_dump()) from exc


@app.get("/internal/metrics")
async def kto_metrics(days: int = 7):
    """오늘 나간 관광공사 API 호출 수와 일일 한도 소진율 (+ 최근 이력).

    DB에 남기므로 B를 재시작해도 값이 유지된다.
    """
    return metrics.snapshot(days)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
