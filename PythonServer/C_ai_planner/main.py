"""C 서비스 진입점 (C_ai_planner.md 13절 완료 조건의 HTTP 경계)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from shared.schemas import ErrorResponse, Plan, PlanRequest, ReplanRequest, ReplanResponse

from . import b_client, llm_usage, planner_service
from .replanner import NoReplacementCandidateError


def _wire_logging() -> None:
    """uvicorn은 자기 로거에만 핸들러를 달아서 우리 INFO 로그(LLM 토큰 사용량,
    기본 문구 전환 사유)가 버려진다. uvicorn의 핸들러를 빌려 붙인다."""

    app_logger = logging.getLogger("C_ai_planner")
    if app_logger.handlers:
        return
    for handler in logging.getLogger("uvicorn.error").handlers:
        app_logger.addHandler(handler)
    if not app_logger.handlers:
        app_logger.addHandler(logging.StreamHandler())
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _wire_logging()
    yield


app = FastAPI(title="C - AI 일정/재추천 서비스", lifespan=_lifespan)


@app.get("/internal/llm-usage")
async def llm_usage_report():
    """오늘(UTC) LLM 요청 수 / 하루 상한 / 토큰 사용량."""
    return llm_usage.snapshot()


@app.post("/plan/generate", response_model=Plan)
async def generate_plan(req: PlanRequest):
    try:
        return await planner_service.generate_plan(req)
    except b_client.BServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail=ErrorResponse(error={"code": "UPSTREAM_ERROR", "message": "관광지 정보를 가져오지 못했습니다."}).model_dump(),
        ) from exc


@app.post("/plan/replan", response_model=ReplanResponse)
async def replan(req: ReplanRequest):
    try:
        return await planner_service.replan(req)
    except NoReplacementCandidateError as exc:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(error={"code": "NO_REPLACEMENT_CANDIDATE", "message": "대체할 관광지를 찾지 못했습니다."}).model_dump(),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(error={"code": "VALIDATION_ERROR", "message": str(exc)}).model_dump(),
        ) from exc
    except b_client.BServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail=ErrorResponse(error={"code": "UPSTREAM_ERROR", "message": "관광지 정보를 가져오지 못했습니다."}).model_dump(),
        ) from exc


if __name__ == "__main__":
    import uvicorn

    from . import config

    uvicorn.run(app, host=config.HOST, port=config.PORT)
