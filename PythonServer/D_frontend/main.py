"""D 비즈니스 로직 서버 (BFF).

이미 만들어진 HTML/JS 화면이 fetch로 호출하는 JSON API만 제공한다.
화면(HTML/CSS)은 이 파일에서 만들지 않는다.

라우트는 D_frontend.md의 화면 단위(주변 관광지/집중률/일정/재추천/저장/
마이페이지/인증)에 맞춰 나눴다. 실제 관광공사·LLM 호출은 각각 B/C가
담당하고, 이 서버는 좌표/세션 쿠키를 그대로 넘기기만 한다 - 좌표를 로그로
남기지 않는다(14절).
"""

from __future__ import annotations

import hmac

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shared.schemas import (
    CongestionTarget,
    LocationReq,
    PlanRequest,
    ReplanRequest,
    SavePlanRequest,
)

from . import config, view_logic
from .api_client import auth as auth_client
from .api_client import places as places_client
from .api_client import plans as plans_client
from .api_client.errors import UpstreamRejectedError, UpstreamUnavailableError

app = FastAPI(title="D - 프론트엔드 비즈니스 로직 서버 (BFF)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _require_gateway_token(request: Request, call_next):
    """화면(worker/dev 프록시)을 거친 요청만 통과시킨다.

    배포하면 D의 주소가 공개되므로, 이 검사가 없으면 누구나 브라우저 없이
    /ui/* 를 직접 호출할 수 있다. BFF_GATEWAY_TOKEN이 비어 있으면(로컬 개발)
    검사하지 않는다.
    """

    if config.GATEWAY_TOKEN and request.url.path.startswith("/ui/"):
        supplied = request.headers.get(config.GATEWAY_HEADER, "")
        if not hmac.compare_digest(supplied, config.GATEWAY_TOKEN):
            return JSONResponse(
                status_code=403,
                content=view_logic.status_envelope(
                    "error",
                    data={"message": "허용되지 않은 요청입니다.", "retryable": False, "code": "FORBIDDEN"},
                ),
            )
    return await call_next(request)


def _session_token(request: Request) -> str | None:
    return request.cookies.get(config.SESSION_COOKIE_NAME)


def _handle(context_key: str, exc: Exception) -> dict:
    return view_logic.status_envelope("error", data=view_logic.error_context(context_key, exc))


# ---------------------------------------------------------------------------
# 인증 (로그인/로그아웃/회원가입/현재 사용자) - A로 프록시
# ---------------------------------------------------------------------------


class CredentialsBody(BaseModel):
    """dict로 받아 body["username"]로 꺼내면 필드 누락 시 KeyError -> 500이 나고,
    화면은 봉투 대신 평문 "Internal Server Error"를 받는다. 모델로 받아
    422 검증 오류로 처리한다."""

    username: str
    password: str


@app.post("/ui/auth/register")
async def register(body: CredentialsBody):
    try:
        user = await auth_client.register(body.username, body.password)
        return view_logic.status_envelope("success", data=user)
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("register", exc)


@app.post("/ui/auth/login")
async def login(body: CredentialsBody, response: Response):
    try:
        user, token = await auth_client.login(body.username, body.password)
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("auth", exc)

    if token:
        # max_age가 없으면 세션 쿠키가 되어 브라우저를 닫는 순간 로그아웃된다.
        response.set_cookie(
            key=config.SESSION_COOKIE_NAME,
            value=token,
            max_age=config.SESSION_COOKIE_MAX_AGE,
            httponly=True,
            secure=config.COOKIE_SECURE,
            samesite=config.COOKIE_SAMESITE,
            path="/",
        )
    return view_logic.status_envelope("success", data=user)


@app.post("/ui/auth/logout")
async def logout(request: Request, response: Response):
    # A가 죽어 있어도 브라우저 쪽 세션은 반드시 끊어준다.
    try:
        await auth_client.logout(_session_token(request))
    except (UpstreamUnavailableError, UpstreamRejectedError):
        pass
    response.delete_cookie(config.SESSION_COOKIE_NAME, path="/")
    return view_logic.status_envelope("success")


@app.get("/ui/auth/me")
async def me(request: Request):
    # 화면이 진입할 때마다 가장 먼저 부르는 API다. 여기서 500이 나면
    # 첫 화면부터 봉투 계약이 깨진다 - 반드시 error 봉투로 돌려준다.
    try:
        user = await auth_client.me(_session_token(request))
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("auth", exc)
    return view_logic.status_envelope("success", data=user)


# ---------------------------------------------------------------------------
# 주변 관광지 / 집중률 - B로 프록시 (좌표는 POST JSON으로만 받는다)
# ---------------------------------------------------------------------------


@app.get("/ui/regions")
async def regions():
    """지역 선택지 - 화면이 좌표를 하드코딩하지 않도록 B에서 받아 그대로 넘긴다."""
    try:
        items = await places_client.regions()
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("regions", exc)

    if not items:
        return view_logic.status_envelope("empty", empty_message="선택할 수 있는 지역이 없습니다.")
    return view_logic.status_envelope("success", data=items)


@app.post("/ui/places/nearby")
async def places_nearby(req: LocationReq):
    try:
        places = await places_client.nearby(req.map_x, req.map_y, req.radius)
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("places_nearby", exc)

    if not places:
        return view_logic.status_envelope("empty", empty_message="주변에 표시할 관광지가 없습니다.")
    return view_logic.status_envelope("success", data=places)


class CongestionBody(BaseModel):
    """targets(이름 포함)를 주면 B가 상세 재조회를 건너뛴다.
    content_ids는 하위 호환 경로."""

    travel_date: str
    targets: list[CongestionTarget] = []
    content_ids: list[str] = []
    area_cd: str = "50"
    l_dong_signgu_cd: str = "110"

    def to_targets(self) -> list[CongestionTarget]:
        if self.targets:
            return self.targets
        return [CongestionTarget(content_id=cid) for cid in self.content_ids]


@app.post("/ui/places/congestion")
async def places_congestion(body: CongestionBody):
    travel_date = body.travel_date

    try:
        raw = await places_client.congestion(
            body.to_targets(), body.area_cd, body.l_dong_signgu_cd
        )
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        # 집중률 실패는 일정 생성 자체를 막지 않는다 - 관광지 정보만으로 계속한다.
        return _handle("congestion", exc)

    shaped = {}
    for content_id, congestion in raw.items():
        rate = next((d["rate"] for d in congestion["daily"] if d["date"] == travel_date), None)
        shaped[content_id] = {
            "has_data": congestion["has_data"],
            "rate": rate,
            "label": view_logic.congestion_label(rate, congestion["has_data"]),
            "is_high": view_logic.is_high_congestion(rate, congestion["has_data"]),
        }
    return view_logic.status_envelope("success", data=shaped)


# ---------------------------------------------------------------------------
# AI 일정 생성 / 재추천 - C로 프록시
# ---------------------------------------------------------------------------


@app.post("/ui/plan/generate")
async def generate_plan(req: PlanRequest):
    try:
        plan = await plans_client.generate_plan(req.model_dump())
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("plan_generate", exc)
    return view_logic.status_envelope("success", data=view_logic.plan_display_context(plan))


@app.post("/ui/plan/replan")
async def replan(req: ReplanRequest):
    try:
        result = await plans_client.replan(req.model_dump())
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("plan_replan", exc)
    return view_logic.status_envelope("success", data=view_logic.replan_result_context(result))


# ---------------------------------------------------------------------------
# 저장 일정 - A로 프록시 (로그인 필요, A가 401/AUTH_REQUIRED로 걸러준다)
# ---------------------------------------------------------------------------


@app.post("/ui/plans")
async def save_plan(req: SavePlanRequest, request: Request):
    try:
        saved = await plans_client.save_plan(_session_token(request), req.model_dump())
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("plan_save", exc)
    return view_logic.status_envelope("success", data=saved)


@app.get("/ui/plans")
async def list_plans(request: Request):
    try:
        plans = await plans_client.list_plans(_session_token(request))
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("generic", exc)

    if not plans:
        return view_logic.status_envelope("empty", empty_message="저장된 일정이 없습니다.")
    return view_logic.status_envelope("success", data=plans)


@app.get("/ui/plans/{plan_id}")
async def get_plan_detail(plan_id: int, request: Request):
    try:
        detail = await plans_client.get_plan_detail(_session_token(request), plan_id)
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("generic", exc)
    return view_logic.status_envelope("success", data=detail)


@app.delete("/ui/plans/{plan_id}")
async def delete_plan(plan_id: int, request: Request):
    try:
        await plans_client.delete_plan(_session_token(request), plan_id)
    except (UpstreamUnavailableError, UpstreamRejectedError) as exc:
        return _handle("generic", exc)
    return view_logic.status_envelope("success")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
