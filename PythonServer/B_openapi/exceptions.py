"""B 내부 공통 예외.

'정상 응답 + 데이터 없음' 과 'API timeout' 과 'API HTTP 오류' 를 명확히
구분한다 (B_openapi.md 6절). has_data=False 는 예외가 아니라 정상 값이다.
"""

from __future__ import annotations


class UpstreamTimeoutError(Exception):
    """한국관광공사 API 호출이 timeout 된 경우."""


class UpstreamAPIError(Exception):
    """한국관광공사 API가 HTTP 오류/비정상 응답을 반환한 경우."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class InvalidUpstreamPayloadError(Exception):
    """응답은 왔지만 JSON 파싱 실패/필수 필드 누락인 경우."""
