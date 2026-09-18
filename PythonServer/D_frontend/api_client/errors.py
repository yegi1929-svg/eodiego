"""api_client 공통 예외. main.py가 이 예외들을 view_logic의 사용자 메시지로 변환한다."""

from __future__ import annotations


class UpstreamUnavailableError(Exception):
    """A/B/C 서버가 timeout 되었거나 연결에 실패한 경우."""

    def __init__(self, service: str, message: str = ""):
        super().__init__(message or f"{service} 서비스 호출 실패")
        self.service = service  # "A" | "B" | "C"


class UpstreamRejectedError(Exception):
    """A/B/C가 4xx/5xx 오류 응답(공통 ErrorResponse)을 반환한 경우."""

    def __init__(self, service: str, status_code: int, code: str, message: str):
        super().__init__(message)
        self.service = service
        self.status_code = status_code
        self.code = code
        self.message = message
