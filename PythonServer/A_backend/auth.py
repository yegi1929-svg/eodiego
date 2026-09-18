"""서버 세션 + HttpOnly Cookie 인증 (A_backend_auth.md 4절).

체크리스트: HttpOnly / Secure / SameSite / CORS / CSRF / 세션 만료 /
로그아웃 / 비회원 접근.

- HttpOnly: 쿠키에 httponly=True (JS에서 쿠키를 읽을 수 없음 -> XSS로 인한
  세션 탈취 방지).
- Secure: config.COOKIE_SECURE (운영에서는 반드시 true, HTTPS 필수).
- SameSite: config.COOKIE_SAMESITE (기본 Lax). D가 별도 origin이면 요청 시
  credentials: "include" + CORS allow_credentials=True 가 필요하다.
- CSRF: 쿠키 기반 세션은 state-changing 요청(POST/DELETE)에 CSRF 위험이
  있다. SameSite=Lax/Strict가 1차 방어이고, cross-site로 운영해야 한다면
  CSRF 토큰을 추가로 검증해야 한다 (TODO: 프로젝트 배포 형태 확정 후 결정).
- 세션 만료: SESSION_TTL_SECONDS. 만료된 토큰은 SessionExpiredError.
- 로그아웃: 서버 세션 스토어에서 즉시 삭제 + 쿠키 삭제.
- 비회원 접근: get_current_user_optional()은 로그인 없이도 None을 반환해
  일정 생성 등 비회원 허용 API에서 쓸 수 있게 한다.
"""

from __future__ import annotations

import hashlib
import secrets
import time

from fastapi import Request, Response

from . import config, db
from .errors import AuthRequiredError, SessionExpiredError

# 세션 저장소는 DB다 (session 테이블). 프로세스 메모리에 두면 서버를
# 재시작하거나 배포할 때마다 접속 중인 사용자가 전부 로그아웃되고, 예고 없는
# 크래시/호스트 재부팅에도 같은 일이 생긴다. SESSION_TTL_SECONDS(7일)를
# 실제로 지키려면 프로세스 밖에 있어야 한다.
# 앱 계정은 DELETE 권한이 없어서 로그아웃은 폐기 기록을 추가하는 방식이다.


def _token_hash(token: str) -> str:
    """DB에는 토큰 원문 대신 해시를 저장한다.

    비밀번호와 달리 토큰은 128비트 랜덤이라 무차별 대입이 불가능하므로,
    느린 KDF 없이 SHA-256으로 충분하다. DB가 유출돼도 저장된 값만으로는
    로그인할 수 없다.
    """

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.create_session(_token_hash(token), user_id, time.time() + config.SESSION_TTL_SECONDS)
    return token


def _lookup(token: str) -> int | None:
    return db.get_session_user(_token_hash(token), time.time())


def delete_session(token: str) -> None:
    """로그아웃. 이후 이 토큰으로는 로그인 상태가 되지 않는다."""

    db.revoke_session(_token_hash(token))


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=token,
        max_age=config.SESSION_TTL_SECONDS,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite=config.COOKIE_SAMESITE,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=config.SESSION_COOKIE_NAME, path="/")


def get_current_user_optional(request: Request) -> int | None:
    """비회원 접근 허용 API용. 로그인 안 했으면 None."""

    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not token:
        return None
    return _lookup(token)


def get_current_user_required(request: Request) -> int:
    """로그인 필수 API용 (예: 일정 저장, 마이페이지)."""

    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not token:
        raise AuthRequiredError("로그인이 필요합니다.")
    user_id = _lookup(token)
    if user_id is None:
        raise SessionExpiredError("세션이 만료되었습니다. 다시 로그인해주세요.")
    return user_id
