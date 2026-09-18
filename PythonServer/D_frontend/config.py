"""D(프론트엔드) 비즈니스 로직 서버(BFF) 설정.

D_frontend.md는 원래 브라우저(Geolocation/fetch/JS)를 다루는 프론트엔드
역할이지만, 이미 완성된 HTML/JS 화면이 fetch로 호출할 "서버 쪽 비즈니스
로직"만 파이썬으로 작성하기로 했다. 이 서버가 D_frontend.md 15절의
"모든 외부 API 호출은 서버를 통해 처리한다"의 그 서버다.

즉 이 서버는:
- 관광공사(B) / AI 일정(C) / 인증·저장(A) 서비스에만 접근하고,
- 서비스키/LLM 키를 직접 다루지 않으며 (B/C가 다룸),
- 화면(html/css)은 만들지 않고, 화면이 호출할 JSON API + 표시용 가공
  로직(라벨, 에러 메시지, 재추천 문구)만 제공한다.
"""

from __future__ import annotations

import os

A_BASE_URL: str = os.environ.get("A_BASE_URL", "http://localhost:8000")
B_BASE_URL: str = os.environ.get("B_BASE_URL", "http://localhost:8001")
C_BASE_URL: str = os.environ.get("C_BASE_URL", "http://localhost:8002")

REQUEST_TIMEOUT_SECONDS: float = float(os.environ.get("UPSTREAM_TIMEOUT_SECONDS", "6"))

# A와 동일한 세션 쿠키 이름을 써야 로그인 쿠키를 그대로 A에 전달(BFF 프록시)할 수 있다.
SESSION_COOKIE_NAME: str = os.environ.get("SESSION_COOKIE_NAME", "session_id")

# 브라우저에 내려보내는 쿠키 속성. 이 값을 지정하지 않으면 세션 쿠키가 되어
# 브라우저를 닫는 순간 로그아웃된다 - A가 세션을 7일 유지해도 소용이 없다.
# A의 SESSION_TTL_SECONDS와 같은 값을 쓰는 것이 맞다.
SESSION_COOKIE_MAX_AGE: int = int(os.environ.get("SESSION_TTL_SECONDS", str(60 * 60 * 24 * 7)))

# 운영(HTTPS)에서는 반드시 true. 로컬 http 개발 편의로 기본값만 false다.
COOKIE_SECURE: bool = os.environ.get("COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}
COOKIE_SAMESITE: str = os.environ.get("COOKIE_SAMESITE", "lax")

# 화면(worker/dev 프록시)만 D를 호출할 수 있게 하는 공유 시크릿.
# 배포하면 D의 주소가 공개되므로, 이게 없으면 누구나 /ui/* 를 직접 부를 수 있다.
# 비워두면 검사하지 않는다(로컬 개발 기본값).
GATEWAY_TOKEN: str = os.environ.get("BFF_GATEWAY_TOKEN", "")
GATEWAY_HEADER: str = "x-bff-token"

# D 화면에서 "예측 집중률 높음/보통/낮음"을 나눌 때 쓰는 기준.
# C의 재추천 임계치(CONGESTION_THRESHOLD)와 같은 값을 쓰는 것을 권장하되,
# 화면 표시 전용이므로 별도 환경변수로 둔다.
CONGESTION_DISPLAY_THRESHOLD: float = float(os.environ.get("CONGESTION_DISPLAY_THRESHOLD", "70.0"))

# 쿠키 인증(allow_credentials=True)과 함께 쓰므로 와일드카드 "*"를 기본값으로
# 두면 안 된다 - Starlette가 요청 Origin을 그대로 반향해서, 아무 사이트나
# 사용자의 세션 쿠키로 이 API를 호출할 수 있게 된다(CSRF).
# A_backend/config.py와 동일하게 명시적 origin을 기본값으로 쓴다.
ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip() and o.strip() != "*"
]

HOST: str = os.environ.get("D_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("D_PORT", "8003"))
