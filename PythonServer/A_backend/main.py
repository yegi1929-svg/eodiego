"""A 서비스 진입점 (A_backend_auth.md 5, 9, 10절).

A의 API 책임: 회원가입/로그인/로그아웃/현재 사용자 확인/일정 저장·조회·삭제/
마이페이지. 관광공사 API는 B를 통해서만 접근한다.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.schemas import ErrorResponse, SavedPlan, SavePlanRequest

from . import auth, config, db, plan_service, security
from .auth_schemas import LoginRequest, RegisterRequest, UserPublic
from .db import DuplicateUserError as DbDuplicateUserError
from .errors import AppError, DuplicateUserError, InvalidCredentialsError


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # 테이블은 db/schema.sql 로 관리자가 만든다 - 앱은 DDL 권한이 없다.
    # 기동 시 접속과 테이블 존재만 확인해서, 설정이 틀렸으면 바로 실패한다.
    db.ping()
    yield


app = FastAPI(title="A - 백엔드/인증/저장 서비스", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,  # 와일드카드 금지: 쿠키 인증과 함께 쓰려면 origin을 명시해야 한다.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content=exc.to_response().model_dump())


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # 사용자에게 내부 예외를 그대로 노출하지 않는다 (7절).
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(error={"code": "VALIDATION_ERROR", "message": "입력값이 올바르지 않습니다."}).model_dump(),
    )


# ---------------------------------------------------------------------------
# 인증
# ---------------------------------------------------------------------------


@app.post("/auth/register", response_model=UserPublic, status_code=201)
def register(req: RegisterRequest):
    try:
        user_id = db.create_user(req.username, security.hash_password(req.password))
    except DbDuplicateUserError as exc:
        raise DuplicateUserError("이미 사용 중인 아이디입니다.") from exc
    return UserPublic(user_id=user_id, username=req.username)


@app.post("/auth/login", response_model=UserPublic)
def login(req: LoginRequest, response: Response):
    row = db.get_user_by_username(req.username)
    if row is None or not security.verify_password(req.password, row["password_hash"]):
        raise InvalidCredentialsError("아이디 또는 비밀번호가 올바르지 않습니다.")

    token = auth.create_session(row["user_id"])
    auth.set_session_cookie(response, token)
    return UserPublic(user_id=row["user_id"], username=row["username"])


@app.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if token:
        auth.delete_session(token)
    auth.clear_session_cookie(response)
    return None


@app.get("/auth/me", response_model=UserPublic | None)
def me(user_id: int | None = Depends(auth.get_current_user_optional)):
    if user_id is None:
        return None
    row = db.get_user_by_id(user_id)
    if row is None:
        return None
    return UserPublic(user_id=row["user_id"], username=row["username"])


# ---------------------------------------------------------------------------
# 일정 저장/조회/삭제 (로그인 필수 - 비회원은 D에서 브라우저 상태로만 유지)
# ---------------------------------------------------------------------------


@app.post("/plans", response_model=SavedPlan, status_code=201)
def save_plan(req: SavePlanRequest, user_id: int = Depends(auth.get_current_user_required)):
    return plan_service.save_plan(user_id, req)


@app.get("/plans", response_model=list[SavedPlan])
def list_plans(user_id: int = Depends(auth.get_current_user_required)):
    return plan_service.list_plans(user_id)


@app.get("/plans/{plan_id}", response_model=plan_service.PlanDetail)
async def get_plan(plan_id: int, user_id: int = Depends(auth.get_current_user_required)):
    return await plan_service.get_plan_detail(user_id, plan_id)


@app.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: int, user_id: int = Depends(auth.get_current_user_required)):
    plan_service.delete_plan(user_id, plan_id)
    return None


@app.get("/mypage")
def mypage(user_id: int = Depends(auth.get_current_user_required)):
    row = db.get_user_by_id(user_id)
    return {"user": UserPublic(user_id=row["user_id"], username=row["username"]), "plans": plan_service.list_plans(user_id)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.HOST, port=config.PORT)
