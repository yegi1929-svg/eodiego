"""회원/인증 전용 요청·응답 모델. 관광 데이터와 무관하므로 팀 공통
shared/schemas.py 에는 넣지 않고 A 내부에만 둔다."""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("username은 비어 있을 수 없습니다.")
        # user.username 컬럼이 VARCHAR(100)이다. 넘기면 DB 오류(500)가 되므로 먼저 막는다.
        if len(v.strip()) > 100:
            raise ValueError("username은 100자 이하여야 합니다.")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다.")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class UserPublic(BaseModel):
    user_id: int
    username: str
