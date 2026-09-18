"""A 설정. 서비스키/시크릿은 전부 환경변수로 관리한다 (A_backend_auth.md 1절)."""

from __future__ import annotations

import os

# DB 접속 정보(DB_HOST/DB_NAME/DB_USER/DB_PASSWORD)는 shared/database.py 가
# 환경변수(.env)에서 직접 읽는다. 여기에 기본값을 두지 않는다.

SESSION_COOKIE_NAME: str = "session_id"
SESSION_TTL_SECONDS: int = int(os.environ.get("SESSION_TTL_SECONDS", str(60 * 60 * 24 * 7)))  # 7일

# 운영 환경(HTTPS)에서는 반드시 true로 설정한다. 로컬 http 개발 편의를 위해
# 기본값만 false로 두고, 환경변수로 반드시 켜도록 강제한다.
COOKIE_SECURE: bool = os.environ.get("COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}
COOKIE_SAMESITE: str = os.environ.get("COOKIE_SAMESITE", "lax")

B_BASE_URL: str = os.environ.get("B_BASE_URL", "http://localhost:8001")
B_TIMEOUT_SECONDS: float = float(os.environ.get("B_TIMEOUT_SECONDS", "5"))

# CORS: D_frontend가 다른 origin에서 쿠키 기반 세션을 쓰려면 credentials 허용+
# 정확한 origin 명시가 필요하다 (와일드카드 "*" 금지).
ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:8003").split(",") if o.strip()
]

HOST: str = os.environ.get("A_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("A_PORT", "8000"))
